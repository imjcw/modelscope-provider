"""Per-model fixed-window rate-limit strategy.

Each (account_id, model_name) pair has its own independent window,
with configurable window_seconds and max_requests per model.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from core.database import DatabaseManager
from services.providers.base import RateLimitStrategy

logger = logging.getLogger(__name__)

# 默认配额：5 小时 1500 次
_DEFAULT_WINDOW_SECONDS = 5 * 3600  # 18000
_DEFAULT_MAX_REQUESTS = 1500


class PerModelFixedWindowStrategy(RateLimitStrategy):
    """Per-model fixed-window rate-limit strategy.

    Each (account_id, model_name) pair has its own independent fixed window.
    The window starts at the first request and expires after ``window_seconds``.
    All requests (including upstream errors) count toward ``max_requests``.

    Model-specific configs can be provided via ``model_configs`` to override
    the default ``window_seconds`` / ``max_requests`` for specific models.

    Uses ``RateLimitCache`` for in-memory counting when available, falling
    back to the database for atomic counting.
    """

    # Request-count window → circuit breaker uses the higher count-window
    # freeze / escalation thresholds.
    window_mode = "count"

    def __init__(
        self,
        db: DatabaseManager,
        window_seconds: int = _DEFAULT_WINDOW_SECONDS,
        max_requests: int = _DEFAULT_MAX_REQUESTS,
        model_configs: Optional[Dict[str, Dict[str, int]]] = None,
        rate_limit_cache=None,
    ):
        self.db = db
        self.default_window_seconds = window_seconds
        self.default_max_requests = max_requests
        # model_configs: {model_name: {"window_seconds": ..., "max_requests": ...}}
        self.model_configs = model_configs or {}
        self._cache = rate_limit_cache  # Optional RateLimitCache

    def _get_model_config(self, model_name: str) -> Tuple[int, int]:
        """Get (window_seconds, max_requests) for a specific model.

        Falls back to defaults if the model is not explicitly configured.
        """
        cfg = self.model_configs.get(model_name, {})
        return (
            cfg.get("window_seconds", self.default_window_seconds),
            cfg.get("max_requests", self.default_max_requests),
        )

    def check_rate_limit(
        self, account_id: str, model_name: str, key_count: int = 1, key_id: int = 0
    ) -> bool:
        """Check and increment the per-(key, model) request counter.

        Each API key of a supplier holds its own upstream quota for a model, so
        the window is scoped to ``(account_id, model_name, key_id)`` — NOT shared
        across the supplier's keys. ``key_count`` is accepted for signature
        compatibility but deliberately NOT used to scale the limit: scaling would
        collapse N independent per-key budgets back into one shared counter.

        Uses in-memory ``RateLimitCache`` when available (fast path),
        otherwise falls back to the database.
        """
        window_seconds, max_requests = self._get_model_config(model_name)

        if self._cache is not None:
            return self._cache.check(
                account_id, model_name,
                window_seconds, max_requests, key_id=key_id,
            )

        # Fallback: database atomic counting
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows "
                "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                (account_id, model_name, key_id),
            ).fetchone()

            if row is None:
                # First request — create window
                conn.execute(
                    "INSERT INTO account_rate_windows (account_id, model_name, key_id, window_start, request_count, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
                    (account_id, model_name, key_id, now_iso),
                )
                logger.info(
                    f"Per-model rate window created for {account_id}/{model_name}/{key_id}: 1/{max_requests}"
                )
                return True

            window_start_str = row["window_start"]
            request_count = row["request_count"]

            # Check if window has expired
            window_start = datetime.fromisoformat(window_start_str)
            elapsed = (now - window_start).total_seconds()

            if elapsed > window_seconds:
                # Window expired — reset
                conn.execute(
                    "UPDATE account_rate_windows SET window_start = ?, request_count = 1, updated_at = CURRENT_TIMESTAMP "
                    "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                    (now_iso, account_id, model_name, key_id),
                )
                logger.info(
                    f"Per-model rate window reset for {account_id}/{model_name}/{key_id}: 1/{max_requests}"
                )
                return True

            if request_count < max_requests:
                # Within limit — increment
                conn.execute(
                    "UPDATE account_rate_windows SET request_count = request_count + 1, updated_at = CURRENT_TIMESTAMP "
                    "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                    (account_id, model_name, key_id),
                )
                new_count = request_count + 1
                logger.debug(
                    f"Per-model rate count for {account_id}/{model_name}/{key_id}: {new_count}/{max_requests}"
                )
                return True

            # Quota exhausted
            logger.warning(
                f"Per-model rate limit reached for {account_id}/{model_name}/{key_id}: "
                f"{request_count}/{max_requests} in current window"
            )
            return False

    def record_request(
        self,
        account_id: str,
        model_name: str,
        response_headers: dict,
        status_code: int,
    ) -> None:
        """No-op — counting is done in check_rate_limit before dispatch."""

    def get_quota_info(self, account_id: str) -> dict:
        """Return aggregated quota info across all known models.

        Uses in-memory cache when available for fast reads.
        """
        all_models = set(self.model_configs.keys())
        # Also query the DB to find any models that have been used
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT model_name FROM account_rate_windows WHERE account_id = ?",
                (account_id,),
            ).fetchall()
            for r in rows:
                all_models.add(r["model_name"])

        if not all_models:
            return {
                "quota_remaining": self.default_max_requests,
                "quota_limit": self.default_max_requests,
                "window_seconds": self.default_window_seconds,
            }

        min_remaining = float("inf")
        max_limit = 0
        for model in all_models:
            info = self.get_model_quota_info(account_id, model)
            remaining = info.get("quota_remaining", 0)
            limit = info.get("quota_limit", 0)
            min_remaining = min(min_remaining, remaining)
            max_limit = max(max_limit, limit)

        return {
            "quota_remaining": max(0, int(min_remaining)),
            "quota_limit": int(max_limit),
            "window_seconds": self.default_window_seconds,
        }

    def get_model_quota_info(self, account_id: str, model_name: str) -> dict:
        """Return quota info for a specific (account_id, model_name) pair.

        The per-model window is keyed per API key, so this aggregates every
        key's window for the model (sum of used requests across keys). The
        limit is the per-key ``max_requests`` (each key holds its own quota).

        Uses in-memory cache when available for fast reads.
        """
        window_seconds, max_requests = self._get_model_config(model_name)

        if self._cache is not None:
            info = self._cache.get_model_count_across_keys(
                account_id, model_name, window_seconds, max_requests
            )
            if info is not None:
                used = info["request_count"]
                return {
                    "quota_remaining": max(0, max_requests - used),
                    "quota_limit": max_requests,
                    "window_seconds": window_seconds,
                }

        # Fallback: database query — sum used across all keys for this model
        now = datetime.now(timezone.utc)

        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows "
                "WHERE account_id = ? AND model_name = ?",
                (account_id, model_name),
            ).fetchall()

        if not rows:
            return {
                "quota_remaining": max_requests,
                "quota_limit": max_requests,
                "window_seconds": window_seconds,
            }

        used = 0
        for row in rows:
            window_start = datetime.fromisoformat(row["window_start"])
            elapsed = (now - window_start).total_seconds()
            if elapsed > window_seconds:
                # expired window contributes nothing
                continue
            used += row["request_count"]

        return {
            "quota_remaining": max(0, max_requests - used),
            "quota_limit": max_requests,
            "window_seconds": window_seconds,
        }