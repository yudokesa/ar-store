# 3D Agentic Store — Shopify + Slant 3D Fulfillment Pipeline

Automated 3D-printing fulfillment. Products are published to Shopify with the
physical attributes Slant 3D requires, orders are handed off through Make.com,
and each order cites the source `.stl` via a `custom.stl_url` metafield.

## Structure

```
3d-agentic-store/
├── assets/                     # Active .stl models (one folder per product)
│   ├── angel-christmas_tree_decor/angel-christmas_tree_decor.stl
│   ├── bearish/bearish.stl
│   └── bullish/bullish.stl
├── legacy/                     # Archived AR pipeline (not part of this pipeline)
├── shopify_client.py           # Reusable Admin API client (auth + GraphQL)
├── publish_catalog.py          # Publishes the 3 assets/ products to Shopify
├── set_inventory_and_publish.py # Sets inventory, activates, publishes to channels
├── enrich_catalog.py           # Taxonomy, SEO, COGS and customs data
├── apply_store_fixes.py        # Metafield definition + channel auto-publish
├── fix_shipping_us_only.py     # US-only shipping zone in USD
├── requirements.txt
├── AUDIT_REPORT.md             # Live-verified store state
└── ROADMAP.md                  # Gap analysis and phased plan
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the repo root (never committed):

```
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_CLIENT_ID=...
SHOPIFY_CLIENT_SECRET=...
```

## Usage

All scripts are dry-run by default; add `--execute` to apply changes. Every
script resolves IDs live from Shopify — no GIDs are hardcoded.

```bash
python publish_catalog.py            # create/update products
python set_inventory_and_publish.py  # inventory + DRAFT -> ACTIVE + channels
python enrich_catalog.py             # taxonomy, SEO, COGS, customs
python apply_store_fixes.py          # metafield definition + autoPublish
```

## Fulfillment requirements

Every 3D-printed product must have `requiresShipping` enabled, a non-zero weight
(0.1 kg), inventory tracking on, and a `custom.stl_url` metafield pointing at a
publicly reachable HTTPS link to the model file — otherwise orders will not
trigger automated fulfillment.
