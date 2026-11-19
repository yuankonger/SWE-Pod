"""The six other tickets of release 2026.12. One check per method, named test_<boundary>__<what>.

Each fails on the company as it was. `rubric.toml` lists them with a note on what each is for."""
import os
import urllib.parse

from shop import Browser, field_named, parse, text_of


class ReleaseChecks:
    # ---- SHOP-31 ----
    def test_storefront_core__the_shop_can_be_searched(self):
        shop = Browser(self.s.url("storefront"))
        status, _, everything = shop.open("/")
        self.assertTrue(field_named(everything, "q"), "the shop page has no search field named q")
        self.assertIn("Small monthly box", text_of(everything))
        status, _, page = shop.open("/?q=" + urllib.parse.quote("crème"))
        self.assertEqual(status, 200)
        found = text_of(page)
        for name in ("Earl Grey Crème", "Rooibos"):
            self.assertIn(name, found)
        for name in ("Small monthly box", "Assam Breakfast", "House Espresso"):
            self.assertNotIn(name, found, "a search for crème still shows {}".format(name))
        status, _, page = shop.open("/?q=zzzz")
        self.assertEqual(status, 200)
        # nothing matches: no product can be put in the cart from this page
        self.assertEqual([f for f in parse(page).forms if set(f["fields"].values()) & set(self.variants.values())], [],
                         "a search that matches nothing still offers products")

    # ---- SUP-12 ----
    def test_support_api__an_agent_lists_one_customers_conversations(self):
        agent = {"api_access_token": "support-agent-token"}

        def listed(query=""):
            status, body = self.s.request("support", "GET", "/api/v1/accounts/1/conversations" + query, headers=agent)
            self.assertEqual(status, 200, body)
            return body["data"]["payload"]

        self.assertGreaterEqual(len(listed()), 5)                      # the five conversations in the company's history
        mine = listed("?email=li.wei%40example.com")
        self.assertEqual([c["meta"]["sender"]["email"] for c in mine], ["li.wei@example.com"])
        self.assertEqual(listed("?email=li.wei%40example.com&status=resolved"), [])
        self.assertEqual(len(listed("?email=amelie.dubois%40example.com&status=resolved")), 1)
        self.assertEqual(listed("?email=nobody%40example.com"), [])

    # ---- PAY-21 ----
    def paged(self):
        status, first = self.s.get("payments", "/api/payment-intents")
        self.assertEqual(status, 200)
        self.assertEqual((len(first["payment_intents"]), first.get("has_more")), (20, True),
                         "the payment intent list is not paged: 20 by default, with has_more")
        return first["payment_intents"]

    def test_payments_api__lists_are_paged_and_an_intent_is_read_by_id(self):
        first = self.paged()
        status, page = self.s.get("payments", "/api/payment-intents?limit=5&starting_after=" + first[4]["id"])
        self.assertEqual((status, [i["id"] for i in page["payment_intents"]], page["has_more"]), (200, [i["id"] for i in first[5:10]], True))
        seen, last, more = [], None, True
        while more:                                                    # walking the pages reaches every record exactly once
            status, page = self.s.get("payments", "/api/payment-intents?limit=100" + ("&starting_after=" + last if last else ""))
            self.assertEqual(status, 200, page)
            self.assertTrue(page["payment_intents"], "a page said more follows and the next one was empty")
            seen += [i["id"] for i in page["payment_intents"]]
            last, more = seen[-1], page["has_more"]
        self.assertGreaterEqual(len(seen), 47)
        self.assertEqual(len(seen), len(set(seen)))
        status, one = self.s.get("payments", "/api/payment-intents/" + seen[-1])
        self.assertEqual((status, one["id"], one["currency"]), (200, seen[-1], "usd"))
        self.assertEqual(self.s.get("payments", "/api/payment-intents/pi_missing")[0], 404)
        for bad in ("limit=500", "limit=0", "starting_after=pi_missing"):
            self.assertEqual(self.s.get("payments", "/api/payment-intents?" + bad)[0], 400, bad)
        status, refunds = self.s.get("payments", "/api/refunds?limit=2")
        self.assertEqual((status, len(refunds["refunds"]), refunds["has_more"]), (200, 2, True))

    # ---- SUB-18 ----
    def test_payments_subscriptions__a_new_subscription_records_its_card_from_a_paged_list(self):
        self.paged()                         # the point of the ticket: the list no longer holds a new payment
        # bought through Core, so that what card a shop's form offers does not come into it
        self.buy("paged-list@example.com", {"BOX-L": 1}, payment_method="pm_card_visa_debit")
        subs = self.s.wait_for(lambda: self.subscriptions("paged-list@example.com"), timeout=20)
        self.assertTrue(subs, "no subscription was started for the paid order")
        self.assertEqual(subs[0]["payment_method"], "pm_card_visa_debit", "the subscription does not hold the card the order was paid with")

    # ---- OPS-9 ----
    def test_ops_subscriptions__a_failed_renewal_raises_the_alert(self):
        def state():
            """The alert's state as Prometheus has it: None if it has no such rule, else "inactive", "pending" or "firing"."""
            status, body = self.s.get("prometheus", "/api/v1/rules")
            rules = [r for g in body["data"]["groups"] for r in g["rules"] if r.get("name") == "RenewalsFailing" and r.get("type") == "alerting"]
            return (rules[0]["state"], rules[0].get("labels", {})) if rules else None

        self.assertIn("prometheus", self.s.procs, "Prometheus is not running")
        self.assertIsNotNone(self.s.wait_for(state, timeout=20), "Prometheus has no alert named RenewalsFailing")
        # No renewal has failed yet: an alert that fires anyway tells on-call nothing.
        self.assertIsNone(self.never(lambda: state()[0] == "firing", 3), "RenewalsFailing fires although no renewal has failed")
        self.buy("dunning@example.com", {"BOX-S": 1})
        subs = self.s.wait_for(lambda: self.subscriptions("dunning@example.com"), timeout=20)
        self.assertTrue(subs, "no subscription was started for the paid order")
        self.s.request("subscriptions", "PUT", "/api/customers/payment-method", {"email": "dunning@example.com", "payment_method": "pm_card_declined"})
        status, run = self.s.post("subscriptions", "/api/renewals/run", {"as_of": subs[0]["current_period_end"]})
        self.assertGreaterEqual(run["failed"], 1, run)
        self.assertTrue(self.s.wait_for(lambda: state()[0] == "firing", timeout=30), "a renewal failed and RenewalsFailing is not firing")
        self.assertEqual(state()[1].get("severity"), "ticket")

    # ---- MOB-8 ----
    def test_mobile_core__release_1_1_0_names_variants_and_1_0_0_still_buys(self):
        builds = self.supported_mobile_builds()
        self.assertIn("1.1.0", builds, "release 1.1.0 is not among the supported builds")
        self.assertTrue(os.path.isfile(os.path.join(builds["1.1.0"], "client.ts")), "release 1.1.0 has not been built")
        names = {}
        for version in ("1.0.0", "1.1.0"):
            email = "variants-{}@example.com".format(version.replace(".", "-"))
            screens = self.replay(builds[version], email=email, items={"TEA-ASM-100": 1})
            self.assertTrue(screens.get("ok"), "release {} cannot buy: {}".format(version, screens))
            names[version] = (screens["cart"]["lines"][0]["name"], screens["order"]["lines"][0]["name"],
                              next(p["name"] for p in screens["shop"]["products"] if p["sku"] == "TEA-ASM-100"))
            bought = [l["productSku"] for o in self.orders_of(email) for l in self.order(o["id"])["lines"]]
            self.assertEqual(bought, ["TEA-ASM-100"], "release {} showed an order that Core does not hold".format(version))
        self.assertEqual(names["1.1.0"], ("Assam Breakfast (100 g)",) * 3)
        self.assertEqual(names["1.0.0"], ("Assam Breakfast",) * 3)       # the old build is what it was
