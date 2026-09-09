"""SearXNG provider — JSON API with HTML fallback, news detection, engine pinning."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import get_config
from app.providers.base import NetworkError, ParseError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15.0
WEB_UA = "Mozilla/5.0 (compatible; SableBot/1.0)"
NEWS_HINTS = ("news", "nyheter", "headlines", "breaking", "latest", "today", "idag")

SAFESEARCH_MAP = {"off": 0, "moderate": 1, "strict": 2}


def _get_instance() -> str:
    cfg = get_config()
    return cfg.get("providers", {}).get("searxng", {}).get("url", "http://localhost:8080").rstrip("/")


def _safesearch_val() -> int:
    ss = get_config().get("safesearch", "moderate")
    return SAFESEARCH_MAP.get(ss, 1)


def _general_engines() -> str:
    return get_config().get("providers", {}).get("searxng", {}).get("general_engines", "bing,mojeek,presearch")


def _is_news_query(query: str, time_filter: str | None) -> bool:
    if time_filter:
        return True
    return any(h in query.lower() for h in NEWS_HINTS)


def _parse_json_results(results: list[dict], count: int) -> list[dict[str, Any]]:
    out = []
    for r in results[:count]:
        url = r.get("url", "")
        if not url:
            continue
        out.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("content", ""),
        })
    return out


async def searxng_search(
    query: str,
    count: int = 10,
    time_filter: str | None = None,
    categories: str = "general",
) -> list[dict[str, Any]]:
    instance = _get_instance()
    headers = {"User-Agent": WEB_UA}
    is_news = _is_news_query(query, time_filter) and categories == "general"
    engines = _general_engines()
    ss = _safesearch_val()

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": "en",
        "safesearch": ss,
    }

    if is_news:
        params["categories"] = "news"
        if time_filter in ("day", "week", "month", "year"):
            params["time_range"] = "week" if time_filter in ("day", "week") else time_filter
    else:
        params["categories"] = categories
        if categories == "general" and engines:
            params["engines"] = engines

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        # Attempt chain: original → drop news → drop language → drop engines
        attempts = [params]

        if is_news:
            fb = dict(params)
            fb["categories"] = "general"
            if engines:
                fb["engines"] = engines
            attempts.append(fb)

        # Drop language
        fb2 = dict(attempts[-1])
        fb2.pop("language", None)
        attempts.append(fb2)

        # Drop pinned engines
        if attempts[-1].get("engines"):
            fb3 = dict(attempts[-1])
            fb3.pop("engines", None)
            attempts.append(fb3)

        last_data: dict = {}
        for attempt_params in attempts:
            try:
                resp = await client.get(f"{instance}/search", params=attempt_params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                last_data = data
                parsed = _parse_json_results(data.get("results", []), count)
                if parsed:
                    logger.info("SearXNG returned %d results for: %s", len(parsed), query)
                    return parsed
            except httpx.HTTPStatusError as e:
                raise NetworkError(f"SearXNG HTTP {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise NetworkError(f"SearXNG connection failed: {e}") from e
            except ValueError as e:
                raise ParseError(f"SearXNG JSON parse error: {e}") from e

        # All JSON attempts returned empty — try HTML fallback
        unresponsive = last_data.get("unresponsive_engines") if isinstance(last_data, dict) else None
        if unresponsive:
            logger.info("SearXNG unresponsive engines for %r: %s", query, unresponsive)

        html_results = await _searxng_html_fallback(client, instance, query, count, ss)
        if html_results:
            logger.info("SearXNG HTML fallback returned %d results for: %s", len(html_results), query)
        return html_results


async def _searxng_html_fallback(
    client: httpx.AsyncClient, instance: str, query: str, count: int, safesearch: int
) -> list[dict[str, Any]]:
    try:
        resp = await client.get(
            f"{instance}/search",
            params={"q": query, "language": "en", "safesearch": safesearch},
            headers={"User-Agent": WEB_UA},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for article in soup.find_all("article", class_="result")[:count]:
            a_tag = article.find("a", class_="url_header") or article.find("h3", {}).find("a") if article.find("h3") else None
            if not a_tag:
                continue
            url = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)
            snippet_el = article.find("p", class_="content")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if url:
                results.append({"title": title, "url": url, "snippet": snippet})
        return results
    except Exception as e:
        logger.warning("SearXNG HTML fallback failed: %s", e)
        return []
