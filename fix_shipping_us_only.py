"""Restrict the storefront to the United States and fix the flat shipping rate.

Background: the shop's only location is in Indonesia, so the delivery profile
priced US orders through a 28-country "International" zone at 340,000 IDR
(~$18.89) - more than the cheapest product. Slant 3D prints from the US, so the
store is being narrowed to a US-only market with a single sane US rate.

Does three things:
  1. Rewrites the US-bearing shipping zone to cover only the United States,
     renaming it and setting a $4.99 USD flat rate.
  2. Deletes the Indonesia "Domestic" zone, so no rate exists for ID.
  3. Sets the Indonesia market to DRAFT, so ID is not sellable at checkout.

Deliberately NOT here: the shop's base currency, plan, billing and payout
settings, and the location's country. The location remains in Indonesia, which
does not affect a *flat* rate but would matter for carrier-calculated rates and
printed labels - flagged in AUDIT_REPORT.md.

Idempotent: re-running re-asserts the same zone/rate/market state.
Dry run by default; pass --execute to apply.
"""

import argparse

from shopify_client import ShopifyClient

TARGET_COUNTRY = "US"
EXCLUDED_COUNTRY = "ID"
US_ZONE_NAME = "United States"
US_RATE_NAME = "Standard US Shipping"
US_RATE_USD = "4.99"

