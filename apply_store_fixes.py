"""Apply the scriptable Phase B hardening fixes from the store audit.

  1. C7 - create and pin the `custom.stl_url` PRODUCT metafield definition,
          so the field the pipeline depends on is a real, validated schema
          contract instead of an orphaned value.
  2. C8 - enable autoPublish on every sales channel, so products created by
          publish_catalog.py reach channels without a separate step.

Deliberately NOT here:
  C4 (`taxesIncluded`) has no Admin API mutation - it is an admin UI setting
  (Settings > Taxes and duties). See AUDIT_REPORT.md.

Idempotent: re-running re-asserts the same definition and channel state.
Dry run by default; pass --execute to apply.
"""

import argparse

from shopify_client import ShopifyClient, check_user_errors

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
METAFIELD_NAMESPACE = "custom"
METAFIELD_KEY = "stl_url"
METAFIELD_NAME = "STL File URL"
METAFIELD_TYPE = "url"
METAFIELD_DESCRIPTION = (
    "Public HTTPS URL of the source .stl file, fetched by Slant 3D at fulfilment."
)

# ---------------------------------------------------------------------------
# GraphQL operations (validated against Admin API 2026-10)
# ---------------------------------------------------------------------------
FIND_DEFINITION = """
query FindDefinition($namespace: String!, $key: String!) {
  metafieldDefinitions(first: 1, ownerType: PRODUCT, namespace: $namespace, key: $key) {
    nodes {
      id
      namespace
      key
      name
      type { name }
      pinnedPosition
    }
  }
}
"""

CREATE_DEFINITION = """
mutation CreateDefinition($definition: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $definition) {
    createdDefinition {
      id
      namespace
      key
      name
      type { name }
      pinnedPosition
    }
    userErrors { field message code }
  }
}
"""

PIN_DEFINITION = """
mutation PinDefinition($id: ID!) {
  metafieldDefinitionPin(definitionId: $id) {
    pinnedDefinition { id namespace key name pinnedPosition }
    userErrors { field message }
  }
}
"""

FIND_PUBLICATIONS = """
query {
  publications(first: 50) {
    nodes { id name autoPublish }
  }
}
"""

UPDATE_PUBLICATION = """
mutation UpdatePublication($id: ID!, $input: PublicationUpdateInput!) {
  publicationUpdate(id: $id, input: $input) {
    publication { id name autoPublish }
    userErrors { field message }
  }
}
"""


def find_definition(client):
    """Return the existing metafield definition, or None."""
    nodes = client.execute(
        FIND_DEFINITION, {"namespace": METAFIELD_NAMESPACE, "key": METAFIELD_KEY}
    )["metafieldDefinitions"]["nodes"]
    return nodes[0] if nodes else None


def create_definition(client):
    """Create (and pin) the STL URL definition. Pin is set on the input itself."""
    variables = {
        "definition": {
            "name": METAFIELD_NAME,
            "namespace": METAFIELD_NAMESPACE,
            "key": METAFIELD_KEY,
            "description": METAFIELD_DESCRIPTION,
            "type": METAFIELD_TYPE,
            "ownerType": "PRODUCT",
            "pin": True,
        }
    }
    data = client.execute(CREATE_DEFINITION, variables)
    return check_user_errors(
        data["metafieldDefinitionCreate"], "metafieldDefinitionCreate"
    )["createdDefinition"]


def pin_definition(client, definition_id):
    """Explicitly pin the definition, for when it already existed unpinned."""
    data = client.execute(PIN_DEFINITION, {"id": definition_id})
    return check_user_errors(
        data["metafieldDefinitionPin"], "metafieldDefinitionPin"
    )["pinnedDefinition"]


def load_publications(client):
    return client.execute(FIND_PUBLICATIONS)["publications"]["nodes"]


def set_auto_publish(client, publication_id, enabled):
    data = client.execute(
        UPDATE_PUBLICATION, {"id": publication_id, "input": {"autoPublish": enabled}}
    )
    return check_user_errors(
        data["publicationUpdate"], "publicationUpdate"
    )["publication"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to the live store (default is a dry run).")
    args = parser.parse_args()

    client = ShopifyClient()

    existing = find_definition(client)
    publications = load_publications(client)

    if not args.execute:
        print("DRY RUN - no changes made\n")
        print("1. metafield definition")
        if existing:
            print(f"   exists: {existing['namespace']}.{existing['key']} "
                  f"({existing['type']['name']}) pinnedPosition={existing['pinnedPosition']}")
            if existing["pinnedPosition"] is None:
                print("   action: pin it")
            else:
                print("   action: none (already correct)")
        else:
            print(f"   create: {METAFIELD_NAMESPACE}.{METAFIELD_KEY} "
                  f"name='{METAFIELD_NAME}' type={METAFIELD_TYPE} ownerType=PRODUCT pin=true")
        print("\n2. channel autoPublish")
        for pub in publications:
            print(f"   {pub['name']}: {pub['autoPublish']} -> True")
        print("\nRe-run with --execute to apply.")
        return

    print(f"Connected to {client.shop_domain} (API {client.api_version}).\n")

    # 1. metafield definition
    if existing:
        definition = existing
        if existing["pinnedPosition"] is None:
            definition = pin_definition(client, existing["id"])
            print(f"metafield definition pinned: {definition['namespace']}.{definition['key']}")
        else:
            print(f"metafield definition ok: {definition['namespace']}.{definition['key']} "
                  f"({definition['type']['name']})")
    else:
        definition = create_definition(client)
        print(f"metafield definition created: {definition['namespace']}.{definition['key']} "
              f"({definition['type']['name']}) pinnedPosition={definition['pinnedPosition']}")

    # 2. autoPublish
    print()
    for pub in publications:
        updated = set_auto_publish(client, pub["id"], True)
        print(f"{updated['name']}: autoPublish = {updated['autoPublish']}")


if __name__ == "__main__":
    main()
