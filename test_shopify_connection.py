"""Smoke test for the live Shopify Admin API connection.

Authenticates with the client credentials grant (SHOPIFY_CLIENT_ID /
SHOPIFY_CLIENT_SECRET) and runs a minimal GraphQL query against the shop.
"""

import os
import sys

import requests
from dotenv import load_dotenv

API_VERSION = "2025-07"


def get_access_token(shop_domain, client_id, client_secret):
    """Exchange client credentials for a short-lived Admin API access token."""
    url = f"https://{shop_domain}/admin/oauth/access_token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def query_shop(shop_domain, access_token):
    """Fetch the shop name, primary domain, and currency via GraphQL."""
    url = f"https://{shop_domain}/admin/api/{API_VERSION}/graphql.json"
    query = """
    {
      shop {
        name
        primaryDomain {
          host
          url
        }
        currencyCode
      }
    }
    """
    response = requests.post(
        url,
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]["shop"]


def main():
    load_dotenv()

    shop_domain = os.getenv("SHOPIFY_STORE_DOMAIN")
    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")

    missing = [
        name
        for name, value in (
            ("SHOPIFY_STORE_DOMAIN", shop_domain),
            ("SHOPIFY_CLIENT_ID", client_id),
            ("SHOPIFY_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    print(f"Connecting to {shop_domain} ...")
    access_token = get_access_token(shop_domain, client_id, client_secret)

    shop = query_shop(shop_domain, access_token)

    print("\nShopify connection successful\n")
    print(f"  Shop name       : {shop['name']}")
    print(f"  Primary domain  : {shop['primaryDomain']['host']}")
    print(f"  Storefront URL  : {shop['primaryDomain']['url']}")
    print(f"  Currency        : {shop['currencyCode']}")


if __name__ == "__main__":
    main()
