"""In-memory cache layer for configuration and rate-limit counters.

Reduces hot-path database reads by keeping frequently-accessed data in memory:

* ``ConfigCache`` — system configuration key-value pairs (``system_config`` table).
* ``RateLimitCache`` — fixed-window rate-limit counters (``account_rate_windows`` table).

All cache writes go *memory-first, DB-second* so the hot path never blocks on I/O.
Background tasks periodically flush dirty counters and reload config from the DB.
"""
import logging
import time
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
    """In-memory fixed-window rate-limit counter.

    The window starts at ``window_start`` (seconds since epoch) and expires
    after ``window_seconds``.  All requests count toward ``max_requests``.
    """

    account_id: str
    model_name: str
    window_seconds: float
    max_requests: int
    window_start: float = 0.0  # time.time()
    request_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.window_start > self.window_seconds

    @property
    def is_exhausted(self) -> bool:
        return self.request_count >= self.max_requests

    def reset(self) -> None:
        self.window_start = time.time()
        self.request_count = 0

    def increment(self) -> int:
        self.request_count += 1
        return self.request_count


class RateLimitCache:
    """In-memory rate-limit counters with periodic DB flush.

    Each ``(account_id, model_name)`` pair has its own independent fixed window.
    The window starts at the first request and expires after ``window_seconds``.

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
        self._load_all()

    # ----- public API ------------------------------------------------------

    def check(
        self,
        account_id: str,
        model_name: str,
        window_seconds: int,
        max_requests: int,
    ) -> bool:
        """Check and increment the rate-limit counter.

        Returns ``True`` if the request is allowed, ``False`` if the window
        quota is exhausted.
        """
        key = (account_id, model_name)
        window = self._windows.get(key)

        if window is None:
            # First request — create new window
            window = RateLimitWindow(
                account_id=account_id,
                model_name=model_name,
                window_seconds=float(window_seconds),
                max_requests=max_requests,
                window_start=time.time(),
                request_count=1,
            )
            self._windows[key] = window
            self._dirty.add(key)
            logger.info(
                "RateLimit window created for %s/%s: 1/%d",
                account_id, model_name, max_requests,
            )
            return True

        if window.is_expired:
            # Window expired — reset
            window.reset()
            window.increment()  # count this request
            self._dirty.add(key)
            logger.info(
                "RateLimit window reset for %s/%s: %d/%d",
                account_id, model_name, window.request_count, max_requests,
            )
            return True

        if not window.is_exhausted:
            window.increment()
            self._dirty.add(key)
            return True

        # Quota exhausted
        logger.warning(
            "RateLimit exhausted for %s/%s: %d/%d",
            account_id, model_name, window.request_count, max_requests,
        )
        return False

    def get_quota_info(self, account_id: str, model_name: str) -> dict:
        """Return quota info for display.

        Expected keys: ``quota_remaining``, ``quota_limit``.
        """
        key = (account_id, model_name)
        window = self._windows.get(key)
        if window is None:
            max_r = 0
            # Try to find the max_requests from any window with same account
            for k, w in self._windows.items():
                if k[0] == account_id:
                    max_r = max(max_r, w.max_requests)
            return {"quota_remaining": max_r, "quota_limit": max_r}

        if window.is_expired:
            return {
                "quota_remaining": window.max_requests,
                "quota_limit": window.max_requests,
            }

        remaining = max(0, window.max_requests - window.request_count)
        return {
            "quota_remaining": remaining,
            "quota_limit": window.max_requests,
            "window_start": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(window.window_start)
            ),
        }

    def flush(self) -> int:
        """Write all dirty windows to the database.

        Returns the number of rows written.
        """
        if not self._dirty:
            return 0

        count = 0
        with self._db.get_connection() as conn:
            for key in self._dirty:
                window = self._windows.get(key)
                if window is None:
                    continue
                account_id, model_name = key
                window_start_iso = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(window.window_start)
                )
                conn.execute(
                    """INSERT INTO account_rate_windows
                       (account_id, model_name, window_start, request_count, updated_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(account_id, model_name)
                       DO UPDATE SET window_start = excluded.window_start,
                                     request_count = excluded.request_count,
                                     updated_at = CURRENT_TIMESTAMP""",
                    (account_id, model_name, window_start_iso, window.request_count),
                )
                count += 1
        self._dirty.clear()
        logger.debug("RateLimitCache flushed %d dirty windows", count)
        return count

    def reload(self) -> None:
        """Reload all windows from the database.

        Called during startup and after crash recovery to ensure consistency.
        WARNING: This discards any in-memory changes that haven't been flushed.
        """
        self._windows.clear()
        self._dirty.clear()
        self._load_all()

    # ----- internals -------------------------------------------------------

    def _load_all(self) -> None:
        """Load all existing rate-limit windows from the database."""
        with self._db.get_connection() as conn:
            rows = conn.execute(
                "SELECT account_id, model_name, window_start, request_count "
                "FROM account_rate_windows"
            ).fetchall()

        for row in rows:
            try:
                ws = time.mktime(
                    time.strptime(row["window_start"], "%Y-%m-%dT%H:%M:%S")
                )
            except (ValueError, KeyError):
                try:
                    # Fallback: try space-separated format
                    ws = time.mktime(
                        time.strptime(row["window_start"], "%Y-%m-%d %H:%M:%S")
                    )
                except (ValueError, KeyError):
                    ws = 0.0

            key = (row["account_id"], row["model_name"])
            self._windows[key] = RateLimitWindow(
                account_id=row["account_id"],
                model_name=row["model_name"],
                window_seconds=0,  # will be set by check() on next access
                max_requests=0,    # same
                window_start=ws,
                request_count=row["request_count"],
            )

        logger.info(
            "RateLimitCache initialized with %d existing windows",
            len(self._windows),
        )