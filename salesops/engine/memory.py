"""Camada 1 — Memória histórica (Context Engine).

Persiste a fotografia diária de cada cliente e o registro de ações tomadas,
para responder às perguntas-chave do agente: "o que já foi feito?" e "o que
mudou nas últimas 24h?". Armazena em arquivos JSON sob data/history/<cliente>/.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Optional

from ..models import StoreSnapshot


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "cliente"


class Memory:
    def __init__(self, data_dir: str, client: str) -> None:
        self.client = client
        self.base = os.path.join(data_dir, "history", _slug(client))
        os.makedirs(self.base, exist_ok=True)

    # ---- snapshots --------------------------------------------------- #
    def _snapshot_path(self, day: str) -> str:
        return os.path.join(self.base, f"{day}.json")

    def save_snapshot(self, snapshot: StoreSnapshot, metrics: list[dict]) -> None:
        payload = {"snapshot": snapshot.to_dict(), "metrics": metrics}
        with open(self._snapshot_path(snapshot.snapshot_date), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def stored_dates(self) -> list[str]:
        dates = [
            f[:-5]
            for f in os.listdir(self.base)
            if f.endswith(".json") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", f[:-5])
        ]
        return sorted(dates)

    def latest_before(self, day: str) -> Optional[str]:
        prior = [d for d in self.stored_dates() if d < day]
        return prior[-1] if prior else None

    def load(self, day: str) -> Optional[dict[str, Any]]:
        path = self._snapshot_path(day)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def previous_metrics(self, day: str) -> dict[tuple[str, str], float]:
        """Métricas do último dia armazenado antes de `day`: {(name, channel): value}."""
        prev_day = self.latest_before(day)
        if prev_day is None:
            return {}
        data = self.load(prev_day) or {}
        return {
            (m["name"], m["channel"]): m["value"]
            for m in data.get("metrics", [])
        }

    def previous_snapshot(self, day: str) -> Optional[StoreSnapshot]:
        prev_day = self.latest_before(day)
        if prev_day is None:
            return None
        data = self.load(prev_day) or {}
        if "snapshot" not in data:
            return None
        return StoreSnapshot.from_dict(data["snapshot"])

    # ---- registro de ações ------------------------------------------ #
    @property
    def _actions_path(self) -> str:
        return os.path.join(self.base, "actions.jsonl")

    def log_action(self, description: str, channel: str = "geral",
                   day: Optional[str] = None) -> None:
        entry = {
            "date": day or date.today().isoformat(),
            "channel": channel,
            "description": description,
        }
        with open(self._actions_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recent_actions(self, limit: int = 15) -> list[dict[str, Any]]:
        if not os.path.exists(self._actions_path):
            return []
        with open(self._actions_path, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]]
