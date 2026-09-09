"""Brave Search API v1 provider — multi-key rotation on 429."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_config
from app.providers.base import AuthError, NetworkError, ParseError, RateLimitError

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15.0


def _get_keys() -> list[str]:
    return get_config().get("providers", {}).get("brave", {}).get("api_keys", [])


async def brave_search(
    query: str, count: int = 10, time_filter: str | None = None
) -> list[dict[str, Any]]:
    keys = _get_keys()
    if not keys:
        raise AuthError("No Brave API keys configured")

    freshness = None
    if time_filter:
        freshness_map = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}
        freshness = freshness_map.get(time_filter)

    for attempt, api_key in enumerate(keys):
        params: dict[str, Any] = {"q": query, "count": min(count, 20)}
        if freshness:
            params["freshness"] = freshness

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                )
                if resp.status_code == 429:
                    if attempt < len(keys) - 1:
                        logger.info("Brave 429 on key %d/%d, rotating...", attempt + 1, len(keys))
                        continue
                    raise RateLimitError("Brave rate limited (all keys exhausted)")
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                })
            logger.info("Brave returned %d results for: %s (key %d/%d)", len(results), query, attempt + 1, len(keys))
            return results

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"Brave HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Brave connection failed: {e}") from e
        except ValueError as e:
            raise ParseError(f"Brave JSON parse error: {e}") from e

    return []
