# Cross-repo dependencies between saleor/saleor (core) and the AvaTax / SMTP apps in saleor/apps

Scope: tax path (core <-> `apps/taxes`, later `apps/avatax`) and notification path (core <-> `apps/emails-and-messages`, later `apps/smtp`), from 2022 to November 2026.

How each item was checked (marker at the end of every finding):

- `[API]` PR description opened through the public GitHub API.
- `[web]` issue or docs page opened in the browser fetcher (returned as a summary, not verbatim text).
- `[git]` commit message and diff stat read in a full-history clone of the public repository; the PR page itself was not opened. PR number comes from the commit subject.
- `[changelog]` text read from `CHANGELOG.md` of the repository or app at the stated version.

Items dated after June 2026 are marked **POST-JUNE-2026** inline and collected again in the last section.

Repository links used throughout: core PRs are `https://github.com/saleor/saleor/pull/N`, app PRs are `https://github.com/saleor/apps/pull/N`.

---

## 1. Tax path: which core changes forced AvaTax-app changes, and the reverse

### Takeaway

The tax contract is not one sentence. Over 2023-2026 at least ten separate pieces of meaning moved between core and the app: who applies order-level discounts, whether prices include tax, which channel strategy means "this app is not the calculator", what an HTTP status means to the caller, which permission lets the app read a field, and what a zero tax with a non-zero rate means. Most breakages were semantic (same payload shape, different meaning) and were found in production or QA, not by schema checks.

### Cited Findings

#### T1. Order-level discounts: who distributes them (the longest chain, Aug 2022 - Nov 2024)

