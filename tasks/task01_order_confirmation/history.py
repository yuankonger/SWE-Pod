"""The company's history before task 1: what was bought, shipped, cancelled, refunded and asked about.

`replay` drives the running company through its own shop, dashboard API and support desk, so every service's
database ends up holding its side of the same history. tools/build_task_seed.py runs it and keeps the databases
as the task's seed. The customers and what they do are fixed; ids and timestamps are whatever they are on the
day the seed is built.
"""
import json
import os
import random
import urllib.parse

# (email, first name, last name, street, city, state, postal code). Codes starting with 9 are taxed at 8.75%, the rest at 6%.
CUSTOMERS = [
    ("legacy.unfulfilled@example.com", "Morgan", "Hale", "12 Dock St", "Portland", "OR", "97209"),
    ("legacy.sub@example.com", "Priya", "Raman", "480 Elm Ave", "Columbus", "OH", "43215"),
    ("amelie.dubois@example.com", "Amélie", "Dubois", "9 Rue Court", "Seattle", "WA", "98101"),
    ("sean.obrien@example.com", "Seán", "O'Brien", "77 Harbor Rd", "Boston", "MA", "02110"),
    ("li.wei@example.com", "Wei", "Li", "301 Grant Ave", "San Francisco", "CA", "94108"),
    ("zoe.nakamura@example.com", "Zoë", "Nakamura-Smith", "18 Pine Ct, Apt 4B", "San Diego", "CA", "92101"),
    ("j.mueller@example.com", "Jörg", "Müller", "5 Lake Dr", "Chicago", "IL", "60601"),
    ("ana.garcia@example.com", "Ana María", "García", "220 Sunset Blvd", "Los Angeles", "CA", "90026"),
    ("t.okafor@example.com", "Tunde", "Okafor", "64 Peachtree St", "Atlanta", "GA", "30303"),
    ("h.jensen@example.com", "Hanne", "Jensen", "3 Fjord Way", "Minneapolis", "MN", "55401"),
    ("d.cohen@example.com", "Dov", "Cohen", "1450 Broadway", "New York", "NY", "10018"),
    ("m.rossi@example.com", "Marta", "Rossi", "88 Vine St", "Sacramento", "CA", "95814"),
    ("k.yilmaz@example.com", "Kerem", "Yılmaz", "17 Mesa Rd", "Phoenix", "AZ", "85004"),
    ("r.singh@example.com", "Ravi", "Singh", "9 Market Sq", "Denver", "CO", "80202"),
]
MESSAGES = [
    ("amelie.dubois@example.com", "Hi, my tea arrived but the tin is dented. Can you send a new one?", "refund", True),
    ("sean.obrien@example.com", "When will my order ship? It's been four days.", "shipping", True),
    ("li.wei@example.com", "I'd like to cancel my last order please.", "cancel", False),
    ("d.cohen@example.com", "Do you ship to Canada?", None, False),
    ("ana.garcia@example.com", "I was charged twice, I think. Can you check?", None, False),
]


def _titles(root):
    """Product card titles as the shop shows them, cheapest first, without gift cards and anything above $150."""
    with open(os.path.join(root, "services", "core", "src", "catalogue.json")) as f:
        products = json.load(f)["products"]
    rows = [(float(v["price"]), "{} ({})".format(p["name"], v["name"]) if v["name"] else p["name"])
            for p in products[3:] for v in p["variants"] if p["category"] != "gift-cards" and float(v["price"]) <= 150]
    return [title for _, title in sorted(rows)]


