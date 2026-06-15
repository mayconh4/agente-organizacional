"""Camada 4 — Detector de anomalias.

Compara o dia atual com o histórico (métricas e vendas por produto) e levanta
mudanças bruscas: quedas de receita/ROAS, produtos que despencaram, e itens que
zeraram estoque depois de vender. As anomalias alimentam o diagnóstico.
"""
from __future__ import annotations

from ..models import Anomaly, Metric, Severity, StoreSnapshot


def detect(
    store: StoreSnapshot,
    metrics: list[Metric],
    previous_store: StoreSnapshot | None,
    drop_threshold_pct: float = 20.0,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    anomalies.extend(_metric_anomalies(metrics, drop_threshold_pct))
    if previous_store is not None:
        anomalies.extend(_product_anomalies(store, previous_store, drop_threshold_pct))
    anomalies.sort(key=lambda a: Severity.ORDER.get(a.severity, 9))
    return anomalies


def _metric_anomalies(metrics: list[Metric], threshold: float) -> list[Anomaly]:
    out: list[Anomaly] = []
    watch = {"receita", "roas", "pedidos"}
    for m in metrics:
        if m.name not in watch or m.delta_pct is None:
            continue
        if m.delta_pct <= -threshold:
            sev = Severity.CRITICA if m.delta_pct <= -(threshold * 2) else Severity.ALTA
            scope = "geral" if m.channel == "geral" else m.channel
            out.append(Anomaly(
                severity=sev, channel=scope, entity=scope,
                metric=m.name, change_pct=m.delta_pct,
                message=f"{m.label} caiu {abs(m.delta_pct):.0f}% vs. o dia anterior "
                        f"({_fmt(m.previous, m.unit)} → {_fmt(m.value, m.unit)}).",
            ))
    return out


def _product_anomalies(
    store: StoreSnapshot, previous: StoreSnapshot, threshold: float
) -> list[Anomaly]:
    out: list[Anomaly] = []
    prev_index = {
        (ch.channel, p.sku): p
        for ch in previous.channels for p in ch.products
    }
    for ch in store.channels:
        for p in ch.products:
            old = prev_index.get((ch.channel, p.sku))
            if old is None:
                continue
            # Queda forte de vendas em produto que tinha volume.
            if old.units_sold_today >= 5 and p.units_sold_today < old.units_sold_today:
                drop = 100 * (old.units_sold_today - p.units_sold_today) / old.units_sold_today
                if drop >= threshold:
                    out.append(Anomaly(
                        severity=Severity.CRITICA if drop >= threshold * 2 else Severity.ALTA,
                        channel=ch.channel, entity=p.sku, metric="vendas",
                        change_pct=round(-drop, 1),
                        message=f"'{p.title}' vendeu {old.units_sold_today}→"
                                f"{p.units_sold_today} un (-{drop:.0f}%).",
                    ))
            # Zerou estoque depois de estar vendendo.
            if p.stock <= 0 < old.stock and old.units_sold_today > 0:
                out.append(Anomaly(
                    severity=Severity.CRITICA, channel=ch.channel, entity=p.sku,
                    metric="estoque",
                    message=f"'{p.title}' zerou o estoque (vinha vendendo).",
                ))
    return out


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "R$":
        return f"R$ {value:,.2f}"
    if unit == "x":
        return f"{value:.2f}x"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{value:g} {unit}".strip()
