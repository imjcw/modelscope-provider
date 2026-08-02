"""Circuit breaker for upstream API failures.

Tracks failures per ``(key_id, model_name)`` pair with configurable
freeze duration and exponential backoff. Each API Key within an account
is tracked independently, so a failed key does not freeze other keys
of the same account for the same model. Used by the fallback loop to
skip currently-frozen candidates.

Error classification
--------------------
Errors are classified into categories, each with a default freeze duration:

- ``bad_request`` (400, 404, 405, 422): 30 min — retry won't help
- ``auth_error``   (401, 403):           1 hour — key issue, needs admin
- ``server_error`` (500, 502, 503, 504): 1 min  — exponential backoff
- ``network_error`` (timeout, DNS):       1 min  — exponential backoff

Exponential backoff schedule (applies to ``server_error`` / ``network_error``):

    1st → 1 min, 2nd → 2 min, 3rd → 4 min, 4th+ → 8 min (cap)

After ``CONSECUTIVE_FAILURE_THRESHOLD`` (10) consecutive failures the circuit
escalates to the provider's ``RateLimitStrategy`` via ``on_circuit_breaker_escalation``.
This lets the strategy decide the final action (mark model unavailable, freeze
account, etc.). Escalation also applies a long freeze (``escalation_freeze_seconds``,
default 1 hour); once it expires the circuit goes half-open and can recover via
a successful probe — escalation is no longer permanent.

State machine
-------------
::

    Closed (正常) ── failure ──→ Open (冻结)
        ↑                            │
        │                       freeze expires
        │                            ↓
        └── success ──── Half-Open (试探)
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

# HTTP status code → error category
_ERROR_CLASSIFICATION: Dict[int, str] = {
    400: "bad_request",
    401: "auth_error",
    403: "auth_error",
    404: "bad_request",
    405: "bad_request",
    422: "bad_request",
    429: "rate_limited",  # already handled by RateLimitStrategy, but tracked
    500: "server_error",
    502: "server_error",
    503: "server_error",
    504: "timeout",
}

# Initial freeze duration (seconds) per error category
_FREEZE_DURATIONS: Dict[str, float] = {
    "bad_request": 1800.0,    # 30 min
    "auth_error": 3600.0,     # 1 hour
    "server_error": 60.0,     # 1 min
    "timeout": 60.0,          # 1 min
    "network_error": 60.0,    # 1 min
    "rate_limited": 60.0,     # 1 min (backup — 429 is already handled pre-request)
}

# Exponential backoff steps (seconds) for transient errors.
# Applied after the *first* failure (index 0 = 2nd consecutive failure).
_BACKOFF_SCHEDULE: List[float] = [60.0, 120.0, 240.0, 480.0, 480.0]

# Consecutive failures before escalating to supplier strategy
_CONSECUTIVE_FAILURE_THRESHOLD: int = 10

# Freeze duration (seconds) applied when a circuit escalates. Unlike the
# previous behaviour (escalated → permanently blocked until process restart),
# the escalated circuit now enters a long freeze and — once it expires — allows
# a half-open probe so it can recover automatically via ``record_success``.
_ESCALATION_FREEZE_SECONDS: float = 3600.0  # 1 hour

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CircuitState:
    """Mutable state for a single ``(key_id, model_name)`` circuit.

    ``account_id`` is stored for display purposes only — the state key
    is ``(key_id, model_name)`` so that different API keys of the same
    account are tracked independently.
    """

    key_id: int
    account_id: str
    model_name: str

    # Failure tracking
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    error_type: Optional[str] = None

    # Freeze
    frozen_until: float = 0.0  # time.time() value; 0 = not frozen
    escalated: bool = False    # True → handed off to supplier strategy


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Circuit breaker for upstream API failures.

    Tracks failures per ``(key_id, model_name)`` pair so that each API Key
    within an account is independent — a failed key does not freeze other
    keys of the same account. ``account_id`` is stored in each state purely
    for admin display.

    Designed for single-threaded async contexts (FastAPI event loop) but guarded
    with a ``threading.Lock`` around the in-memory ``_states`` dict so it can also
    be shared safely across threads (e.g. when deployed with a threaded worker).

    Usage
    -----
    .. code-block:: python

        cb = CircuitBreaker()

        # Before request — skip if frozen
        if not cb.check(key_id, model_name):
            continue  # try next candidate

        # After successful request
        cb.record_success(key_id, model_name)

        # After failed request
        cb.record_failure(key_id, account_id, model_name, status_code, strategy)
    """

    def __init__(self):
        # Key: (key_id, model_name) → CircuitState
        self._states: Dict[Tuple[int, str], CircuitState] = {}

        # Tunable parameters (exposed so subclasses / callers can tweak)
        self.error_classification = dict(_ERROR_CLASSIFICATION)
        self.freeze_durations = dict(_FREEZE_DURATIONS)
        self.backoff_schedule = list(_BACKOFF_SCHEDULE)
        self.failure_threshold = _CONSECUTIVE_FAILURE_THRESHOLD
        self.escalation_freeze_seconds = _ESCALATION_FREEZE_SECONDS

        # Guards all access to the shared ``_states`` dict.
        self._lock = threading.Lock()

    # ----- public API ------------------------------------------------------

    def check(self, key_id: int, model_name: str) -> bool:
        """Return ``True`` if the request may proceed (circuit is closed).

        ``key_id`` is the ``account_api_keys.id`` (0 = primary key from
        the accounts table). Returns ``False`` if the circuit is open
        (frozen).  Once the freeze expires the circuit enters *half-open*
        state — the next call returns ``True`` so a probe request is allowed.
        """
        with self._lock:
            state = self._states.get((key_id, model_name))
            if state is None:
                return True

            if time.time() < state.frozen_until:
                return False

            # Freeze expired → half-open: allow probe. This also covers
            # escalated circuits once their long freeze lapses, so they can
            # recover via a successful probe instead of being blocked forever.
            if state.consecutive_failures > 0:
                logger.info(
                    "Circuit breaker half-open for key %s / %s: "
                    "freeze expired, allowing probe request%s",
                    key_id, model_name,
                    " (escalated)" if state.escalated else "",
                )
            return True

    def record_failure(
        self,
        key_id: int,
        account_id: str,
        model_name: str,
        status_code: int,
        strategy: Any = None,
    ) -> None:
        """Record a failure and (possibly) freeze the circuit.

        ``key_id`` is the ``account_api_keys.id`` (0 = primary key).  ``account_id``
        is stored for display only.  ``status_code`` can be an HTTP status code
        or a negative number for network errors (e.g. ``-1`` for timeout,
        ``-2`` for connection error).
        """
        with self._lock:
            key = (key_id, model_name)
            state = self._states.get(key)
            if state is None:
                state = CircuitState(
                    key_id=key_id, account_id=account_id, model_name=model_name,
                )
                self._states[key] = state

            state.consecutive_failures += 1
            state.last_failure_time = time.time()
            state.error_type = self._classify_error(status_code)

            # ----- Escalation check -----
            if (
                state.consecutive_failures >= self.failure_threshold
                and not state.escalated
            ):
                state.escalated = True
                # Apply a long (but finite) freeze so the circuit can recover
                # via a half-open probe after it expires, rather than staying
                # permanently blocked until a process restart.
                state.frozen_until = time.time() + self.escalation_freeze_seconds
                logger.warning(
                    "Circuit breaker: key %s / %s (account %s) reached %d consecutive "
                    "failures, escalating to supplier strategy (freezing %.0fs)",
                    key_id, model_name, account_id, state.consecutive_failures,
                    self.escalation_freeze_seconds,
                )
                self._escalate(strategy, account_id, model_name, state.error_type)
                return

            # 瞬时错误（server_error / network_error / timeout / rate_limited）第 1 次
            # 失败不冻结 — 允许下一次请求继续尝试，避免单一候选场景因一次上游抖动
            # （含偶发 429）就整条路由冻住。第 2 次起才进入冻结 + exponential backoff。
            # bad_request / auth_error 不在此列：这些错误重试无意义，立即冻结。
            if state.consecutive_failures == 1 and state.error_type in (
                "server_error", "network_error", "timeout", "rate_limited",
            ):
                logger.info(
                    "Circuit breaker: key %s / %s first transient failure (status=%s), "
                    "not freezing — allowing next request to retry",
                    key_id, model_name, status_code,
                )
                return

            # ----- Freeze -----
            freeze_seconds = self._get_freeze_seconds(
                state.error_type, state.consecutive_failures,
            )
            state.frozen_until = time.time() + freeze_seconds

            logger.warning(
                "Circuit breaker: key %s / %s (account %s) failed (status=%s, type=%s, "
                "failures=%d), freezing for %.0fs",
                key_id, model_name, account_id,
                status_code, state.error_type,
                state.consecutive_failures, freeze_seconds,
            )

    def record_success(self, key_id: int, model_name: str) -> None:
        """Record a successful request and reset the circuit.

        Only has an effect when the circuit was in a failure state
        (half-open probe).  If the circuit is healthy this is a no-op.
        """
        with self._lock:
            key = (key_id, model_name)
            state = self._states.get(key)
            if state is None or state.consecutive_failures == 0:
                return

            logger.info(
                "Circuit breaker: key %s / %s recovered after %d failures, resetting state",
                key_id, model_name, state.consecutive_failures,
            )
            del self._states[key]

    # ----- introspection ---------------------------------------------------

    def get_state(self, key_id: int, model_name: str) -> Optional[CircuitState]:
        """Return the current ``CircuitState`` (or ``None``)."""
        with self._lock:
            return self._states.get((key_id, model_name))

    def get_all_states(self) -> List[Dict[str, Any]]:
        """Return a list of all tracked states (for admin display)."""
        with self._lock:
            return [
                {
                    "key_id": s.key_id,
                    "account_id": s.account_id,
                    "model_name": s.model_name,
                    "consecutive_failures": s.consecutive_failures,
                    "error_type": s.error_type,
                    "frozen_until": s.frozen_until,
                    "frozen_remaining": max(0.0, s.frozen_until - time.time()),
                    "escalated": s.escalated,
                    "last_failure_time": s.last_failure_time,
                }
                for s in self._states.values()
            ]

    def clear(self) -> None:
        """Reset all circuit states."""
        with self._lock:
            self._states.clear()

    def clear_one(self, key_id: int, model_name: str) -> bool:
        """Reset a single ``(key_id, model_name)`` circuit.

        Returns ``True`` if a tracked state was removed, ``False`` if there was
        nothing to clear. Useful for manually unfreezing a supplier from the
        admin panel without wiping every circuit.
        """
        with self._lock:
            return self._states.pop((key_id, model_name), None) is not None

    # ----- internals -------------------------------------------------------

    @staticmethod
    def _classify_error(status_code: int) -> str:
        """Map an HTTP status code (or negative code) to a category."""
        if status_code < 0:
            return "network_error"
        return _ERROR_CLASSIFICATION.get(status_code, "server_error")

    def _get_freeze_seconds(
        self, error_type: str, consecutive_failures: int,
    ) -> float:
        """Calculate freeze duration.

        * ``bad_request`` / ``auth_error``: a fixed long duration — retry
          won't resolve the issue.
        * Transient errors (``server_error``, ``timeout``, ``network_error``):
          exponential backoff.
        """
        base = self.freeze_durations.get(error_type, 60.0)

        if error_type in ("bad_request", "auth_error"):
            return base

        if consecutive_failures <= 1:
            return base

        idx = min(consecutive_failures - 2, len(self.backoff_schedule) - 1)
        return self.backoff_schedule[idx]

    @staticmethod
    def _escalate(
        strategy: Any,
        account_id: str,
        model_name: str,
        error_type: Optional[str],
    ) -> None:
        """Notify the supplier strategy that the circuit breaker escalated."""
        if strategy is None:
            return
        handler = getattr(strategy, "on_circuit_breaker_escalation", None)
        if handler is None:
            return
        try:
            handler(account_id, model_name, error_type)
        except Exception:
            logger.exception(
                "Circuit breaker escalation handler failed for %s/%s",
                account_id, model_name,
            )
