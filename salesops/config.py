"""Configuração do agente, lida a partir de variáveis de ambiente / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # carregamento opcional do .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv não instalado; seguimos só com o ambiente
    pass

from .models import Channel


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    client_name: str = "Loja"
    channels: list[str] = field(default_factory=Channel.all)
    model: str = "claude-opus-4-8"
    anthropic_api_key: str | None = None
    drop_threshold_pct: float = 20.0
    data_dir: str = "data"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            client_name=os.getenv("SALESOPS_CLIENT", "Loja").strip() or "Loja",
            channels=_split(os.getenv("SALESOPS_CHANNELS", "")) or Channel.all(),
            model=os.getenv("SALESOPS_MODEL", "claude-opus-4-8").strip()
            or "claude-opus-4-8",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            drop_threshold_pct=float(os.getenv("SALESOPS_DROP_THRESHOLD", "20") or 20),
            data_dir=os.getenv("SALESOPS_DATA_DIR", "data").strip() or "data",
        )


def get_settings() -> Settings:
    return Settings.from_env()
