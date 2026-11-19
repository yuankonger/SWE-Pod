# HTTP wiring for the support desk: the public inbox API customers write to, the account API agents use,
# the manifest Core installs it from and its webhook, health and metrics.
require "json"
require "net/http"
require "time"
require "uri"
require "webrick"
require_relative "desk"

PORT = (ENV["PORT"] || "7007").to_i
APP_URL = ENV["APP_URL"] || "http://127.0.0.1:#{PORT}"
CORE_URL = ENV["CORE_URL"] || "http://127.0.0.1:7000/graphql/"
DASHBOARD_URL = ENV["DASHBOARD_URL"] || "http://127.0.0.1:7002"
AGENT_TOKEN = ENV["SUPPORT_AGENT_TOKEN"] || "support-agent-token"
GRAPHQL = File.join(__dir__, "..", "graphql")
COUNTERS = Hash.new(0)
COUNTERS_LOCK = Mutex.new

def log(level, message, **attributes)
  puts JSON.generate({ timestamp: Time.now.utc.iso8601, level: level, service: "support", message: message }.merge(attributes))
  $stdout.flush
end

def count(name, **labels)
  series = "#{name}{#{labels.map { |k, v| "#{k}=\"#{v}\"" }.join(',')}}"
  COUNTERS_LOCK.synchronize { COUNTERS[series] += 1 }
end

def metrics
  series = COUNTERS_LOCK.synchronize { COUNTERS.sort }
  names = series.map { |s, _| s.split("{").first }.uniq
  names.map { |n| "# TYPE #{n} counter\n" }.join + series.map { |s, v| "#{s} #{v}\n" }.join
end

DESK = Support::Desk.new(Support::Desk.default_path, orders: lambda { |email|
  # The customer's orders, from Core, with the token Core gave this app when it installed it.
  token = DESK.setting("auth_token") or raise "Core has not installed this app yet"
  uri = URI(CORE_URL)
  response = Net::HTTP.start(uri.host, uri.port, read_timeout: 20) do |http|
    http.post(uri.path, JSON.generate(query: File.read(File.join(GRAPHQL, "contact-orders.graphql")), variables: { email: email }),
              "Content-Type" => "application/json", "Authorization" => "Bearer #{token}")
  end
  body = JSON.parse(response.body)
  raise "core: #{body['errors'].first['message']}" if body["errors"] && !body["errors"].empty?
  body["data"]["orders"]["edges"].map { |e| e["node"] }
})

def manifest
  { id: "seedco.support", name: "Support desk", version: "1.0.0", permissions: ["MANAGE_ORDERS"], tokenTargetUrl: "#{APP_URL}/api/register",
    webhooks: [{ name: "order-events", asyncEvents: %w[ORDER_CANCELLED ORDER_REFUNDED], query: File.read(File.join(GRAPHQL, "order-events.graphql")),
                 targetUrl: "#{APP_URL}/api/webhooks/order-events" }] }
end

