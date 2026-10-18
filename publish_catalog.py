"""Publish the active 3D-print catalog to Shopify.

Maps each product in assets/ to a live Shopify product wired for Slant 3D
fulfillment: physical shipping enabled, a non-zero weight, inventory tracking,
and a `custom.stl_url` metafield pointing at the model's public GitHub Raw URL.

Idempotent: an existing product with the same handle is updated rather than
duplicated. Dry run by default; pass --execute to apply changes.
"""

import argparse

from shopify_client import ShopifyClient, ShopifyError, check_user_errors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GITHUB_OWNER = "yudokesa"
GITHUB_REPO = "ar-store"
GITHUB_BRANCH = "main"

PRODUCT_TYPE = "3D Printed Model"
VENDOR = "Slant 3D"
STATUS = "DRAFT"           # set to "ACTIVE" to publish to sales channels
WEIGHT_KG = 0.1            # non-zero weight so shipping zones evaluate
WEIGHT_UNIT = "KILOGRAMS"

PRODUCTS = [
    {
        "handle": "angel-christmas-tree-decor",
        "title": "Angel Christmas Tree Decoration",
        "price": "19.99",
        "sku": "STL-ANGEL-XMAS-001",
        "stl_path": "assets/angel-christmas_tree_decor/angel-christmas_tree_decor.stl",
        "tags": ["3D Model", "3D Printing", "Slant3D", "STL", "christmas"],
    },
    {
        "handle": "bullish",
        "title": "Bullish 3D Printed Model",
        "price": "12.99",
        "sku": "STL-BULLISH-001",
        "stl_path": "assets/bullish/bullish.stl",
        "tags": ["3D Model", "3D Printing", "Slant3D", "STL", "stock-market"],
    },
    {
        "handle": "bearish",
        "title": "Bearish 3D Printed Model",
        "price": "9.99",
        "sku": "STL-BEARISH-001",
        "stl_path": "assets/bearish/bearish.stl",
        "tags": ["3D Model", "3D Printing", "Slant3D", "STL", "stock-market"],
    },
]

# ---------------------------------------------------------------------------
# GraphQL operations (validated against Admin API 2026-10)
# ---------------------------------------------------------------------------
FIND_BY_HANDLE = """
query FindProductByHandle($query: String!) {
  products(first: 1, query: $query) {
    nodes {
      id
      handle
      title
      variants(first: 1) {
        nodes {
          id
        }
      }
    }
  }
}
"""

CREATE_PRODUCT = """
mutation CreateProduct($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product {
      id
      title
      handle
      variants(first: 1) {
        nodes {
          id
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_PRODUCT = """
mutation UpdateProduct($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      id
      title
      handle
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_VARIANT = """
mutation UpdateVariant($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      price
      sku
      inventoryItem {
        tracked
        requiresShipping
        measurement {
          weight {
            value
            unit
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

SET_STL_METAFIELD = """
mutation SetStlMetafield($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      namespace
      key
      type
      value
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""


def raw_stl_url(stl_path):
    """Build the public GitHub Raw URL for a model in this repo."""
    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{stl_path}"
    )


def find_by_handle(client, handle):
    data = client.execute(FIND_BY_HANDLE, {"query": f"handle:{handle}"})
    nodes = data["products"]["nodes"]
    return nodes[0] if nodes else None


def describe(spec):
    return {
        "title": spec["title"],
        "handle": spec["handle"],
        "productType": PRODUCT_TYPE,
        "vendor": VENDOR,
        "tags": spec["tags"],
        "status": STATUS,
        "descriptionHtml": (
            f"<p>{spec['title']} — 3D printed to order and fulfilled via Slant 3D. "
            f"Source model attached as the custom.stl_url metafield.</p>"
        ),
    }


def create_product(client, spec):
    data = client.execute(CREATE_PRODUCT, {"product": describe(spec)})
    payload = check_user_errors(data["productCreate"], "productCreate")
    return payload["product"]


def update_product(client, product_id, spec):
    product = {"id": product_id}
    product.update(describe(spec))
    data = client.execute(UPDATE_PRODUCT, {"product": product})
    payload = check_user_errors(data["productUpdate"], "productUpdate")
    return payload["product"]


def configure_variant(client, product_id, variant_id, spec):
    variables = {
        "productId": product_id,
        "variants": [
            {
                "id": variant_id,
                "price": spec["price"],
                "inventoryItem": {
                    "sku": spec["sku"],
                    "tracked": True,
                    "requiresShipping": True,
                    "measurement": {
                        "weight": {"value": WEIGHT_KG, "unit": WEIGHT_UNIT}
                    },
                },
            }
        ],
    }
    data = client.execute(UPDATE_VARIANT, variables)
    payload = check_user_errors(data["productVariantsBulkUpdate"], "productVariantsBulkUpdate")
    return payload["productVariants"][0]


def set_stl_metafield(client, product_id, stl_url):
    variables = {
        "metafields": [
            {
                "ownerId": product_id,
                "namespace": "custom",
                "key": "stl_url",
                "type": "url",
                "value": stl_url,
            }
        ]
    }
    data = client.execute(SET_STL_METAFIELD, variables)
    payload = check_user_errors(data["metafieldsSet"], "metafieldsSet")
    return payload["metafields"][0]


def publish(client, spec):
    stl_url = raw_stl_url(spec["stl_path"])
    existing = find_by_handle(client, spec["handle"])

    if existing:
        product = update_product(client, existing["id"], spec)
        variant_id = existing["variants"]["nodes"][0]["id"]
        action = "Updated"
    else:
        product = create_product(client, spec)
        variant_id = product["variants"]["nodes"][0]["id"]
        action = "Created"

    variant = configure_variant(client, product["id"], variant_id, spec)
    metafield = set_stl_metafield(client, product["id"], stl_url)

    print(f"{action} {product['title']} ({product['id']})")
    print(f"   variant {variant['id']} | price {variant['price']} | "
          f"weight {variant['inventoryItem']['measurement']['weight']['value']} kg | "
          f"ship {variant['inventoryItem']['requiresShipping']} | "
          f"tracked {variant['inventoryItem']['tracked']}")
    print(f"   {metafield['namespace']}.{metafield['key']} = {metafield['value']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to the live store (default is a dry run).")
    args = parser.parse_args()

    if not args.execute:
        print(f"DRY RUN — {len(PRODUCTS)} products, no changes made. Plan:\n")
        for spec in PRODUCTS:
            print(f"  {spec['title']}  [{spec['handle']}]")
            print(f"    type/vendor : {PRODUCT_TYPE} / {VENDOR}")
            print(f"    price       : {spec['price']} USD   sku: {spec['sku']}")
            print(f"    weight      : {WEIGHT_KG} kg, requiresShipping=true, tracked=true")
            print(f"    tags        : {', '.join(spec['tags'])}")
            print(f"    custom.stl_url : {raw_stl_url(spec['stl_path'])}\n")
        print("Re-run with --execute to publish to the live store.")
        return

    client = ShopifyClient()
    print(f"Connected to {client.shop_domain} (API {client.api_version}).\n")
    for spec in PRODUCTS:
        publish(client, spec)
    print("\nDone. Set inventory quantity at a location before activating.")


if __name__ == "__main__":
    try:
        main()
    except ShopifyError as error:
        raise SystemExit(f"Shopify error: {error}")
