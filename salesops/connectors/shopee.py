"""Conector real da Shopee Open Platform (https://open.shopee.com).

A Shopee exige assinatura HMAC-SHA256 em cada chamada. A base string da
assinatura para APIs de loja é:

    partner_id + api_path + timestamp + access_token + shop_id

assinada com a partner_key. Credenciais via env (SHOPEE_PARTNER_ID,
SHOPEE_PARTNER_KEY, SHOPEE_SHOP_ID, SHOPEE_ACCESS_TOKEN). Sem elas, a fábrica
usa o SampleConnector.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import requests

from ..models import ChannelSnapshot, Order, Product
from .base import Connector, ConnectorError

TIMEOUT = 20


class ShopeeConnector(Connector):
    channel = "shopee"

    def __init__(self) -> None:
        self.partner_id = os.getenv("SHOPEE_PARTNER_ID", "").strip()
        self.partner_key = os.getenv("SHOPEE_PARTNER_KEY", "").strip()
        self.shop_id = os.getenv("SHOPEE_SHOP_ID", "").strip()
        self.access_token = os.getenv("SHOPEE_ACCESS_TOKEN", "").strip()
        self.host = os.getenv("SHOPEE_HOST", "https://partner.shopeemobile.com").strip()

    def is_configured(self) -> bool:
        return all([self.partner_id, self.partner_key, self.shop_id, self.access_token])

    # ------------------------------------------------------------------ #
    def _signed_params(self, path: str) -> dict:
        ts = int(time.time())
        base = f"{self.partner_id}{path}{ts}{self.access_token}{self.shop_id}"
        sign = hmac.new(
            self.partner_key.encode(), base.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "partner_id": int(self.partner_id),
            "timestamp": ts,
            "access_token": self.access_token,
            "shop_id": int(self.shop_id),
            "sign": sign,
        }

    def _get(self, path: str, **extra) -> dict:
        params = self._signed_params(path)
        params.update(extra)
        try:
            resp = requests.get(f"{self.host}{path}", params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise ConnectorError(f"Shopee {path}: {exc}") from exc
        if data.get("error"):
            raise ConnectorError(f"Shopee {path}: {data.get('error')} {data.get('message')}")
        return data

    # ------------------------------------------------------------------ #
    def fetch_snapshot(self, day: str) -> ChannelSnapshot:
        info = self._get("/api/v2/shop/get_shop_info")
        products = self._fetch_products()
        orders = self._fetch_orders(day)
        return ChannelSnapshot(
            channel=self.channel,
            reputation=None,  # Shopee expõe penalty/performance em outra API
            unanswered_questions=0,
            products=products,
            campaigns=[],  # Shopee Ads: API separada (fora do MVP)
            orders=orders,
        )

    def _fetch_products(self, page_size: int = 30) -> list[Product]:
        listing = self._get(
            "/api/v2/product/get_item_list",
            offset=0, page_size=page_size, item_status="NORMAL",
        )
        item_ids = [i["item_id"] for i in listing.get("response", {}).get("item", [])]
        if not item_ids:
            return []
        detail = self._get(
            "/api/v2/product/get_item_base_info",
            item_id_list=",".join(str(i) for i in item_ids),
        )
        products: list[Product] = []
        for item in detail.get("response", {}).get("item_list", []):
            price_info = (item.get("price_info") or [{}])[0]
            stock_info = item.get("stock_info_v2", {}).get("summary_info", {})
            products.append(
                Product(
                    sku=str(item.get("item_id")),
                    title=item.get("item_name", ""),
                    channel=self.channel,
                    price=float(price_info.get("current_price") or 0),
                    stock=int(stock_info.get("total_available_stock") or 0),
                    status="ativo" if item.get("item_status") == "NORMAL" else "pausado",
                    images=len((item.get("image") or {}).get("image_url_list") or []),
                    rating=float((item.get("rating_star") or {}).get("rating_star") or 0)
                    or None,
                    description_length=len(item.get("description") or ""),
                )
            )
        return products

    def _fetch_orders(self, day: str) -> list[Order]:
        ts = time.strptime(day, "%Y-%m-%d")
        start = int(time.mktime(ts))
        end = start + 86399
        listing = self._get(
            "/api/v2/order/get_order_list",
            time_range_field="create_time", time_from=start, time_to=end,
            page_size=100,
        )
        sn = [o["order_sn"] for o in listing.get("response", {}).get("order_list", [])]
        if not sn:
            return []
        detail = self._get(
            "/api/v2/order/get_order_detail",
            order_sn_list=",".join(sn), response_optional_fields="total_amount",
        )
        orders = []
        for o in detail.get("response", {}).get("order_list", []):
            orders.append(
                Order(
                    id=o.get("order_sn", ""),
                    channel=self.channel,
                    created_at=day,
                    total=float(o.get("total_amount") or 0),
                    status=o.get("order_status", "").lower() or "pago",
                )
            )
        return orders
