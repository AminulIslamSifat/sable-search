"""DuckDuckGo HTML scraping provider — Chrome UA required, 4s throttle."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import unquote, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from app.config import get_config
from app.providers.base import NetworkError, ParseError, RateLimitError

logger = logging.getLogger(__name__)

DDG_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15.0
_last_request_ts: float = 0.0


def _min_interval() -> float:
    return get_config().get("providers", {}).get("duckduckgo", {}).get("min_interval", 4.0)


def _unwrap_ddg_url(raw_url: str) -> str:
    """DDG wraps links in /l/?uddg=... — extract the real URL."""
    if not raw_url:
        return raw_url
    parsed = urlparse(raw_url)
    if "/l/" in parsed.path:
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [None])[0]
        if uddg:
            return unquote(uddg)
    return raw_url


async def duckduckgo_search(query: str, count: int = 10) -> list[dict[str, Any]]:
    global _last_request_ts

    interval = _min_interval()
    now = time.monotonic()
    elapsed = now - _last_request_ts
    if elapsed < interval:
        wait = interval - elapsed
        logger.debug("DDG throttle: waiting %.1fs", wait)
        await asyncio.sleep(wait)

    _last_request_ts = time.monotonic()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": DDG_UA},
            )
            if resp.status_code == 202:
                raise RateLimitError("DDG returned 202 challenge page")
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("DDG rate limited") from e
            raise NetworkError(f"DDG HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise NetworkError(f"DDG connection failed: {e}") from e

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            results: list[dict[str, Any]] = []
            for r in soup.find_all("div", class_="result")[:count]:
                a_tag = r.find("a", class_="result__a")
                if not a_tag:
                    continue
                raw_url = a_tag.get("href", "")
                url = _unwrap_ddg_url(raw_url)
                title = a_tag.get_text(strip=True)
                snip_el = r.find("a", class_="result__snippet") or r.find("span", class_="result__snippet")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                # Clean up snippet artifacts
                snippet = re.sub(r"^.*?\.\.\.\s*", "", snippet, count=1)
                if url:
                    results.append({"title": title, "url": url, "snippet": snippet})
            logger.info("DDG returned %d results for: %s", len(results), query)
            return results
        except Exception as e:
            raise ParseError(f"DDG HTML parse error: {e}") from e
