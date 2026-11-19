# The support desk: contacts, conversations and messages, in the shape of Chatwoot's API.
#
# A customer writes in through the public inbox API; agents answer through the account API. Beside a conversation
# the desk shows the customer's orders, read from Core, and it leaves a private note for the agent when one of
# those orders is cancelled or refunded.
require "json"
require "sqlite3"

module Support
  class BadRequest < StandardError; end
  class NotFound < StandardError; end

  class Desk
    STATUSES = %w[open pending resolved].freeze
    # Message types are integers on the way out, as in Chatwoot, and names on the way in.
    MESSAGE_TYPES = { "incoming" => 0, "outgoing" => 1, "activity" => 2 }.freeze
    CANNED = {
      "refund" => "I have asked our payments team to refund this order. You will get an email once it is done.",
      "shipping" => "Your order is being prepared. You will get an email as soon as it ships.",
      "cancel" => "I can cancel an order as long as nothing in it has shipped. Shall I go ahead?"
    }.freeze

    # `orders` is called with an email address and returns that customer's orders from Core.
    def initialize(path = ":memory:", orders: ->(_email) { [] })
      @db = SQLite3::Database.new(path)
      @orders = orders
      @lock = Mutex.new
      @db.execute_batch(<<~SQL)
        CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER NOT NULL,
          status TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL,
          message_type INTEGER NOT NULL, private INTEGER NOT NULL, content TEXT NOT NULL, sender TEXT, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
      SQL
    end

    def self.default_path
      dir = ENV["SEEDCO_DATA_DIR"]
      return ":memory:" if dir.nil? || dir.empty?
      Dir.mkdir(dir) unless Dir.exist?(dir)
      File.join(dir, "support.db")
    end

    def setting(name)
      row = query("SELECT value FROM settings WHERE name = ?", [name]).first
      row && row[0]
    end

    def set_setting(name, value)
      query("INSERT OR REPLACE INTO settings VALUES (?, ?)", [name, value])
    end

    # A contact is found by email: writing in twice gives the same contact.
    def create_contact(name:, email:)
      raise BadRequest, "a valid email is required" unless email.is_a?(String) && email.include?("@")
      @lock.synchronize do
        found = query("SELECT id FROM contacts WHERE email = ?", [email.downcase]).first
        id = found ? found[0] : insert("INSERT INTO contacts (name, email) VALUES (?, ?)", [name.to_s.empty? ? email : name, email.downcase])
        contact(id)
      end
    end

    def contact(id)
      row = query("SELECT id, name, email FROM contacts WHERE id = ?", [id]).first or raise NotFound, "no contact #{id}"
      { "id" => row[0], "name" => row[1], "email" => row[2] }
    end

    def create_conversation(contact_id, content = nil)
      contact(contact_id)
      id = @lock.synchronize { insert("INSERT INTO conversations (contact_id, status, created_at) VALUES (?, 'open', ?)", [contact_id, Time.now.to_i]) }
      add_message(id, content: content) unless content.to_s.strip.empty?
      conversation(id)
    end

    # Adds a message. A customer writing into a resolved conversation reopens it. A private message is a note
    # only agents see; a customer cannot write one.
    def add_message(conversation_id, content:, message_type: "incoming", private: false, sender: nil)
      type = MESSAGE_TYPES[message_type.to_s] or raise BadRequest, "message_type must be one of #{MESSAGE_TYPES.keys.join(', ')}"
      raise BadRequest, "content is required" if content.to_s.strip.empty?
      raise BadRequest, "only agents can write private notes" if private && type.zero?
      @lock.synchronize do
        row = query("SELECT status FROM conversations WHERE id = ?", [conversation_id]).first or raise NotFound, "no conversation #{conversation_id}"
        query("UPDATE conversations SET status = 'open' WHERE id = ?", [conversation_id]) if type.zero? && row[0] == "resolved"
        id = insert("INSERT INTO messages (conversation_id, message_type, private, content, sender, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    [conversation_id, type, private ? 1 : 0, content.to_s, sender, Time.now.to_i])
        message(id)
      end
    end

    def message(id)
      row = query("SELECT id, conversation_id, message_type, private, content, sender, created_at FROM messages WHERE id = ?", [id]).first
      { "id" => row[0], "conversation_id" => row[1], "message_type" => row[2], "private" => row[3] == 1, "content" => row[4],
        "sender" => row[5], "created_at" => row[6] }
    end

    # One conversation with its contact and messages. Customers never see private notes.
    def conversation(id, include_private: true)
      row = query("SELECT id, contact_id, status, created_at FROM conversations WHERE id = ?", [id]).first or raise NotFound, "no conversation #{id}"
      ids = query("SELECT id FROM messages WHERE conversation_id = ? ORDER BY id", [id]).map(&:first)
      messages = ids.map { |m| message(m) }.select { |m| include_private || !m["private"] }
      { "id" => row[0], "status" => row[2], "created_at" => row[3], "meta" => { "sender" => contact(row[1]) }, "messages" => messages }
    end

    # Conversations, newest first, optionally of one status and of one customer (by email, in any case).
    def conversations(status: nil, email: nil)
      raise BadRequest, "status must be one of #{STATUSES.join(', ')}" if status && !STATUSES.include?(status)
      ids = query("SELECT c.id FROM conversations c JOIN contacts k ON k.id = c.contact_id " \
                  "WHERE (?1 IS NULL OR c.status = ?1) AND (?2 IS NULL OR k.email = ?2) ORDER BY c.id DESC", [status, email&.downcase]).map(&:first)
      ids.map { |id| conversation(id) }
    end

    # Sets the status, or flips between open and resolved when none is given.
    def toggle_status(id, status = nil)
      current = conversation(id)["status"]
      status ||= current == "resolved" ? "open" : "resolved"
      raise BadRequest, "status must be one of #{STATUSES.join(', ')}" unless STATUSES.include?(status)
      query("UPDATE conversations SET status = ? WHERE id = ?", [status, id])
      conversation(id)
    end

    def canned_responses
      CANNED.map { |short_code, content| { "short_code" => short_code, "content" => content } }
    end

    # The customer's orders as the agent's side panel shows them. Money is Core's: a decimal in major units.
    def orders_for(contact_id, dashboard_url: nil)
      @orders.call(contact(contact_id)["email"]).map do |o|
        { "id" => o["id"], "number" => o["number"], "created" => o["created"], "status" => o["status"], "charge_status" => o["chargeStatus"],
          "total" => format("%.2f", o["total"]["gross"]["amount"]), "currency" => o["total"]["gross"]["currency"],
          "refunded" => format("%.2f", o["totalRefunded"]["amount"]),
          "items" => o["lines"].map { |l| "#{l['quantity']} x #{l['productName']}" }.join(", "),
          "dashboard_url" => dashboard_url && "#{dashboard_url}/orders/#{URI.encode_www_form_component(o['id'])}" }
      end
    end

    # An order event from Core: leaves one private note on each unresolved conversation of that customer.
    # Core may deliver an event more than once; the same note is not left twice.
    def order_event(payload)
      order = payload["order"] or raise BadRequest, "order is missing from the payload"
      note = case payload["__typename"]
             when "OrderCancelled" then "Order ##{order.fetch('number')} was cancelled."
             when "OrderRefunded" then format("Order #%s was refunded: $%.2f so far.", order.fetch("number"), order.fetch("totalRefunded").fetch("amount"))
             end
      return [] if note.nil? || order["userEmail"].nil?
      found = query("SELECT id FROM contacts WHERE email = ?", [order["userEmail"].downcase]).first
      return [] unless found
      open = query("SELECT id FROM conversations WHERE contact_id = ? AND status != 'resolved'", [found[0]]).map(&:first)
      open.reject { |id| query("SELECT 1 FROM messages WHERE conversation_id = ? AND private = 1 AND content = ?", [id, note]).any? }
          .map { |id| add_message(id, content: note, message_type: "activity", private: true, sender: "core") }
    rescue KeyError => e
      raise BadRequest, "#{e.key} is missing from the payload"
    end

    private

    def query(sql, args = [])
      @db.execute(sql, args)
    end

    def insert(sql, args)
      @db.execute(sql, args)
      @db.last_insert_row_id
    end
  end
end
