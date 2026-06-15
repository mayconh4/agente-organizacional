"""Camada 3 — Motor de métricas.

Calcula as métricas do dia por canal e consolidadas (receita, pedidos, ticket
médio, investimento e receita de Ads, ROAS), liga cada uma ao valor do dia
anterior (via Memory) e calcula um score de saúde da operação a partir dos
problemas encontrados pelo auditor.
"""
from __future__ import annotations

from ..models import Channel, Issue, Metric, Severity, StoreSnapshot


def compute_metrics(
    store: StoreSnapshot,
    previous: dict[tuple[str, str], float] | None = None,
) -> list[Metric]:
    previous = previous or {}
    metrics: list[Metric] = []

    def add(name: str, label: str, channel: str, value: float, unit: str) -> None:
        m = Metric(name=name, label=label, channel=channel,
                   value=round(value, 2), unit=unit,
                   previous=previous.get((name, channel)))
        metrics.append(m)

    total_rev = total_orders = total_units = 0.0
    total_spend = total_ad_rev = 0.0

    for ch in store.channels:
        rev = ch.revenue_today
        orders = ch.orders_count
        units = ch.units_today
        spend = ch.ad_spend
        ad_rev = ch.ad_revenue

        add("receita", "Receita", ch.channel, rev, "R$")
        add("pedidos", "Pedidos", ch.channel, orders, "un")
        add("ticket_medio", "Ticket médio", ch.channel,
            (rev / orders) if orders else 0.0, "R$")
        if spend:
            add("investimento_ads", "Investimento Ads", ch.channel, spend, "R$")
            add("roas", "ROAS", ch.channel, (ad_rev / spend) if spend else 0.0, "x")

        total_rev += rev
        total_orders += orders
        total_units += units
        total_spend += spend
        total_ad_rev += ad_rev

    add("receita", "Receita total", "geral", total_rev, "R$")
    add("pedidos", "Pedidos", "geral", total_orders, "un")
    add("unidades", "Unidades vendidas", "geral", total_units, "un")
    add("ticket_medio", "Ticket médio", "geral",
        (total_rev / total_orders) if total_orders else 0.0, "R$")
    if total_spend:
        add("investimento_ads", "Investimento Ads", "geral", total_spend, "R$")
        add("roas", "ROAS", "geral",
            (total_ad_rev / total_spend) if total_spend else 0.0, "x")

    return metrics


def health_score(issues: list[Issue]) -> int:
    """Score 0-100: parte de 100 e desconta por severidade dos problemas."""
    penalty = sum(Severity.WEIGHTS.get(i.severity, 0) for i in issues)
    return max(0, min(100, 100 - penalty))


def channel_health(issues: list[Issue], channel: str) -> int:
    return health_score([i for i in issues if i.channel == channel])
