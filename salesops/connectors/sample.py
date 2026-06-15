"""Provedor de dados de exemplo.

Gera uma operação multicanal realista, com problemas plantados de propósito
(anúncio sem foto, estoque zerado, Buy Box perdida, campanha no prejuízo, etc.)
para demonstrar o agente sem precisar de credenciais. A variação por dia é
determinística (semente derivada da data), então o detector consegue comparar
"hoje" contra "ontem" e o relatório é reproduzível.
"""
from __future__ import annotations

import hashlib

from ..models import AdCampaign, Channel, ChannelSnapshot, Order, Product
from .base import Connector


def _factor(day: str, key: str, low: float = 0.8, high: float = 1.2) -> float:
    """Multiplicador determinístico em [low, high] para (dia, chave)."""
    digest = hashlib.sha256(f"{day}:{key}".encode()).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF
    return round(low + frac * (high - low), 3)


def _orders(channel: str, day: str, revenue: float, count: int) -> list[Order]:
    if count <= 0:
        return []
    ticket = revenue / count
    return [
        Order(id=f"{channel[:3].upper()}-{day}-{i:03d}", channel=channel,
              created_at=day, total=round(ticket, 2))
        for i in range(count)
    ]


class SampleConnector(Connector):
    def __init__(self, channel: str) -> None:
        self.channel = channel

    def is_configured(self) -> bool:  # sempre disponível
        return True

    def fetch_snapshot(self, day: str) -> ChannelSnapshot:
        builder = {
            Channel.SHOPEE: self._shopee,
            Channel.MERCADO_LIVRE: self._mercado_livre,
            Channel.AMAZON: self._amazon,
        }.get(self.channel)
        if builder is None:
            return ChannelSnapshot(channel=self.channel, is_sample=True)
        snap = builder(day)
        snap.is_sample = True
        return snap

    # ------------------------------------------------------------------ #
    def _shopee(self, day: str) -> ChannelSnapshot:
        f = lambda k, lo=0.8, hi=1.2: _factor(day, f"shopee:{k}", lo, hi)  # noqa: E731
        products = [
            # Campeão de vendas que ZEROU o estoque hoje (alerta crítico).
            Product(sku="SHP-001", title="Fone Bluetooth XYZ Pro", channel=self.channel,
                    price=89.90, stock=0, status="ativo", images=4, rating=4.6,
                    reviews=128, visits=int(420 * f("v1")),
                    units_sold_today=int(3 * f("s1")), ctr=2.1,
                    conversion_rate=1.8, ranking=9, description_length=640),
            # Anúncio SEM FOTO e com título fraco (problemas de catálogo).
            Product(sku="SHP-002", title="fone", channel=self.channel,
                    price=59.90, stock=40, status="ativo", images=0, rating=4.1,
                    reviews=14, visits=int(90 * f("v2")),
                    units_sold_today=int(1 * f("s2")), ctr=0.6,
                    conversion_rate=0.7, ranking=37, description_length=80),
            # Produto saudável com CTR alto = oportunidade de escalar.
            Product(sku="SHP-003", title="Carregador Turbo 20W USB-C", channel=self.channel,
                    price=39.90, stock=150, status="ativo", images=6, rating=4.8,
                    reviews=312, visits=int(610 * f("v3")),
                    units_sold_today=int(22 * f("s3")), ctr=4.3,
                    conversion_rate=3.9, ranking=3, description_length=720),
            # Anúncio pausado sem motivo aparente.
            Product(sku="SHP-004", title="Cabo HDMI 2.1 8K 2m", channel=self.channel,
                    price=49.90, stock=80, status="pausado", images=3, rating=4.5,
                    reviews=60, visits=0, units_sold_today=0, ctr=None,
                    conversion_rate=None, ranking=None, description_length=300),
        ]
        revenue = sum(p.revenue_today for p in products)
        campaigns = [
            AdCampaign(id="SHP-ADS-1", channel=self.channel, name="Shopee Ads — Carregador",
                       status="ativa", spend=round(80 * f("c1"), 2),
                       impressions=int(12000 * f("i1")), clicks=int(520 * f("k1")),
                       conversions=int(40 * f("cv1")), revenue=round(820 * f("r1"), 2)),
        ]
        return ChannelSnapshot(
            channel=self.channel, reputation="verde", late_shipment_rate=1.2,
            unanswered_questions=2, products=products, campaigns=campaigns,
            orders=_orders(self.channel, day, revenue, len(products) and
                           sum(p.units_sold_today for p in products)),
        )

    def _mercado_livre(self, day: str) -> ChannelSnapshot:
        f = lambda k, lo=0.8, hi=1.2: _factor(day, f"ml:{k}", lo, hi)  # noqa: E731
        products = [
            Product(sku="MLB-1001", title="Smartwatch Fit Pro 2 — Tela AMOLED",
                    channel=self.channel, price=219.90, stock=25, status="ativo",
                    images=8, rating=4.7, reviews=540, visits=int(1300 * f("v1")),
                    units_sold_today=int(11 * f("s1")), ctr=2.8,
                    conversion_rate=0.9, ranking=5, description_length=900),
            # Queda forte de impressões (vendas despencando dia a dia).
            Product(sku="MLB-1002", title="Mochila Antifurto USB Executiva",
                    channel=self.channel, price=149.90, stock=60, status="ativo",
                    images=6, rating=4.4, reviews=210, visits=int(180 * f("v2", 0.4, 0.7)),
                    units_sold_today=int(2 * f("s2", 0.3, 0.6)), ctr=1.1,
                    conversion_rate=1.0, ranking=44, description_length=520),
        ]
        revenue = sum(p.revenue_today for p in products)
        return ChannelSnapshot(
            channel=self.channel,
            reputation="amarelo",            # reputação caindo
            late_shipment_rate=8.6,          # acima do limite saudável (~5%)
            unanswered_questions=14,         # perguntas acumuladas
            products=products,
            campaigns=[
                AdCampaign(id="ML-ADS-1", channel=self.channel,
                           name="Product Ads — Smartwatch", status="ativa",
                           spend=round(140 * f("c1"), 2), impressions=int(22000 * f("i1")),
                           clicks=int(610 * f("k1")), conversions=int(18 * f("cv1")),
                           revenue=round(3950 * f("r1"), 2)),
            ],
            orders=_orders(self.channel, day, revenue,
                           sum(p.units_sold_today for p in products)),
        )

    def _amazon(self, day: str) -> ChannelSnapshot:
        f = lambda k, lo=0.8, hi=1.2: _factor(day, f"amz:{k}", lo, hi)  # noqa: E731
        products = [
            # Buy Box perdida + preço acima da concorrência (alerta crítico).
            Product(sku="AMZ-2001", title="Liquidificador Power 1200W 12 velocidades",
                    channel=self.channel, price=329.90, stock=18, status="ativo",
                    images=7, rating=4.5, reviews=880, visits=int(540 * f("v1")),
                    units_sold_today=int(2 * f("s1", 0.3, 0.6)), ctr=1.4,
                    conversion_rate=0.5, ranking=22, has_buybox=False,
                    description_length=1100),
            # Avaliações negativas recentes derrubaram a nota.
            Product(sku="AMZ-2002", title="Air Fryer Digital 5L Premium",
                    channel=self.channel, price=389.90, stock=33, status="ativo",
                    images=9, rating=3.4, reviews=64, visits=int(700 * f("v2")),
                    units_sold_today=int(6 * f("s2")), ctr=2.0,
                    conversion_rate=1.2, ranking=14, has_buybox=True,
                    description_length=950),
        ]
        revenue = sum(p.revenue_today for p in products)
        return ChannelSnapshot(
            channel=self.channel, reputation="verde", late_shipment_rate=2.1,
            unanswered_questions=0, products=products,
            campaigns=[
                # Sponsored Products com CPA muito alto (queimando verba).
                AdCampaign(id="AMZ-SP-1", channel=self.channel,
                           name="Sponsored Products — Air Fryer", status="ativa",
                           spend=round(260 * f("c1"), 2), impressions=int(18000 * f("i1")),
                           clicks=int(430 * f("k1")), conversions=int(7 * f("cv1")),
                           revenue=round(2730 * f("r1"), 2)),
            ],
            orders=_orders(self.channel, day, revenue,
                           sum(p.units_sold_today for p in products)),
        )
