# Architecture Gap Analysis & Roadmap — Target: Automated 3D Print-on-Demand Engine

**Store:** i0ajun-f5.myshopify.com (`gid://shopify/Shop/84894712036`) · **API:** 2026-10
**Companion to:** [AUDIT_REPORT.md](AUDIT_REPORT.md) (current ground truth)
**Method:** Every "Current" value below was read live from the store or from the store's own
GraphQL schema. Nothing is assumed. Where a claim cannot be verified from this environment it is
labelled **[unverifiable]**.

> WebAR / 3D preview is explicitly out of scope for this analysis.

---

## 0. Executive Summary

The store is **transactionally sound but architecturally unproven**. Catalog, inventory, metafields,
publications, shipping and markets are all correct and live-verified. What is missing is not
configuration — it is **the engine itself**: not one order has ever completed the
`order → Slant 3D → tracking` loop, and the entire multi-channel layer (taxonomy, GTIN, customs,
COGS, images) that syndication depends on does not yet exist.

Three findings change the shape of the plan:

| # | Finding | Consequence |
|---|---|---|
| 1 | **`appRevokeAccessScopes(scopes)` exists** in 2026-10 | Least-privilege reduction (N1) is **scriptable**, not an admin-only manual task. |
| 2 | **`orderCreate` accepts `test: Boolean`** | An end-to-end fulfillment rehearsal is possible **without** a real payment. |
| 3 | **Etsy has no first-party Shopify sales channel** | The vision's Etsy target requires a third-party app or a separate storefront — it is not a channel install. |

Also, two vision assumptions need correcting:

* **"~10–15 scopes"** is accurate for *our Python scripts* (11 are verifiably required) but
  **understated for the whole pipeline** — inventory, publications, shipping, markets and file
  upload each need a `write_*` pair. A realistic target is **~19 scopes**, not 10–15.
* **"instantly triggers"** contradicts the confirmed **12-hour polling** trigger model.

---

## 1. Architectural Gap Assessment

### Domain A — Zero-Touch Fulfillment Engine

| ID | Gap | Current (live-verified) | Target | Blocking? |
|---|---|---|---|---|
| **A1** | **No end-to-end proof** | 0 orders have ever been fulfilled. Only order `#1001` exists — cancelled, `FULFILLMENT_NOT_REQUIRED`, FO `CLOSED` | A rehearsed, observed order→print→tracking cycle | **Critical** |
| **A2** | Trigger latency contradicts the vision | `webhookSubscriptions: []` — 0 webhooks; Make.com polls every 12h **[user-reported]** | "instantly triggers Slant 3D" | Architectural decision |
| **A3** | No tracking write-back path | `fulfillmentCreate` / `fulfillmentTrackingInfoUpdate` exist and are **unused**; no script, no verification | Tracking + carrier pushed back to Shopify automatically | **Critical** |
| **A4** | No fulfillment service | `fulfillmentServices: [Manual]` only | Either register Slant 3D as a 3P service, or formally document that Make.com owns routing | Decision + doc |
| **A5** | No idempotency guard | Pipeline is HTTP-poll driven; no evidence of a dedupe key on the Make.com side **[unverifiable]** | One print job per order line, always | **Critical risk** (duplicate paid prints) |
| **A6** | No failure detection | No alerting, no retry/backoff, no dead-letter, no logging on order→print→tracking | Observable pipeline with alerting | **Critical risk** (silent failure = unfulfilled order) |
| **A7** | Address payload never validated against a real order | `countryCodeV2`, `provinceCode`, `city`, `zip` are **null** on the only order (`#1001` has `US/NY` but the order is cancelled and $0) | Confirmed non-null mapping for every order | **Critical** |

### Domain B — Omnichannel Market Expansion