# Returns [status, body, route]. `body` is nil for an unknown address.
def route(method, path, params, body, agent)
  case [method, path]
  in ["GET", "/health"] then return [200, { ok: true }, path]
  in ["GET", "/api/manifest"] then return [200, manifest, path]
  in ["POST", "/api/register"]
    DESK.set_setting("auth_token", body.fetch("auth_token"))
    return [200, { success: true }, path]
  in ["POST", "/api/webhooks/order-events"]
    DESK.order_event(body).each { count("seedco_support_messages_total", message_type: "activity") }
    return [200, { success: true }, path]
  else nil
  end

  # The public inbox API: what the shop's contact form and chat widget call. No token; a customer sees no private notes.
  if (m = path.match(%r{\A/public/api/v1/inboxes/web/contacts(?:/(\d+)/conversations(?:/(\d+)(/messages)?)?)?\z}))
    contact_id, conversation_id, messages = m[1]&.to_i, m[2]&.to_i, m[3]
    route = "/public/api/v1/inboxes/web/contacts"
    return [200, DESK.create_contact(name: body["name"], email: body["email"]), route] if method == "POST" && contact_id.nil?
    return [404, nil, "unmatched"] if contact_id.nil?
    if conversation_id.nil?
      return [200, DESK.create_conversation(contact_id, body["message"] || body["content"]), route + "/{id}/conversations"] if method == "POST"
      return [404, nil, "unmatched"]
    end
    mine = DESK.conversation(conversation_id, include_private: false)
    raise Support::NotFound, "no conversation #{conversation_id}" unless mine["meta"]["sender"]["id"] == contact_id
    if messages && method == "POST"
      count("seedco_support_messages_total", message_type: "incoming")
      return [200, DESK.add_message(conversation_id, content: body["content"], sender: mine["meta"]["sender"]["email"]), route + "/{id}/conversations/{id}/messages"]
    end
    return [200, mine, route + "/{id}/conversations/{id}"] if method == "GET" && !messages
    return [404, nil, "unmatched"]
  end

  # The account API: what agents use. Needs the agent's token in the `api_access_token` header.
  if (m = path.match(%r{\A/api/v1/accounts/1/(.+)\z}))
    return [401, { error: "Invalid access token" }, "/api/v1/accounts/1"] unless agent
    rest = m[1]
    base = "/api/v1/accounts/1/"
    case rest
    when "conversations"
      # WEBrick hands query values over as binary strings, which SQLite would compare as blobs, not text
      status = params["status"] && String.new(params["status"]).force_encoding("UTF-8")
      email = params["email"] && String.new(params["email"]).force_encoding("UTF-8")
      list = DESK.conversations(status: status, email: email)
      return [200, { data: { meta: { all_count: list.size }, payload: list } }, base + rest] if method == "GET"
    when "canned_responses"
      return [200, DESK.canned_responses, base + rest] if method == "GET"
    when "integrations/saleor/orders"
      return [200, { orders: DESK.orders_for(params.fetch("contact_id").to_i, dashboard_url: DASHBOARD_URL) }, base + rest] if method == "GET"
    when %r{\Aconversations/(\d+)\z}
      return [200, DESK.conversation($1.to_i), base + "conversations/{id}"] if method == "GET"
    when %r{\Aconversations/(\d+)/messages\z}
      if method == "POST"
        count("seedco_support_messages_total", message_type: body["private"] ? "note" : "outgoing")
        return [200, DESK.add_message($1.to_i, content: body["content"], message_type: body["message_type"] || "outgoing",
                                      private: body["private"] == true, sender: "agent"), base + "conversations/{id}/messages"]
      end
    when %r{\Aconversations/(\d+)/toggle_status\z}
      return [200, DESK.toggle_status($1.to_i, body["status"]), base + "conversations/{id}/toggle_status"] if method == "POST"
    end
  end
  [404, nil, "unmatched"]
end

# BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
server = WEBrick::HTTPServer.new(BindAddress: ENV["BIND"] || "127.0.0.1", Port: PORT, Logger: WEBrick::Log.new(File::NULL), AccessLog: [])
server.mount_proc("/") do |req, res|
  status, payload, matched = 500, nil, "unmatched"
  begin
    if req.path == "/metrics"
      res.status, res["Content-Type"], res.body = 200, "text/plain; version=0.0.4", metrics
      next
    end
    body = req.body.to_s.empty? ? {} : JSON.parse(req.body)
    raise Support::BadRequest, "the body must be a JSON object" unless body.is_a?(Hash)
    status, payload, matched = route(req.request_method, req.path, req.query, body, req["api_access_token"] == AGENT_TOKEN)
    payload ||= { error: "not_found" }
  rescue JSON::ParserError
    status, payload = 400, { error: "invalid_json" }
  rescue Support::BadRequest, KeyError => e
    status, payload = 400, { error: "bad_request", message: e.message }
  rescue Support::NotFound => e
    status, payload = 404, { error: "not_found", message: e.message }
  rescue StandardError => e
    status, payload = 502, { error: "upstream_failed", message: e.message }
    log("error", "request failed", path: req.path, reason: e.message)
  end
  count("http_server_request_count_total", http_route: matched, http_response_status_code: status)
  res.status, res["Content-Type"], res.body = status, "application/json", JSON.generate(payload)
end
trap("TERM") { server.shutdown }
trap("INT") { server.shutdown }
log("info", "support listening on #{PORT}")
server.start
