"""Admin routes: runtime config updates and cache management."""

from __future__ import annotations

import copy

from fastapi import APIRouter

from app.cache import clear_cache
from app.config import get_config, update_config

router = APIRouter()


@router.get("/config")
async def get_current_config() -> dict:
    """Return current runtime config (redacts API keys)."""
    cfg = copy.deepcopy(get_config())
    providers = cfg.get("providers", {})
    for prov_name, prov_cfg in providers.items():
        if isinstance(prov_cfg, dict) and "api_keys" in prov_cfg:
            keys = prov_cfg["api_keys"]
            prov_cfg["api_keys"] = [f"{k[:4]}..." if len(k) > 4 else "***" for k in keys]
    return cfg


@router.post("/config")
async def patch_config(updates: dict) -> dict:
    """Update runtime configuration. Does NOT persist to disk."""
    update_config(updates)
    return {"status": "ok", "message": "Config updated (runtime only)"}


@router.delete("/cache")
async def invalidate_cache(q: str | None = None) -> dict:
    deleted = clear_cache(q)
    return {"status": "ok", "deleted_entries": deleted}
