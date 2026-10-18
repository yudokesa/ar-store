"""Reusable Shopify Admin API client for the 3D-printing fulfillment pipeline.

Handles client-credentials token generation and exposes one helper for running
Admin GraphQL queries and mutations. Credentials are read from the .env file
(SHOPIFY_STORE_DOMAIN, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET).
"""

import os
import time

import requests
from dotenv import load_dotenv

DEFAULT_API_VERSION = "2026-10"
TOKEN_REFRESH_MARGIN_SECONDS = 60


class ShopifyError(RuntimeError):
    """Raised when Shopify returns an HTTP error or a GraphQL error."""


class ShopifyClient:
    def __init__(self, shop_domain=None, client_id=None, client_secret=None,
                 api_version=DEFAULT_API_VERSION):
        load_dotenv()
        self.shop_domain = shop_domain or os.getenv("SHOPIFY_STORE_DOMAIN")
        self.client_id = client_id or os.getenv("SHOPIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SHOPIFY_CLIENT_SECRET")
        self.api_version = api_version

        missing = [
            name
            for name, value in (
                ("SHOPIFY_STORE_DOMAIN", self.shop_domain),
                ("SHOPIFY_CLIENT_ID", self.client_id),
                ("SHOPIFY_CLIENT_SECRET", self.client_secret),
            )
            if not value
        ]
        if missing:
            raise ShopifyError(f"Missing credentials: {', '.join(missing)}")

        self._session = requests.Session()
        self._access_token = None
        self._expires_at = 0.0

    def _fetch_access_token(self):
        response = self._session.post(
            f"https://{self.shop_domain}/admin/oauth/access_token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise ShopifyError(
                f"Token request failed ({response.status_code}): {response.text}"
            )
        payload = response.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + payload.get("expires_in", 86399)

    @property
    def access_token(self):
        """Return a valid token, refreshing it shortly before it expires."""
        if not self._access_token or time.time() >= self._expires_at - TOKEN_REFRESH_MARGIN_SECONDS:
            self._fetch_access_token()
        return self._access_token

    def execute(self, query, variables=None):
        """Run an Admin GraphQL operation and return its `data` payload.

        Raises ShopifyError on transport failures or when the response
        contains top-level GraphQL `errors`.
        """
        response = self._session.post(
            f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json",
            headers={
                "X-Shopify-Access-Token": self.access_token,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        if response.status_code >= 400:
            raise ShopifyError(
                f"GraphQL request failed ({response.status_code}): {response.text}"
            )

        body = response.json()
        if body.get("errors"):
            raise ShopifyError(f"GraphQL errors: {body['errors']}")
        return body["data"]


def check_user_errors(payload, mutation_name):
    """Raise if a mutation payload contains userErrors, else return the payload."""
    errors = payload.get("userErrors") or []
    if errors:
        raise ShopifyError(f"{mutation_name} userErrors: {errors}")
    return payload
