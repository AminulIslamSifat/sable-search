"""Search route — the main endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query

from app.cache import get_cached, set_cached
from app.models import SearchMeta, SearchResponse, SearchResult
from app.providers import search
from app.query import parse_query
from app.ranking import rank_results

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    count: int = Query(10, ge=1, le=50, description="Number of results"),
    provider: str | None = Query(None, description="Force specific provider"),
    time_filter: str | None = Query(None, pattern="^(day|week|month|year)$"),
    categories: str = Query("general", pattern="^(general|news|images)$"),
) -> SearchResponse:
    start = time.monotonic()
    parsed = parse_query(q)
    query_str = parsed.cleaned or q

    # Apply parsed hints if not explicitly provided
    effective_time = time_filter or parsed.time_hint
    effective_count = count

    # Check cache first
    effective_provider = provider or "auto"
    cached = get_cached(query_str, effective_provider, effective_count, effective_time)
    if cached is not None:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return SearchResponse(
            query=query_str,
            provider_used="cache",
            results_count=len(cached),
            cached=True,
            results=[SearchResult(**r) for r in cached],
            meta=SearchMeta(response_time_ms=elapsed_ms, fallback_used=False),
        )

    # Run search with fallback chain
    results, prov_used, fallback_used = await search(
        query=query_str,
        count=effective_count,
        provider=provider,
        time_filter=effective_time,
        categories=categories,
    )

    # Rank and deduplicate
    ranked = rank_results(results, query_str)

    # Trim to requested count
    ranked = ranked[:effective_count]

    # Cache results
    if ranked:
        is_news = categories == "news" or bool(effective_time)
        set_cached(query_str, effective_provider, effective_count, ranked, effective_time, is_news)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SearchResponse(
        query=query_str,
        provider_used=prov_used,
        results_count=len(ranked),
        cached=False,
        results=[SearchResult(**r) for r in ranked],
        meta=SearchMeta(response_time_ms=elapsed_ms, fallback_used=fallback_used),
    )
