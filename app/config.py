"""Configuration loader: YAML + SSE_ env var overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_config: dict[str, Any] | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """Map SSE_* env vars to config keys."""
    mapping = {
        "SSE_HOST": ("server", "host"),
        "SSE_PORT": ("server", "port"),
        "SSE_LOG_LEVEL": ("server", "log_level"),
        "SSE_DEFAULT_PROVIDER": ("default_provider",),
        "SSE_RESULT_COUNT": ("result_count",),
        "SSE_SAFESEARCH": ("safesearch",),
        "SSE_SEARXNG_URL": ("providers", "searxng", "url"),
        "SSE_DDG_MIN_INTERVAL": ("providers", "duckduckgo", "min_interval"),
        "SSE_GOOGLE_PSE_CX": ("providers", "google_pse", "cx"),
        "SSE_CACHE_MAX_ENTRIES": ("cache", "max_entries"),
        "SSE_CACHE_DB_PATH": ("cache", "db_path"),
    }

    # API key lists (comma-separated)
    key_mapping = {
        "SSE_BRAVE_API_KEYS": ("providers", "brave", "api_keys"),
        "SSE_GOOGLE_PSE_API_KEYS": ("providers", "google_pse", "api_keys"),
        "SSE_TAVILY_API_KEYS": ("providers", "tavily", "api_keys"),
        "SSE_SERPER_API_KEYS": ("providers", "serper", "api_keys"),
    }

    for env_key, path in mapping.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        target = cfg
        for p in path[:-1]:
            target = target.setdefault(p, {})
        # Type coercion
        if path[-1] == "port" or path[-1] == "result_count" or path[-1] == "max_entries":
            val = int(val)
        elif path[-1] == "min_interval":
            val = float(val)
        target[path[-1]] = val

    for env_key, path in key_mapping.items():
        val = os.environ.get(env_key)
        if val is None:
            continue
        target = cfg
        for p in path[:-1]:
            target = target.setdefault(p, {})
        target[path[-1]] = [k.strip() for k in val.split(",") if k.strip()]

    # Fallback chain from env
    fb = os.environ.get("SSE_FALLBACK_CHAIN")
    if fb:
        cfg["fallback_chain"] = [p.strip() for p in fb.split(",") if p.strip()]

    return cfg


def load_config(path: Path | None = None) -> dict[str, Any]:
    global _config
    if _config is not None:
        return _config

    cfg_path = path or _DEFAULT_CONFIG_PATH
    if cfg_path.exists():
        with open(cfg_path) as f:
            _config = yaml.safe_load(f) or {}
    else:
        _config = {}

    _config = _apply_env_overrides(_config)
    return _config


def get_config() -> dict[str, Any]:
    if _config is None:
        return load_config()
    return _config


def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Runtime config update (does NOT persist to disk)."""
    cfg = get_config()
    _deep_merge(cfg, updates)
    return cfg
