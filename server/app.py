"""API + servidor de arquivos estáticos do SalesOps AI.

Expõe o cadastro de lojas (com credenciais de API por canal) e o dashboard
com dados reais de cada loja. Serve o front glass em web/.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from salesops import service, store_repo
from salesops.config import get_settings
from salesops.connectors import CREDENTIAL_FIELDS, ConnectorError
from salesops.models import Channel

app = FastAPI(title="SalesOps AI")
settings = get_settings()

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


class StoreIn(BaseModel):
    name: str
    channel: str
    credentials: dict = {}


class CredsIn(BaseModel):
    credentials: dict = {}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "claude": bool(settings.anthropic_api_key)}


@app.get("/api/channels")
def channels() -> list[dict]:
    return [
        {"id": c, "label": Channel.label(c), "fields": CREDENTIAL_FIELDS.get(c, [])}
        for c in Channel.all()
    ]


@app.get("/api/stores")
def list_stores() -> list[dict]:
    return store_repo.list_stores()


@app.post("/api/stores")
def create_store(body: StoreIn) -> dict:
    if body.channel not in Channel.all():
        raise HTTPException(400, "Canal inválido.")
    if not body.name.strip():
        raise HTTPException(400, "Informe o nome da loja.")
    return store_repo.add_store(body.name, body.channel, body.credentials)


@app.put("/api/stores/{store_id}")
def update_store(store_id: str, body: CredsIn) -> dict:
    result = store_repo.update_credentials(store_id, body.credentials)
    if not result:
        raise HTTPException(404, "Loja não encontrada.")
    return result


@app.delete("/api/stores/{store_id}")
def delete_store(store_id: str) -> dict:
    if not store_repo.delete_store(store_id):
        raise HTTPException(404, "Loja não encontrada.")
    return {"deleted": True}


@app.get("/api/stores/{store_id}/dashboard")
def dashboard(store_id: str) -> dict:
    store = store_repo.get_store(store_id)
    if not store:
        raise HTTPException(404, "Loja não encontrada.")
    try:
        return service.build_dashboard(settings, store)
    except ConnectorError as exc:
        raise HTTPException(502, f"Não foi possível buscar dados reais: {exc}")


@app.get("/api/stores/{store_id}/report")
def report(store_id: str) -> dict:
    store = store_repo.get_store(store_id)
    if not store:
        raise HTTPException(404, "Loja não encontrada.")
    try:
        context = service.build_dashboard(settings, store)
    except ConnectorError as exc:
        raise HTTPException(502, f"Não foi possível buscar dados reais: {exc}")
    return service.build_report(settings, store, context)


# Front-end estático (precisa ficar por último para não capturar as rotas /api).
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
