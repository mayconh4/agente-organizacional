"""Serviço que monta o dashboard real de uma loja.

Usa as credenciais cadastradas para falar com a API do marketplace (dados
reais), roda os motores de análise (auditor, métricas, detector) e mantém
histórico por loja para calcular variações dia a dia.
"""
from __future__ import annotations

from datetime import date

from .config import Settings
from .connectors import ConnectorError, build_connector
from .engine import auditor, detector, metrics, reporter
from .engine.memory import Memory


def build_dashboard(settings: Settings, store: dict, day: str | None = None) -> dict:
    """Coleta dados reais da loja e devolve o contexto estruturado do painel.

    Levanta ConnectorError se as credenciais forem inválidas ou a API falhar.
    """
    from .models import StoreSnapshot

    day = day or date.today().isoformat()
    connector = build_connector(store["channel"], store.get("credentials"))
    if not connector.is_configured():
        raise ConnectorError("Credenciais incompletas para este canal.")

    snapshot = connector.fetch_snapshot(day)  # pode levantar ConnectorError
    store_snap = StoreSnapshot(
        client=store["name"], snapshot_date=day, channels=[snapshot]
    )

    memory = Memory(settings.data_dir, f"store-{store['id']}")
    previous_metrics = memory.previous_metrics(day)
    previous_snapshot = memory.previous_snapshot(day)

    issues = auditor.audit(store_snap)
    day_metrics = metrics.compute_metrics(store_snap, previous_metrics)
    anomalies = detector.detect(
        store_snap, day_metrics, previous_snapshot, settings.drop_threshold_pct
    )
    health = metrics.channel_health(issues, store["channel"])

    context = reporter.build_context(
        store_snap, issues, day_metrics, anomalies, health,
        {store["channel"]: health}, memory.recent_actions(),
    )
    memory.save_snapshot(store_snap, [m.to_dict() for m in day_metrics])
    context["store_id"] = store["id"]
    context["channel"] = store["channel"]
    return context


def build_report(settings: Settings, store: dict, context: dict) -> dict:
    """Gera o relatório executivo (Claude ou regras) para a loja."""
    markdown, engine = reporter.generate_report(settings, context)
    return {"markdown": markdown, "engine": engine}