FIND_PROFILE = """
query {
  deliveryProfiles(first: 10) {
    nodes {
      id
      name
      default
      profileLocationGroups {
        locationGroup { id locations(first: 5) { nodes { id name } } }
        locationGroupZones(first: 50) {
          nodes {
            zone {
              id
              name
              countries { code { countryCode restOfWorld } }
            }
            methodDefinitions(first: 20) {
              nodes {
                id
                name
                active
                rateProvider {
                  __typename
                  ... on DeliveryRateDefinition { id price { amount currencyCode } }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

UPDATE_PROFILE = """
mutation UpdateProfile($id: ID!, $profile: DeliveryProfileInput!) {
  deliveryProfileUpdate(id: $id, profile: $profile) {
    profile {
      id
      name
      profileLocationGroups {
        locationGroup { id }
        locationGroupZones(first: 50) {
          nodes {
            zone { id name countries { code { countryCode restOfWorld } } }
            methodDefinitions(first: 20) {
              nodes {
                id name active
                rateProvider {
                  __typename
                  ... on DeliveryRateDefinition { id price { amount currencyCode } }
                }
              }
            }
          }
        }
      }
    }
    userErrors { field message }
  }
}
"""

FIND_MARKETS = """
query {
  markets(first: 20) { nodes { id name handle enabled status } }
}
"""

UPDATE_MARKET = """
mutation DisableMarket($id: ID!, $input: MarketUpdateInput!) {
  marketUpdate(id: $id, input: $input) {
    market { id name handle enabled status }
    userErrors { field message code }
  }
}
"""

STATE_QUERY = """
query {
  shop { currencyCode shipsToCountries }
  markets(first: 20) { nodes { id name handle enabled status } }
}
"""


def load_profile(client):
    """Return the default delivery profile, with zones and rates resolved live."""
    profiles = client.execute(FIND_PROFILE)["deliveryProfiles"]["nodes"]
    default = next((p for p in profiles if p["default"]), profiles[0] if profiles else None)
    if not default:
        raise SystemExit("No delivery profile found.")
    return default


def flatten(profile):
    """Yield (location_group_id, zone, method, rate) tuples."""
    for group in profile["profileLocationGroups"]:
        gid = group["locationGroup"]["id"]
        for node in group["locationGroupZones"]["nodes"]:
            zone = node["zone"]
            for method in node["methodDefinitions"]["nodes"]:
                yield gid, zone, method, method.get("rateProvider")


def country_codes(zone):
    return {c["code"]["countryCode"] for c in zone["countries"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to the live store (default is a dry run).")
    args = parser.parse_args()

    client = ShopifyClient()
    profile = load_profile(client)
    rows = list(flatten(profile))

    # Identify the zone carrying US (the one to keep) and the ID-only zone (to drop).
    us_row = next((r for r in rows if TARGET_COUNTRY in country_codes(r[1])), None)
    id_row = next((r for r in rows
                   if country_codes(r[1]) == {EXCLUDED_COUNTRY} and r[1]["id"] != (us_row[1]["id"] if us_row else None)), None)

    if not us_row:
        raise SystemExit(f"No shipping zone contains {TARGET_COUNTRY}; nothing to update.")
    if not id_row:
        print(f"note: no {EXCLUDED_COUNTRY}-only zone found (may already be removed).")

    gid, us_zone, us_method, us_rate = us_row
    if not us_rate or not us_rate.get("id"):
        raise SystemExit("US zone has no flat rate definition to update.")

    markets = client.execute(FIND_MARKETS)["markets"]["nodes"]
    id_market = next((m for m in markets if m["handle"] == EXCLUDED_COUNTRY.lower()), None)

    print(f"shop currency : {client.execute(STATE_QUERY)['shop']['currencyCode']}")
    print(f"profile       : {profile['name']} ({profile['id']})\n")

    print("SHIPPING")
    print(f"  zone  {us_zone['id']} '{us_zone['name']}'")
    print(f"        countries {sorted(country_codes(us_zone))} -> ['{TARGET_COUNTRY}']")
    print(f"        rename  -> '{US_ZONE_NAME}'")
    print(f"  method {us_method['id']} '{us_method['name']}' -> '{US_RATE_NAME}'")
    print(f"  rate   {us_rate['id']} {us_rate['price']['amount']} {us_rate['price']['currencyCode']}"
          f" -> {US_RATE_USD} USD")
    if id_row:
        print(f"  delete zone {id_row[1]['id']} '{id_row[1]['name']}' (countries {sorted(country_codes(id_row[1]))})")

    print("\nMARKETS")
    if id_market:
        print(f"  {id_market['name']} ({id_market['id']}) status={id_market['status']} -> DRAFT")
    else:
        print(f"  no '{EXCLUDED_COUNTRY}' market found (may already be deactivated)")
    us_market = next((m for m in markets if m["handle"] == "united-states"), None)
    print(f"  United States: {us_market['status'] if us_market else 'not found'} (left untouched)")

    if not args.execute:
        print("\nDRY RUN - no changes made. Re-run with --execute to apply.")
        return

    print("\nApplying...\n")

    # 1 + 2: rewrite the US zone, then delete the ID zone.
    profile_input = {
        "locationGroupsToUpdate": [{
            "id": gid,
            "zonesToUpdate": [{
                "id": us_zone["id"],
                "name": US_ZONE_NAME,
                "countries": [{"code": TARGET_COUNTRY, "includeAllProvinces": True}],
                "methodDefinitionsToUpdate": [{
                    "id": us_method["id"],
                    "name": US_RATE_NAME,
                    "active": True,
                    "rateDefinition": {
                        "id": us_rate["id"],
                        "price": {"amount": US_RATE_USD, "currencyCode": "USD"},
                    },
                }],
            }],
        }],
    }
    if id_row:
        profile_input["zonesToDelete"] = [id_row[1]["id"]]

    data = client.execute(UPDATE_PROFILE, {"id": profile["id"], "profile": profile_input})["deliveryProfileUpdate"]
    if data["userErrors"]:
        raise SystemExit(f"deliveryProfileUpdate userErrors: {data['userErrors']}")

    print("SHIPPING now:")
    for _, zone, method, rate in flatten(data["profile"]):
        price = f"{rate['price']['amount']} {rate['price']['currencyCode']}" if rate else "-"
        print(f"  zone {zone['id']} '{zone['name']}' countries={sorted(country_codes(zone))}")
        print(f"    method '{method['name']}' active={method['active']} rate={price}")

    # 3: deactivate the Indonesia market.
    if id_market and id_market["status"] != "DRAFT":
        res = client.execute(UPDATE_MARKET, {"id": id_market["id"], "input": {"status": "DRAFT"}})["marketUpdate"]
        if res["userErrors"]:
            raise SystemExit(f"marketUpdate userErrors: {res['userErrors']}")
        m = res["market"]
        print(f"\nMARKET {m['name']}: status={m['status']} enabled={m['enabled']}")

    state = client.execute(STATE_QUERY)
    print(f"\nshop shipsToCountries -> {state['shop']['shipsToCountries']}")
    for m in state["markets"]["nodes"]:
        print(f"  market {m['name']}: status={m['status']} enabled={m['enabled']}")


if __name__ == "__main__":
    main()
