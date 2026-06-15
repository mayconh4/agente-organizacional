"""Testes do pipeline com dados de exemplo (sem rede, sem chave de API)."""
from __future__ import annotations

from salesops.config import Settings
from salesops.connectors.sample import SampleConnector
from salesops.engine import auditor, detector, metrics, reporter
from salesops.models import Channel, Severity, StoreSnapshot


def _store(day: str) -> StoreSnapshot:
    channels = [SampleConnector(c).fetch_snapshot(day) for c in Channel.all()]
    return StoreSnapshot(client="Loja Teste", snapshot_date=day, channels=channels)


def test_sample_connector_has_products():
    snap = SampleConnector(Channel.SHOPEE).fetch_snapshot("2026-06-14")
    assert snap.is_sample
    assert len(snap.products) >= 3
    assert snap.revenue_today >= 0


def test_auditor_finds_planted_issues():
    issues = auditor.audit(_store("2026-06-14"))
    messages = " ".join(i.message.lower() for i in issues)
    assert "estoque zerado" in messages          # SHP-001
    assert "sem foto" in messages                # SHP-002
    assert "buy box perdida" in messages         # AMZ-2001
    assert any(i.severity == Severity.CRITICA for i in issues)
    # Mercado Livre com reputação amarela deve gerar alerta de conta.
    assert any(i.area == "conta" and i.channel == Channel.MERCADO_LIVRE for i in issues)


def test_health_score_penalizes_issues():
    issues = auditor.audit(_store("2026-06-14"))
    score = metrics.health_score(issues)
    assert 0 <= score < 100  # há problemas plantados, então < 100


def test_metrics_link_previous_day():
    store = _store("2026-06-14")
    prev = {("receita", "geral"): 100.0}
    ms = metrics.compute_metrics(store, prev)
    geral = next(m for m in ms if m.name == "receita" and m.channel == "geral")
    assert geral.previous == 100.0
    assert geral.delta_pct is not None


def test_detector_flags_drop():
    store = _store("2026-06-14")
    ms = metrics.compute_metrics(store)
    # Receita anterior bem maior força uma anomalia de queda.
    for m in ms:
        if m.name == "receita" and m.channel == "geral":
            m.previous = m.value * 3
    anomalies = detector._metric_anomalies(ms, threshold=20.0)
    assert any(a.metric == "receita" for a in anomalies)


def test_rule_based_report_has_sections():
    store = _store("2026-06-14")
    issues = auditor.audit(store)
    ms = metrics.compute_metrics(store)
    anomalies = detector.detect(store, ms, None)
    ctx = reporter.build_context(
        store, issues, ms, anomalies,
        metrics.health_score(issues),
        {c.channel: 80 for c in store.channels}, [],
    )
    md = reporter._rule_based_report(ctx)
    assert "# Relatório diário" in md
    assert "## 🚨 Alertas críticos" in md
    assert "## ✅ Ações recomendadas hoje" in md


def test_full_run_offline(tmp_path):
    from salesops.brain import run_daily

    settings = Settings(
        client_name="Loja Teste",
        channels=Channel.all(),
        anthropic_api_key=None,            # força o gerador por regras
        data_dir=str(tmp_path),
    )
    # Dois dias: o segundo deve enxergar histórico e poder detectar variação.
    run_daily(settings, day="2026-06-13")
    result = run_daily(settings, day="2026-06-14")

    assert result.engine == "regras"
    assert "Relatório diário" in result.report_markdown
    assert result.report_path.endswith("2026-06-14.md")
    assert set(result.sample_channels) == set(Channel.all())
