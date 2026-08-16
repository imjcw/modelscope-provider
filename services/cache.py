"""In-memory cache layer for configuration and rate-limit counters.

Reduces hot-path database reads by keeping frequently-accessed data in memory:

* ``ConfigCache`` — system configuration key-value pairs (``system_config`` table).
* ``RateLimitCache`` — sliding-window rate-limit counters (``account_rate_windows`` table).

All cache writes go *memory-first, DB-second* so the hot path never blocks on I/O.
Background tasks periodically flush dirty counters and reload config from the DB.
"""
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core.database import DatabaseManager
from repositories.config_repository import ConfigRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ConfigCache
# ---------------------------------------------------------------------------


class ConfigCache:
    """In-memory cache for ``system_config`` key-value pairs.

    Usage
    -----
    .. code-block:: python

        cache = ConfigCache(config_repo)
        cache.get("load_balancer_strategy")       # → "round_robin"
        cache.set("load_balancer_strategy", "rr")  # memory ↑, DB ↓
        cache.reload()                             # sync from DB
    """

    def __init__(self, config_repo: ConfigRepository):
        self._repo = config_repo
        self._cache: Dict[str, str] = {}
        self._load_all()

    # ----- public API ------------------------------------------------------

    def get(self, key: str) -> Optional[str]:
        """Return cached config value (or ``None``)."""
        return self._cache.get(key)

    def set(self, key: str, value: str) -> None:
        """Update value in memory first, then persist to DB."""
        self._cache[key] = value
        self._repo.set(key, value)

    def reload(self) -> None:
        """Reload all config from the database.

        Called periodically by a background task to catch any changes that
        may have been made directly to the database.
        """
        raw = self._repo.get_all()
        self._cache = {k: v["value"] for k, v in raw.items()}
        logger.debug("ConfigCache reloaded %d entries", len(self._cache))

    def get_all(self) -> Dict[str, str]:
        """Return a copy of the entire cached config as a flat dict."""
        return dict(self._cache)

    # ----- internals -------------------------------------------------------

    def _load_all(self) -> None:
        """Initial bulk load from database."""
        self.reload()
        logger.info("ConfigCache initialized with %d entries", len(self._cache))


# ---------------------------------------------------------------------------
# RateLimitCache
# ---------------------------------------------------------------------------


@dataclass
class RateLimitWindow:
    """In-memory sliding-window rate-limit counter.

    Instead of a single ``window_start`` + ``request_count``, we keep the
    timestamp of every counted request in ``timestamps`` (epoch seconds, oldest
    first).  A request counts toward ``max_requests`` only if it falls within
    ``window_seconds`` of *now* — i.e. a sliding window ending at the current
    time.  This means "已用" reflects *the last N seconds up to now*, not a fixed
    window anchored at the first request.
    """

    account_id: str
    model_name: str
    window_seconds: float
    max_requests: int
    # API key id this window belongs to. 0 = the supplier's primary key.
    # Per-key windows let a supplier's N keys each hold their own quota for a
    # model instead of sharing a single counter.
    key_id: int = 0
    # Sliding window: epoch seconds of each counted request, oldest first.
    timestamps: deque = field(default_factory=deque)

    def _purge(self, now: Optional[float] = None) -> float:
        """Drop timestamps older than now - window_seconds. Returns ``now``."""
        now = time.time() if now is None else now
        if not self.window_seconds:
            # Unconfigured placeholder (window restored from DB before the real
            # config is backfilled by check()/get_quota_info()) — skip purging,
            # otherwise a 0-second window would drop every timestamp.
            return now
        cutoff = now - self.window_seconds
        ts = self.timestamps
        while ts and ts[0] < cutoff:
            ts.popleft()
        return now

    @property
    def count(self) -> int:
        """Number of requests inside the current sliding window."""
        self._purge()
        return len(self.timestamps)

    @property
    def is_exhausted(self) -> bool:
        return self.count >= self.max_requests

    def add(self) -> int:
        """Record one request at ``now``; return the new window count."""
        self.timestamps.append(time.time())
        return len(self.timestamps)

    @property
    def window_start(self) -> float:
        """Start of the sliding window (now - window_seconds) in epoch seconds."""
        self._purge()
        return time.time() - self.window_seconds


