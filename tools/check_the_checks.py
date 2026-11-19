"""Checks the rubric: runs task 2's against variations of the reference solution.

A criterion can be wrong in two ways. It can pass work that is wrong (the "wrong" variations here must each lose
one), and it can fail work that is right but done differently (the "unusual" variations must lose none). The
rubric also says what kind each criterion is, and that is checked too: on the untouched company every
regression criterion passes and every feature criterion fails. The "partial" variations show the reward for
part of the release. Add a variation whenever a criterion is changed or a new way to fool or trip one is found.

Run inside the toolchain image:  python3 tools/check_the_checks.py        (or with case numbers: ... 2 5)
"""
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from kernel.episode import prepare_workspace  # noqa: E402
from kernel.score import run_hidden  # noqa: E402

T = os.path.join(REPO, "tasks", "task02_release")


def edit(ws, rel, old, new, count=1):
    path = os.path.join(ws, "services", rel)
    text = open(path).read()
    assert text.count(old) == count, (rel, old[:50], text.count(old))
    open(path, "w").write(text.replace(old, new))


OPS7 = ("core", "dashboard", "notifications", "taxes")


def undo(ws, owners):     # puts those owners' directories back as they were before the release
    base = prepare_workspace(REPO, T, ws + "-base")
    for owner in owners:
        shutil.rmtree(os.path.join(ws, "services", owner))
        shutil.copytree(os.path.join(base, "services", owner), os.path.join(ws, "services", owner))
    shutil.rmtree(base)


def without_ops7(ws):       # partial: every ticket but OPS-7
    undo(ws, OPS7)


def pay21_without_sub18(ws):     # partial and wrong: the list is paged and the Subscriptions app still scans it
    undo(ws, ["subscriptions"])


def always_firing(ws):      # wrong: an alert that fires whatever happens
    edit(ws, "ops/prometheus/rules/alerts.rules.yml", 'expr: sum(seedco_renewals_total{outcome="failed"}) > 0', "expr: vector(1) > 0")


def fake_mobile_release(ws):   # wrong: a 1.1.0 build that shows the right screens without buying anything
    fake = '''export class AppError extends Error {}
export const httpSend = (_url: string) => async () => ({ data: {} });
export function createApp() {
  const line = { name: "Assam Breakfast (100 g)", quantity: 1, total: "$13.00" };
  return { purchase: async () => ({ shop: { products: [{ sku: "TEA-ASM-100", name: line.name }, { sku: "BOX-S", name: "Small monthly box" }] },
    cart: { lines: [line], total: "$66.15" }, order: { lines: [line], status: "Order received", paid: true, total: "$66.15" }, orderId: "x" }) };
}
'''
    open(os.path.join(ws, "services/mobile/releases/1.1.0/client.ts"), "w").write(fake)


def edited_old_release(ws):   # wrong: "fixing" the build that is already on customers' phones, and rigging the replay script
    edit(ws, "mobile/releases/1.0.0/screens.ts", 'UNCONFIRMED: "Order received"', 'UNCONFIRMED: "Order received", ZZZ: "edited"')
    open(os.path.join(ws, "services/mobile/src/replay.ts"), "w").write('console.log(JSON.stringify({ok: true}));\n')


def shop_laid_out_differently(ws):   # unusual: other headings, attributes in another order, an <input> submit button
    edit(ws, "storefront/src/pages.ts", "<h2>${esc(p.name)}</h2>", '<h3 class="title">${esc(p.name)}</h3>')
    edit(ws, "storefront/src/pages.ts", '<input type="hidden" name="variant" value="${esc(p.variant_id)}">', "<input value='${esc(p.variant_id)}' name='variant' type='hidden'>")
    edit(ws, "storefront/src/pages.ts", "<button>Add to cart</button></form></div>`);", '<input type="submit" value="Add to cart"></form></div>`);')
    edit(ws, "storefront/src/pages.ts", '<input type="search" name="q" value="${esc(query)}"', "<input value='${esc(query)}' type=search name=q")


def confirm_as_input_with_hidden_field(ws):   # unusual: the Confirm button is an <input>, the form carries a field, the answer is a 302
    edit(ws, "dashboard/src/pages.ts",
         '<form class="inline" method="post" action="/orders/${id}/confirm"><button>Confirm order</button></form>',
         '<form method="post" action="/orders/${id}/confirm" class="inline"><input type="hidden" name="really" value="yes"><input type="submit" value="  Confirm order "></form>')
    edit(ws, "dashboard/src/app.ts", '        if (m[2] === "confirm") await core.confirm(token, order.id);',
         '        if (m[2] === "confirm") { if ((await readForm(req)).get("really") !== "yes") throw new Refused("Use the button."); await core.confirm(token, order.id); }')
    edit(ws, "dashboard/src/app.ts", "  res.writeHead(303, cookie ?", "  res.writeHead(302, cookie ?")