def replay(s, Browser, log=print):
    rng = random.Random(20261113)
    admin = s.staff_token()
    titles = _titles(s.root)
    placed = []          # (customer email, order as Core holds it)

    def buy(customer, items, **more):
        email, first, last, street, city, state, postal = customer
        status, location, text = Browser(s.url("storefront")).buy(
            items, email=email, firstName=first, lastName=last, streetAddress1=street, city=city, countryArea=state, postalCode=postal, **more)
        if status != 303:
            return None
        order = s.gql("query($id: ID!) { order(id: $id) { id number lines { id quantity } transactions { id } } }",
                      id=urllib.parse.unquote(location.rsplit("/", 1)[-1]))["order"]
        placed.append((email, order))
        return order

    def fulfil(order, lines):
        s.gql("mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { errors { code } } }",
              admin, o=order["id"], l=lines)

    def refund(order, amount=None):
        s.gql("mutation($id: ID!, $a: PositiveDecimal) { transactionRequestAction(id: $id, actionType: REFUND, amount: $a) { errors { code } } }",
              admin, id=order["transactions"][0]["id"], a=amount)

    # Two customers the task's checks look for: an order that is paid and still waiting to be shipped, and a
    # subscriber whose first box has shipped.
    buy(CUSTOMERS[0], {"BOX-S": 1, "Assam Breakfast (100 g)": 2})
    waiting = len(placed)
    fulfil(buy(CUSTOMERS[1], {"BOX-L": 1}), [{"orderLineId": l["id"], "quantity": l["quantity"]} for l in placed[-1][1]["lines"]])

    # Everyone else: 42 orders of one to four products, some with a monthly box.
    others = CUSTOMERS[2:]
    for i in range(42):
        customer = others[i % len(others)] if i < len(others) else rng.choice(others)
        items = {rng.choice(titles): rng.randint(1, 3) for _ in range(rng.randint(1, 4))}
        if i % 5 == 0:
            items[rng.choice(["BOX-S", "BOX-L"])] = rng.randint(1, 2)
        if i == 20:
            items = {'Lever espresso machine "La Paziente" (Chrome)': 1, "House Espresso (1 kg)": 2}
        buy(customer, items)
    buy(others[3], {"Peppermint (50 g)": 1}, paymentMethod="pm_card_declined")      # two cards that were declined: no order
    buy(others[7], {"BOX-S": 1}, paymentMethod="pm_card_declined")

    # What staff did with them. Of every ten orders: six shipped, one part-shipped, one cancelled and refunded,
    # one partly refunded, one still waiting.
    for i, (email, order) in enumerate(placed[waiting + 1:]):
        every = [{"orderLineId": l["id"], "quantity": l["quantity"]} for l in order["lines"]]
        step = i % 10
        if step < 6:
            fulfil(order, every)
        elif step == 6:
            fulfil(order, [{"orderLineId": order["lines"][0]["id"], "quantity": 1}])
        elif step == 7:
            s.gql("mutation($id: ID!) { orderCancel(id: $id) { errors { code } } }", admin, id=order["id"])
            refund(order)
        elif step == 8:
            refund(order, 5)

    # Subscriptions: started by Core's events, so wait for them; then one upgrade, one downgrade and one cancellation.
    def subscriptions():
        return s.get("subscriptions", "/api/subscriptions")[1]["subscriptions"]

    s.wait_for(lambda: len([x for x in subscriptions() if x["email"] == CUSTOMERS[1][0]]) == 1, timeout=30)
    s.wait_for(lambda: len(subscriptions()) >= 9, timeout=30)
    active = [x for x in subscriptions() if x["status"] == "active" and not x["email"].startswith("legacy.")]
    small = [x for x in active if x["sku"] == "BOX-S"]
    large = [x for x in active if x["sku"] == "BOX-L"]
    if small:
        s.post("subscriptions", "/api/subscriptions/{}/plan".format(small[0]["subscription_id"]), {"sku": "BOX-L"})
    if large:
        s.post("subscriptions", "/api/subscriptions/{}/plan".format(large[0]["subscription_id"]), {"sku": "BOX-S"})
    if len(small) > 1:
        s.post("subscriptions", "/api/subscriptions/{}/cancel".format(small[1]["subscription_id"]))

    # Support: five customers wrote in. Agents answered three, left notes on two and resolved two.
    agent = {"api_access_token": "support-agent-token"}
    canned = {c["short_code"]: c["content"] for c in s.request("support", "GET", "/api/v1/accounts/1/canned_responses", headers=agent)[1]}
    names = {c[0]: "{} {}".format(c[1], c[2]) for c in CUSTOMERS}
    for email, text, reply, resolved in MESSAGES:
        contact = s.post("support", "/public/api/v1/inboxes/web/contacts", {"name": names[email], "email": email})[1]
        conversation = s.post("support", "/public/api/v1/inboxes/web/contacts/{}/conversations".format(contact["id"]), {"message": text})[1]
        path = "/api/v1/accounts/1/conversations/{}".format(conversation["id"])
        if reply:
            s.request("support", "POST", path + "/messages", {"content": canned[reply]}, agent)
        else:
            s.request("support", "POST", path + "/messages", {"content": "Checking with the team before I answer.", "private": True}, agent)
        if resolved:
            s.request("support", "POST", path + "/toggle_status", {"status": "resolved"}, agent)
    log("history: {} orders, {} subscriptions, {} conversations".format(len(placed), len(subscriptions()), len(MESSAGES)))
