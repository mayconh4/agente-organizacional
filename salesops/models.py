"""Modelos de dados do SalesOps AI.

Estruturas que representam o estado de uma operação comercial multicanal:
produtos, anúncios, pedidos e a "fotografia" (snapshot) diária de cada canal.
Os motores de análise (auditor, métricas, detector) consomem essas estruturas
e produzem achados (Issue, Metric, Anomaly) que alimentam o relatório.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enums simples (strings para facilitar serialização e leitura no relatório)
# --------------------------------------------------------------------------- #
class Channel:
    SHOPEE = "shopee"
    MERCADO_LIVRE = "mercado_livre"
    AMAZON = "amazon"

    LABELS = {
        SHOPEE: "Shopee",
        MERCADO_LIVRE: "Mercado Livre",
        AMAZON: "Amazon",
    }

    @classmethod
    def label(cls, channel: str) -> str:
        return cls.LABELS.get(channel, channel)

    @classmethod
    def all(cls) -> list[str]:
        return [cls.SHOPEE, cls.MERCADO_LIVRE, cls.AMAZON]


class Severity:
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"

    # Peso usado no cálculo do score de saúde da operação.
    WEIGHTS = {CRITICA: 18, ALTA: 9, MEDIA: 4, BAIXA: 1}
    ORDER = {CRITICA: 0, ALTA: 1, MEDIA: 2, BAIXA: 3}


# --------------------------------------------------------------------------- #
# Entidades de catálogo / vendas
# --------------------------------------------------------------------------- #
@dataclass
class Product:
    sku: str
    title: str
    channel: str
    price: float
    stock: int
    status: str = "ativo"            # "ativo" | "pausado"
    images: int = 0                  # quantidade de fotos do anúncio
    rating: Optional[float] = None   # nota média (0-5)
    reviews: int = 0
    visits: int = 0                  # visitas no dia
    units_sold_today: int = 0
    ctr: Optional[float] = None             # % (clique sobre impressão)
    conversion_rate: Optional[float] = None  # % (venda sobre visita)
    ranking: Optional[int] = None    # posição no marketplace (1 = topo)
    has_buybox: Optional[bool] = None  # relevante na Amazon
    description_length: int = 0

    @property
    def revenue_today(self) -> float:
        return round(self.price * self.units_sold_today, 2)


@dataclass
class AdCampaign:
    id: str
    channel: str
    name: str
    status: str           # "ativa" | "pausada"
    spend: float          # investimento no dia (R$)
    impressions: int
    clicks: int
    conversions: int
    revenue: float        # receita atribuída à campanha (R$)

    @property
    def ctr(self) -> Optional[float]:
        if not self.impressions:
            return None
        return round(100 * self.clicks / self.impressions, 2)

    @property
    def cpa(self) -> Optional[float]:
        if not self.conversions:
            return None
        return round(self.spend / self.conversions, 2)

    @property
    def roas(self) -> Optional[float]:
        if not self.spend:
            return None
        return round(self.revenue / self.spend, 2)


@dataclass
class Order:
    id: str
    channel: str
    created_at: str       # data ISO (YYYY-MM-DD)
    total: float
    status: str = "pago"


@dataclass
class ChannelSnapshot:
    """Fotografia de um canal num dia."""
    channel: str
    reputation: Optional[str] = None        # ex.: "verde", "amarelo", "vermelho"
    late_shipment_rate: Optional[float] = None  # % de envios atrasados
    unanswered_questions: int = 0
    is_sample: bool = False                 # True se veio de dados de exemplo
    products: list[Product] = field(default_factory=list)
    campaigns: list[AdCampaign] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)

    # ---- agregados de conveniência ----
    @property
    def revenue_today(self) -> float:
        if self.orders:
            return round(sum(o.total for o in self.orders), 2)
        return round(sum(p.revenue_today for p in self.products), 2)

    @property
    def orders_count(self) -> int:
        return len(self.orders) or sum(p.units_sold_today for p in self.products)

    @property
    def units_today(self) -> int:
        return sum(p.units_sold_today for p in self.products)

    @property
    def ad_spend(self) -> float:
        return round(sum(c.spend for c in self.campaigns), 2)

    @property
    def ad_revenue(self) -> float:
        return round(sum(c.revenue for c in self.campaigns), 2)


@dataclass
class StoreSnapshot:
    """Estado consolidado da loja (todos os canais) num dia."""
    client: str
    snapshot_date: str
    channels: list[ChannelSnapshot] = field(default_factory=list)

    def channel(self, name: str) -> Optional[ChannelSnapshot]:
        return next((c for c in self.channels if c.channel == name), None)

    @property
    def revenue_today(self) -> float:
        return round(sum(c.revenue_today for c in self.channels), 2)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreSnapshot":
        channels = []
        for ch in data.get("channels", []):
            ch = dict(ch)
            ch["products"] = [Product(**p) for p in ch.get("products", [])]
            ch["campaigns"] = [AdCampaign(**c) for c in ch.get("campaigns", [])]
            ch["orders"] = [Order(**o) for o in ch.get("orders", [])]
            channels.append(ChannelSnapshot(**ch))
        return cls(
            client=data["client"],
            snapshot_date=data["snapshot_date"],
            channels=channels,
        )


# --------------------------------------------------------------------------- #
# Achados produzidos pelos motores de análise
# --------------------------------------------------------------------------- #
@dataclass
class Issue:
    """Problema técnico/operacional encontrado pelo auditor."""
    severity: str
    channel: str
    area: str            # "anúncio", "estoque", "campanha", "conta", "catálogo"
    entity: str          # SKU, id de campanha ou "conta"
    message: str
    recommendation: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Metric:
    """Métrica do dia, opcionalmente comparada ao período anterior."""
    name: str            # identificador estável (ex.: "receita")
    label: str           # rótulo legível (ex.: "Receita")
    channel: str         # "geral" ou nome do canal
    value: float
    unit: str            # "R$", "%", "un", "x", ""
    previous: Optional[float] = None

    @property
    def delta_abs(self) -> Optional[float]:
        if self.previous is None:
            return None
        return round(self.value - self.previous, 2)

    @property
    def delta_pct(self) -> Optional[float]:
        if not self.previous:
            return None
        return round(100 * (self.value - self.previous) / self.previous, 1)

    @property
    def trend(self) -> str:
        d = self.delta_pct
        if d is None or abs(d) < 1:
            return "estável"
        return "subindo" if d > 0 else "caindo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "channel": self.channel,
            "value": self.value,
            "unit": self.unit,
            "previous": self.previous,
            "delta_pct": self.delta_pct,
            "trend": self.trend,
        }


@dataclass
class Anomaly:
    """Mudança brusca detectada em relação ao histórico."""
    severity: str
    channel: str
    entity: str
    message: str
    metric: Optional[str] = None
    change_pct: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
