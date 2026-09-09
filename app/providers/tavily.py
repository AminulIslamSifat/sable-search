"""Tavily search API provider — multi-key rotation on 429."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_config
from app.providers.base import AuthError, NetworkError, ParseError, RateLimitError

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15.0


def _get_keys() -> list[str]:
    return get_config().get("providers", {}).get("tavily", {}).get("api_keys", [])


async def tavily_search(
    query: str, count: int = 10, time_filter: str | None = None
) -> list[dict[str, Any]]:
    keys = _get_keys()
    if not keys:
        raise AuthError("No Tavily API keys configured")

    topic = "general"
    if time_filter in ("day", "week"):
        topic = "news"

    for attempt, api_key in enumerate(keys):
        payload: dict[str, Any] = {
            "api_key": api_key,
            "query": query,
            "max_results": count,
            "include_answer": False,
            "topic": topic,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json=payload,
                )
                if resp.status_code == 429:
                    if attempt < len(keys) - 1:
                        logger.info("Tavily 429 on key %d/%d, rotating...", attempt + 1, len(keys))
                        continue
                    raise RateLimitError("Tavily rate limited (all keys exhausted)")
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("results", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                })
            logger.info("Tavily returned %d results for: %s (key %d/%d)", len(results), query, attempt + 1, len(keys))
            return results

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"Tavily HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Tavily connection failed: {e}") from e
        except ValueError as e:
            raise ParseError(f"Tavily JSON parse error: {e}") from e

    return []
