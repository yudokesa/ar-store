"""Template: create a 3D-printable product wired for Slant3D fulfillment.

Shows the product architecture required so a Shopify order triggers automated
fulfillment through Make.com -> Slant 3D:

  * physical product toggle (requiresShipping) so shipping zones evaluate
  * a real, non-zero weight for shipping calculation
  * inventory tracking enabled
  * active pricing on the variant
  * the `custom.stl_url` metafield (type: url) pointing at the model file

Dry run by default; pass --execute to actually create the product.
See create_sample_3d_product.py --help for the CLI options.
"""

import argparse

from shopify_client import ShopifyClient, ShopifyError, check_user_errors

# ---------------------------------------------------------------------------
# 1. Sample product definition -- swap these values for a real model.
# ---------------------------------------------------------------------------
SAMPLE_PRODUCT = {
    "title": "Hair Comb for 3D Printing",
    "description_html": (
        "<p>A printable hair comb model. Ships as a physical 3D-printed part. "
        "The STL is attached via the custom.stl_url metafield.</p>"
    ),
    "product_type": "3D Printed Model",
    "vendor": "Slant 3D",
    "tags": ["3D Model", "3D Printing", "Slant3D", "STL", "hair-comb"],
    "status": "DRAFT",          # use ACTIVE to publish to sales channels
    "price": "12.00",
    "sku": "STL-HAIRCOMB-001",
    "weight_kg": 0.1,           # must be non-zero for shipping to evaluate
    # Must be a secure, publicly accessible direct HTTPS link to the .stl file.
    "stl_url": "https://example-cdn.com/models/hair_comb_for_3d_printing.stl",
}

# ---------------------------------------------------------------------------
# 2. GraphQL operations (validated against Admin API 2026-10).
# ---------------------------------------------------------------------------
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
          inventoryItem {
            id
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

UPDATE_VARIANT = """
mutation UpdateVariant($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      price
      sku
      inventoryItem {
        id
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
      id
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


def create_product(client, spec):
    """Create the product shell and return its product node (with first variant)."""
    variables = {
        "product": {
            "title": spec["title"],
            "descriptionHtml": spec["description_html"],
            "productType": spec["product_type"],
            "vendor": spec["vendor"],
            "tags": spec["tags"],
            "status": spec["status"],
        }
    }
    data = client.execute(CREATE_PRODUCT, variables)
    payload = check_user_errors(data["productCreate"], "productCreate")
    return payload["product"]


def configure_variant(client, product, spec):
    """Apply pricing, weight, physical toggle and inventory tracking."""
    variant = product["variants"]["nodes"][0]
    variables = {
        "productId": product["id"],
        "variants": [
            {
                "id": variant["id"],
                "price": spec["price"],
                "inventoryItem": {
                    "sku": spec["sku"],
                    "tracked": True,
                    "requiresShipping": True,
                    "measurement": {
                        "weight": {"value": spec["weight_kg"], "unit": "KILOGRAMS"}
                    },
                },
            }
        ],
    }
    data = client.execute(UPDATE_VARIANT, variables)
    payload = check_user_errors(data["productVariantsBulkUpdate"], "productVariantsBulkUpdate")
    return payload["productVariants"][0]


def set_stl_metafield(client, product, spec):
    """Attach custom.stl_url so Make.com can forward the model to Slant 3D."""
    variables = {
        "metafields": [
            {
                "ownerId": product["id"],
                "namespace": "custom",
                "key": "stl_url",
                "type": "url",
                "value": spec["stl_url"],
            }
        ]
    }
    data = client.execute(SET_STL_METAFIELD, variables)
    payload = check_user_errors(data["metafieldsSet"], "metafieldsSet")
    return payload["metafields"][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create the product (default is a dry run).",
    )
    args = parser.parse_args()

    if not args.execute:
        print("DRY RUN - no product created. Planned operations:\n")
        print(f"  Title          : {SAMPLE_PRODUCT['title']}")
        print(f"  Type/Vendor    : {SAMPLE_PRODUCT['product_type']} / {SAMPLE_PRODUCT['vendor']}")
        print(f"  Tags           : {', '.join(SAMPLE_PRODUCT['tags'])}")
        print(f"  Status         : {SAMPLE_PRODUCT['status']}")
        print(f"  Price          : {SAMPLE_PRODUCT['price']} USD")
        print(f"  SKU            : {SAMPLE_PRODUCT['sku']}")
        print(f"  Weight         : {SAMPLE_PRODUCT['weight_kg']} kg (requiresShipping = true)")
        print(f"  custom.stl_url : {SAMPLE_PRODUCT['stl_url']}")
        print("\nRe-run with --execute to create this product on the live store.")
        return

    client = ShopifyClient()
    print(f"Connected to {client.shop_domain} (API {client.api_version}).")

    product = create_product(client, SAMPLE_PRODUCT)
    print(f"Created product: {product['id']} (handle: {product['handle']})")

    variant = configure_variant(client, product, SAMPLE_PRODUCT)
    print(f"Configured variant: {variant['id']} "
          f"(price {variant['price']}, tracked={variant['inventoryItem']['tracked']})")

    metafield = set_stl_metafield(client, product, SAMPLE_PRODUCT)
    print(f"Set metafield: {metafield['namespace']}.{metafield['key']} = {metafield['value']}")

    print("\nDone. Remember to set inventory quantity at a location before publishing.")


if __name__ == "__main__":
    try:
        main()
    except ShopifyError as error:
        raise SystemExit(f"Shopify error: {error}")
