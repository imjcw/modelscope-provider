"""供应商限流策略抽象基类。"""

from abc import ABC, abstractmethod


class RateLimitStrategy(ABC):
    """Per-provider rate-limit / quota strategy.

    Each provider implements its own rate-limiting semantics:
    - ModelScope: reactive, header-driven (reads modelscope-ratelimit-* headers)
    - SenseTime: proactive, local fixed-window counter (1500 req / 5h)

    ``window_mode`` marks how this strategy meters its limit:
    ``"token"`` (default) = quota is token-based (reactive, header-driven,
    e.g. ModelScope); ``"count"`` = quota is a request-count window
    (``max_requests``), e.g. SenseTime / per-model fixed windows. The circuit
    breaker reads this to tune its freeze threshold per model.
    """

    # Token-based by default; count-window strategies override this.
    window_mode: str = "token"

    @abstractmethod
    def check_rate_limit(
        self,
        account_id: str,
        model_name: str,
        key_count: int = 1,
        key_id: int = 0,
    ) -> bool:
        """Pre-request check. Return True if the request may proceed.

        For proactive providers (e.g. SenseTime), this atomically increments
        the request counter and returns False when the limit is reached.
        For reactive providers (e.g. ModelScope), this always returns True.

        ``key_id`` is the specific API key serving this request. Strategies that
        track quota per key+model scope their counters to ``(account_id,
        model_name, key_id)`` so each of a supplier's N keys holds its own
        upstream quota for the model. ``key_id = 0`` denotes the primary key.

        ``key_count`` is the number of active API keys on the account; strategies
        that do NOT key per key (e.g. SenseTime's supplier-wide window) use it to
        scale the effective limit by N. Defaults to 1.
        """

    @abstractmethod
    def record_request(
        self,
        account_id: str,
        model_name: str,
        response_headers: dict,
        status_code: int,
    ) -> None:
        """Post-request recording (called for ALL responses including errors).

        For ModelScope: parses rate-limit headers and updates quota tables.
        For SenseTime: no-op (counting already done in check_rate_limit).
        """

    def record_usage(
        self,
        account_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage (typically from streaming responses).

        Default is no-op. Override for providers that track token consumption.
        """

    @abstractmethod
    def get_quota_info(self, account_id: str) -> dict:
        """Return quota info dict for display.

        Expected keys: quota_remaining, quota_limit.
        Providers may include additional keys (e.g. window_start, window_seconds).
        """

    def get_model_quota_info(self, account_id: str, model_name: str) -> dict:
        """Return per-model quota info for display.

        Expected keys: quota_remaining, quota_limit.
        Default raises NotImplementedError — only strategies that support
        per-model tracking need to override this.
        """
        raise NotImplementedError(
            "Per-model quota not supported by this strategy"
        )

