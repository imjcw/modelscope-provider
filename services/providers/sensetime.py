"""商汤（SenseTime）限流策略：主动式固定窗口计数器。

Coding Plan: 每 5 小时 1500 次请求，所有请求（含失败）均计入。
"""

import logging
from datetime import datetime, timezone

from core.database import DatabaseManager
from services.providers.base import RateLimitStrategy

logger = logging.getLogger(__name__)

# 默认配额：5 小时 1500 次
DEFAULT_WINDOW_SECONDS = 5 * 3600  # 18000
DEFAULT_MAX_REQUESTS = 1500

# 按供应商模式（per_provider）使用固定 model_name 来存储窗口记录
_GLOBAL_MODEL = "__global__"


class SenseTimeStrategy(RateLimitStrategy):
    """SenseTime rate-limit strategy.

    Proactive fixed-window counter: the window starts at the first request
    and expires after ``window_seconds``. All requests (including upstream
    errors) count toward ``max_requests``.

    Uses ``RateLimitCache`` for in-memory counting when available, falling
    back to the database for atomic counting.
    """

    def __init__(
        self,
        db: DatabaseManager,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        rate_limit_cache=None,
    ):
        self.db = db
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._cache = rate_limit_cache  # Optional RateLimitCache

    def check_rate_limit(self, account_id: str, model_name: str, key_count: int = 1) -> bool:
        """Check and increment the request counter.

        Uses in-memory ``RateLimitCache`` when available (fast path),
        otherwise falls back to the database.

        ``key_count`` scales the effective quota limit: an account with N
        active keys holds N× the per-key ``max_requests`` budget.
        """
        effective_max = self.max_requests * max(1, key_count)
        if self._cache is not None:
            return self._cache.check(
                account_id, _GLOBAL_MODEL,
                self.window_seconds, effective_max,
            )

        # Fallback: database atomic counting
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows WHERE account_id = ? AND model_name = ?",
                (account_id, _GLOBAL_MODEL),
            ).fetchone()

            if row is None:
                # First request — create window
                conn.execute(
                    "INSERT INTO account_rate_windows (account_id, model_name, window_start, request_count, updated_at) "
                    "VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)",
                    (account_id, _GLOBAL_MODEL, now_iso),
                )
                logger.info(
                    f"SenseTime rate window created for {account_id}: 1/{effective_max}"
                )
                return True

            window_start_str = row["window_start"]
            request_count = row["request_count"]

            # Check if window has expired
            window_start = datetime.fromisoformat(window_start_str)
            elapsed = (now - window_start).total_seconds()

            if elapsed > self.window_seconds:
                # Window expired — reset
                conn.execute(
                    "UPDATE account_rate_windows SET window_start = ?, request_count = 1, updated_at = CURRENT_TIMESTAMP "
                    "WHERE account_id = ? AND model_name = ?",
                    (now_iso, account_id, _GLOBAL_MODEL),
                )
                logger.info(
                    f"SenseTime rate window reset for {account_id}: 1/{effective_max}"
                )
                return True

            if request_count < effective_max:
                # Within limit — increment
                conn.execute(
                    "UPDATE account_rate_windows SET request_count = request_count + 1, updated_at = CURRENT_TIMESTAMP "
                    "WHERE account_id = ? AND model_name = ?",
                    (account_id, _GLOBAL_MODEL),
                )
                new_count = request_count + 1
                logger.debug(
                    f"SenseTime rate count for {account_id}: {new_count}/{effective_max}"
                )
                return True

            # Quota exhausted — no write, context manager commits the (empty) txn
            logger.warning(
                f"SenseTime rate limit reached for {account_id}: "
                f"{request_count}/{effective_max} in current window"
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
        """Return current window quota info for display.

        Uses in-memory cache when available for fast reads.
        """
        if self._cache is not None:
            return self._cache.get_quota_info(account_id, _GLOBAL_MODEL)

        # Fallback: database query
        now = datetime.now(timezone.utc)

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows WHERE account_id = ? AND model_name = ?",
                (account_id, _GLOBAL_MODEL),
            ).fetchone()

        if row is None:
            return {
                "quota_remaining": self.max_requests,
                "quota_limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        window_start = datetime.fromisoformat(row["window_start"])
        elapsed = (now - window_start).total_seconds()

        if elapsed > self.window_seconds:
            # Window expired — full quota available
            return {
                "quota_remaining": self.max_requests,
                "quota_limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        remaining = max(0, self.max_requests - row["request_count"])
        return {
            "quota_remaining": remaining,
            "quota_limit": self.max_requests,
            "window_seconds": self.window_seconds,
            "window_start": row["window_start"],
        }
