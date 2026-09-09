"""Google Custom Search JSON API provider."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_config
from app.providers.base import AuthError, NetworkError, ParseError, RateLimitError

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15.0
SAFESEARCH_MAP = {"off": "off", "moderate": "medium", "strict": "high"}


def _get_keys() -> list[str]:
    return get_config().get("providers", {}).get("google_pse", {}).get("api_keys", [])


def _get_cx() -> str:
    return get_config().get("providers", {}).get("google_pse", {}).get("cx", "")


async def google_pse_search(
    query: str, count: int = 10, time_filter: str | None = None
) -> list[dict[str, Any]]:
    keys = _get_keys()
    if not keys:
        raise AuthError("No Google PSE API keys configured")
    cx = _get_cx()
    if not cx:
        raise AuthError("Google PSE CX not configured")

    ss = get_config().get("safesearch", "moderate")
    safe_val = SAFESEARCH_MAP.get(ss, "medium")

    date_restrict = None
    if time_filter:
        dr_map = {"day": "d1", "week": "w1", "month": "m1", "year": "y1"}
        date_restrict = dr_map.get(time_filter)

    for attempt, api_key in enumerate(keys):
        params: dict[str, Any] = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(count, 10),
            "safe": safe_val,
        }
        if date_restrict:
            params["dateRestrict"] = date_restrict

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params=params,
                )
                if resp.status_code == 429:
                    if attempt < len(keys) - 1:
                        logger.info("Google PSE 429 on key %d/%d, rotating...", attempt + 1, len(keys))
                        continue
                    raise RateLimitError("Google PSE rate limited (all keys exhausted)")
                resp.raise_for_status()
                data = resp.json()

            results = []
            for item in data.get("items", [])[:count]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            logger.info("Google PSE returned %d results for: %s", len(results), query)
            return results

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise NetworkError(f"Google PSE HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"Google PSE connection failed: {e}") from e
        except ValueError as e:
            raise ParseError(f"Google PSE JSON parse error: {e}") from e

    return []