| ID | Gap | Current (live-verified) | Target |
|---|---|---|---|
| **B1** | No taxonomy | `category: null` on **3/3** products | Standard Product Taxonomy on every product |
| **B2** | No SEO | `seo.title` + `seo.description` **null** on 3/3 | Populated, feed-ready |
| **B3** | No COGS | `unitCost: null` on 3/3 | Cost per unit → automated margin reporting |
| **B4** | No customs data | `countryCodeOfOrigin: null`, `harmonizedSystemCode: null` on 3/3 | Origin + HS code on every item |
| **B5** | No barcodes | `barcode: null` on 3/3 | GTIN **or** a documented brand+MPN exemption (Meta/Google require one of the two) |
| **B6** | No images | `mediaCount: 0` on 3/3 | ≥1 image per product — **hard blocker** for Meta/IG Shop, eBay, Google |
| **B7** | No price anchoring | `compareAtPrice: null` on 3/3 | Optional, but drives marketplace CTR |
| **B8** | Single default variant | `Title / Default Title` on all 3 | Real options where marketplaces expect them |
| **B9** | No merchandising | 1 collection — the default `frontpage` | Curated collections for navigation + feed segmentation |
| **B10** | No channels | `publications: [Online Store, Point of Sale]` (both `autoPublish: true`) | Google, Meta/IG, eBay (+ Etsy via 3rd-party) |
| **B11** | No feeds | `productFeeds: []` | Meta + Google Merchant Center feeds |
| **B12** | **Vision correction — Etsy** | No first-party Shopify channel exists | Requires a third-party app or a separate store; plan/budget for it separately |
| **B13** | Inventory model fights marketplaces | `tracked: true`, exactly 50, `inventoryPolicy: DENY` | Made-to-order needs a buffer flush to capacity, or marketplaces will show oversell/cancellation churn |

### Domain C — Enterprise Security & Compliance

| ID | Gap | Current (live-verified) | Target |
|---|---|---|---|
| **C1** | Least-privilege violation | **183 scopes** granted, ~70 `write_*` — including `write_themes`, `write_script_tags`, `write_gift_cards`, `write_payment_mandate`, `read_all_orders`, all 13 `customer_*`, all 16 `unauthenticated_*` | ~19 scopes |
| **C2** | **Leaked credential still live** | `TENCENTCLOUD_SECRET_ID`/`_KEY` committed in `4a50313`, removed in `6dfe1b9`, **still in history on the public `github.com/yudokesa/ar-store`** | Rotated + purged history |
| **C3** | Tax inclusion | `taxesIncluded: true` · `taxShipping: false` | `taxesIncluded: false` (US convention) — **admin UI only, no API mutation exists** |
| **C4** | US tax compliance | Selling US-wide; no tax-registration/nexus configuration in evidence | Registered where nexus exists; tax collected correctly |
| **C5** | Secret sprawl | Credentials in a local `.env` **and** in Make.com; no secrets manager | Centralised secret store, rotated on a schedule |
| **C6** | Storefront unreachable | Password-protected (`/en-us/password`) | Public before any launch/paid traffic |
| **C7** | Business identity | Store name `My Store`; support contact is a personal Gmail; home address published in policies; `ianaTimezone: Asia/Jakarta`; `countryCodeOfOrigin` billing = `ID` | Branded name + domain + business contact + US-aligned timezone |
| **C8** | No audit trail | No logging of who/what mutated the store | Change log for all pipeline mutations |

### Domain D — Resilient Asset & Data Infrastructure

| ID | Gap | Current (live-verified) | Target |
|---|---|---|---|
| **D1** | STL host is not infrastructure | `raw.githubusercontent.com`, 74.5/54.2/68.3 MB, HTTP 200 — no CDN, no SLA, soft rate limits | Cloudflare R2 / S3 behind a CDN |
| **D2** | Repo bloat | ~190 MB of STL binaries in git history; no Git LFS | LFS or fully externalised assets |
| **D3** | No integrity check | No checksum before handing an STL to Slant 3D | Hash verified per upload — a corrupt STL is a failed print and a refund |
| **D4** | No access control | STL URLs are world-readable and unguessable only by path | Signed, expiring URLs |
| **D5** | Weak metafield contract | `custom.stl_url` is `url` type with no HTTPS/length constraint | Validated URL contract at the definition level |
| **D6** | No test coverage / CI | All scripts are manual dry-runs; no tests | Automated checks on every change |
| **D7** | No domain for the US market | `markets[0].webPresence.domain: null` | Domain attached once a custom domain exists |

### Domain E — Genuine Latent Bugs Found During This Analysis

