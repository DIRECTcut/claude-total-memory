"""
QueryCache — Thread-safe LRU cache with TTL for Claude Memory MCP Server.

Usage:
    from cache import QueryCache

    cache = QueryCache(maxsize=200)

    # On recall/search:
    key = cache.make_key(query="auth", project="myproject", ktype="solution")
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = expensive_search(...)
    cache.put(key, result, ttl=300)

    # On save/update/delete — invalidate:
    cache.invalidate(project="myproject")  # project-specific
    cache.invalidate()                      # clear all

    # Monitoring:
    stats = cache.stats()
    # {"hit_count": 42, "miss_count": 10, "hit_rate": 0.808, "size": 15, "maxsize": 200}
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _CacheEntry:
    """Single cached result with expiration metadata."""

    value: Any
    expires_at: float
    project: str | None = None


class QueryCache:
    """Thread-safe LRU cache with TTL expiration for memory search queries.

    Args:
        maxsize: Maximum number of entries. Oldest accessed entry is evicted
                 when the limit is reached. Defaults to 200.
        default_ttl: Default time-to-live in seconds. Defaults to 300 (5 min).
    """

    def __init__(self, maxsize: int = 200, default_ttl: int = 300) -> None:
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0

    # ── Public API ──────────────────────────────────────────

    @staticmethod
    def make_key(
        query: str,
        project: str | None = None,
        ktype: str | None = None,
        limit: int | None = None,
        detail: str | None = None,
        branch: str | None = None,
        **kwargs,
    ) -> str:
        """Build a deterministic cache key from search parameters.

        Returns a hex digest string that uniquely identifies the query
        combination. Parameters are normalized (stripped, lowered) before
        hashing to reduce near-duplicate cache misses.

        Args:
            query: The search query text.
            project: Optional project filter.
            ktype: Optional knowledge type filter.
            limit: Optional result limit.
            detail: Optional detail level ("summary" or "full").
            branch: Optional git branch filter.
            **kwargs: Additional parameters (e.g. fusion) included in key.

        Returns:
            A 32-character hex digest cache key.
        """
        parts = [
            str(v).strip().lower() if v is not None else ""
            for v in (query, project, ktype, limit, detail, branch)
        ]
        # Include any extra kwargs in deterministic order
        for k in sorted(kwargs):
            v = kwargs[k]
            parts.append(f"{k}={str(v).strip().lower() if v is not None else ''}")
        raw = "|".join(parts)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(self, query_key: str) -> Any | None:
        """Retrieve a cached result by key.

        Moves the entry to the end of the LRU queue on hit.
        Expired entries are evicted transparently.

        Args:
            query_key: Cache key from ``make_key()``.

        Returns:
            The cached result, or ``None`` on miss / expiry.
        """
        with self._lock:
            entry = self._cache.get(query_key)
            if entry is None:
                self._miss_count += 1
                return None

            # Check TTL expiry
            if time.time() > entry.expires_at:
                del self._cache[query_key]
                self._miss_count += 1
                return None

            # LRU: move to end (most recently used)
            self._cache.move_to_end(query_key)
            self._hit_count += 1
            return entry.value

    def put(
        self,
        query_key: str,
        result: Any,
        ttl: int | None = None,
        project: str | None = None,
    ) -> None:
        """Store a result in the cache.

        If the cache is full, the least recently used entry is evicted.

        Args:
            query_key: Cache key from ``make_key()``.
            result: The value to cache.
            ttl: Time-to-live in seconds. Uses ``default_ttl`` if not given.
            project: Optional project tag for targeted invalidation.
        """
        if ttl is None:
            ttl = self._default_ttl

        with self._lock:
            # If key exists, update in place and move to end
            if query_key in self._cache:
                self._cache.move_to_end(query_key)

            self._cache[query_key] = _CacheEntry(
                value=result,
                expires_at=time.time() + ttl,
                project=project,
            )

            # Evict LRU entries if over capacity
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def invalidate(self, project: str | None = None) -> int:
        """Invalidate cached entries.

        Args:
            project: If provided, only entries tagged with this project are
                     removed. If ``None``, the entire cache is cleared.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            if project is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            keys_to_remove = [
                k
                for k, entry in self._cache.items()
                if entry.project is not None
                and entry.project.lower() == project.lower()
            ]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def stats(self) -> dict[str, Any]:
        """Return cache performance statistics.

        Returns:
            Dictionary with hit_count, miss_count, hit_rate, size, maxsize.
        """
        with self._lock:
            total = self._hit_count + self._miss_count
            return {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": round(self._hit_count / total, 3) if total > 0 else 0.0,
                "size": len(self._cache),
                "maxsize": self._maxsize,
            }

    def clear_expired(self) -> int:
        """Remove all expired entries from the cache.

        Useful for periodic maintenance without waiting for access-time eviction.

        Returns:
            Number of expired entries removed.
        """
        now = time.time()
        with self._lock:
            expired_keys = [
                k for k, entry in self._cache.items() if now > entry.expires_at
            ]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (
            f"QueryCache(size={len(self)}, maxsize={self._maxsize}, "
            f"ttl={self._default_ttl}s)"
        )
