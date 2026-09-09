"""FastAPI application — lifespan, middleware, route registration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_config
from app.providers.base import SearchError
from app.routes import admin, health, proxy, search

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load config (triggers YAML + env var loading)
    cfg = load_config()
    log_level = cfg.get("server", {}).get("log_level", "info").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    logger.info("Sable Search Engine starting — default provider: %s", cfg.get("default_provider", "searxng"))
    yield
    logger.info("Sable Search Engine shutting down")


app = FastAPI(
    title="Sable Search Engine",
    description="Standalone multi-provider search API. Any client can consume this.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins since any tool should be able to hit this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global error handler for search errors
@app.exception_handler(SearchError)
async def search_error_handler(request: Request, exc: SearchError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "query": request.query_params.get("q", ""),
        },
    )


# Register routes
app.include_router(search.router, tags=["search"])
app.include_router(health.router, tags=["health"])
app.include_router(admin.router, tags=["admin"])
app.include_router(proxy.router, tags=["proxy"])


@app.api_route("/", methods=["GET", "HEAD"])
async def root() -> dict:
    return {
        "service": "Sable Search Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "search": "/search?q=your+query",
    }