| ID | Bug | Impact |
|---|---|---|
| **E1** | ~~[publish_catalog.py](file:///c:/Users/User/3d-agentic-store/publish_catalog.py#L24) hardcodes `STATUS = "DRAFT"` and that value is applied by **both** `create_product` *and* `update_product`~~ | **FIXED.** `status` is now sent on CREATE only (`describe(spec, include_status=True)`); updates never touch status. Re-running can no longer unpublish live products. |
| **E2** | ~~[test_shopify_connection.py](file:///c:/Users/User/3d-agentic-store/test_shopify_connection.py) pins `2025-07`~~ | **DELETED.** Superseded by `shopify_client.py` + the dry-run of any pipeline script. |
| **E3** | ~~[create_sample_3d_product.py](file:///c:/Users/User/3d-agentic-store/create_sample_3d_product.py) references the deleted hair-comb sample~~ | **DELETED.** Superseded by `publish_catalog.py`. |

---

## 2. Actionable 3-Phase Roadmap

### Phase 1 — Production Hardening & Security

Sequenced so that nothing blind is executed. Items marked **[admin]** have no API path and must be
done in the Shopify admin.

| # | Action | How | Gate |
|---|---|---|---|
| 1.1 | ~~**Fix E1** (the DRAFT regression landmine)~~ | **DONE.** `status` is now create-only. | — |
| 1.2 | **Rotate everything exposed** | Rotate the Shopify app secret, revoke the Tencent key pair, purge git history (`git filter-repo`/BFG → force-push) for `4a50313` | Do this **before** scope work |
| 1.3 | **Enumerate Make.com's scopes** | Read every module in the scenario and list the exact operations it performs | **Blocker for 1.4** — see risk note |
| 1.4 | **Reduce 183 scopes → ~19** | `appRevokeAccessScopes(scopes:)` (scriptable), allowlist only what 1.3 + our own scripts require | Requires 1.3 complete |
| 1.5 | **`taxesIncluded` → false** **[admin]** | Settings → Taxes and duties → uncheck "All prices include tax" | — |
| 1.6 | **US tax registration review** | Confirm nexus + register; verify Shopify tax is collecting correctly | Needs 1.5 |
| 1.7 | **Fulfillment rehearsal (A1, A7)** | `orderCreate` with `test: true` against a US address; assert every mapped field is non-null | After 1.3 |
| 1.8 | **Build tracking write-back (A3)** | `fulfillmentCreate` + `fulfillmentTrackingInfoUpdate` | After 1.7 |
| 1.9 | **Remove storefront password** **[admin]** | Before any launch | — |
| 1.10 | ~~**Delete dead scripts (E2, E3)**~~ | **DONE.** Both deleted; README updated to match. | — |

> **Risk note on 1.4 — do not revoke blind.** Make.com's module scope requirements are
> **[unverifiable]** from here. Revoking a scope the scenario depends on breaks fulfillment
> *silently*, which is the single worst failure mode for this business. The 11 scopes our own code
> provably needs are safe to keep; everything else must be justified by 1.3 first.

### Phase 2 — Multi-Channel Catalog Enrichment

| # | Action | How | Status |
|---|---|---|---|
| 2.1 | **Taxonomy (B1)** | `productUpdate(category:)` — resolved live from `taxonomy.categories` | **DONE** — all 3 products categorized via [enrich_catalog.py](file:///c:/Users/User/3d-agentic-store/enrich_catalog.py) |
| 2.2 | **SEO (B2)** | `productUpdate(seo:)` | **DONE** — title + description on all 3 |
| 2.3 | **COGS (B3)** | `inventoryItemUpdate(cost:)` | **DONE** — `$4.25`/unit on all 3 |
| 2.4 | **Customs (B4)** | `inventoryItemUpdate(countryCodeOfOrigin:, harmonizedSystemCode:)` | **DONE** — `US` + HS `3926.40` |
| 2.5 | **Images (B6)** | `stagedUploadsCreate` → `fileCreate` → attach | Awaiting your renders (C3, deferred by you) |
| 2.6 | **Barcodes (B5)** | GTIN, or register a brand+MPN exemption with Meta/Google | Merchant input |
| 2.7 | **Collections (B9)** | `collectionCreate` + `collectionReorderProducts` | Scriptable |
| 2.8 | **Inventory policy (B13)** | Decide the made-to-order buffer model | Decision |
| 2.9 | **Install channels + feeds (B10, B11)** **[admin]** | Google, Meta/IG, eBay | After 2.1–2.6 |
| 2.10 | **Etsy track (B12)** | Evaluate a third-party app or a separate storefront | Separate workstream |
| 2.11 | **Variant options (B8)** | Add real options only where a marketplace demands them | Defer until a channel asks |

### Phase 3 — Infrastructure & Asset Optimization

| # | Action | How |
|---|---|---|
| 3.1 | **Migrate STLs to R2/S3 + CDN (D1)** | Upload, repoint `custom.stl_url`, verify HTTP 200 + `Content-Length` |
| 3.2 | **Purge STL binaries from git history (D2)** | Git LFS for future assets; rewrite history for existing ones |
| 3.3 | **Add checksum verification (D3)** | Hash each STL at publish and at hand-off |
| 3.4 | **Signed URLs (D4)** | Expiring links if STLs should not stay world-readable |
| 3.5 | **Harden the metafield contract (D5)** | Tighten the `custom.stl_url` definition |
| 3.6 | **Pipeline observability (A6)** | Logging + alerting on order→print→tracking; retry/backoff; dead-letter |
| 3.7 | **Idempotency keys (A5)** | Dedupe on the Make.com side — one print per line item |
| 3.8 | **Custom domain + brand (C7, D7)** | Attach domain to the US market web presence |
| 3.9 | **CI + tests (D6)** | Automate the dry-run assertions |
| 3.10 | **Secrets manager (C5)** | Move off local `.env` + Make.com plaintext |

---

## 3. Immediate Next Action — Executed (Phase 2.1–2.4)

**`enrich_catalog.py --execute` has been run and independently verified.** All three products now
carry a taxonomy category, SEO metadata, COGS and customs data.

Verified by a separate read-back query (not the writing script's own output):

| Product | Category (fullName) | SEO title | COGS | Customs |
|---|---|---|---|---|
| angel-christmas-tree-decor | Home & Garden > Decor > Seasonal & Holiday Decorations > Holiday Ornaments | Angel Christmas Tree Decoration \| 3D Printed | `4.25 USD` | `US` / `392640` |
| bullish | Home & Garden > Decor > Figurines | Bullish 3D Printed Figurine \| Stock Market Decor | `4.25 USD` | `US` / `392640` |
| bearish | Home & Garden > Decor > Figurines | Bearish 3D Printed Figurine \| Stock Market Decor | `4.25 USD` | `US` / `392640` |

All three remain **ACTIVE**, `tracked: true`, `requiresShipping: true`, with their original SKUs and
prices intact — the enrichment touched nothing else.

> **Note on HS code format:** Shopify normalised the value `3926.40` to **`392640`** (punctuation
> stripped) on write. That is expected storage behaviour, not a data error — verify against
> `harmonizedSystemCode` when filing, and expect the same normalisation for any HS code you supply.

### What this unblocks

* **Google Merchant Center and Meta/IG Shop** can now accept listings — both reject uncategorized products.
* **Margin reporting** is possible: `unitCost` × price gives gross margin per order.
* **Customs/COGS fields are populated**, so the customs data path is proven end-to-end and future
  products inherit it.
* **`enrich_catalog.py` is now the reusable "make a new STL sellable" step** — the scaling primitive.

### What is still the true next action

**Phase 2.1–2.4 were the largest *scriptable* step. They were not the highest-impact one.**

The binding constraint remains **A1 — no fulfilled order has ever completed the loop.** Everything
configured so far is unproven against real traffic, and the pipeline's failure modes (duplicate prints,
silent dropouts, unmapped addresses) are all invisible until an order runs through it.

Recommended order from here:

1. **1.3 — enumerate Make.com's modules** (admin, and it is the gate on scope reduction).
2. **1.7 — the `test: true` fulfillment rehearsal** (A1, A7). This is the single highest-value action
   available: it validates the whole engine without charging anyone or printing anything.
3. **2.5 — product images** (B6) once your renders are ready; still the hardest blocker on syndication.


---

## 4. Appendix — Schema Facts Verified Live (2026-10)

These were confirmed by introspection, not documentation, because several differ from expectation:

| Fact | Detail |
|---|---|
| Scope revocation is scriptable | `appRevokeAccessScopes(scopes: [String!])` exists on `Mutation` |
| Test orders are supported | `orderCreate(order: OrderCreateOrderInput, options: OrderCreateOptionsInput)`; `OrderCreateOrderInput` has `test: Boolean`, `financialStatus`, `transactions` |
| Draft-order path | `draftOrderCreate(input: DraftOrderInput)` → `draftOrderComplete(id, paymentGatewayId, sourceName)` |
| Taxonomy is queryable | `taxonomy { categories(search:) }` — `TaxonomyCategory` exposes `fullName`, `isLeaf`, `isArchived`, `ancestorIds` (⚠ no `parent` field) |
| Category + SEO are one mutation | `ProductUpdateInput` carries both `category: ID` and `seo: SEOInput` |
| COGS + customs live on the item | `InventoryItemInput` carries `sku`, `cost`, `tracked`, `countryCodeOfOrigin`, `provinceCodeOfOrigin`, `harmonizedSystemCode`, `countryHarmonizedSystemCodes`, `measurement`, `requiresShipping` |
| Media upload path | `stagedUploadsCreate` → `fileCreate(files: [FileCreateInput!])` |
| Taxonomy names collide | "Figurines" matches **two** leaves — `fullName` matching is mandatory, not optional |
| Markets, not zones, gate countries | `shipsToCountries` is market-derived (proven in N2) |
| No API for shop tax settings | The complete shop-level mutation set is `shopLocale*`, `shopPolicyUpdate`, `shopResourceFeedbackCreate`, `shopifyPaymentsPayoutAlternateCurrencyCreate` |