- Core 2022-08-26: "Order discount is applied 2 times when any tax app/plugin is active". Core stopped pre-applying order discounts when a tax app or plugin is active — [saleor#10428](https://github.com/saleor/saleor/pull/10428) `[git]`
- Core issue 2023-05-26: the tax payload carries a `discounts` list that "the tax app must apply"; Saleor does not propagate an entire-order voucher because "different tax providers handle this differently". Request to add already-discounted price fields; closed 2025-03-24 with only an internal tracker reference — [saleor#12941](https://github.com/saleor/saleor/issues/12941) `[web]`
- Core issue 2023-04-26: after a tax app responds, `checkoutLine.totalPrice` has tax and voucher, but `unitPrice` and `undiscounted*` have neither. The page assigns no blame; closed 2024-10-29 — [saleor#12691](https://github.com/saleor/saleor/issues/12691) `[web]`
- App-side QA list (opened 2023-04-24, still open): parity items from core tax engineers include "the `discounts` field from Saleor is handled", net/gross respected, rounding (unit 3.66, 5% discount, qty 3), JPY, free-shipping voucher, country exceptions using tax-app strategy, product tax class overriding product-type tax class — [apps#415](https://github.com/saleor/apps/issues/415) `[web]`
- Core issue 2024-03-04, filed by a tax-app developer: `discounts` in `CalculateTaxes` is populated for `SPECIFIC_PRODUCT` and `applyOncePerOrder` vouchers even though Saleor already reduced the line, so an app following the docs discounts twice. The app cannot tell the cases apart without `HANDLE_DISCOUNTS`. Reported on 3.18 and 3.20 — [saleor#15531](https://github.com/saleor/saleor/issues/15531) `[web]`. Fixed by "Fix discounts resolver to work like in docs", 2024-05-10 — [saleor#15880](https://github.com/saleor/saleor/pull/15880) `[git]`
- App 2024-05-13 (v1.5.0): switched to "price reduction" — "Saleor is responsible for calculating discounted prices and Avatax will receive totalPrice (discounted or not)" — [apps#1342](https://github.com/saleor/apps/pull/1342) `[API]`
- Core 2024-06-12, merged to the 3.19 branch and listed as a breaking change: `order.discounts` is disabled in sync events "to prevent circular calls" — [saleor#16111](https://github.com/saleor/saleor/pull/16111) `[API]`, [3.19 changelog](https://github.com/saleor/saleor/blob/3.20.0/CHANGELOG.md) `[changelog]`
- App 2024-06-17/18 (v1.6.3, v1.7.0): added `TaxDiscount` to the `TaxBase` subscription, then reversed the May decision for the calculate-taxes webhooks: discounts are now sent to Avalara for automatic distribution, while `ORDER_CONFIRMED` keeps price reduction. Two webhooks in one app now use two different discount models — [apps#1427](https://github.com/saleor/apps/pull/1427) `[git]`, [apps#1396](https://github.com/saleor/apps/pull/1396) `[API]`
- Core 2024-08-08 and 2024-08-19: "Fix `TaxableObject.discounts` resolver", "Return proper order level discounts when generating static order tax payload" — [saleor#16468](https://github.com/saleor/saleor/pull/16468), [saleor#16572](https://github.com/saleor/saleor/pull/16572) `[git]`
- App 2024-08-19 (v1.8.0): non-taxable lines returned to Saleor now take discounts into account and always report rate 0 — [apps#1522](https://github.com/saleor/apps/pull/1522) `[API]`
- Core RFC 2024-08-28: Saleor sends order discounts with only `name` and `amount`; Avalara therefore spreads every discount over all lines including shipping. First proposal (new `shipping_discounts` field, split mutations, data migration) drew a zero-downtime objection: old and new discounts could coexist during upgrade. Dropped in favour of the next RFC — [saleor#16595](https://github.com/saleor/saleor/issues/16595) `[web]`
- Core RFC 2024-08-29: lists both halves of the fix. Core: add `type` (`SUBTOTAL` / `SHIPPING`) to `TaxableObjectDiscount` and split manual discounts in two. App: sum `SUBTOTAL` into the document `discount`, subtract `SHIPPING` from the shipping line, flag product lines as discounted, never flag shipping — [saleor#16613](https://github.com/saleor/saleor/issues/16613) `[web]`
- Core 2024-09-05: `TaxableObjectDiscountType` added "because the Avatax app does not have enough information on how to distribute order-level discounts over the lines, resulting in incorrect tax calculations" — [saleor#16630](https://github.com/saleor/saleor/pull/16630) `[API]`
- App 2024-09-10 (v1.9.0): "Implemented new discount strategy - for SHIPPING and SUBTOTAL values"; minimum Saleor raised to 3.19 in the same release; commit notes "Fetch final schema for 3.20" — [apps#1552](https://github.com/saleor/apps/pull/1552) `[API]` `[changelog]`
- Core 2024-09-26: order totals were wrong with a tax app plus order-level discounts. Core stops propagating order-level discounts to lines for the tax-app strategy ("Flat rates and plugin requires the propagation, but tax app does it itself"), and treats shipping vouchers like line discounts — [saleor#16696](https://github.com/saleor/saleor/pull/16696) `[API]`
- Core 2024-10-07: a tax webhook registered without a subscription query got the shipping voucher applied twice in the legacy payload — [saleor#16814](https://github.com/saleor/saleor/pull/16814) `[API]`
- Core 2024-11-13: partial revert of #16696. Skipping price assignment for the tax-app strategy was "redundant"; and when the app returns empty data (for example no address) core previously skipped all calculation, so not even untaxed discounted values were produced — [saleor#16986](https://github.com/saleor/saleor/pull/16986) `[API]`
- Current docs state the resulting split: product lines `discounted: true` with unchanged amounts, shipping line reduced, subtotal-type discounts summed into `discount` — [AvaTax app configuration docs](https://docs.saleor.io/developer/app-store/apps/avatax/configuration) `[web]`

#### T2. Prices entered with or without tax

- Old Taxes app 2023-05-16: "respect pricesEnteredWithTax setting"; before this the app ignored it — [apps#466](https://github.com/saleor/apps/pull/466) `[git]`
- AvaTax app v1.4.0: "Fixed bug when app sends wrong information to Avatax indicating if tax is included in prices. After this change app will get this information from Saleor" — [apps#1275](https://github.com/saleor/apps/pull/1275), merged 2024-03-27 `[API]` `[changelog]`
- The app could not make that fix alone: the `ORDER_CONFIRMED` async payload had no way to read the flag. Core added `Channel.taxConfiguration` for it: "allows reading the `taxConfiguration.pricesEnteredWithTax` property for tax app calculation correctness" — [saleor#15610](https://github.com/saleor/saleor/pull/15610), merged 2024-03-21 `[API]`
- Core 2024-12-03: "Fix gross prices as default values when prices entered with taxes" and the related undiscounted-price fix — [saleor#16992](https://github.com/saleor/saleor/pull/16992) `[git]`

#### T3. Flat rates and "this app is not the calculator"

- App v1.4.0, 2024-03-27: "Avatax app no longer creates new transactions if Saleor is set to use flat rates." The PR adds `taxConfiguration` to the order channel in the subscription and returns early on flat rates; description says "~~Requires saleor#15610~~" — [apps#1255](https://github.com/saleor/apps/pull/1255) `[API]`
- Same rule on the plugin side three months earlier: "Do not call Avatax when using flat rate" — [saleor#15038](https://github.com/saleor/saleor/pull/15038), 2023-12-15 `[git]`
- App 2026-06-15 (v1.22.12): `ORDER_CONFIRMED` failed with a validation error and HTTP 500 when the channel had no strategy at all; the app only accepted `TAX_APP` or `FLAT_RATES`. `null` is now treated like flat rates — [apps#2373](https://github.com/saleor/apps/pull/2373) `[API]`
- Core background: flat rates became the default strategy for channels with nothing set — [saleor#12069](https://github.com/saleor/saleor/pull/12069), 2023-02-20 `[git]`

#### T4. `taxAppId`, app identifier, and blocking checkout when the tax app fails

- Issue 2023-05-22: with a failing sync tax app "there is no way to stop the operation"; a US state with no sales tax looks identical to a failed calculation (tax 0, prices unchanged). Closed as duplicate — [saleor#12896](https://github.com/saleor/saleor/issues/12896) `[web]`
- RFC 2023-05-26: assign a tax app per channel and per country; block finalisation on invalid response; make `App.identifier` mandatory; an apps-side engineer asks docs to define "what makes an invalid and successful response (status codes etc.)" and to convert all 4xx/5xx to a tax-app problem — [saleor#12942](https://github.com/saleor/saleor/issues/12942) `[web]`
- Core 2024-02-13 (3.19): `taxAppId` on `TaxConfiguration` and per-country config, `Shop.availableTaxApps`, `checkout.tax_error` column, migration making `App.identifier` non-blank. With `taxAppId` set, `checkoutComplete` and `draftOrderComplete` refuse to finish if the app did not respond. PR notes "Needs fixes from saleor#15378. Zero downtime will be provided with those fixes" — [saleor#15292](https://github.com/saleor/saleor/pull/15292) `[API]`
- Follow-ups: plugins allowed in the same field — [saleor#15460](https://github.com/saleor/saleor/pull/15460) (2024-02-26); schema text corrected to say the value must be the app *identifier* (manifest id), not the app's GraphQL ID — [saleor#15596](https://github.com/saleor/saleor/pull/15596) (2024-03-19) `[git]`
- App 2024-10-17 (v1.10.9): the manifest id became configurable through `MANIFEST_APP_ID` "to set different ID in production, dev, staging envs allowing them to be installed at the same time" — [apps#1628](https://github.com/saleor/apps/pull/1628) `[git]` `[changelog]`. The value a merchant stores as `taxAppId` therefore depends on a deployment variable of the app.
- Core 2024-04-10: "Fix checkout base prices when tax app is broken" — [saleor#15783](https://github.com/saleor/saleor/pull/15783) `[git]`
- Core 2025-01-17: `orderCreateFromCheckout` was not covered by the block and could create an order after a tax error — [saleor#17258](https://github.com/saleor/saleor/pull/17258) `[API]`
- Docs: without `taxAppId`, Saleor tries every subscribed app in turn until one returns a valid response — [tax webhook docs](https://docs.saleor.io/developer/extending/webhooks/synchronous-events/tax) `[web]`

#### T5. HTTP status codes changed meaning three times

- Old Taxes app 2023-05: failed webhooks returned 200 with an error body; changed to 500 — [apps#462](https://github.com/saleor/apps/pull/462) and taxes changelog entry 72adeb3 `[git]` `[changelog]`
- Core 3.18: "Saleor will no longer reattempt delivery for webhooks that return non-transient HTTP errors (400, 404, etc.)" — [saleor#14566](https://github.com/saleor/saleor/pull/14566) `[changelog]`. Apps then used 4xx for "do not retry".
- Core 3.21: sync-webhook circuit breaker, plus `App.breakerState` and `appReenableSyncWebhooks`. PR opened 2024-09-05, merged 2025-02-27 — [saleor#16658](https://github.com/saleor/saleor/pull/16658) `[API]`; wrapper fix [saleor#17443](https://github.com/saleor/saleor/pull/17443) `[git]`
- App 2025-11-21 (v1.21.3): "With the new Circuit Breaker mechanism, 4xx responses will cause Saleor to disable webhooks." The app moves incomplete payloads, entity-not-found, string-length errors, already-fulfilled orders and missing documents on cancel from 4xx to **202**; 4xx is kept only for "app not configured", where being disabled is the wanted outcome — [apps#2136](https://github.com/saleor/apps/pull/2136) `[API]`
- Core 2026-02-12 and 2026-04-17: order and checkout tax webhooks moved to a promise-based path — [saleor#18793](https://github.com/saleor/saleor/pull/18793), [saleor#19067](https://github.com/saleor/saleor/pull/19067); this broke the breaker and needed "Fix Circuit Breaker for promise webhook approach" — [saleor#18955](https://github.com/saleor/saleor/pull/18955), 2026-03-20 `[git]`
- App 2025-2026: address problems reclassified one by one from 500 to 400 (invalid zip for state [apps#2055](https://github.com/saleor/apps/pull/2055); incomplete ship-from address, v1.25.1; "exact street name match could not be found", v1.27.1 **POST-JUNE-2026**) because a 500 makes Saleor retry and "looked like an app outage" `[git]` `[changelog]`

#### T6. Validation of the app's response, and the tax-rate semantics

- Core 2024-09-25: responses are rejected when any value is negative, line count differs, rate exceeds 100%, or price exceeds the DB limit — [saleor#16720](https://github.com/saleor/saleor/pull/16720) `[API]`. The line-count check was then dropped for the built-in plugin only — [saleor#16917](https://github.com/saleor/saleor/pull/16917) `[git]`
- Docs: lines must come back "in the same order in which they were sent"; there is no line id in the response — [tax webhook docs](https://docs.saleor.io/developer/extending/webhooks/synchronous-events/tax) `[web]`
- App history of `tax_rate`: v1.5.3 starts returning the real rate from AvaTax details instead of 0 — [apps#1375](https://github.com/saleor/apps/pull/1375) (2024-06-03); v1.8.1 raises precision from 2 to 6 decimals; v1.12.3/1.12.4 add a log for "line tax rate is non-zero but amount of taxes is zero"; v1.12.8 resets the rate to 0 when taxable amount is 0 (exempt customer on a normally taxable product) — [apps#1726](https://github.com/saleor/apps/pull/1726) (2025-02-05) `[API]` `[git]` `[changelog]`
- Core in the same weeks: "Fix incorrect tax rate returned by Avatax plugin" — [saleor#17238](https://github.com/saleor/saleor/pull/17238) (2025-01-13); "Fix undiscounted price taxation inside an order calculations when the Avatax plugin is used" — [saleor#17253](https://github.com/saleor/saleor/pull/17253) `[git]`
- Why the rate matters to core: core uses the returned rate to tax the *undiscounted* prices. A quantize added to the rate in the weighted-shipping-tax PR ([saleor#17726](https://github.com/saleor/saleor/pull/17726)) "can cause that we will lose the precision while calculate the undiscounted amount" and was reverted next day — [saleor#17777](https://github.com/saleor/saleor/pull/17777), 2025-06-03 `[API]`
- Open core issue since 2023-11-13: undiscounted-price taxation was done for plugins ([saleor#14095](https://github.com/saleor/saleor/pull/14095)) but "should also apply to Apps in `_apply_tax_data`" — [saleor#14729](https://github.com/saleor/saleor/issues/14729) `[web]`; bug report for the same gap on draft orders — [saleor#15333](https://github.com/saleor/saleor/issues/15333) `[web]`

#### T7. Commit / void lifecycle and document codes

- 2023-04: Taxes app creates the AvaTax transaction on `ORDER_CREATED` and commits on `ORDER_FULFILLED` — [apps#355](https://github.com/saleor/apps/pull/355) `[git]`
- 2023-08-10: flow moved to `ORDER_CONFIRMED` (commit decided by "isAutocommit"), new `ORDER_CANCELLED` handler voids the transaction, order metadata key `externalId` renamed `avataxId`, an `AppWebhookMigrator` introduced, docs PR in a third repository — [apps#826](https://github.com/saleor/apps/pull/826) `[API]`. Old code deleted two weeks later; "All the cloud environments had been migrated automatically" — [apps#916](https://github.com/saleor/apps/pull/916) `[git]` `[changelog]`
- Cancel edge cases discovered later, each a separate release: order with no `avataxId` (not an AvaTax order) — [apps#1293](https://github.com/saleor/apps/pull/1293); document missing in AvaTax — [apps#1573](https://github.com/saleor/apps/pull/1573); already cancelled — [apps#1596](https://github.com/saleor/apps/pull/1596) `[git]`
- Core 2022-12-20: "Fix double avatax requests for created order" — [saleor#11509](https://github.com/saleor/saleor/pull/11509) `[git]`
- Address used at commit: app first used billing address, then "Use shipping address in `order-confirmed`" with fallback — [apps#1246](https://github.com/saleor/apps/pull/1246) (2024-03-19), then "Fixed broken taxes resolving for billing address" — [apps#1604](https://github.com/saleor/apps/pull/1604) (2024-10-02) `[git]`. Core rule: shipping address, or billing if shipping is not required — [tax webhook docs](https://docs.saleor.io/developer/extending/webhooks/synchronous-events/tax) `[web]`; core fix for click-and-collect — [saleor#15505](https://github.com/saleor/saleor/pull/15505) `[git]`
- Document code: app sent the first 20 characters of the order id, so an AvaTax document could not be traced back to a Saleor order; changed to order number — [apps#2075](https://github.com/saleor/apps/pull/2075), 2025-09-08 `[API]`
- Line identity: `itemCode` from SKU with fallback to variant id, and gross amount taken from `OrderLine` instead of recomputed — [apps#1248](https://github.com/saleor/apps/pull/1248) (2024-03-18), [apps#1644](https://github.com/saleor/apps/pull/1644) `[API]` `[git]`
- The current app subscribes to exactly four events: `checkout-calculate-taxes`, `order-calculate-taxes`, `order-confirmed`, `order-cancelled` — [apps/avatax webhooks directory](https://github.com/saleor/apps/tree/main/apps/avatax/src/app/api/webhooks) `[git]`

#### T8. Customer code, exemption, and what metadata reaches the app

- Core issue 2022-10-10: checkout metadata set after creation never reached the tax webhook, because core caches tax results and recalculates only on line or address change; the reporter needed it for reverse-charge status — [saleor#10897](https://github.com/saleor/saleor/issues/10897) `[web]`
- App: user id missing in payload, so email used; then "cannot resolve customer code" and "cannot resolve email" crashes fixed with fallbacks — [apps#922](https://github.com/saleor/apps/pull/922), [apps#1068](https://github.com/saleor/apps/pull/1068), [apps#1071](https://github.com/saleor/apps/pull/1071) (Aug-Oct 2023) `[git]`
- Customer-code source moved: user metadata — [apps#1189](https://github.com/saleor/apps/pull/1189) (2024-02), then checkout/order metadata first — [apps#1300](https://github.com/saleor/apps/pull/1300) (2024-04). Docs now say the user-metadata option "does not work with the CheckoutCalculateTaxes webhook" and the key should be set "before tax calculation" — [apps#864](https://github.com/saleor/apps/issues/864), [AvaTax docs](https://docs.saleor.io/developer/app-store/apps/avatax/configuration) `[web]`
- Exemption status written back to checkout public metadata after calculation, as background work — [apps#2183](https://github.com/saleor/apps/pull/2183), 2026-02-09 `[git]`
- Core tax exemption API (`taxExemptionManage`) — [saleor#10344](https://github.com/saleor/saleor/pull/10344), 2022-09-16 `[git]`

#### T9. Permission gap: ship-from override (feature, revert, core change, re-land)

- 2025-10-08 request, 2025-10-10 merge: read `avataxShipFromAddress` from *private* metadata of checkout/order; the subscription fragment gains `privateMetafield(key: "avataxShipFromAddress")` — [apps#2097](https://github.com/saleor/apps/issues/2097) `[web]`, [apps#2098](https://github.com/saleor/apps/pull/2098) `[API]`
- 2025-10-13/15: two "Fix avatax e2e" PRs, then full revert with no stated reason — [apps#2104](https://github.com/saleor/apps/pull/2104) `[API]` `[web]`
- 2025-10-27: core, targeted at the 3.22 release branch: "Apps with `HANDLE_TAXES` should have access to those fields" (`privateMetadata` and `user` on Checkout and Order) — [saleor#18374](https://github.com/saleor/saleor/pull/18374) `[API]`, forward-port [saleor#18390](https://github.com/saleor/saleor/pull/18390) `[git]`
- 2025-11-27: feature re-landed inside a PR titled "Fix avatax e2e" — [apps#2135](https://github.com/saleor/apps/pull/2135) `[git]`

#### T10. When core calls the app at all

- 3.21 breaking: list queries (`checkouts`, `checkoutLines`, `me.checkouts`, `orders`, `draftOrders`, `me.orders`) no longer trigger tax webhooks — [saleor#17268](https://github.com/saleor/saleor/pull/17268), [saleor#17421](https://github.com/saleor/saleor/pull/17421) `[changelog]`
- 3.21: draft-order base prices refresh after 24 hours by default; unconfirmed orders never refresh — [saleor#17160](https://github.com/saleor/saleor/pull/17160) `[changelog]`
- 3.23: "sync webhooks (such as `ORDER_CALCULATE_TAXES`) are no longer pre-fired before sending async webhook events" — [3.23 changelog](https://github.com/saleor/saleor/blob/3.23/CHANGELOG.md), implemented in [saleor#18809](https://github.com/saleor/saleor/pull/18809) (2026-02-17) `[changelog]` `[git]`
- Race fixes in order price recalculation — [saleor#18135](https://github.com/saleor/saleor/pull/18135) (2025-09), [saleor#18615](https://github.com/saleor/saleor/pull/18615) (2025-12) `[git]`
- Docs: checkout prices expire after `CHECKOUT_PRICES_TTL`; order prices never expire and are invalidated only on draft/unconfirmed orders — [tax webhook docs](https://docs.saleor.io/developer/extending/webhooks/synchronous-events/tax) `[web]`
- App response for a checkout without an address: v1.4.0 returns `totalPrice` as both net and gross "so storefront user won't be confused with prices being 0" — [apps#1278](https://github.com/saleor/apps/pull/1278) `[git]` `[changelog]`

#### T11. Client-side logs: removed because they broke calculation

- Added 2023-09 with logs stored in app metadata (last 100 events) — [apps#944](https://github.com/saleor/apps/pull/944); narrowed to failures — [apps#1046](https://github.com/saleor/apps/pull/1046) `[git]` `[changelog]`
- Core RFC for a Saleor-hosted app-log API, with a core maintainer objecting that logs must not become a storage mechanism; moved to a discussion, no decision — [saleor#13461](https://github.com/saleor/saleor/issues/13461) `[web]`
- 2024-03-20 removal: the feature "was effectively breaking taxes calculation, because it performed heavy data+network operations during short time period of a webhook execution"; same day the AvaTax client timeout went from 5s to 15s, and next day a metadata cache was added because an extra GraphQL call "was timing out the handler" — [apps#1262](https://github.com/saleor/apps/pull/1262) `[API]`, [apps#1257](https://github.com/saleor/apps/pull/1257), [apps#1265](https://github.com/saleor/apps/pull/1265) `[git]` `[changelog]`
- Rebuilt on the app's own database 2024-09 — [apps#1576](https://github.com/saleor/apps/pull/1576); on by default 2025-01 — [apps#1705](https://github.com/saleor/apps/pull/1705) `[git]`
- Core side arrived two years later as a different feature: "Add Problems API for apps" — [saleor#18724](https://github.com/saleor/saleor/pull/18724) (2026-02-16), consumed two weeks later by "Problems API for AvaTax app" — [apps#2261](https://github.com/saleor/apps/pull/2261) (v1.22.0) `[git]`

#### T12. Shipping and tax classes

- Shipping sent as its own AvaTax line with a configurable tax code — [apps#424](https://github.com/saleor/apps/pull/424), unified in [apps#1215](https://github.com/saleor/apps/pull/1215) `[git]`
- Non-taxable items: "returning 0 for line price if item is not taxable" (states with no sales tax) fixed to fall back to original price — [apps#476](https://github.com/saleor/apps/pull/476), 2023-05-17 `[git]` `[changelog]`
- Tax code matcher (Saleor tax class to AvaTax code), default `P0000000` — [apps#564](https://github.com/saleor/apps/pull/564), v1.4.2 `[git]` `[changelog]`
- Core: "Fixes tax class not clearing when selecting a shipping method without a tax class" — [saleor#17560](https://github.com/saleor/saleor/pull/17560); weighted shipping tax rate — [saleor#17726](https://github.com/saleor/saleor/pull/17726) `[git]`

### Inferences

- T1 is the best evidence that "who applies the discount" cannot be fixed on one side: the app changed strategy three times in four months (May, June, September 2024) and core changed its own propagation twice (September, November 2024), each reacting to the other.
- T9: the public record does not say why the feature was reverted. The sequence (fragment reads private metadata; e2e fix attempts; revert; core grants `HANDLE_TAXES` access to private metadata twelve days later on the release branch; re-land a month after) fits a permission failure found only against a real Saleor instance. This is an inference from order and content, not a stated cause.
- T5: the same status code meant "retry" (pre-3.18), "do not retry" (3.18+), and "count toward disabling the webhook" (3.21+). An app owner cannot choose a status without knowing the caller's current policy.
- T6: `tax_rate` looks decorative in the response but core uses it to derive other stored prices, so "rate 6.25 with tax 0" for an exempt customer corrupts undiscounted totals. Neither side's schema expresses this.
- T7: the app has no refund or fulfilment handler today. A refund in Saleor does not adjust the committed AvaTax document; only cancellation voids it. The docs page neither claims nor denies refund handling.

### Gaps

- No public statement of the reason for the ship-from revert (T9).
- The internal tracker references (Linear, Slack) in core PRs #16111, #16630, #16986, #17258 are not public; the customer-facing symptoms behind them are not documented publicly.
- Could not find a public incident write-up for the March 2024 timeout episode (T11) beyond changelog text.
- `taxError` surfacing to storefronts (`CheckoutProblem` types) is not described on the tax webhook docs page; not researched further.
- GitHub issue search for the old "taxes" label in saleor/apps was cut short by API rate limits; issues #779-#781 linked from apps#415 were not opened.

---

## 2. Email path: payloads, templates, NOTIFY_USER, plugin-to-app migration

### Takeaway

The SMTP app's templates depend on fields whose meaning only core knows (masked versus full gift-card code, which notify sub-events exist, which GraphQL types exist in which minor version). The worst failures were silent: the app installed and answered 200 while sending nothing. The app still depends on the deprecated `NOTIFY_USER` event in 2026, three years after deprecation.

### Cited Findings

#### E1. NOTIFY_USER deprecation and the app's continued dependence

- Core issue: `NOTIFY_USER` has no subscription support, always sends a static JSON payload, and needs `MANAGE_USERS` although it carries order data. Deprecated in 3.16 — [saleor#13803](https://github.com/saleor/saleor/issues/13803) `[web]`, [saleor#13881](https://github.com/saleor/saleor/pull/13881) (2023-09-05) `[API]`
- Replacement events arrived over many versions: order events 3.2, fulfilment created 3.4, `GiftCardSent` 3.13, `OrderRefunded` 3.14, account events 3.15, fulfilment tracking and export events 3.16. Fields that do not exist in the new payloads: `domain`, `site_name` (fetch via `shop` query) and `logo_url` (app must supply) — [NOTIFY_USER deprecation guide](https://docs.saleor.io/upgrade-guides/notify-user-deprecation) `[web]`
- Core events added for the migration: `GIFT_CARD_SENT` — [saleor#12472](https://github.com/saleor/saleor/pull/12472) (2023-04); `ACCOUNT_CHANGE_EMAIL_REQUESTED` — [saleor#13233](https://github.com/saleor/saleor/pull/13233); `ACCOUNT_EMAIL_CHANGED` — [saleor#13537](https://github.com/saleor/saleor/pull/13537); `notify_customer` flag on fulfilment events — [saleor#13620](https://github.com/saleor/saleor/pull/13620), [saleor#13637](https://github.com/saleor/saleor/pull/13637) `[git]`
- Core bug in between: a webhook could not be created with `NOTIFY_USER` plus another event — [saleor#13584](https://github.com/saleor/saleor/pull/13584), 2023-08-08 `[git]`
- App side: "Notify event webhook for customer emails" — [apps#408](https://github.com/saleor/apps/pull/408) (2023-04). As of the latest public code the app still has a `notify.ts` webhook and maps seven `notify_event` strings (account confirmation, delete, password reset, set customer password, change email request/confirm, fulfilment update) — [notify-event-types.ts](https://github.com/saleor/apps/blob/main/apps/smtp/src/lib/notify-event-types.ts) `[git]`
- 2026-05-14 (v2.3.5): `customerCreate` with `redirectUrl` emits `NOTIFY_USER` with `notify_event=account_set_customer_password`. "The SMTP app had no mapping for this sub-event and silently returned 200, so newly-created customers never received their set-password email." Same PR corrects a wrong string literal for `account_change_email_request`. PR text: "It uses legacy `NOTIFY` webhook ... This event will be removed in the future, but this is fast way to implement missing behavior" — [apps#2357](https://github.com/saleor/apps/pull/2357) `[API]`
- Earlier template bug of the same family: password-reset template used `confirm_url` instead of `reset_url` — [apps#1395](https://github.com/saleor/apps/pull/1395) (2024-06); example payloads for email-change events wrong — [apps#2089](https://github.com/saleor/apps/pull/2089) (2025-09) `[git]`

#### E2. Subscription query valid on one minor version, rejected on another

- 2026-03-31: schema bumped to 3.23; `digitalContentUrl` removed from the SMTP order fragment because core removed the digital content API ([saleor#18952](https://github.com/saleor/saleor/pull/18952)); a webhook migration script rewrites already-registered subscription queries with a regex to strip the field — [apps#2302](https://github.com/saleor/apps/pull/2302) `[API]`, [apps#2304](https://github.com/saleor/apps/pull/2304), cleaned up in [apps#2306](https://github.com/saleor/apps/pull/2306) `[git]`
- **POST-JUNE-2026** 2026-07-16 (v2.6.0): `ORDER_CREATED` payload gains transactions with payment method details; required Saleor raised to `>=3.22` "(paymentMethodDetails was added in 3.22)" — [apps#2398](https://github.com/saleor/apps/pull/2398) `[API]`
- **POST-JUNE-2026** 2026-09-16 (v2.8.0): the fragment also selected `GiftCardPaymentMethodDetails`, which exists only in 3.23. On 3.22, `webhookCreate` rejected the whole query, "7 of 9 webhooks fail to register", install still returned 200, "the app looks installed and healthy while sending no order or invoice emails"; 13 instances affected in the prior week; live for two months. Not caught because codegen validated against a 3.23 schema file, and the failure log serialised to `"error":{}`. Fix: detect Saleor version and strip inline fragments the instance cannot resolve; existing installs re-register only "on the next config save" — [apps#2442](https://github.com/saleor/apps/pull/2442) `[API]`
- Core origin of the type: gift cards as payment method — [saleor#18579](https://github.com/saleor/saleor/pull/18579) (2025-12-10) `[git]`; payment method details on transactions (3.22) — [3.22 changelog](https://github.com/saleor/saleor/blob/3.22.0/CHANGELOG.md) `[changelog]`

#### E3. Field meaning known only to core

- **POST-JUNE-2026** (2026-06-29, v2.5.0): default "Gift card sent" template rendered `giftCard.displayCode`, "which Saleor returns masked (last 4 chars only), so customers received an unusable code". Switched to `giftCard.code` — [apps#2383](https://github.com/saleor/apps/pull/2383) `[git]`
- Gift-card event needs an extra permission: "Manage gift card permission is now required to enable gift cards event", event available only on Saleor 3.13+ — [apps#661](https://github.com/saleor/apps/pull/661), [apps#733](https://github.com/saleor/apps/pull/733) (2023-06/07) `[git]` `[changelog]`
- `INVOICE_SENT`: invoice data was not passed to the template; one-line fix — [apps#2345](https://github.com/saleor/apps/pull/2345), 2026-04-28 `[git]`. Earlier: manifest minimum set to 3.10 because "Invoices events don't work correctly in older Saleor versions" — [apps#312](https://github.com/saleor/apps/pull/312) `[git]` `[changelog]`. Core-side invoice notification fixes: [saleor#9909](https://github.com/saleor/saleor/pull/9909), [saleor#10014](https://github.com/saleor/saleor/pull/10014) `[git]`
- Recipient: core switched to "checkout/order email instead of user.email" — [saleor#17753](https://github.com/saleor/saleor/pull/17753) (2025-05-30) `[git]`. **POST-JUNE-2026** app v2.9.5: events with no recipient (order placed without customer email) now answer 202 instead of raising errors — commit [9934357](https://github.com/saleor/apps/commit/99343578) `[git]` `[changelog]`. Sources conflict on the status: the changelog says `202 Accepted`, the inner commit title in the same sync says "warn and return 400 when email recipient is missing".
- Payload growth driven by template needs: order attributes, price details, translated names — [apps#816](https://github.com/saleor/apps/pull/816); metadata and private metadata — [apps#730](https://github.com/saleor/apps/pull/730); `countryArea` — [apps#1177](https://github.com/saleor/apps/pull/1177) `[git]`
- **POST-JUNE-2026** core 3.24 (unreleased): the always-empty `digital_lines` key is removed from the fulfilment confirmation notification payload; `OrderEventsEmailsEnum.DIGITAL_LINKS` removed — [core CHANGELOG on main](https://github.com/saleor/saleor/blob/main/CHANGELOG.md) `[changelog]`

#### E4. Status codes and retries for async email webhooks

- 2025-11-06 (v1.4.1): SMTP provider failure returned 500, so Saleor retried; changed to 400 to stop "retry loops" — [apps#2123](https://github.com/saleor/apps/pull/2123) `[API]`
- 2026-03 (v1.7.0): response body changed from `{"message": ...}` to plain text because the JSON shape "is not recognized shape officially by Saleor nor Dashboard" — [apps#2266](https://github.com/saleor/apps/pull/2266) `[git]` `[changelog]`
- **POST-JUNE-2026** v2.9.2: the 400 rule lost emails. When the app could not reach Saleor to load its own configuration, it answered 400 and "Saleor dropped the event, so the email was never sent". Now 503 for Saleor-side failures (retry), still 400 for SMTP send failures (no duplicate emails) — commit [205859e](https://github.com/saleor/apps/commit/205859ef) `[git]` `[changelog]`
- **POST-JUNE-2026** v2.9.3: when Saleor rejects the app token (environment restored, app reinstalled) the app used to treat it as "no configuration" and answer 200; now 400 with "reinstall the app" — same commit `[git]` `[changelog]`
- Duplicate emails from two installations of the same app both receiving events and both finding an active configuration; closed as not a bug — [apps#746](https://github.com/saleor/apps/issues/746) `[web]`

#### E5. Deferred payloads change what an email describes

- Core: async payload generation moved out of the request — [saleor#16808](https://github.com/saleor/saleor/pull/16808) (2024-11); order events moved 2026-02 — [saleor#18809](https://github.com/saleor/saleor/pull/18809); "Wait for read replica before building deferred payload" merged, reverted two days later, re-landed five days after that — [saleor#18607](https://github.com/saleor/saleor/pull/18607), [saleor#18635](https://github.com/saleor/saleor/pull/18635), [saleor#18638](https://github.com/saleor/saleor/pull/18638) (2025-12); deferred turned off again for fulfilment events "that are using dict to pass data" — [saleor#19011](https://github.com/saleor/saleor/pull/19011) (2026-04) `[git]`
- **POST-JUNE-2026** 2026-10-16: "two updates made in quick succession produce two deliveries that both carry the newer state"; per-webhook `payloadGeneration: IMMEDIATE | DEFERRED` added to webhook mutations *and to the app manifest*, with an ADR — [saleor#19916](https://github.com/saleor/saleor/pull/19916) `[git]`

#### E6. Core plugins to app

- 3.22 marks plugins deprecated and names the replacements: Sendgrid plugin -> SMTP app; Avalara plugin -> AvaTax app — [3.22 changelog](https://github.com/saleor/saleor/blob/3.22.0/CHANGELOG.md) `[changelog]`
- **POST-JUNE-2026** 2026-09-01: Sendgrid plugin removed from core (3.24). It implemented one hook, `notify`, covering 15 customer events. Staff emails stay in the `admin_email` plugin — [saleor#19725](https://github.com/saleor/saleor/pull/19725) `[git]`
- Staff order confirmation email regression fixed in core, not the app — [saleor#18343](https://github.com/saleor/saleor/pull/18343) (2025-10-22) `[git]`
- App extraction: SMTP split out of Emails and Messages — [apps#1335](https://github.com/saleor/apps/pull/1335) (2024-05-08); old app removed — [apps#1503](https://github.com/saleor/apps/pull/1503) (2024-08-21) `[git]`
- Template engine changes that invalidate stored merchant templates: Handlebars helpers added (v1.2.0), templates validated on save (v1.4.0), some helpers removed for security (v2.0.0, [apps#2296](https://github.com/saleor/apps/pull/2296)) with a script to find affected templates, `JSONparse` restored three days later ([apps#2319](https://github.com/saleor/apps/pull/2319)) `[git]` `[changelog]`
- MJML import style caused webhook timeouts: `require` -> `import` -> external bundle, three releases in August 2024 — [apps#1531](https://github.com/saleor/apps/pull/1531), [apps#1538](https://github.com/saleor/apps/pull/1538), [apps#1540](https://github.com/saleor/apps/pull/1540) `[git]`

### Inferences

- E2 is a clean example of a contract that is not expressible in one sentence: "requires 3.22" was true for one field and false for a sibling union member in the same fragment; only the core owner knows which minor introduced each type.
- E1 shows the deprecation guide's mapping table is not sufficient: the app still relies on `NOTIFY_USER` for account flows in 2026, and a missing sub-event mapping fails silently with 200.
- E4: for async webhooks the right status depends on *which dependency failed* (Saleor API versus SMTP server), and on core's retry policy. The app got it wrong in both directions within one year.
- E3 gift-card case: both fields exist, both are strings, tests with example payloads pass either way; only knowledge of core's masking rule distinguishes them.

### Gaps

- The replacement "Customer Emails" app is not in the public saleor/apps repository; its contract with core 3.24 could not be inspected.
- No public issue found describing merchant impact of the gift-card masked-code bug or the 3.22 registration failure beyond the PR text.
- The 3.22-to-3.23 upgrade guide URL guessed for docs.saleor.io returned 404; 3.23 facts are taken from the core changelog only.
- GitHub issue search for NOTIFY_USER and SMTP in saleor/saleor was blocked by API rate limits; only issues found by other routes are listed.

---

## 3. Cases touching three or more owners

### Takeaway

Several real changes needed core, an app and at least one more party (dashboard, docs repository, a second app, or the deployment platform) to move together; in most of them one party discovered the dependency after shipping.

### Cited Findings

- **Order-level discount split (core + AvaTax app + docs + dashboard-created manual discounts).** Core adds `type`, splits manual discounts; app changes its Avalara payload; docs page rewritten; manual discounts are created by staff in the dashboard and are the only discount covering both subtotal and shipping — [saleor#16613](https://github.com/saleor/saleor/issues/16613) `[web]`, [saleor#16630](https://github.com/saleor/saleor/pull/16630), [apps#1552](https://github.com/saleor/apps/pull/1552) `[API]`
- **`taxAppId` (core + dashboard + app + docs).** The RFC to-do lists a dashboard mutation change to show installed tax apps, docs for response validity, and an app identifier requirement — [saleor#12942](https://github.com/saleor/saleor/issues/12942) `[web]`, [saleor#15292](https://github.com/saleor/saleor/pull/15292) `[API]`
- **Circuit breaker (core + AvaTax app + NP Atobarai payment app + dashboard).** One app PR changes status codes in two apps and fixes "stripe statuses" in passing; breaker state is exposed on `App` for the dashboard with a re-enable mutation — [saleor#16658](https://github.com/saleor/saleor/pull/16658), [apps#2136](https://github.com/saleor/apps/pull/2136) `[API]`
- **Payment method details in emails (core + Stripe app + SMTP app).** Core 3.22 lets payment apps return `paymentMethodDetails`; the SMTP app renders them in `ORDER_CREATED`; **POST-JUNE-2026** the Stripe app later ships "send payment method details on Saleor 3.23+" — [3.22 changelog](https://github.com/saleor/saleor/blob/3.22.0/CHANGELOG.md) `[changelog]`, [apps#2398](https://github.com/saleor/apps/pull/2398) `[API]`, commit [3601e29](https://github.com/saleor/apps/commit/3601e299) `[git]`
- **Gift card as payment method (core + SMTP app + Stripe/payment flow).** Core adds a gift-card payment gateway and `GiftCardPaymentMethodDetails` in 3.23; the SMTP fragment selecting it broke on 3.22 (E2) — [saleor#18579](https://github.com/saleor/saleor/pull/18579) `[git]`, [apps#2442](https://github.com/saleor/apps/pull/2442) `[API]`
- **Dashboard extensions per core version (core + dashboard + AvaTax app).** Order-details widget showing AvaTax metadata "3.22 and above" — [apps#1981](https://github.com/saleor/apps/pull/1981) (2025-06); **POST-JUNE-2026** product tax-code widget "Requires Saleor 3.22+" — [apps#2405](https://github.com/saleor/apps/pull/2405). The app's manifest handler reads the Saleor schema version and adds extensions conditionally. Core 3.23 then removed `options`, `mount`, `target` from `AppExtension` in favour of `mountName`, `targetName`, `settings`, and moved extension validation from core to the dashboard ("now Dashboard is only entity that ensures the contract") — [3.23 changelog](https://github.com/saleor/saleor/blob/3.23/CHANGELOG.md) `[changelog]` `[git]`
- **Apps tab permission (dashboard + every app).** "Since the release 3.20 Dashboard will allow all users to access to apps tabs without checking permission", so each app must check `MANAGE_APPS` itself — [apps#1252](https://github.com/saleor/apps/pull/1252), 2024-03-18 `[git]` `[changelog]`
- **Order notes on commit/void (AvaTax app writes to core order, visible in dashboard).** "App will now add Note to Order when a transaction is committed or cancelled" — [apps#2059](https://github.com/saleor/apps/pull/2059), 2025-08 `[git]`
- **POST-JUNE-2026 app deprecation notice (core + dashboard + SMTP app + deployment config).** Core adds `App.deprecationReason` and `appSelfUpdate`, because "manifests are only ever read at install time and apps are usually deprecated long after they are installed"; dashboard shows it as a non-dismissable problem; SMTP v2.9.0 needs a `CRON_SECRET` variable or "stores that installed the app earlier will not be told"; v2.9.1 fixes the cron timing out at about 2000 installations — [saleor#19814](https://github.com/saleor/saleor/pull/19814), commit [4400af6](https://github.com/saleor/apps/commit/4400af60) `[git]` `[changelog]`

### Inferences

- No public case was found where a single refund changed payment, AvaTax document and email together in one coordinated change; the AvaTax app has no refund handler (T7), while the SMTP app has `order-refunded`. The absence itself is a finding: refunds are a place where the three paths diverge without any recorded coordination.
- Promotions: order promotions and gift rewards (core 3.19, [saleor#14696](https://github.com/saleor/saleor/pull/14696), [saleor#15259](https://github.com/saleor/saleor/pull/15259)) landed four to seven months before the discount-type split; the app's three strategy changes in 2024 followed them.

### Gaps

- No saleor/saleor-dashboard history was mined here; dashboard-side PRs for `taxAppId`, breaker state and deprecation banners are not linked.
- Refund Reasons phase 2 ([saleor#19272](https://github.com/saleor/saleor/pull/19272), 2026-06-23) was seen in the log but its effect on emails or tax was not checked.

---

## 4. Chains: reverts, re-lands, hotfixes, backports, misattributed bugs

### Takeaway

Reverts and re-lands cluster exactly where the two sides share unstated meaning: discounts, permissions, payload timing, and tax-rate precision.

### Cited Findings

- **Discount strategy flip-flop (app):** price reduction 2024-05-13 -> automatic distribution 2024-06-18 -> typed split 2024-09-10 — [apps#1342](https://github.com/saleor/apps/pull/1342), [apps#1396](https://github.com/saleor/apps/pull/1396), [apps#1552](https://github.com/saleor/apps/pull/1552) `[API]`
- **Core fix then partial self-revert:** [saleor#16696](https://github.com/saleor/saleor/pull/16696) (2024-09-26) -> [saleor#16986](https://github.com/saleor/saleor/pull/16986) (2024-11-13, "to revert the change introduced in #16696") `[API]`
- **RFC superseded in one day:** [saleor#16595](https://github.com/saleor/saleor/issues/16595) -> [saleor#16613](https://github.com/saleor/saleor/issues/16613) after a migration/zero-downtime objection `[web]`
- **Ship-from override:** merge 2025-10-10, revert 2025-10-15, core permission change 2025-10-27 (release branch 3.22, forward-ported to main), re-land 2025-11-27 — [apps#2098](https://github.com/saleor/apps/pull/2098), [apps#2104](https://github.com/saleor/apps/pull/2104), [saleor#18374](https://github.com/saleor/saleor/pull/18374), [apps#2135](https://github.com/saleor/apps/pull/2135)
- **Tax-rate quantize:** added inside an unrelated feature PR, reverted next day — [saleor#17726](https://github.com/saleor/saleor/pull/17726) -> [saleor#17777](https://github.com/saleor/saleor/pull/17777) `[API]`
- **Deferred payload / read replica:** merge, revert, re-land within one week — [saleor#18607](https://github.com/saleor/saleor/pull/18607), [saleor#18635](https://github.com/saleor/saleor/pull/18635), [saleor#18638](https://github.com/saleor/saleor/pull/18638) `[git]`
- **Client logs:** add 2023-09, restrict 2023-10, remove 2024-03, rebuild on new storage 2024-09, default-on 2025-01 (T11)
- **Webhook migration script (app):** parallel 2024-07 ([apps#1468](https://github.com/saleor/apps/pull/1468)) -> "Restore sequential migration script" 2024-09 ([apps#1570](https://github.com/saleor/apps/pull/1570)) -> parallel again 2024-10 ([apps#1639](https://github.com/saleor/apps/pull/1639)) -> 2025-01 "Fixed bug in webhook migration script that was causing app webhooks to be disabled by migration" ([apps#1717](https://github.com/saleor/apps/pull/1717)) `[git]`
- **Handlebars helper removal and partial restore:** [apps#2296](https://github.com/saleor/apps/pull/2296) -> [apps#2319](https://github.com/saleor/apps/pull/2319) `[git]`
- **Backports that carry the cross-repo dependency:** [saleor#16111](https://github.com/saleor/saleor/pull/16111) merged to branch 3.19; [saleor#18374](https://github.com/saleor/saleor/pull/18374) merged to branch 3.22; **POST-JUNE-2026** [saleor#19801](https://github.com/saleor/saleor/pull/19801) merged to branch 3.23 then cherry-picked to main as [saleor#19806](https://github.com/saleor/saleor/pull/19806) `[API]` `[git]`
- **Bug first seen on the app side, cause in core:** doubled discounts reported by an app developer, fixed in core's resolver — [saleor#15531](https://github.com/saleor/saleor/issues/15531) -> [saleor#15880](https://github.com/saleor/saleor/pull/15880); missing prices-with-tax flag, fixed by a core API addition — [saleor#15610](https://github.com/saleor/saleor/pull/15610); untaxed undiscounted prices with a tax app, located in core `_apply_tax_data` — [saleor#15333](https://github.com/saleor/saleor/issues/15333)
- **Bug that looked like core/cloud, cause in app input handling:** "doesn't send email via SMTP provider on Saleor Cloud" was leading spaces in the host field — [apps#1082](https://github.com/saleor/apps/issues/1082) `[web]`
- **Bug that looked like an app outage, cause in merchant data:** address errors answered 500 and were retried and reported as failures until reclassified (T5)
- **POST-JUNE-2026 core race producing untaxed orders:** a concurrent modification dropped the tax calculation and `draftOrderComplete` finalised with untaxed totals, because pre-tax prices for promotion qualification overwrote `subtotal`/`total`. Fix adds `base_subtotal_amount`/`base_total_amount` columns and returns `TAX_ERROR` — [saleor#19801](https://github.com/saleor/saleor/pull/19801) `[API]`
- **POST-JUNE-2026 plugin retry:** "Before definitely giving up from posting data to Avatax double check" — [saleor#19320](https://github.com/saleor/saleor/pull/19320), 2026-06-16 `[git]`

### Inferences

- The webhook-migration chain is entirely on the app side but its failure mode (webhooks disabled) is visible only as "taxes stopped being calculated" in core.
- In four of the chains the second step happened within seven days of the first, which suggests discovery in staging or production rather than in review.

### Gaps

- Review-comment threads (27 review comments on [saleor#15292](https://github.com/saleor/saleor/pull/15292), 19 on [saleor#16696](https://github.com/saleor/saleor/pull/16696), 21 on [saleor#16720](https://github.com/saleor/saleor/pull/16720), 18 on [apps#2123](https://github.com/saleor/apps/pull/2123)) were not read; they likely hold more detail on disagreements.
- Core discussion [#12607](https://github.com/saleor/saleor/discussions/12607), referenced by two tax issues, was not opened.

---

## 5. Rollout order: webhook migrations, `requiredSaleorVersion`, deprecation windows, backfills

### Takeaway

Subscription queries live in core's database once registered, so an app deploy does not change them; each app release that edits a fragment needs a migration over every installation, and each core release that removes a field needs that migration to have run first.

### Cited Findings

- **Registered queries must be rewritten per installation.** AvaTax has `scripts/run-webhooks-migration.ts` run from `deploy.ts`; history in section 4. SMTP wrote a one-off regex migration to strip `digitalContentUrl` from stored queries before 3.23 — [apps#2304](https://github.com/saleor/apps/pull/2304) `[git]`
- **Order matters for field removal.** Core removed the digital content API on 2026-03-20 ([saleor#18952](https://github.com/saleor/saleor/pull/18952)); the app removed the field and shipped the migration on 2026-03-31 ([apps#2302](https://github.com/saleor/apps/pull/2302), [apps#2304](https://github.com/saleor/apps/pull/2304)) `[git]`
- **SMTP registers webhooks lazily.** "Webhooks are no longer created during the app registration. Instead, the app will subscribe events based on its configuration" — [apps#646](https://github.com/saleor/apps/pull/646) (2023-06). Consequence seen in E2: a fixed query reaches existing installs only "on the next config save" — [apps#2442](https://github.com/saleor/apps/pull/2442) `[API]` `[changelog]`
- **`requiredSaleorVersion` history, AvaTax:** 3.9 (taxes app) -> 3.19 with the discount-type release (2024-09) -> drop 3.19 (v1.21.4, changelog entry 58fac0d5; PR not identified) -> 3.21 (2026-07, [apps#2342](https://github.com/saleor/apps/pull/2342), **POST-JUNE-2026**) -> `>=3.22 <4` (2026-09, [apps#2433](https://github.com/saleor/apps/pull/2433), **POST-JUNE-2026**) `[git]` `[changelog]`
- **`requiredSaleorVersion` history, SMTP:** `>=3.10` (2023-03) -> 3.20 (v1.4.0, [apps#2110](https://github.com/saleor/apps/pull/2110), 2025-10) -> 3.21 -> `>=3.22` (2026-07) -> `>=3.22 <3.24` (2026-09-15, [apps#2441](https://github.com/saleor/apps/pull/2441), **POST-JUNE-2026**): first use of an upper bound, because "Saleor 3.24 is not supported by this app" `[API]` `[git]`
- **Version check moved from app to core.** App removed its own version check on `/register` because "Saleor checks if app can be installed for given env on manifest fetching" — [apps#1592](https://github.com/saleor/apps/pull/1592), 2024-09 `[git]` `[changelog]`. The check is install-time only; it does not protect against a later core upgrade or against a fragment that is wrong for an allowed version (E2).
- **Feature flags by core version inside the app.** Emails app gated `giftCardSentEvent` (>=3.13) and `orderRefundedEvent` (>=3.14) at runtime; flags, tooltip and `WrongSaleorVersionError` deleted in [apps#2442](https://github.com/saleor/apps/pull/2442) once the floor passed them `[API]`
- **Two-step tax flow migration with automatic cloud migration** — [apps#826](https://github.com/saleor/apps/pull/826) then [apps#916](https://github.com/saleor/apps/pull/916); metadata key rename `externalId` -> `avataxId` in the same step means orders created before the switch have no `avataxId`, the case later handled in [apps#1293](https://github.com/saleor/apps/pull/1293) `[API]` `[git]`
- **Core data migrations tied to the tax-app feature:** `App.identifier` made non-blank with a backward-compatibility path ("technically possible on database level that app.identifier will be blank string") — [saleor#15292](https://github.com/saleor/saleor/pull/15292) `[git]`; `tax_class` migration fixes — [saleor#11838](https://github.com/saleor/saleor/pull/11838), [saleor#13465](https://github.com/saleor/saleor/pull/13465) `[git]`
- **Core deprecation windows relevant to the apps:** `NOTIFY_USER` deprecated 3.16 (2023-09), still emitted and still consumed in 2026 (E1); two-phase `PromotionCreateInput.type` (optional in 3.19, required in 3.20) — [3.19/3.20 changelog](https://github.com/saleor/saleor/blob/3.20.0/CHANGELOG.md) `[changelog]`; 3.22: "Webhooks are no longer triggered for deactivated Apps", changelog entry added after the fact — [saleor#18198](https://github.com/saleor/saleor/pull/18198) `[git]`
- **Zero-downtime note in the deprecation guide:** upgrade to at least 3.16.2 first with the Celery worker on, so data migrations run asynchronously — [NOTIFY_USER deprecation guide](https://docs.saleor.io/upgrade-guides/notify-user-deprecation) `[web]`
- **POST-JUNE-2026** 3.24 removes event types with a migration that deletes existing subscriptions: "a webhook left with no other events will stop being triggered" (gift card and voucher export events) — [core CHANGELOG on main](https://github.com/saleor/saleor/blob/main/CHANGELOG.md) `[changelog]`
- **POST-JUNE-2026** 3.24: apps holding `MANAGE_APPS` are rejected at install; "ensure that all installed apps do not have this permission" before upgrading — same changelog `[changelog]`

### Inferences

- Three different rollout mechanisms exist for the same problem (deploy-time migration script in AvaTax, one-off script in SMTP, lazy re-registration on config save in SMTP). The last one leaves broken installs in place until a human acts.
- An upper version bound on an app plus a core upgrade is an ordering constraint on the merchant: on 3.24 the SMTP app is unsupported and the Sendgrid plugin is gone, so the replacement app must be installed and configured before the core upgrade or customer emails stop.

### Gaps

- Could not confirm from public sources whether `requiredSaleorVersion` is re-checked when core is upgraded under an installed app.
- The AvaTax migration script's behaviour on a Saleor instance that rejects the new query (older minor) was not traced in code.

---

## 6. Items dated after June 2026 (flagged separately)

### Takeaway

Everything below comes from the public repositories' history between July and November 2026 and lies beyond the usual reference horizon; treat as real but less corroborated (no third-party discussion found). From 2026-09-17 the public saleor/apps repository receives batched "Sync from internal repository" commits whose inner PR numbers do not resolve on github.com/saleor/apps, so those are linked by commit.

### Cited Findings

- 2026-06-15: AvaTax null tax strategy fix — [apps#2373](https://github.com/saleor/apps/pull/2373) (on the boundary) `[API]`
- 2026-06-16: core plugin "double check before giving up posting to Avatax" — [saleor#19320](https://github.com/saleor/saleor/pull/19320) `[git]`
- 2026-06-29: gift card full code in template — [apps#2383](https://github.com/saleor/apps/pull/2383) `[git]`
- 2026-07-07 and 2026-09-03: drop Saleor 3.20, then 3.21 — [apps#2342](https://github.com/saleor/apps/pull/2342), [apps#2433](https://github.com/saleor/apps/pull/2433) `[git]`
- 2026-07-16: ORDER_CREATED payment methods — [apps#2398](https://github.com/saleor/apps/pull/2398); 2026-09-16 registration failure on 3.22 fixed — [apps#2442](https://github.com/saleor/apps/pull/2442) `[API]`
- 2026-07-27: AvaTax product tax-code widget — [apps#2405](https://github.com/saleor/apps/pull/2405) `[git]`
- 2026-08-04: core removes deprecated `shopFetchTaxRates` — [saleor#19581](https://github.com/saleor/saleor/pull/19581) `[git]`
- 2026-09-01: core removes Sendgrid plugin — [saleor#19725](https://github.com/saleor/saleor/pull/19725) `[git]`
- 2026-09-01: apps identify themselves by User-Agent on GraphQL calls — [apps#2428](https://github.com/saleor/apps/pull/2428) `[git]`
- 2026-09-15: SMTP capped at `<3.24` — [apps#2441](https://github.com/saleor/apps/pull/2441) `[API]`
- 2026-09-16: lint warning for deprecated GraphQL fields across apps; `OrderDiscount.amount` -> `total` in AvaTax e2e — [apps#2443](https://github.com/saleor/apps/pull/2443) `[git]`
- 2026-09-17/30: untaxed-order race fix with new columns — [saleor#19801](https://github.com/saleor/saleor/pull/19801), [saleor#19806](https://github.com/saleor/saleor/pull/19806) `[API]`
- 2026-09-30: `App.deprecationReason`, `appSelfUpdate` — [saleor#19814](https://github.com/saleor/saleor/pull/19814) `[git]`
- 2026-09-30: AvaTax client-log writes deferred until after the response ("Vercel could stop the function before the log was saved") — commit [967a0d6](https://github.com/saleor/apps/commit/967a0d64) `[git]` `[changelog]`
- 2026-10-07: SMTP app deprecated in favour of Customer Emails — commit [4400af6](https://github.com/saleor/apps/commit/4400af60) `[git]` `[changelog]`
- 2026-10-13: SMTP returns 503 when Saleor calls fail; 400 when Saleor rejects the token — commit [205859e](https://github.com/saleor/apps/commit/205859ef) `[git]` `[changelog]`
- 2026-10-15: SMTP no longer errors when recipient is missing (202 per changelog, 400 per commit title) — commit [9934357](https://github.com/saleor/apps/commit/99343578) `[git]` `[changelog]`
- 2026-10-16: per-webhook `payloadGeneration` — [saleor#19916](https://github.com/saleor/saleor/pull/19916) `[git]`
- 2026-10-28: AvaTax handles unknown street and unknown `GetTaxError` sub-codes; unmapped provider errors now raise an error report — commit [f001ac7](https://github.com/saleor/apps/commit/f001ac7e) `[git]` `[changelog]`
- Unreleased 3.24 changelog entries cited in sections 2 and 5 — [core CHANGELOG on main](https://github.com/saleor/saleor/blob/main/CHANGELOG.md) `[changelog]`

### Inferences

- The post-June material repeats earlier patterns (status-code reclassification, version-bounded fragments, silent 200s) rather than introducing new kinds of dependency; the one new mechanism is app self-deprecation.

### Gaps

- None of the post-June items could be cross-checked against docs.saleor.io upgrade guides (the 3.23 guide URL tried returned 404; 3.24 is unreleased).
- Changeset hashes in the "Sync from internal repository" commits could not be mapped to public PR pages.
