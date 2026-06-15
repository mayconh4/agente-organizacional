"""Contrato comum a todos os conectores de marketplace."""
from __future__ import annotations

import abc

from ..models import ChannelSnapshot


class ConnectorError(RuntimeError):
    """Falha ao coletar dados de um canal (rede, credenciais, API)."""


class Connector(abc.ABC):
    """Interface de um conector de canal.

    Implementações reais (Shopee, Mercado Livre, Amazon) falam com a API do
    marketplace. Quando não há credenciais configuradas, a fábrica usa o
    SampleConnector no lugar, para que o pipeline rode de ponta a ponta.
    """

    channel: str

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True se há credenciais suficientes para chamar a API real."""

    @abc.abstractmethod
    def fetch_snapshot(self, day: str) -> ChannelSnapshot:
        """Coleta a fotografia do canal para a data (YYYY-MM-DD)."""
