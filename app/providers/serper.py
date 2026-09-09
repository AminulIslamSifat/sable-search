"""Serper.dev API provider — multi-key rotation on 429."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_config
from app.providers.base import AuthError, NetworkError, ParseError, RateLimitError

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15.0


def _get_keys() -> list[str]:
    return get_config().get("providers", {}).get("serper", {}).get("api_keys", [])


async def serper_search(
    query: str, count: int = 10, time_filter: str | None = None
) -> list[dict[str, Any]]:
    keys = _get_keys()
    if not keys:
        raise AuthError("No Serper API keys configured")

    tbs = None
    if time_filter:
        tbs_map = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}
        tbs = tbs_map.get(time_filter)

    for attempt, api_key in enumerate(keys):
        payload: dict[str, Any] = {"q": query, "num": count}
        if tbs:
            payload["tbs"] = tbs

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json=payload,
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 429:
                    if attempt < len(keys) - 1:
                        logger.info("Serper 429 on key %d/%d, rotating...", attempt + 1, len(keys))
                        continue
                    raise RateLimitError("Serper rate limited (all keys exhausted)")
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("organic", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            logger.info("Serper returned %d results for: %s (key %d/%d)", len(results), query, attempt + 1, len(keys))
            return results

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"Serper HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Serper connection failed: {e}") from e
        except ValueError as e:
            raise ParseError(f"Serper JSON parse error: {e}") from e

    return []
