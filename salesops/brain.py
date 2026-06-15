"""Orquestrador do SalesOps AI — costura as 7 camadas em uma execução diária.

Fluxo:
  1. Coleta o snapshot de cada canal (conector real ou dados de exemplo).
  2. Audita os canais (problemas técnicos).
  3. Calcula métricas + liga ao dia anterior (memória) + score de saúde.
  4. Detecta anomalias vs. histórico.
  5. Gera o relatório executivo (Claude ou regras).
  6. Persiste o snapshot do dia e salva o relatório em data/reports/.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date

from .config import Settings
from .connectors import ConnectorError, get_connector
from .engine import auditor, detector, metrics, reporter
from .engine.memory import Memory
from .models import ChannelSnapshot, StoreSnapshot


@dataclass
class RunResult:
    report_markdown: str
    report_path: str
    engine: str                       # "claude" | "regras"
    health: int
    context: dict = field(default_factory=dict)   # dados estruturados (p/ web)
    sample_channels: list[str] = field(default_factory=list)
    failed_channels: list[str] = field(default_factory=list)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "cliente"


def run_daily(settings: Settings, day: str | None = None) -> RunResult:
    day = day or date.today().isoformat()
    memory = Memory(settings.data_dir, settings.client_name)

    channels: list[ChannelSnapshot] = []
    sample_channels: list[str] = []
    failed_channels: list[str] = []

    for channel in settings.channels:
        connector, is_real = get_connector(channel)
        try:
            snapshot = connector.fetch_snapshot(day)
        except ConnectorError:
            # API real falhou: cai para dados de exemplo para não travar o dia.
            from .connectors.sample import SampleConnector

            snapshot = SampleConnector(channel).fetch_snapshot(day)
            failed_channels.append(channel)
            is_real = False
        if not is_real or snapshot.is_sample:
            sample_channels.append(channel)
        channels.append(snapshot)

    store = StoreSnapshot(
        client=settings.client_name, snapshot_date=day, channels=channels
    )

    # Camadas de análise.
    issues = auditor.audit(store)
    previous_metrics = memory.previous_metrics(day)
    day_metrics = metrics.compute_metrics(store, previous_metrics)
    previous_store = memory.previous_snapshot(day)
    anomalies = detector.detect(
        store, day_metrics, previous_store, settings.drop_threshold_pct
    )
    per_channel_health = {
        c.channel: metrics.channel_health(issues, c.channel) for c in store.channels
    }
    # Saúde geral = média das saúdes por canal (evita somar penalidades de
    # canais distintos e produzir um número artificialmente baixo).
    health = (
        round(sum(per_channel_health.values()) / len(per_channel_health))
        if per_channel_health
        else metrics.health_score(issues)
    )

    # Relatório.
    context = reporter.build_context(
        store, issues, day_metrics, anomalies, health,
        per_channel_health, memory.recent_actions(),
    )
    report_md, engine = reporter.generate_report(settings, context)

    # Persistência (memória + relatório em arquivo).
    memory.save_snapshot(store, [m.to_dict() for m in day_metrics])
    report_path = _save_report(settings, day, report_md)

    return RunResult(
        report_markdown=report_md,
        report_path=report_path,
        engine=engine,
        health=health,
        context=context,
        sample_channels=sample_channels,
        failed_channels=failed_channels,
    )


def _save_report(settings: Settings, day: str, markdown: str) -> str:
    out_dir = os.path.join(settings.data_dir, "reports", _slug(settings.client_name))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{day}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(markdown + "\n")
    return path
