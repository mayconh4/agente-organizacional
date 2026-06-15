"""Conector real da Amazon SP-API (https://sellercentral.amazon.com.br).

Autenticação por Login with Amazon (LWA): troca o refresh token por um access
token de curta duração e chama o SP-API com o header x-amz-access-token.
Credenciais via env (AMAZON_LWA_CLIENT_ID, AMAZON_LWA_CLIENT_SECRET,
AMAZON_REFRESH_TOKEN). Sem elas, a fábrica usa o SampleConnector.

Cobertura do MVP: pedidos do dia (Orders API). Catálogo/Buy Box e Ads exigem
chamadas adicionais (Listings, Product Pricing, Amazon Ads API) e ficam como
evolução — o relatório sinaliza a cobertura parcial.
"""
from __future__ import annotations

import os
import time

import requests

from ..models import ChannelSnapshot, Order
from .base import Connector, ConnectorError

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
TIMEOUT = 30


class AmazonConnector(Connector):
    channel = "amazon"

    def __init__(self, lwa_client_id: str | None = None,
                 lwa_client_secret: str | None = None,
                 refresh_token: str | None = None,
                 spapi_endpoint: str | None = None,
                 marketplace_id: str | None = None) -> None:
        self.client_id = (lwa_client_id or os.getenv("AMAZON_LWA_CLIENT_ID", "")).strip()
        self.client_secret = (lwa_client_secret
                              or os.getenv("AMAZON_LWA_CLIENT_SECRET", "")).strip()
        self.refresh_token = (refresh_token
                             or os.getenv("AMAZON_REFRESH_TOKEN", "")).strip()
        self.endpoint = (spapi_endpoint or os.getenv(
            "AMAZON_SPAPI_ENDPOINT", "https://sellingpartnerapi-na.amazon.com"
        )).strip()
        self.marketplace_id = (marketplace_id
                              or os.getenv("AMAZON_MARKETPLACE_ID", "A2Q3Y263D00KWC")).strip()
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    def is_configured(self) -> bool:
        return all([self.client_id, self.client_secret, self.refresh_token])

    # ------------------------------------------------------------------ #
    def _access(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        try:
            resp = requests.post(
                LWA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise ConnectorError(f"Amazon LWA: {exc}") from exc
        self._access_token = payload["access_token"]
        self._token_expiry = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def _get(self, path: str, **params) -> dict:
        try:
            resp = requests.get(
                f"{self.endpoint}{path}",
                headers={"x-amz-access-token": self._access()},
                params=params,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ConnectorError(f"Amazon {path}: {exc}") from exc

    # ------------------------------------------------------------------ #
    def fetch_snapshot(self, day: str) -> ChannelSnapshot:
        orders = self._fetch_orders(day)
        return ChannelSnapshot(
            channel=self.channel,
            products=[],   # Listings/Buy Box: evolução do MVP
            campaigns=[],  # Amazon Ads API: evolução do MVP
            orders=orders,
        )

    def _fetch_orders(self, day: str) -> list[Order]:
        data = self._get(
            "/orders/v0/orders",
            MarketplaceIds=self.marketplace_id,
            CreatedAfter=f"{day}T00:00:00Z",
            CreatedBefore=f"{day}T23:59:59Z",
        )
        orders = []
        for o in data.get("payload", {}).get("Orders", []):
            amount = (o.get("OrderTotal") or {}).get("Amount")
            orders.append(
                Order(
                    id=o.get("AmazonOrderId", ""),
                    channel=self.channel,
                    created_at=day,
                    total=float(amount or 0),
                    status=(o.get("OrderStatus") or "").lower() or "pago",
                )
            )
        return orders
