"""Exportação dos dados do agente para o painel web (GitHub Pages).

Gera o `report.json` que o painel estático (docs/index.html) consome. O painel
é 100% estático; toda a inteligência roda aqui, no agente Python. Em produção,
um workflow do GitHub Actions executa o agente e publica o resultado.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .brain import RunResult
from .config import Settings


def build_payload(settings: Settings, result: RunResult) -> dict:
    """Monta o JSON consumido pelo painel a partir do resultado da rodada."""
    ctx = result.context
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "client": ctx.get("cliente", settings.client_name),
        "date": ctx.get("data"),
        "engine": result.engine,
        "health": result.health,
        "channel_health": ctx.get("saude_por_canal", {}),
        "channels_analyzed": ctx.get("canais_analisados", []),
        "metrics": ctx.get("metricas", []),
        "issues": ctx.get("problemas", []),
        "anomalies": ctx.get("anomalias", []),
        "actions_recent": ctx.get("acoes_recentes", []),
        "report_markdown": result.report_markdown,
        "sample_channels": result.sample_channels,
        "failed_channels": result.failed_channels,
    }


def export_web(settings: Settings, result: RunResult, out_dir: str = "docs") -> str:
    """Escreve o report.json no diretório do painel. Retorna o caminho."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(build_payload(settings, result), fh, ensure_ascii=False, indent=2)
    return path