class RateLimitCache:
    """In-memory rate-limit counters (sliding window) with periodic DB flush.

    Each ``(account_id, model_name)`` pair has its own independent sliding
    window: requests count toward ``max_requests`` only if they fall within
    ``window_seconds`` of *now* — i.e. the last N seconds up to the current
    time, not a fixed window anchored at the first request.

    Writes happen in memory immediately and are flushed to the database
    periodically (or on demand) for durability.

    Usage
    -----
    .. code-block:: python

        cache = RateLimitCache(db)
        allowed = cache.check("acc-1", "__global__", 18000, 1500)
        cache.flush()   # persist dirty windows
        cache.reload()  # reload from DB (e.g. after crash recovery)
    """

    def __init__(self, db: DatabaseManager):
        self._db = db
        # Key: (account_id, model_name) → RateLimitWindow
        self._windows: Dict[Tuple[str, str], RateLimitWindow] = {}
        # Set of keys that have been modified since last flush
        self._dirty: Set[Tuple[str, str]] = set()
        # Guard shared state against the flush() worker thread (main.py runs
        # flush() via asyncio.to_thread) racing the event-loop's check()/reload().
        # RLock so reload() (which calls _load_all()) can re-enter safely.
        self._lock = threading.RLock()
        self._load_all()

    # ----- public API ------------------------------------------------------

    def check(
        self,
        account_id: str,
        model_name: str,
        window_seconds: int,
        max_requests: int,
        key_id: int = 0,
    ) -> bool:
        """Check and increment the rate-limit counter (sliding window).

        Returns ``True`` if the request is allowed (under the limit),
        ``False`` if adding this request would exceed ``max_requests`` within
        the last ``window_seconds`` (the sliding window ending now).

        ``key_id`` scopes the window to a single API key (per key+model
        isolation). Defaults to 0 (supplier primary key).
        """
        with self._lock:
            key = (account_id, model_name, key_id)
            window = self._windows.get(key)

            if window is None:
                # First request — create new sliding window and record it.
                window = RateLimitWindow(
                    account_id=account_id,
                    model_name=model_name,
                    window_seconds=float(window_seconds),
                    max_requests=max_requests,
                    key_id=key_id,
                )
                window.add()
                self._windows[key] = window
                self._dirty.add(key)
                logger.info(
                    "RateLimit window created for %s/%s/%s: 1/%d",
                    account_id, model_name, key_id, max_requests,
                )
                return True

            # Windows restored from DB by ``_load_all`` carry placeholder config
            # (window_seconds/max_requests == 0) because the strategy config is not
            # persisted in ``account_rate_windows``. Backfill the real config from
            # the caller on first access; otherwise the window would be
            # misinterpreted (e.g. a 0-second window purges every timestamp).
            # Also self-heal when the caller's limit changed (e.g. the account's
            # active key count changed → quota limit = config_limit × N).
            if not window.window_seconds:
                window.window_seconds = float(window_seconds)
            if max_requests and window.max_requests != max_requests:
                window.max_requests = max_requests

            # Sliding window: reject only if the current window is already full.
            if window.is_exhausted:
                logger.warning(
                    "RateLimit exhausted for %s/%s: %d/%d in last %ds",
                    account_id, model_name, window.count, max_requests,
                    int(window.window_seconds),
                )
                return False

            window.add()
            self._dirty.add(key)
            return True

    def get_quota_info(
        self,
        account_id: str,
        model_name: str,
        window_seconds: int = 0,
        max_requests: int = 0,
        key_id: int = 0,
    ) -> dict:
        """Return quota info for display for a single (key_id, model).

        Expected keys: ``quota_remaining``, ``quota_limit``.

        ``window_seconds`` / ``max_requests`` let callers pass the real strategy
        config so windows restored from DB (with placeholder 0 config) report
        correct limits instead of falsely appearing empty.

        ``request_count`` is the number of requests counted in the current
        sliding window (now - window_seconds) — the authoritative "已用" value.
        It is ``None`` when no in-memory window exists, so callers can fall back
        to the DB snapshot rather than treating absence as 0.

        ``key_id`` selects the API key's window (defaults to 0). Use
        :meth:`get_model_count_across_keys` to aggregate across all keys.
        """
        with self._lock:
            key = (account_id, model_name, key_id)
            window = self._windows.get(key)
            if window is None:
                return {
                    "quota_remaining": max_requests or 0,
                    "quota_limit": max_requests or 0,
                    "request_count": None,
                }

            # Backfill placeholder config from restored-from-DB windows.
            if not window.window_seconds and window_seconds:
                window.window_seconds = float(window_seconds)
            if max_requests and window.max_requests != max_requests:
                window.max_requests = max_requests

            count = window.count
            return {
                "quota_remaining": max(0, window.max_requests - count),
                "quota_limit": window.max_requests,
                "request_count": count,
                "window_start": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(window.window_start)
                ),
            }

    def get_model_count_across_keys(
        self,
        account_id: str,
        model_name: str,
        window_seconds: int = 0,
        max_requests: int = 0,
        key_id: int | None = None,
    ) -> Optional[dict]:
        """Sum the sliding-window request count for ``(account_id, model_name)``.

        When ``key_id`` is set, scope to that specific key; otherwise sum across
        ALL API keys of the supplier (per key+model isolation means each key has
        its own window). Returns ``{"request_count": <sum>}`` or ``None`` when
        no in-memory window exists for that model, so callers fall back to the
        DB snapshot instead of treating absence as 0.
        """
        with self._lock:
            windows = [
                w
                for (aid, mdl, _kid), w in self._windows.items()
                if aid == account_id and mdl == model_name
                and (key_id is None or _kid == key_id)
            ]
            if not windows:
                return None
            total = 0
            for w in windows:
                if not w.window_seconds and window_seconds:
                    w.window_seconds = float(window_seconds)
                if max_requests and w.max_requests != max_requests:
                    w.max_requests = max_requests
                total += w.count
            return {"request_count": total}

    def flush(self) -> int:
        """Write all dirty windows to the database.

        Persists each window's current sliding-window count and the list of
        request timestamps (JSON) so the window can be reconstructed exactly
        after a restart.  Returns the number of rows written.

        Snapshot + clear ``_dirty`` under the lock, then perform DB I/O outside
        the lock so the hot-path ``check()`` is never blocked on disk.
        """
        if not self._dirty:
            return 0

        with self._lock:
            snapshots = []
            for key in self._dirty:
                window = self._windows.get(key)
                if window is None:
                    continue
                # Purge stale timestamps so the persisted count reflects the
                # current sliding window (now - window_seconds).
                window._purge()
                window_start_iso = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(window.window_start)
                )
                timestamps_json = json.dumps(list(window.timestamps))
                snapshots.append(
                    (key[0], key[1], key[2], window_start_iso,
                     len(window.timestamps), timestamps_json)
                )
            self._dirty.clear()

        count = 0
        with self._db.get_connection() as conn:
            for account_id, model_name, key_id, window_start_iso, request_count, timestamps_json in snapshots:
                conn.execute(
                    """INSERT INTO account_rate_windows
                       (account_id, model_name, key_id, window_start, request_count, timestamps, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(account_id, model_name, key_id)
                       DO UPDATE SET window_start = excluded.window_start,
                                     request_count = excluded.request_count,
                                     timestamps = excluded.timestamps,
                                     updated_at = CURRENT_TIMESTAMP""",
                    (account_id, model_name, key_id, window_start_iso,
                     request_count, timestamps_json),
                )
                count += 1
        logger.debug("RateLimitCache flushed %d dirty windows", count)
        return count

    def reload(self) -> None:
        """Reload all windows from the database.

        Called during startup and after crash recovery to ensure consistency.
        WARNING: This discards any in-memory changes that haven't been flushed.
        """
        with self._lock:
            self._windows.clear()
            self._dirty.clear()
            self._load_all()

    # ----- internals -------------------------------------------------------

    def _load_all(self) -> None:
        """Load all existing rate-limit windows from the database."""
        with self._db.get_connection() as conn:
            rows = conn.execute(
                "SELECT account_id, model_name, key_id, request_count, timestamps "
                "FROM account_rate_windows"
            ).fetchall()

        for row in rows:
            # Rebuild the sliding window from persisted timestamps (if any).
            # Older rows may have a NULL/empty ``timestamps`` column — fall back
            # to ``request_count`` by seeding that many timestamps near now, so
            # the count is preserved until real request timestamps arrive.
            loaded_ts: deque = deque()
            raw_ts = row["timestamps"]
            if raw_ts:
                try:
                    loaded_ts = deque(float(t) for t in json.loads(raw_ts))
                except (ValueError, TypeError, json.JSONDecodeError):
                    loaded_ts = deque()
            rc = row["request_count"]
            if not loaded_ts and rc:
                # Rebuild approximate timestamps from the per-minute request
                # stats so the sliding window reflects the real traffic in the
                # last few hours (including requests before this process
                # started), instead of a fixed-window approximation.
                loaded_ts = self._backfill_from_stats(row["account_id"], row["model_name"])
            if not loaded_ts and rc:
                # Absolute fallback: seed ``request_count`` stamps near now.
                now = time.time()
                for _i in range(int(rc)):
                    loaded_ts.append(now - (_i * 0.001))
            # Keep timestamps sorted (oldest first) so the sliding-window purge
            # (which only trims from the front) behaves correctly regardless of
            # how the timestamps were originally persisted.
            loaded_ts = deque(sorted(loaded_ts))

            key = (row["account_id"], row["model_name"], row["key_id"])
            self._windows[key] = RateLimitWindow(
                account_id=row["account_id"],
                model_name=row["model_name"],
                window_seconds=0,  # set by check()/get_quota_info() on access
                max_requests=0,    # same
                key_id=row["key_id"],
                timestamps=loaded_ts,
            )

        logger.info(
            "RateLimitCache initialized with %d existing windows",
            len(self._windows),
        )

    def _backfill_from_stats(
        self, account_id: str, model_name: str, backfill_seconds: int = 6 * 3600
    ) -> "deque":
        """Reconstruct sliding-window timestamps from per-minute request stats.

        Used when a window loaded from ``account_rate_windows`` has no persisted
        ``timestamps`` column (e.g. after upgrading from the fixed-window
        schema, or before the first flush of the new code).  We read
        ``request_stats_minute`` for the last few hours and synthesize one
        timestamp per counted request, so the sliding window immediately
        reflects real traffic — including requests that happened before this
        process started — rather than collapsing to a fixed-window count.
        """
        try:
            cutoff = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(time.time() - backfill_seconds)
            )
            with self._db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT bucket, requests FROM request_stats_minute "
                    "WHERE account_id = ? AND model = ? AND bucket >= ? "
                    "ORDER BY bucket",
                    (account_id, model_name, cutoff),
                ).fetchall()
            stamps: deque = deque()
            for r in rows:
                try:
                    base = time.mktime(
                        time.strptime(r["bucket"], "%Y-%m-%d %H:%M:%S")
                    )
                except (ValueError, KeyError, TypeError):
                    continue
                n = int(r["requests"] or 0)
                if n <= 0:
                    continue
                # Spread the per-minute requests evenly across the minute so
                # they expire naturally instead of all at once.
                step = 60.0 / n
                for i in range(n):
                    stamps.append(base + (i + 0.5) * step)
            return deque(sorted(stamps))
        except Exception:
            logger.warning(
                "Backfill sliding window from stats failed for %s/%s",
                account_id, model_name, exc_info=True,
            )
            return deque()