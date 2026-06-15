"""Conector real do Mercado Livre (https://developers.mercadolivre.com.br).

Usa um access token OAuth2 (env ML_ACCESS_TOKEN). O seller_id é descoberto via
/users/me quando não informado. Sem token, a fábrica troca este conector pelo
SampleConnector automaticamente.

Campanhas (Product Ads) exigem o escopo de Advertising e uma API separada;
ficam de fora deste MVP (lista vazia) — o relatório sinaliza isso.
"""
from __future__ import annotations

import os

import requests

from ..models import ChannelSnapshot, Order, Product
from .base import Connector, ConnectorError

API = "https://api.mercadolibre.com"
TIMEOUT = 20


class MercadoLivreConnector(Connector):
    channel = "mercado_livre"

    def __init__(self) -> None:
        self.token = os.getenv("ML_ACCESS_TOKEN", "").strip()
        self.seller_id = os.getenv("ML_SELLER_ID", "").strip()

    def is_configured(self) -> bool:
        return bool(self.token)

    # ------------------------------------------------------------------ #
    def _get(self, path: str, **params) -> dict:
        try:
            resp = requests.get(
                f"{API}{path}",
                headers={"Authorization": f"Bearer {self.token}"},
                params=params,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:  # rede / HTTP
            raise ConnectorError(f"Mercado Livre {path}: {exc}") from exc

    def _resolve_seller(self) -> str:
        if not self.seller_id:
            self.seller_id = str(self._get("/users/me").get("id", ""))
        if not self.seller_id:
            raise ConnectorError("Mercado Livre: não foi possível obter o seller_id")
        return self.seller_id

    # ------------------------------------------------------------------ #
    def fetch_snapshot(self, day: str) -> ChannelSnapshot:
        seller = self._resolve_seller()
        user = self._get(f"/users/{seller}")
        reputation = (user.get("seller_reputation", {}) or {}).get("level_id")
        metrics = (user.get("seller_reputation", {}) or {}).get("metrics", {})
        late = (((metrics.get("delayed_handling_time") or {}).get("rate") or 0) * 100) or None

        products = self._fetch_products(seller)
        orders = self._fetch_orders(seller, day)
        questions = self._count_unanswered_questions(seller)

        return ChannelSnapshot(
            channel=self.channel,
            reputation=self._reputation_label(reputation),
            late_shipment_rate=round(late, 1) if late else None,
            unanswered_questions=questions,
            products=products,
            campaigns=[],  # Product Ads: API/escopo separado (fora do MVP)
            orders=orders,
        )

    # ------------------------------------------------------------------ #
    def _fetch_products(self, seller: str, limit: int = 30) -> list[Product]:
        ids = self._get(f"/users/{seller}/items/search", limit=limit).get("results", [])
        products: list[Product] = []
        for item_id in ids:
            item = self._get(f"/items/{item_id}")
            visits = self._item_visits(item_id)
            pics = len(item.get("pictures") or [])
            products.append(
                Product(
                    sku=item.get("id", item_id),
                    title=item.get("title", ""),
                    channel=self.channel,
                    price=float(item.get("price") or 0),
                    stock=int(item.get("available_quantity") or 0),
                    status="ativo" if item.get("status") == "active" else "pausado",
                    images=pics,
                    visits=visits,
                    units_sold_today=int(item.get("sold_quantity_today") or 0),
                    ranking=None,
                    description_length=len(item.get("descriptions") and "" or ""),
                )
            )
        return products

    def _item_visits(self, item_id: str) -> int:
        try:
            data = self._get(f"/items/{item_id}/visits/time_window",
                             last=1, unit="day")
            results = data.get("results") or []
            return int(results[-1].get("total", 0)) if results else 0
        except ConnectorError:
            return 0

    def _fetch_orders(self, seller: str, day: str) -> list[Order]:
        data = self._get(
            "/orders/search",
            seller=seller,
            **{"order.date_created.from": f"{day}T00:00:00.000-00:00",
               "order.date_created.to": f"{day}T23:59:59.000-00:00"},
        )
        orders = []
        for o in data.get("results", []):
            orders.append(
                Order(
                    id=str(o.get("id")),
                    channel=self.channel,
                    created_at=day,
                    total=float(o.get("total_amount") or 0),
                    status=o.get("status", "paid"),
                )
            )
        return orders

    def _count_unanswered_questions(self, seller: str) -> int:
        try:
            data = self._get("/questions/search", seller_id=seller, status="UNANSWERED")
            return int(data.get("total", 0))
        except ConnectorError:
            return 0

    @staticmethod
    def _reputation_label(level_id: str | None) -> str | None:
        if not level_id:
            return None
        # level_id ex.: "5_green", "3_yellow", "1_red"
        if "green" in level_id:
            return "verde"
        if "yellow" in level_id:
            return "amarelo"
        if "red" in level_id:
            return "vermelho"
        return level_id
