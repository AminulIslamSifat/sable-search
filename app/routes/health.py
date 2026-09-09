"""Health and provider info routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_config
from app.models import HealthResponse, ProviderInfo
from app.providers import PROVIDER_INFO, _is_provider_configured

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    providers: dict[str, ProviderInfo] = {}
    for name, info in PROVIDER_INFO.items():
        configured = _is_provider_configured(name)
        prov_cfg = get_config().get("providers", {}).get(name, {})
        has_key = bool(prov_cfg.get("api_keys", []))
        has_url = bool(prov_cfg.get("url", ""))
        providers[name] = ProviderInfo(
            name=name,
            label=info["label"],
            needs_key=info["needs_key"],
            needs_url=info["needs_url"],
            has_key=has_key,
            has_url=has_url,
            configured=configured,
        )
    return HealthResponse(status="ok", providers=providers)


@router.get("/providers")
async def list_providers() -> list[dict]:
    cfg = get_config()
    default = cfg.get("default_provider", "searxng")
    result = []
    for name, info in PROVIDER_INFO.items():
        configured = _is_provider_configured(name)
        result.append({
            "name": name,
            "label": info["label"],
            "configured": configured,
            "is_default": name == default,
            "needs_key": info["needs_key"],
            "needs_url": info["needs_url"],
        })
    return result
