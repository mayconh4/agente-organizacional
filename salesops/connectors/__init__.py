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
    """Retorna (conector, usando_dados_reais) para o canal (credenciais via env)."""
    connector = _real_connector(channel)
    if connector is not None and connector.is_configured():
        return connector, True
    return SampleConnector(channel), False


def build_connector(channel: str, credentials: dict | None) -> Connector:
    """Constrói o conector real do canal a partir de credenciais explícitas.

    Usado pelo backend para falar com a API de cada loja cadastrada.
    """
    c = credentials or {}
    if channel == Channel.MERCADO_LIVRE:
        from .mercadolivre import MercadoLivreConnector

        return MercadoLivreConnector(
            access_token=c.get("access_token"), seller_id=c.get("seller_id")
        )
    if channel == Channel.SHOPEE:
        from .shopee import ShopeeConnector

        return ShopeeConnector(
            partner_id=c.get("partner_id"), partner_key=c.get("partner_key"),
            shop_id=c.get("shop_id"), access_token=c.get("access_token"),
            host=c.get("host"),
        )
    if channel == Channel.AMAZON:
        from .amazon import AmazonConnector

        return AmazonConnector(
            lwa_client_id=c.get("lwa_client_id"),
            lwa_client_secret=c.get("lwa_client_secret"),
            refresh_token=c.get("refresh_token"),
            spapi_endpoint=c.get("spapi_endpoint"),
            marketplace_id=c.get("marketplace_id"),
        )
    raise ConnectorError(f"Canal desconhecido: {channel}")


# Campos de credencial exigidos por canal (usado pelo formulário do front).
CREDENTIAL_FIELDS = {
    Channel.MERCADO_LIVRE: [
        {"key": "access_token", "label": "Access Token (OAuth2)", "required": True},
        {"key": "seller_id", "label": "Seller ID (opcional)", "required": False},
    ],
    Channel.SHOPEE: [
        {"key": "partner_id", "label": "Partner ID", "required": True},
        {"key": "partner_key", "label": "Partner Key", "required": True},
        {"key": "shop_id", "label": "Shop ID", "required": True},
        {"key": "access_token", "label": "Access Token", "required": True},
        {"key": "host", "label": "Host da API (opcional)", "required": False},
    ],
    Channel.AMAZON: [
        {"key": "lwa_client_id", "label": "LWA Client ID", "required": True},
        {"key": "lwa_client_secret", "label": "LWA Client Secret", "required": True},
        {"key": "refresh_token", "label": "Refresh Token", "required": True},
        {"key": "spapi_endpoint", "label": "Endpoint SP-API (opcional)", "required": False},
        {"key": "marketplace_id", "label": "Marketplace ID (opcional)", "required": False},
    ],
}


__all__ = [
    "Connector",
    "ConnectorError",
    "get_connector",
    "build_connector",
    "CREDENTIAL_FIELDS",
    "SampleConnector",
]
