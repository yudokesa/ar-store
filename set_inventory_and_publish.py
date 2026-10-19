"""Set initial inventory and activate the published catalog.

For each configured product handle this script:
  1. sets available inventory at the store's primary location,
  2. flips the product status from DRAFT to ACTIVE,
  3. publishes the product to every available sales channel.

Idempotent: re-running re-asserts the same quantity, status, and publications.
Dry run by default; pass --execute to apply changes.
"""

import argparse
import uuid

from shopify_client import ShopifyClient, ShopifyError, check_user_errors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PRODUCT_HANDLES = [
    "angel-christmas-tree-decor",
    "bullish",
    "bearish",
]

INITIAL_QUANTITY = 50
TARGET_STATUS = "ACTIVE"
ADJUSTMENT_REASON = "correction"

# ---------------------------------------------------------------------------
# GraphQL operations (validated against Admin API 2026-10)
# ---------------------------------------------------------------------------
FIND_PRODUCTS = """
query {
  products(first: 50) {
    nodes {
      id
      handle
      title
      status
      variants(first: 1) {
        nodes {
          id
          inventoryItem {
            id
          }
        }
      }
    }
  }
}
"""

FIND_LOCATIONS = """
query {
  locations(first: 10) {
    nodes {
      id
    }
  }
}
"""

FIND_PUBLICATIONS = """
query {
  publications(first: 50) {
    nodes {
      id
      name
    }
  }
}
"""

SET_QUANTITIES = """
mutation SetQuantities($input: InventorySetQuantitiesInput!, $key: String!) {
  inventorySetQuantities(input: $input) @idempotent(key: $key) {
    inventoryAdjustmentGroup {
      createdAt
      reason
    }
    userErrors {
      field
      message
    }
  }
}
"""

GET_QUANTITY = """
query GetQuantity($id: ID!, $loc: ID!) {
  inventoryItem(id: $id) {
    inventoryLevel(locationId: $loc) {
      quantities(names: ["available"]) {
        quantity
      }
    }
  }
}
"""

ACTIVATE_ITEM = """
mutation ActivateItem($inventoryItemId: ID!, $locationId: ID!) {
  inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
    inventoryLevel {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""

SET_STATUS = """
mutation SetStatus($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      id
      handle
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""

PUBLISH_PRODUCT = """
mutation PublishProduct($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable {
      resourcePublicationsCount {
        count
      }
      ... on Product {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""


def load_products(client):
    """Return the configured products keyed by handle, resolved live from Shopify."""
    nodes = client.execute(FIND_PRODUCTS)["products"]["nodes"]
    by_handle = {
        node["handle"]: {
            "id": node["id"],
            "handle": node["handle"],
            "title": node["title"],
            "status": node["status"],
            "item_id": node["variants"]["nodes"][0]["inventoryItem"]["id"],
        }
        for node in nodes
        if node["handle"] in PRODUCT_HANDLES
    }
    missing = [handle for handle in PRODUCT_HANDLES if handle not in by_handle]
    if missing:
        raise ShopifyError(f"Products not found: {', '.join(missing)}")
    return [by_handle[handle] for handle in PRODUCT_HANDLES]


def primary_location(client):
    """Return the store's first location ID, which will hold the inventory."""
    nodes = client.execute(FIND_LOCATIONS)["locations"]["nodes"]
    if not nodes:
        raise ShopifyError("No location available to hold inventory.")
    return nodes[0]["id"]


def read_quantity(client, item_id, location_id):
    """Return the available quantity, or None when the item isn't stocked there. Read-only."""
    level = client.execute(
        GET_QUANTITY, {"id": item_id, "loc": location_id}
    )["inventoryItem"]["inventoryLevel"]
    return None if level is None else level["quantities"][0]["quantity"]


def ensure_quantity(client, item_id, location_id):
    """Return the available quantity, stocking the item at the location if needed."""
    quantity = read_quantity(client, item_id, location_id)
    if quantity is not None:
        return quantity
    data = client.execute(
        ACTIVATE_ITEM, {"inventoryItemId": item_id, "locationId": location_id}
    )
    check_user_errors(data["inventoryActivate"], "inventoryActivate")
    return 0


def set_quantity(client, item_id, location_id, quantity, change_from):
    variables = {
        "input": {
            "name": "available",
            "reason": ADJUSTMENT_REASON,
            "quantities": [
                {
                    "inventoryItemId": item_id,
                    "locationId": location_id,
                    "quantity": quantity,
                    "changeFromQuantity": change_from,
                }
            ],
        },
        "key": str(uuid.uuid4()),
    }
    data = client.execute(SET_QUANTITIES, variables)
    return check_user_errors(data["inventorySetQuantities"], "inventorySetQuantities")


def set_status(client, product_id, status):
    variables = {"product": {"id": product_id, "status": status}}
    data = client.execute(SET_STATUS, variables)
    return check_user_errors(data["productUpdate"], "productUpdate")["product"]


def publish(client, product_id, publication_ids):
    variables = {
        "id": product_id,
        "input": [{"publicationId": pid} for pid in publication_ids],
    }
    data = client.execute(PUBLISH_PRODUCT, variables)
    return check_user_errors(data["publishablePublish"], "publishablePublish")


def discover_publications(client):
    """Return (publications, error). A missing scope must not block the rest."""
    try:
        return client.execute(FIND_PUBLICATIONS)["publications"]["nodes"], None
    except ShopifyError as error:
        return [], str(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to the live store (default is a dry run).")
    args = parser.parse_args()

    client = ShopifyClient()
    products = load_products(client)
    location_id = primary_location(client)
    publications, publication_error = discover_publications(client)

    if not args.execute:
        print(f"DRY RUN — no changes made ({len(products)} products)\n")
        print(f"  location: {location_id}")
        for product in products:
            current = read_quantity(client, product["item_id"], location_id)
            current = "not stocked" if current is None else current
            print(f"\n  {product['title']}  [{product['handle']}]")
            print(f"    status    : {product['status']} -> {TARGET_STATUS}")
            print(f"    inventory : {current} -> {INITIAL_QUANTITY} available")
        if publications:
            names = ", ".join(p["name"] for p in publications)
            print(f"\n  channels  : publish to {len(publications)} -> {names}")
        else:
            print(f"\n  channels  : SKIPPED — {publication_error}")
        print("\nRe-run with --execute to apply.")
        return

    print(f"Connected to {client.shop_domain} (API {client.api_version}).")
    print(f"Location: {location_id}\n")

    for product in products:
        previous = ensure_quantity(client, product["item_id"], location_id)
        set_quantity(client, product["item_id"], location_id, INITIAL_QUANTITY, previous)
        print(f"{product['title']}  [{product['handle']}]")
        print(f"   inventory : {previous} -> {INITIAL_QUANTITY} available")

        updated = set_status(client, product["id"], TARGET_STATUS)
        print(f"   status    : {updated['status']}")

        if publications:
            publish(client, product["id"], [p["id"] for p in publications])
            print(f"   channels  : published to {len(publications)} channel(s)")
        else:
            print("   channels  : SKIPPED (missing publications scope)")
        print()

    if not publications:
        print(f"Channel publishing skipped: {publication_error}")
        print("Add read_publications + write_publications to the app, then re-run.")


if __name__ == "__main__":
    try:
        main()
    except ShopifyError as error:
        raise SystemExit(f"Shopify error: {error}")
