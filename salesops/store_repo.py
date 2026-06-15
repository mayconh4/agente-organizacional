"""Repositório de lojas cadastradas (nome, canal e credenciais de API).

Persiste em um arquivo JSON. O caminho vem de SALESOPS_STORE_FILE (no Hugging
Face Spaces, aponte para /data/stores.json com armazenamento persistente).
As credenciais NUNCA são devolvidas ao front — só metadados e quais campos
estão preenchidos.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

_LOCK = threading.Lock()


def _store_path() -> str:
    return os.getenv("SALESOPS_STORE_FILE", os.path.join("data", "stores.json"))


def _load_all() -> list[dict]:
    path = _store_path()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return []


def _save_all(stores: list[dict]) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(stores, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _public(store: dict) -> dict:
    """Versão sem segredos, para o front."""
    creds = store.get("credentials", {})
    return {
        "id": store["id"],
        "name": store["name"],
        "channel": store["channel"],
        "created_at": store.get("created_at"),
        "credential_keys": sorted(k for k, v in creds.items() if v),
    }


def list_stores() -> list[dict]:
    return [_public(s) for s in _load_all()]


def get_store(store_id: str) -> dict | None:
    """Registro completo (com credenciais) — uso interno do backend."""
    return next((s for s in _load_all() if s["id"] == store_id), None)


def add_store(name: str, channel: str, credentials: dict) -> dict:
    store = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip() or "Loja",
        "channel": channel,
        "credentials": {k: v for k, v in (credentials or {}).items() if v},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with _LOCK:
        stores = _load_all()
        stores.append(store)
        _save_all(stores)
    return _public(store)


def update_credentials(store_id: str, credentials: dict) -> dict | None:
    with _LOCK:
        stores = _load_all()
        for s in stores:
            if s["id"] == store_id:
                s["credentials"] = {k: v for k, v in (credentials or {}).items() if v}
                _save_all(stores)
                return _public(s)
    return None


def delete_store(store_id: str) -> bool:
    with _LOCK:
        stores = _load_all()
        new = [s for s in stores if s["id"] != store_id]
        if len(new) == len(stores):
            return False
        _save_all(new)
    return True
