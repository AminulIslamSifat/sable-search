"""SQLite-based search result cache with LRU eviction."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.config import get_config

_conn: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn

    cfg = get_config().get("cache", {})
    db_path = Path(cfg.get("db_path", "search_cache.db"))
    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "key TEXT PRIMARY KEY, "
        "data TEXT NOT NULL, "
        "expires_at REAL NOT NULL, "
        "last_access REAL NOT NULL"
        ")"
    )
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_access ON cache(last_access)")
    _conn.commit()
    return _conn


def _make_key(query: str, provider: str, count: int, time_filter: str | None) -> str:
    raw = f"{query}|{provider}|{count}|{time_filter or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _evict_lru(db: sqlite3.Connection) -> None:
    cfg = get_config().get("cache", {})
    max_entries = int(cfg.get("max_entries", 1000))
    # Delete expired first
    db.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
    # Then evict oldest by last_access if over limit
    row = db.execute("SELECT COUNT(*) FROM cache").fetchone()
    current_count = row[0] if row else 0
    if current_count > max_entries:
        excess = current_count - max_entries
        db.execute(
            "DELETE FROM cache WHERE key IN ("
            "SELECT key FROM cache ORDER BY last_access ASC LIMIT ?"
            ")",
            (excess,),
        )
    db.commit()


def get_cached(
    query: str, provider: str, count: int, time_filter: str | None = None
) -> list[dict[str, Any]] | None:
    db = _get_db()
    key = _make_key(query, provider, count, time_filter)
    now = time.time()
    row = db.execute(
        "SELECT data, expires_at FROM cache WHERE key = ?", (key,)
    ).fetchone()

    if not row:
        return None
    data_str, expires_at = row
    if expires_at < now:
        db.execute("DELETE FROM cache WHERE key = ?", (key,))
        db.commit()
        return None

    # Update last access for LRU
    db.execute("UPDATE cache SET last_access = ? WHERE key = ?", (now, key))
    db.commit()
    return json.loads(data_str)


def set_cached(
    query: str,
    provider: str,
    count: int,
    results: list[dict[str, Any]],
    time_filter: str | None = None,
    is_news: bool = False,
) -> None:
    db = _get_db()
    key = _make_key(query, provider, count, time_filter)
    cfg = get_config().get("cache", {})

    if is_news:
        ttl = int(cfg.get("news_ttl_minutes", 30)) * 60
    else:
        ttl = int(cfg.get("reference_ttl_hours", 24)) * 3600

    now = time.time()
    db.execute(
        "INSERT OR REPLACE INTO cache (key, data, expires_at, last_access) VALUES (?, ?, ?, ?)",
        (key, json.dumps(results), now + ttl, now),
    )
    db.commit()
    _evict_lru(db)


def clear_cache(query: str | None = None) -> int:
    """Clear cache. If query provided, clears all provider variants for that query."""
    db = _get_db()
    if query:
        # Generate keys for all known providers to delete them
        from app.providers import PROVIDER_INFO
        keys_to_delete = []
        for prov in list(PROVIDER_INFO.keys()) + ["auto"]:
            for tf in [None, "day", "week", "month", "year"]:
                for c in [5, 10, 20]:
                    keys_to_delete.append(_make_key(query, prov, c, tf))
        if keys_to_delete:
            placeholders = ",".join("?" * len(keys_to_delete))
            cursor = db.execute(
                f"DELETE FROM cache WHERE key IN ({placeholders})",
                keys_to_delete,
            )
        else:
            cursor = db.execute("DELETE FROM cache")
    else:
        cursor = db.execute("DELETE FROM cache")
    deleted = cursor.rowcount
    db.commit()
    return deleted
