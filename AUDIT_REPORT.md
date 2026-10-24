# Shopify Store Audit & Gap Report — Final Operational State

**Store:** i0ajun-f5.myshopify.com (`gid://shopify/Shop/84894712036`)
**App:** `Make Slant3D Integration` (client ID redacted — see the repo's public-visibility note in §3, N1)
**Method:** Live Admin GraphQL introspection (API 2026-10) + HTTP verification. Every value below was
read from the store. No assumptions.

> **Scope caveat:** the Make.com scenario itself is **not verifiable from this environment** — there is
> no Make.com tooling available here. Everything reported about Shopify is live-verified; the Make.com
> pipeline is recorded as *user-reported* and marked as such. See §6.

---

## 0. Ground Truth Snapshot

| Setting | Live value |
|---|---|
| Store name | `My Store` (default, never configured) |
| Primary / only domain | `i0ajun-f5.myshopify.com` (no custom domain) |
| Plan | Basic |
| Currency (shop base) | **USD** |
| Timezone | Asia/Jakarta |
| Weight unit / system | GRAMS / METRIC_SYSTEM |
| `taxesIncluded` | **true** ← *still open* |
| `taxShipping` | false |
| `shipsToCountries` | **`["US"]`** — US-only (was `["ID","US"]`) |
| Markets | **United States only** (`ACTIVE`, base `USD`). Indonesia market **deleted** |
| Locations | 1 — `Shop location` (`gid://shopify/Location/94780489956`), active, fulfillsOnlineOrders |
| Delivery profile | 1 default ("General profile"), 3 variants, **1 zone / 1 country — "United States", flat `$4.99 USD`** |
| Publications | Online Store + Point of Sale, **both `autoPublish: true`** |
| Products | 3 — all **ACTIVE**, published, 50 units each |
| Catalog enrichment | all 3 categorized + SEO + `unitCost` `4.25 USD` + customs `US` / `392640` |
| Collections | 1 (`frontpage` default only) |
| Orders | 1 (`#1001`) — **cancelled** |
| Customers | 1 |
| Webhooks | 0 (by design — polling model) |
| Product feeds | none |
| Fulfillment services | `Manual` only |
| Metafield definitions | **1** — `custom.stl_url`, `ALL_VALID`, `pinnedPosition: 1` |
| Granted app scopes | **183** (70 of them `write_*`) ← *see N1* |
| Legal policies | 5 present with real content |
| Locales | `en` — primary, published |
| Storefront | **password-protected** — redirects to `/en-us/password` ("opening soon") |

---

## 1. Previously Reported Blockers — Now Resolved

| Ref | Was | Now (verified live) |
|---|---|---|
| **C6** | Shipping unreadable | **Resolved.** Readable. 1 default profile, **1 zone — "United States"**, 1 active flat rate **`$4.99 USD`**. Checkout will not fail for lack of a rate. |
| **C7** | 0 metafield definitions | **Resolved.** `custom.stl_url` created — `type: url`, `ownerType: PRODUCT`, `pinnedPosition: 1`, `validationStatus: ALL_VALID`. All 3 products now resolve `definition = STL File URL` (previously `null`). |
| **C8** | `autoPublish: false` | **Resolved.** Both channels now `autoPublish: true`. New products reach channels without the separate activation pass. |
| **C25** | Policies unverifiable | **Resolved.** All 5 exist with real bodies: Contact, Privacy policy, Refund policy, Shipping, Terms of service. |
| **C26** | Markets unverifiable | **Resolved.** United States market is `ACTIVE` with base currency **USD** — matches the Slant 3D requirement. |
| **C2** | `#1001` PAID + UNFULFILLED | **Resolved.** Cancelled — `cancelledAt` set, fulfillment order `CLOSED`, status `FULFILLMENT_NOT_REQUIRED`. Out of the fulfillment queue. |
| **C27** | 15 scopes, reads denied | **Changed** — expanded to 183 scopes. All previously denied reads now work, but see **N1**. |
| **N2** | Rates in IDR; 28-country zone incl. US; ID sellable | **Resolved.** Storefront restricted to the US: single "United States" zone at **`$4.99 USD`**, ID zone deleted, ID market deleted, `shipsToCountries` = `['US']`. |
| **N3** | — | **Withdrawn, see §3.** The "no webhooks = broken" framing was wrong once polling was confirmed. |
| **C22** (partly) | Assumed weight drives shipping rates | **Corrected — my earlier reasoning was wrong.** Rates are flat `DeliveryRateDefinition` prices, not weight-based. Weight does **not** currently drive shipping cost. See N2. |

---

## 2. REMAINING CRITICAL BLOCKERS

### C3 — No product images on any product *(unchanged)*
All three: `mediaCount: {count: 0}`. Blank product pages; **Meta/Instagram Shop and eBay reject
listings without images**. Blocks all syndication and damages conversion. Highest-impact open item.

### C4 — `taxesIncluded = true` on a USD / US-fulfillment store *(unchanged)*
Confirmed still `true`. **No Admin API mutation exists for this** — the complete set of shop-level
mutations is `shopLocale*`, `shopPolicyUpdate`, `shopResourceFeedbackCreate`, and
`shopifyPaymentsPayoutAlternateCurrencyCreate`. Admin UI only:
*Settings → Taxes and duties → uncheck "All prices include tax"*.

### C5 — No Slant 3D fulfillment service; only `Manual` *(unchanged)*
Only `gid://shopify/FulfillmentService/manual`. Fulfillment orders cannot be routed to Slant 3D via
Shopify routing. **Presumed intentional** (the Make.com HTTP path does the routing) — but this is a
design decision that should be documented rather than inherited.

---

## 3. NEW FINDINGS FROM RE-INTROSPECTION

### N1 — 183 granted scopes is a serious least-privilege violation ⚠️
The app went from **15 → 183** scopes, **70 of them `write_*`**. This is effectively unrestricted access,
including scopes that are far outside a print-fulfillment pipeline's needs:

| High-risk scope | Why it matters |
|---|---|
| `write_themes`, `write_theme_code` | Can modify storefront/checkout code |
| `write_script_tags` | Can inject arbitrary scripts into checkout |
| `write_payment_mandate`, `write_payment_customizations` | Payment handling |
| `read_shopify_payments_accounts`, `write_shopify_payments_disputes` | Payment/account data |
| `write_gift_cards`, `write_gift_card_transactions` | Can issue store credit |
| `write_customers`, `write_customer_data_erasure`, `write_privacy_settings` | Customer PII lifecycle |
| `write_products`, `write_discounts`, `write_price_rules` | Catalog/pricing integrity |
| `read_all_orders` | Full order history |

**Why this is elevated, not theoretical:** these credentials live in a local `.env` and inside Make.com,
and this repository has a **demonstrated history of secret leakage** — a `TENCENTCLOUD_SECRET_ID`/`_KEY`
was committed in `4a50313`, removed in `6dfe1b9`, and remains in history on the public
`github.com/yudokesa/ar-store`.

A leaked 183-scope credential is a **near-total store takeover**, including paths to checkout
script injection and card-skimming. Recommend reducing to the minimal set the pipeline actually needs
(~10–15 scopes: products, inventory, orders, fulfillments, locations, publications) and treating the
current credential as compromised-by-policy until rotated.

### N2 — Shipping rates were denominated in IDR while the catalog is USD — **RESOLVED**
**Was:** two flat IDR zones —

| Zone | Countries | Method | Rate |
|---|---|---|---|
| Domestic | ID | "Standar" | **48,229 IDR** |
| International | 28 (incl. **US**) | "International" | **340,000 IDR** |

Two problems: (a) the catalog is priced in **USD** but shipping was set in **IDR** — an inconsistency a
US buyer sees as a converted, unpredictable rate; (b) a flat **340,000 IDR** international charge
against products priced **$9.99–$19.99** meant shipping plausibly cost more than the item. Because the
rates are *flat*, the per-product `0.1 kg` weight has no effect on the calculated cost.

**Fix applied (verified live).** Per the merchant's directive to sell strictly within the US:

| Zone | Countries | Method | Rate |
|---|---|---|---|
| United States | US | "Standard US Shipping" | **$4.99 USD** |

* The "Domestic" (ID) zone was **deleted**; the international 28-country zone was replaced with a
  single-country **US** zone at a flat **`$4.99 USD`** (matching the USD catalog).
* The **Indonesia market was deleted**, so the only market is **United States** (`ACTIVE`, base USD).
* `shipsToCountries` and `countriesInShippingZones` now both return **`['US']`**.
* **Finding:** `shipsToCountries` / `countriesInShippingZones` are **market-derived, not zone-derived** —
  deleting the ID *zone* alone did not change `shipsToCountries`; deleting the ID *market* cleared it
  to `['US']` instantly. Any future "which countries can buy?" question must be answered at the market
  layer, not the shipping-profile layer.
* Still flat — weight does not drive cost (see C22). A real carrier/weight-based model remains a
  Phase 3 consideration if shipping cost needs to track model size.

### N3 — 12-hour polling means up to 12 hours of fulfilment latency
`webhookSubscriptions` is empty and — consistent with a polling design — `read_webhooks`/`write_webhooks`
are **not** granted (`read_webhooks`/`write_webhooks` are also absent from Shopify's official scope
reference, confirming they are not valid current scopes). So:

* There is **no** real-time trigger; an order can sit up to 12 hours before reaching Slant 3D.
* The earlier "no webhooks = broken automation" framing is **withdrawn** — polling is a valid trigger
  model. But confirm 12h latency is an accepted customer-facing lead time, since the storefront makes
  no lead-time promise today.

### N4 — Indonesia market had `currencySettings: null` — **MOOT (market deleted)**
The ID market returned no currency configuration, so Indonesian buyers likely presented in the shop's
base currency (**USD**). The Indonesia market has since been **deleted** as part of the US-only
restriction (N2), so this no longer applies.

### N5 — US market web presence has no domain
`MarketWebPresence` exists for the United States but `domain: null`. With only the `myshopify.com`
subdomain this may be benign, but it is unresolved once a custom domain is added.

### N6 — Store identity and support contact unconfigured
Store name is still `My Store`; support contact is a **personal Gmail** (`yudokesa@gmail.com`) and the
published policy carries the merchant's home/office street address. Fine functionally; weak on brand
trust and separation of personal/business identity.

### N7 — `coversAllItems: false` on the delivery profile
Observed while the profile holds all 3 variants (3 variants exist in total). Coverage appears complete,
but the flag warrants a direct check that no future variant falls outside any shipping profile.

### N8 — No `read_webhooks`/`write_webhooks` (and none exist)
Recorded so the roadmap does not chase a scope that cannot be granted. If real-time triggers are ever
wanted, they require a different mechanism than these scopes.

---

## 4. MULTI-CHANNEL & EXPANSION GAPS

| Ref | Gap |
|---|---|
| **C9** | Only 2 channels — Online Store, Point of Sale. No eBay, Meta/Facebook & Instagram, TikTok, Google, Amazon or Walmart. |
| **C10** | `productFeeds: []` — no Meta or Google Merchant feed exists. |
| **C11** | ~~`category: null` on all products~~ **Resolved.** All 3 products categorized (`Holiday Ornaments`, `Figurines`) via `enrich_catalog.py`. |
| **C12** | ~~`seo.title` / `seo.description` both `null`~~ **Resolved.** Title + description set on all 3 products. |
| **C13** | `barcode: null` on all variants — no GTIN/UPC/EAN or brand+MPN exemption. |
| **C14** | Only the default `frontpage` collection — no curated collections to drive navigation or syndication. |
| **C15** | Single default variant only (`Title` / `Default Title`) — no size/material options. |
| **C16** | ~~`countryCodeOfOrigin: null`, `harmonizedSystemCode: null`~~ **Resolved.** All 3 items now `US` / `392640`. |
| **C17** | ~~`unitCost: null`~~ **Partly resolved.** `unitCost = 4.25 USD` on all 3; `compareAtPrice` still `null` — no price anchoring for marketplace CTR. |

---

## 5. OPTIMIZATIONS (open)

| Ref | Item |
|---|---|
| **C18** | Store name `My Store`; no custom domain. |
| **C19** | `Asia/Jakarta` timezone vs US-based fulfilment — order timestamps and cut-offs misleading for US buyers. |
| **C20** | ~~`shipsToCountries` includes `ID`~~ **Resolved (N2)** — `shipsToCountries` is now `['US']`; the ID market/zone were removed, so only US destinations are selectable. |
| **C21** | Shop weight unit GRAMS vs variants written in KILOGRAMS (both = 100 g, but inconsistent in the admin UI). |
| **C22** | All three products share `0.1 kg` despite models of 74.5 / 54.2 / 68.3 MB. *(No longer a shipping-rate bug — rates are flat, see N2 — but still wrong for labels, future carrier rates, and Slant 3D.)* |
| **C23** | STLs served from `raw.githubusercontent.com` — re-verified **HTTP 200**: 74.5 MB / 54.2 MB / 68.3 MB. Not a CDN, no SLA, soft rate limits; repo carries ~190 MB of STL history. Migrate to object storage/CDN + Git LFS. |
| **C24** | `tracked: true`, exactly 50 available, `inventoryPolicy: DENY`. For made-to-order printing a fixed buffer risks false sell-outs. Confirm this is deliberate. |

---

## 6. Make.com → Slant 3D Integration Status

**User-reported as fully configured, dynamically mapped, and active on a 12-hour polling schedule.**
Recorded as reported.

**Independently verified on the Shopify side:**
* `custom.stl_url` exists as a pinned, validated definition, populated on all 3 products (§1).
* All 3 products ACTIVE, published, `requiresShipping: true`, weight set, SKU set, 50 units at a real
  active location.
* All 3 STL URLs return **HTTP 200** and are publicly fetchable by Slant 3D.
* Both sales channels have `autoPublish: true`.
* No stale test order remains in the fulfillment queue.

**Not verifiable from this environment:** the Make.com scenario's module mappings, the Slant 3D
API/Stripe credentials and billing state, and whether the 12-hour poll is currently running. Those
require inspection inside Make.com.

---

## 7. REMAINING ROADMAP

### Phase 1 — Correctness (do first)
1. **Add product images** (C3) — `productCreateMedia`. Blocks Meta/eBay; highest impact.
2. **`taxesIncluded` → false** (C4) — admin UI only, no API path.
3. **Reduce app scopes from 183 to the minimal set** (N1) and rotate the credential.
4. ~~**Re-price shipping** (N2)~~ — **DONE.** Flat IDR zones replaced by a single US zone at `$4.99 USD`; ID zone and ID market removed.
5. **Confirm 12h latency is acceptable** (N3); otherwise revisit the trigger model and lead-time copy.

### Phase 2 — Multi-channel readiness
6. Taxonomy `category` (C11) · 7. SEO title/description (C12) · 8. barcodes/GTIN (C13)
9. Collections (C14) · 10. customs `countryCodeOfOrigin` + HS code (C16) · 11. `unitCost` (C17)
12. Install eBay / Meta / Google channels + create feeds (C9, C10) — admin action.

### Phase 3 — Hygiene
13. Brand name + custom domain (C18, N6) · 14. timezone alignment with US fulfilment (C19)
15. weight unit normalisation + real per-product weights (C21, C22, N7)
16. STL migration to CDN + Git LFS (C23) · 17. confirm inventory model (C24) · 18. US market domain (N5)

---

## 8. Severity Summary

**Open and operationally significant:** C3 (no images), N1 (183-scope over-grant),
C4 (tax inclusion).

**Blocking growth:** C9, C10, C13–C15, and C17 (partly — `compareAtPrice` only).

**Config debt / trust:** C18–C24, N5–N7 (N4 moot).

**Verified good:** products ACTIVE, published, `requiresShipping: true`, 0.1 kg weights, SKUs and prices
set, 50 units at a real active location, correct `custom.stl_url` on all three resolving to HTTP 200,
pinned metafield definition, `autoPublish` on both channels, complete legal policies, USD base currency
with an ACTIVE US market, working shipping rates to the US, no stale pre-production order, and full
catalog enrichment (taxonomy category, SEO, `unitCost = 4.25 USD`, customs `US` / `392640`) on all three.
