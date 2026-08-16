"""商汤（SenseTime）限流策略：主动式固定窗口计数器。

Coding Plan: 每 5 小时 1500 次请求，所有请求（含失败）均计入。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from core.database import DatabaseManager
from repositories.quota_repository import QuotaRepository
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
        quota_repository: QuotaRepository = None,
    ):
        self.db = db
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._cache = rate_limit_cache  # Optional RateLimitCache
        self.quota_repository = quota_repository

    # 仅瞬态错误触发标记 unavailable；auth_error 和 bad_request 属于
    # 密钥/配置问题，不应标记模型不可用。
    _TRANSIENT_ERROR_TYPES = {"server_error", "timeout", "network_error", "rate_limited"}

    def on_circuit_breaker_escalation(
        self,
        account_id: str,
        model_name: str,
        error_type: Optional[str],
        key_id: int = 0,
    ) -> None:
        """熔断升级：连续 10 次瞬态失败后，标记模型今日不可用，
        让路由直接跳过该候选，而不是等 1 小时冻结窗口过去再试。

        ``key_id`` 透传自熔断器的 ``(key_id, model)`` 维度，因此只标记该 key
        的模型不可用（SenseTime 的全局窗口也已是 per-key），而不影响同供应商
        的其它 key。
        """
        if error_type not in self._TRANSIENT_ERROR_TYPES:
            logger.debug(
                "Circuit-breaker escalation skipped (non-transient error): "
                "%s/%s error_type=%s",
                account_id, model_name, error_type,
            )
            return
        if self.quota_repository is None:
            logger.warning(
                "Circuit-breaker escalation for %s/%s (key %s) but quota_repository is None — "
                "cannot mark model unavailable",
                account_id, model_name, key_id,
            )
            return
        logger.warning(
            "Circuit-breaker escalation: marking %s/%s (key %s) unavailable (error_type=%s)",
            account_id, model_name, key_id, error_type,
        )
        self.quota_repository.mark_model_unavailable(account_id, model_name, key_id=key_id)

    def check_rate_limit(
        self, account_id: str, model_name: str, key_count: int = 1, key_id: int = 0
    ) -> bool:
        """Check and increment the request counter.

        Uses in-memory ``RateLimitCache`` when available (fast path),
        otherwise falls back to the database.

        SenseTime tracks one supplier-wide window (aliased to ``_GLOBAL_MODEL``),
        but the window is now keyed per API key (``key_id``) so each key holds its
        own ``max_requests`` budget — identical to the per-model window semantics.
        ``key_count`` is therefore no longer used to scale the limit; each key is
        already counted independently and the admin view sums them.
        """
        effective_max = self.max_requests
        if self._cache is not None:
            return self._cache.check(
                account_id, _GLOBAL_MODEL,
                self.window_seconds, effective_max, key_id=key_id,
            )

        # Fallback: database atomic counting, keyed per (account_id, key_id)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows "
                "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                (account_id, _GLOBAL_MODEL, key_id),
            ).fetchone()

            if row is None:
                # First request — create window
                conn.execute(
                    "INSERT INTO account_rate_windows (account_id, model_name, key_id, window_start, request_count, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
                    (account_id, _GLOBAL_MODEL, key_id, now_iso),
                )
                logger.info(
                    f"SenseTime rate window created for {account_id} (key {key_id}): 1/{effective_max}"
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
                    "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                    (now_iso, account_id, _GLOBAL_MODEL, key_id),
                )
                logger.info(
                    f"SenseTime rate window reset for {account_id} (key {key_id}): 1/{effective_max}"
                )
                return True

            if request_count < effective_max:
                # Within limit — increment
                conn.execute(
                    "UPDATE account_rate_windows SET request_count = request_count + 1, updated_at = CURRENT_TIMESTAMP "
                    "WHERE account_id = ? AND model_name = ? AND key_id = ?",
                    (account_id, _GLOBAL_MODEL, key_id),
                )
                new_count = request_count + 1
                logger.debug(
                    f"SenseTime rate count for {account_id} (key {key_id}): {new_count}/{effective_max}"
                )
                return True

            # Quota exhausted — no write, context manager commits the (empty) txn
            logger.warning(
                f"SenseTime rate limit reached for {account_id} (key {key_id}): "
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

    def get_quota_info(self, account_id: str, key_id: int = 0) -> dict:
        """Return current window quota info for display.

        Uses in-memory cache when available for fast reads. The supplier-wide
        window is aliased to ``_GLOBAL_MODEL`` and tracked per ``key_id``; callers
        that want the whole-supplier picture should pass no ``key_id`` to sum
        across every key.
        """
        if self._cache is not None:
            if key_id is not None:
                return self._cache.get_quota_info(account_id, _GLOBAL_MODEL, key_id=key_id)
            # Aggregate across all keys held in the cache for this supplier.
            total = 0
            found = False
            if getattr(self._cache, "_windows", None):  # noqa: SLF001 - internal read-only aggregation
                for (acc, model, kid), win in self._cache._windows.items():
                    if acc == account_id and model == _GLOBAL_MODEL:
                        _ws = datetime.fromisoformat(win["window_start"])
                        _elapsed = (datetime.now(timezone.utc) - _ws).total_seconds()
                        if _elapsed <= self.window_seconds:
                            total += win.get("request_count", 0)
                        found = True
            if found:
                return {
                    "quota_remaining": max(0, self.max_requests - total),
                    "quota_limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                }
            return {
                "quota_remaining": self.max_requests,
                "quota_limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        # Fallback: database query. Sum the per-key __global__ rows.
        now = datetime.now(timezone.utc)

        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT window_start, request_count FROM account_rate_windows "
                "WHERE account_id = ? AND model_name = ?",
                (account_id, _GLOBAL_MODEL),
            ).fetchall()

        if not rows:
            return {
                "quota_remaining": self.max_requests,
                "quota_limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

        total_used = 0
        for row in rows:
            window_start = datetime.fromisoformat(row["window_start"])
            elapsed = (now - window_start).total_seconds()
            if elapsed <= self.window_seconds:
                total_used += row["request_count"]

        return {
            "quota_remaining": max(0, self.max_requests - total_used),
            "quota_limit": self.max_requests,
            "window_seconds": self.window_seconds,
        }
