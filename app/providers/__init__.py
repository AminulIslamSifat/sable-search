"""Provider registry and dispatcher."""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_config
from app.providers.base import AuthError, RateLimitError, SearchError

logger = logging.getLogger(__name__)

PROVIDER_INFO: dict[str, dict[str, Any]] = {
    "searxng": {"label": "SearXNG", "needs_key": False, "needs_url": True},
    "brave": {"label": "Brave Search", "needs_key": True, "needs_url": False},
    "duckduckgo": {"label": "DuckDuckGo", "needs_key": False, "needs_url": False},
    "google_pse": {"label": "Google PSE", "needs_key": True, "needs_url": False},
    "tavily": {"label": "Tavily", "needs_key": True, "needs_url": False},
    "serper": {"label": "Serper", "needs_key": True, "needs_url": False},
}


def _is_provider_configured(name: str) -> bool:
    cfg = get_config()
    info = PROVIDER_INFO.get(name)
    if not info:
        return False
    prov_cfg = cfg.get("providers", {}).get(name, {})
    if info["needs_url"]:
        url = prov_cfg.get("url", "")
        if not url:
            return False
    if info["needs_key"]:
        keys = prov_cfg.get("api_keys", [])
        if not keys:
            return False
    return True


async def search(
    query: str,
    count: int = 10,
    provider: str | None = None,
    time_filter: str | None = None,
    categories: str = "general",
) -> tuple[list[dict[str, Any]], str, bool]:
    """
    Run search with fallback chain.
    Returns (results, provider_used, fallback_was_used).
    """
    cfg = get_config()
    primary = provider or cfg.get("default_provider", "searxng")
    fallback_chain = cfg.get("fallback_chain", [])

    # Build ordered list: primary first, then fallbacks
    chain = [primary] + [p for p in fallback_chain if p != primary]

    last_error: Exception | None = None
    for i, prov_name in enumerate(chain):
        if not _is_provider_configured(prov_name):
            logger.debug("Provider %s not configured, skipping", prov_name)
            continue

        try:
            results = await _call_provider(prov_name, query, count, time_filter, categories)
            if results:
                return results, prov_name, i > 0
            # Empty results — try next in chain
            logger.info("Provider %s returned 0 results for %r, trying next", prov_name, query)
        except RateLimitError as e:
            logger.warning("Provider %s rate-limited: %s", prov_name, e)
            last_error = e
            continue
        except SearchError as e:
            logger.warning("Provider %s failed: %s", prov_name, e)
            last_error = e
            continue
        except Exception as e:
            logger.error("Provider %s unexpected error: %s", prov_name, e)
            last_error = e
            continue

    # All providers exhausted
    logger.error("All providers failed for query %r. Last error: %s", query, last_error)
    return [], primary, False


async def _call_provider(
    name: str,
    query: str,
    count: int,
    time_filter: str | None,
    categories: str,
) -> list[dict[str, Any]]:
    """Dispatch to the correct provider function."""
    if name == "searxng":
        from app.providers.searxng import searxng_search
        return await searxng_search(query, count, time_filter, categories)
    elif name == "brave":
        from app.providers.brave import brave_search
        return await brave_search(query, count, time_filter)
    elif name == "duckduckgo":
        from app.providers.duckduckgo import duckduckgo_search
        return await duckduckgo_search(query, count)
    elif name == "google_pse":
        from app.providers.google_pse import google_pse_search
        return await google_pse_search(query, count, time_filter)
    elif name == "tavily":
        from app.providers.tavily import tavily_search
        return await tavily_search(query, count, time_filter)
    elif name == "serper":
        from app.providers.serper import serper_search
        return await serper_search(query, count, time_filter)
    else:
        raise SearchError(f"Unknown provider: {name}")