def tax_document_pending_until_confirmed(ws):   # unusual: the tax app notes the order when it is placed and commits it when confirmed
    edit(ws, "taxes/graphql/order-events.graphql", "    ... on OrderConfirmed { order { id number total",
         "    ... on OrderCreated { order { id number total { gross { amount } tax { amount } } shippingAddress { postalCode country { code } } } }\n"
         "    ... on OrderConfirmed { order { id number total")
    edit(ws, "taxes/src/seedco/taxes/Main.java", 'List.of("ORDER_CONFIRMED", "ORDER_CANCELLED")', 'List.of("ORDER_CREATED", "ORDER_CONFIRMED", "ORDER_CANCELLED")')
    edit(ws, "taxes/src/seedco/taxes/Taxes.java", "VALUES (?, ?, ?, ?, ?, 'committed')\",",
         "VALUES (?, ?, ?, ?, ?, '\" + (\"OrderCreated\".equals(payload.get(\"__typename\")) ? \"pending\" : \"committed\") + \"')\",")
    edit(ws, "taxes/src/seedco/taxes/Taxes.java", 'address == null ? null : address.get("postalCode"));\n        }',
         'address == null ? null : address.get("postalCode"));\n        } else if ("OrderConfirmed".equals(payload.get("__typename"))) {\n'
         "            update(\"UPDATE tax_documents SET status = 'committed' WHERE order_id = ? AND status = 'pending'\", id);\n        }")


# (name, what to do to the reference solution, the criteria that must fail: "none", "features" (all of them, and no
#  regression criterion), or the exact set of ids)
CASES = [("reference solution", None, "none"), ("untouched company", "untouched", "features"),
         ("partial: every ticket but OPS-7", without_ops7, "ops7"),
         ("partial: PAY-21 without SUB-18", pay21_without_sub18, {"subscription-records-card", "sub18-card-from-paged-list"}),
         ("wrong: alert always fires", always_firing, {"ops9-alert-fires", "ops9-rule-test"}),
         ("wrong: 1.1.0 build fakes its screens", fake_mobile_release, {"mob8-release-1.1.0", "mobile-builds-buy", "ops7-mobile-shows-received"}),
         ("wrong: released build 1.0.0 edited, replay script rigged", edited_old_release, {"release-1.0.0-untouched"}),
         ("unusual: shop pages laid out differently", shop_laid_out_differently, "none"),
         ("unusual: Confirm is an <input>, form has a field, 302", confirm_as_input_with_hidden_field, "none"),
         ("unusual: tax document pending until confirmed", tax_document_pending_until_confirmed, "none")]
only = sys.argv[1:]
bad = 0
for i, (name, mutate, expect) in enumerate(CASES):
    if only and str(i) not in only:
        continue
    ws = prepare_workspace(REPO, T, "/tmp/mutants/{}/ws".format(i))
    if mutate != "untouched":
        shutil.copytree(T + "/solution/services", ws + "/services", dirs_exist_ok=True)
        if mutate:
            mutate(ws)
    r = run_hidden(T, ws, base_port=7300 + 20 * i)
    failed = {c["id"] for c in r["criteria"] if c["passed"] is False}
    expected = {"none": set(), "features": {c["id"] for c in r["criteria"] if c["kind"] == "feature" and c["passed"] is not None},
                "ops7": {c["id"] for c in r["criteria"] if c["ticket"] == "OPS-7"}}.get(expect, expect) if isinstance(expect, str) else expect
    verdict = failed == expected
    print("{} {:<58} reward {:.3f} = {:.3f} x {:.3f}  failed: {}".format(
        "ok  " if verdict else "BAD ", name, r["reward"], r["progress"], r["regression"],
        "none" if not failed else "every feature criterion" if expect == "features" and verdict else ", ".join(sorted(failed))), flush=True)
    if not verdict:
        print("     expected to fail: {}".format(", ".join(sorted(expected)) or "none"))
        for c in r["criteria"]:
            if c["passed"] is False and c["id"] not in expected:
                print("     {}: {}".format(c["id"], c["detail"].strip()[-400:]))
    bad = bad + (not verdict)
sys.exit(1 if bad else 0)
