"""Result ranking: score by relevance, domain authority, recency."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Domain authority boosts
_AUTHORITY_DOMAINS = {
    ".edu": 1.5,
    ".gov": 1.5,
    ".org": 1.2,
    "wikipedia.org": 1.8,
    "github.com": 1.3,
    "stackoverflow.com": 1.4,
    "arxiv.org": 1.5,
    "docs.python.org": 1.6,
}


def _title_score(title: str, query: str) -> float:
    if not title or not query:
        return 0.0
    t = title.lower()
    q = query.lower()
    # Exact phrase match
    if q in t:
        return 3.0
    # Word overlap
    q_words = set(q.split())
    t_words = set(t.split())
    if not q_words:
        return 0.0
    overlap = len(q_words & t_words)
    return (overlap / len(q_words)) * 2.0


def _snippet_score(snippet: str, query: str) -> float:
    if not snippet or not query:
        return 0.0
    s = snippet.lower()
    q = query.lower()
    if q in s:
        return 1.5
    q_words = set(q.split())
    s_words = set(re.findall(r"\w+", s))
    if not q_words:
        return 0.0
    overlap = len(q_words & s_words)
    return (overlap / len(q_words)) * 1.0


def _domain_score(url: str) -> float:
    if not url:
        return 0.0
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return 0.0

    for suffix, boost in _AUTHORITY_DOMAINS.items():
        if host.endswith(suffix) or host == suffix.lstrip("."):
            return boost
    return 1.0  # neutral


def rank_results(results: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not results:
        return results

    for r in results:
        title_s = _title_score(r.get("title", ""), query)
        snippet_s = _snippet_score(r.get("snippet", ""), query)
        domain_s = _domain_score(r.get("url", ""))

        # Base score
        score = title_s + snippet_s
        # Apply domain multiplier
        score *= domain_s

        # Penalty for empty fields
        if not r.get("title"):
            score -= 1.0
        if not r.get("snippet"):
            score -= 0.5

        r["score"] = round(max(score, 0.0), 2)

    # Sort descending by score
    results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)

    return deduped
