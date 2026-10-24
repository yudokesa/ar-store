"""Enrich the live catalog for multi-channel syndication.

For every configured product this script sets:
  1. the Shopify Standard Product Taxonomy `category` (resolved live by full
     ancestor path, never a hardcoded GID),
  2. `seo.title` and `seo.description`,
  3. the inventory item's customs `countryCodeOfOrigin` + `harmonizedSystemCode`
     and its COGS `cost`.

Google Merchant Center, Meta/Instagram Shop and eBay all reject listings that
lack a category, and none can report margin without a unit cost — so this is the
prerequisite step before any channel is installed.

Idempotent: re-running re-asserts the same values. Dry run by default; pass
--execute to apply changes.
"""

import argparse

from shopify_client import ShopifyClient, ShopifyError, check_user_errors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# `category_path` must match TaxonomyCategory.fullName exactly. It is matched
# against a live taxonomy search, so no taxonomy GID is stored in this repo.
#
# `unit_cost` is the Slant 3D print cost per unit; `hs_code` is the customs
# tariff code. Both are merchant-supplied — this script never invents
# financial or tariff data.
CATALOG = [
    {
        "handle": "angel-christmas-tree-decor",
        "category_path": "Home & Garden > Decor > Seasonal & Holiday Decorations > Holiday Ornaments",
        "seo_title": "Angel Christmas Tree Decoration | 3D Printed",
        "seo_description": (
            "3D-printed angel Christmas tree decoration, produced to order and "
            "fulfilled in the United States via Slant 3D."
        ),
        "origin_country": "US",
        "unit_cost": "4.25",
        "hs_code": "3926.40",
    },
    {
        "handle": "bullish",
        "category_path": "Home & Garden > Decor > Figurines",
        "seo_title": "Bullish 3D Printed Figurine | Stock Market Decor",
        "seo_description": (
            "3D-printed bull figurine for stock market fans, produced to order "
            "and fulfilled in the United States via Slant 3D."
        ),
        "origin_country": "US",
        "unit_cost": "4.25",
        "hs_code": "3926.40",
    },
    {
        "handle": "bearish",
        "category_path": "Home & Garden > Decor > Figurines",
        "seo_title": "Bearish 3D Printed Figurine | Stock Market Decor",
        "seo_description": (
            "3D-printed bear figurine for stock market fans, produced to order "
            "and fulfilled in the United States via Slant 3D."
        ),
        "origin_country": "US",
        "unit_cost": "4.25",
        "hs_code": "3926.40",
    },
]

# ---------------------------------------------------------------------------
# GraphQL operations (validated against Admin API 2026-10)
# ---------------------------------------------------------------------------
RESOLVE_CATEGORY = """
query ResolveCategory($search: String!) {
  taxonomy {
    categories(first: 20, search: $search) {
      nodes {
        id
        name
        fullName
        isLeaf
        isArchived
      }
    }
  }
}
"""

FIND_PRODUCT = """
query FindProduct($query: String!) {
  products(first: 1, query: $query) {
    nodes {
      id
      handle
      title
      category {
        id
        name
      }
      seo {
        title
        description
      }
      variants(first: 1) {
        nodes {
          id
          inventoryItem {
            id
            unitCost {
              amount
              currencyCode
            }
            countryCodeOfOrigin
            harmonizedSystemCode
          }
        }
      }
    }
  }
}
"""

