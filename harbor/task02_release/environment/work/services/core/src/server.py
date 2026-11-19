"""HTTP wiring for Core: the GraphQL endpoint, health, metrics, app installation and the delivery worker."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from graphql import GraphQLError, build_schema, execute, get_operation_ast, parse, validate

import telemetry
from core import ApiError, Core
from store import Store, default_path
from webhooks import Apps

HERE = os.path.dirname(os.path.abspath(__file__))


def load_schema():
    with open(os.path.join(HERE, "..", "contracts", "schema.graphql")) as f:
        return build_schema(f.read())


def need(info, permission: str):
    if permission not in info.context["permissions"]:
        raise GraphQLError("You need one of the following permissions: {}".format(permission),
                           extensions={"exception": {"code": "PermissionDenied"}})


def bind(schema, core: Core):
    """Attaches Core's operations to the schema's Query and Mutation fields."""
    def query(name, fn, permission=None):
        def resolve(root, info, **args):
            if permission:
                need(info, permission)
            return fn(**args)
        schema.query_type.fields[name].resolve = resolve

    def mutation(name, fn, permission=None):
        def resolve(root, info, **args):
            if permission:
                need(info, permission)
            try:
                return dict(fn(**args), errors=[])
            except ApiError as e:
                return {"errors": [{"field": e.field, "message": e.message, "code": e.code}]}
        schema.mutation_type.fields[name].resolve = resolve

    def by_id(kind, view, loader):
        def find(id):
            try:
                return view(loader(id))
            except ApiError:
                return None
        return find

    query("products", lambda first=20, after=None, channel=None, filter=None: core.products(first, after, filter))
    query("channel", lambda slug=None: core.channel_view())
    query("checkout", by_id("checkout", core.checkout_view, core._checkout))
    query("order", by_id("order", core.order_view, core._order))
    query("orders", lambda first=20, after=None, filter=None: core.orders(first, after, filter), "MANAGE_ORDERS")
    query("apps", lambda: [core.app_view(a) for a in core.apps.all()], "MANAGE_APPS")

    mutation("tokenCreate", core.token_create)
    mutation("checkoutCreate", core.checkout_create)
    mutation("checkoutLinesAdd", core.checkout_lines_add)
    mutation("checkoutLinesUpdate", core.checkout_lines_update)
    mutation("checkoutEmailUpdate", core.checkout_email_update)
    mutation("checkoutShippingAddressUpdate", core.checkout_shipping_address_update)
    mutation("checkoutDeliveryMethodUpdate", core.checkout_delivery_method_update)
    mutation("transactionInitialize", core.transaction_initialize)
    mutation("checkoutComplete", core.checkout_complete)
    mutation("orderCancel", core.order_cancel, "MANAGE_ORDERS")
    mutation("orderFulfill", core.order_fulfill, "MANAGE_ORDERS")
    mutation("transactionRequestAction", core.transaction_request_action, "HANDLE_PAYMENTS")
    mutation("draftOrderCreate", core.draft_order_create, "MANAGE_ORDERS")
    mutation("draftOrderComplete", core.draft_order_complete, "MANAGE_ORDERS")
    mutation("updateMetadata", core.update_metadata, "MANAGE_ORDERS")


class Api:
    """Runs GraphQL requests against Core, one at a time."""

    def __init__(self, store: Store, api_url: str):
        self.schema = load_schema()
        self.apps = Apps(store, self.schema, api_url)
        self.core = Core(store, self.apps)
        self.lock = threading.RLock()
        bind(self.schema, self.core)

    def principal(self, authorization: str) -> dict:
        token = (authorization or "").removeprefix("Bearer ").strip()
        if token:
            app = self.apps.by_token(token)
            if app:
                return {"kind": "app", "name": app["identifier"], "permissions": set(app["permissions"])}
            staff = self.core.staff_by_token(token)
            if staff:
                return {"kind": "staff", "name": staff["id"], "permissions": set(staff["permissions"])}
        return {"kind": "anonymous", "name": "", "permissions": set()}

    def run(self, body: dict, authorization: str = None) -> dict:
        """Executes one GraphQL request and returns the response body."""
        try:
            document = parse(body.get("query") or "")
        except GraphQLError as e:
            return {"errors": [e.formatted]}
        problems = validate(self.schema, document)
        operation = get_operation_ast(document, body.get("operationName"))
        if problems or operation is None or operation.operation.value == "subscription":
            return {"errors": [p.formatted for p in problems] or [{"message": "Send one query or mutation."}]}
        with self.lock:
            result = execute(self.schema, document, context_value=self.principal(authorization),
                             variable_values=body.get("variables") or {}, operation_name=body.get("operationName"))
        telemetry.count("saleor_graphql_operation_count_total", saleor_graphql_operation_type=operation.operation.value,
                        saleor_graphql_operation_name=operation.name.value if operation.name else "",
                        outcome="error" if result.errors else "success")
        for e in result.errors or []:
            if not isinstance(e.original_error, GraphQLError) and e.original_error is not None:
                telemetry.log("error", "unhandled error in a resolver", reason=repr(e.original_error), path=e.path)
        return result.formatted


def serve():
    port = int(os.environ.get("PORT", "7000"))
    api_url = os.environ.get("PUBLIC_URL", "http://127.0.0.1:{}".format(port)) + "/graphql/"
    api = Api(Store(default_path()), api_url)
    manifests = [m for m in os.environ.get("SEEDCO_APP_MANIFESTS", "").split(",") if m]
    waiting = set(manifests)

    def install():
        # Apps start alongside Core, so each manifest is tried until its app answers.
        while waiting:
            for url in sorted(waiting):
                try:
                    with api.lock:
                        api.apps.install(url)
                    waiting.discard(url)
                except Exception as exc:
                    telemetry.log("debug", "app not installed yet", manifest=url, reason=repr(exc))
            time.sleep(0.3)

    threading.Thread(target=install, daemon=True, name="install").start()
    api.apps.run_worker()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, status, body, content_type="application/json"):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                # healthy once every configured app is installed; until then checkouts could not be taxed or paid
                return self.send(503 if waiting else 200, {"ok": not waiting, "waiting_for": sorted(waiting)})
            if self.path == "/metrics":
                return self.send(200, telemetry.render(), "text/plain; version=0.0.4")
            self.send(404, {"error": "not_found"})

        def do_POST(self):
            if self.path.rstrip("/") != "/graphql":
                return self.send(404, {"error": "not_found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self.send(400, {"errors": [{"message": "The request body must be a JSON object."}]})
            self.send(200, api.run(body, self.headers.get("Authorization")))

    telemetry.log("info", "core listening", port=port)
    # BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
    ThreadingHTTPServer((os.environ.get("BIND", "127.0.0.1"), port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
