"""Pydantic models for request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    score: float = 0.0


class SearchMeta(BaseModel):
    response_time_ms: int = 0
    fallback_used: bool = False


class SearchResponse(BaseModel):
    query: str
    provider_used: str
    results_count: int
    cached: bool = False
    results: list[SearchResult] = Field(default_factory=list)
    meta: SearchMeta = Field(default_factory=SearchMeta)


class ProviderInfo(BaseModel):
    name: str
    label: str
    needs_key: bool
    needs_url: bool
    has_key: bool = False
    has_url: bool = False
    configured: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    providers: dict[str, ProviderInfo] = Field(default_factory=dict)


class ConfigUpdateRequest(BaseModel):
    default_provider: Optional[str] = None
    safesearch: Optional[str] = None
    result_count: Optional[int] = None
    fallback_chain: Optional[list[str]] = None
    searxng_url: Optional[str] = None
    brave_api_keys: Optional[list[str]] = None
    google_pse_api_keys: Optional[list[str]] = None
    google_pse_cx: Optional[str] = None
    tavily_api_keys: Optional[list[str]] = None
    serper_api_keys: Optional[list[str]] = None