UPDATE_PRODUCT = """
mutation UpdateProduct($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      id
      handle
      category {
        id
        name
      }
      seo {
        title
        description
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_INVENTORY_ITEM = """
mutation UpdateInventoryItem($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      unitCost {
        amount
        currencyCode
      }
      countryCodeOfOrigin
      harmonizedSystemCode
    }
    userErrors {
      field
      message
    }
  }
}
"""


def resolve_category(client, full_name):
    """Resolve a taxonomy `fullName` to its live leaf category GID."""
    # Search on the last path segment: the full path is not a search key.
    term = full_name.split(" > ")[-1]
    nodes = client.execute(RESOLVE_CATEGORY, {"search": term})["taxonomy"]["categories"]["nodes"]
    matches = [n for n in nodes if n["fullName"] == full_name and n["isLeaf"] and not n["isArchived"]]
    if len(matches) != 1:
        candidates = "\n    ".join(f"{n['fullName']}  ({n['id']})" for n in nodes) or "(none)"
        raise ShopifyError(
            f"Taxonomy path {full_name!r} resolved to {len(matches)} leaf categories. "
            f"Candidates returned by search {term!r}:\n    {candidates}"
        )
    return matches[0]


def find_product(client, handle):
    nodes = client.execute(FIND_PRODUCT, {"query": f"handle:{handle}"})["products"]["nodes"]
    if not nodes:
        raise ShopifyError(f"No product found for handle {handle!r}")
    return nodes[0]


def describe(spec, category):
    return {
        "seo": {"title": spec["seo_title"], "description": spec["seo_description"]},
        "category": category["id"],
    }


def enrich(client, spec):
    product = find_product(client, spec["handle"])
    category = resolve_category(client, spec["category_path"])

    print(f"\n{product['title']}  [{spec['handle']}]  {product['id']}")
    print(f"   category : {product['category'] or '(none)'}")
    print(f"           -> {category['name']}  {category['id']}")
    print(f"   seo      : {product['seo'] or '(none)'}")
    print(f"           -> {spec['seo_title']!r}")

    data = client.execute(UPDATE_PRODUCT, {"product": dict(describe(spec, category), id=product["id"])})
    payload = check_user_errors(data["productUpdate"], "productUpdate")

    item = product["variants"]["nodes"][0]["inventoryItem"]
    item_input = {"countryCodeOfOrigin": spec["origin_country"]}
    if spec["hs_code"]:
        item_input["harmonizedSystemCode"] = spec["hs_code"]
    if spec["unit_cost"]:
        item_input["cost"] = spec["unit_cost"]

    data = client.execute(UPDATE_INVENTORY_ITEM, {"id": item["id"], "input": item_input})
    payload = check_user_errors(data["inventoryItemUpdate"], "inventoryItemUpdate")
    updated = payload["inventoryItem"]

    print(f"   origin   : {item['countryCodeOfOrigin']} -> {updated['countryCodeOfOrigin']}")
    print(f"   hs code  : {item['harmonizedSystemCode']} -> {updated['harmonizedSystemCode']}")
    cost = updated["unitCost"]
    print(f"   unit cost: {item['unitCost']} -> {cost['amount'] + ' ' + cost['currencyCode'] if cost else None}")
    if not spec["hs_code"]:
        print("   ! hs_code is unset — customs data still incomplete (no customs data => no cross-border shipping)")
    if not spec["unit_cost"]:
        print("   ! unit_cost is unset — margin reporting will stay unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to the live store (default is a dry run).")
    args = parser.parse_args()

    client = ShopifyClient()

    if not args.execute:
        print(f"DRY RUN — {len(CATALOG)} products, no changes made. Plan:\n")
        for spec in CATALOG:
            category = resolve_category(client, spec["category_path"])
            product = find_product(client, spec["handle"])
            print(f"  {product['title']}  [{spec['handle']}]")
            print(f"    category  : {product['category']} -> {category['name']} ({category['id']})")
            print(f"    seo.title : {spec['seo_title']}")
            print(f"    origin    : {spec['origin_country']}")
            print(f"    hs_code   : {spec['hs_code'] or '(unset — blocked, needs customs input)'}")
            print(f"    unit_cost : {spec['unit_cost'] or '(unset — blocked, needs Slant 3D cost)'}\n")
        print("Re-run with --execute to apply.")
        return

    print(f"Connected to {client.shop_domain} (API {client.api_version}).")
    for spec in CATALOG:
        enrich(client, spec)
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except ShopifyError as error:
        raise SystemExit(f"Shopify error: {error}")
