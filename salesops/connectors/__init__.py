"""Fábrica de conectores.

Para cada canal devolve o conector real quando há credenciais; caso contrário,
cai para o SampleConnector (dados de exemplo), de modo que o pipeline sempre
roda de ponta a ponta. O segundo elemento da tupla indica se a fonte é real.

Os conectores reais são importados sob demanda (lazy): o modo de dados de
exemplo funciona mesmo sem a dependência `requests` instalada.
"""
from __future__ import annotations

from ..models import Channel
from .base import Connector, ConnectorError
from .sample import SampleConnector


def _real_connector(channel: str) -> Connector | None:
    try:
        if channel == Channel.SHOPEE:
            from .shopee import ShopeeConnector

            return ShopeeConnector()
        if channel == Channel.MERCADO_LIVRE:
            from .mercadolivre import MercadoLivreConnector

            return MercadoLivreConnector()
        if channel == Channel.AMAZON:
            from .amazon import AmazonConnector

            return AmazonConnector()
    except ImportError:
        # `requests` ausente: seguimos com dados de exemplo.
        return None
    return None


def get_connector(channel: str) -> tuple[Connector, bool]:
    """Retorna (conector, usando_dados_reais) para o canal."""
    connector = _real_connector(channel)
    if connector is not None and connector.is_configured():
        return connector, True
    return SampleConnector(channel), False


__all__ = [
    "Connector",
    "ConnectorError",
    "get_connector",
    "SampleConnector",
]
