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
├── create_sample_3d_product.py # Minimal single-product template
├── test_shopify_connection.py  # Connection smoke test
└── requirements.txt
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

Smoke-test the connection:

```bash
python test_shopify_connection.py
```

Publish the catalog (dry run by default; add `--execute` to apply):

```bash
python publish_catalog.py
python publish_catalog.py --execute
```

## Fulfillment requirements

Every 3D-printed product must have `requiresShipping` enabled, a non-zero weight
(0.1 kg), inventory tracking on, and a `custom.stl_url` metafield pointing at a
publicly reachable HTTPS link to the model file — otherwise orders will not
trigger automated fulfillment.
