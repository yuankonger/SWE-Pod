require "minitest/autorun"
require "tmpdir"
require "uri"
require_relative "../src/desk"

class DeskTest < Minitest::Test
  ORDER = { "id" => "T3JkZXI6MQ==", "number" => "1", "created" => "2026-01-01T10:00:00Z", "status" => "UNFULFILLED", "chargeStatus" => "FULL",
            "userEmail" => "pat@example.com", "total" => { "gross" => { "amount" => 66.15, "currency" => "USD" } },
            "totalRefunded" => { "amount" => 0.0 },
            "lines" => [{ "productName" => "Small monthly box", "quantity" => 2 }, { "productName" => "Tea add-on", "quantity" => 1 }] }.freeze

  def setup
    @asked = []
    @desk = Support::Desk.new(orders: ->(email) { @asked << email; email == "pat@example.com" ? [ORDER] : [] })
    @pat = @desk.create_contact(name: "Pat Lee", email: "Pat@Example.com")
  end

  def test_a_contact_is_found_by_email
    assert_equal "pat@example.com", @pat["email"]
    assert_equal @pat["id"], @desk.create_contact(name: "P", email: "pat@example.com")["id"]
    assert_raises(Support::BadRequest) { @desk.create_contact(name: "x", email: "nope") }
  end

  def test_a_conversation_holds_messages_and_private_notes_stay_with_agents
    conversation = @desk.create_conversation(@pat["id"], "Where is my order?")
    @desk.add_message(conversation["id"], content: "Checking the warehouse", message_type: "outgoing", private: true, sender: "agent")
    @desk.add_message(conversation["id"], content: "It ships today.", message_type: "outgoing", sender: "agent")
    full = @desk.conversation(conversation["id"])
    assert_equal [0, 1, 1], full["messages"].map { |m| m["message_type"] }            # integers on the way out
    assert_equal [false, true, false], full["messages"].map { |m| m["private"] }
    assert_equal ["Where is my order?", "It ships today."], @desk.conversation(conversation["id"], include_private: false)["messages"].map { |m| m["content"] }
    assert_equal "pat@example.com", full["meta"]["sender"]["email"]
    assert_raises(Support::BadRequest) { @desk.add_message(conversation["id"], content: "psst", private: true) }
    assert_raises(Support::BadRequest) { @desk.add_message(conversation["id"], content: " ") }
    assert_raises(Support::BadRequest) { @desk.add_message(conversation["id"], content: "x", message_type: "shout") }
    assert_raises(Support::NotFound) { @desk.conversation(999) }
  end

  def test_status_toggles_and_a_customer_reply_reopens
    id = @desk.create_conversation(@pat["id"], "Hello")["id"]
    assert_equal "resolved", @desk.toggle_status(id)["status"]
    assert_equal [], @desk.conversations(status: "open")
    assert_equal [id], @desk.conversations(status: "resolved").map { |c| c["id"] }
    @desk.add_message(id, content: "One more thing")
    assert_equal "open", @desk.conversation(id)["status"]
    assert_equal "pending", @desk.toggle_status(id, "pending")["status"]
    assert_raises(Support::BadRequest) { @desk.toggle_status(id, "snoozed") }
    assert_raises(Support::BadRequest) { @desk.conversations(status: "closed") }
  end

  def test_conversations_can_be_listed_for_one_customer
    mine = @desk.create_conversation(@pat["id"], "Hello")["id"]
    sam = @desk.create_contact(name: "Sam", email: "sam@example.com")
    @desk.create_conversation(sam["id"], "Hi")
    assert_equal [mine], @desk.conversations(email: "PAT@example.com").map { |c| c["id"] }
    assert_equal 2, @desk.conversations.size
    assert_equal [], @desk.conversations(email: "nobody@example.com")
    assert_equal [], @desk.conversations(status: "resolved", email: "pat@example.com")
  end

  def test_the_side_panel_shows_the_customers_orders_from_core
    orders = @desk.orders_for(@pat["id"], dashboard_url: "http://dashboard.test")
    assert_equal ["pat@example.com"], @asked
    assert_equal({ "id" => "T3JkZXI6MQ==", "number" => "1", "created" => "2026-01-01T10:00:00Z", "status" => "UNFULFILLED", "charge_status" => "FULL",
                   "total" => "66.15", "currency" => "USD", "refunded" => "0.00", "items" => "2 x Small monthly box, 1 x Tea add-on",
                   "dashboard_url" => "http://dashboard.test/orders/T3JkZXI6MQ%3D%3D" }, orders.first)
    assert_equal [], @desk.orders_for(@desk.create_contact(name: "Sam", email: "sam@example.com")["id"])
  end

  def test_an_order_event_leaves_one_private_note_on_open_conversations
    open = @desk.create_conversation(@pat["id"], "Please cancel my order")["id"]
    closed = @desk.create_conversation(@pat["id"], "Old question")["id"]
    @desk.toggle_status(closed)
    refunded = { "__typename" => "OrderRefunded", "order" => { "number" => "1", "userEmail" => "pat@example.com", "totalRefunded" => { "amount" => 66.15 } } }
    assert_equal 1, @desk.order_event(refunded).size
    assert_equal 0, @desk.order_event(refunded).size                                   # a delivery can arrive twice
    @desk.order_event({ "__typename" => "OrderCancelled", "order" => { "number" => "1", "userEmail" => "pat@example.com" } })
    notes = @desk.conversation(open)["messages"].select { |m| m["private"] }.map { |m| m["content"] }
    assert_equal ["Order #1 was refunded: $66.15 so far.", "Order #1 was cancelled."], notes
    assert_equal 1, @desk.conversation(closed)["messages"].size
    assert_equal [], @desk.order_event({ "__typename" => "OrderRefunded", "order" => { "number" => "2", "userEmail" => "nobody@example.com", "totalRefunded" => { "amount" => 1 } } })
    assert_raises(Support::BadRequest) { @desk.order_event({ "__typename" => "OrderRefunded", "order" => { "userEmail" => "pat@example.com" } }) }
  end

  def test_conversations_survive_a_restart
    path = File.join(Dir.mktmpdir("seedco-support-"), "support.db")
    first = Support::Desk.new(path)
    contact = first.create_contact(name: "Pat", email: "pat@example.com")
    id = first.create_conversation(contact["id"], "Hello")["id"]
    first.set_setting("auth_token", "tok")
    again = Support::Desk.new(path)
    assert_equal ["Hello"], again.conversation(id)["messages"].map { |m| m["content"] }
    assert_equal "tok", again.setting("auth_token")
    assert_equal 3, again.canned_responses.size
  end
end
