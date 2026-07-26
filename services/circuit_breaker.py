"""Circuit breaker for upstream API failures.

Tracks failures per ``(account_id, model_name)`` pair with configurable
freeze duration and exponential backoff. Used by the fallback loop to
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
account, etc.).

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

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CircuitState:
    """Mutable state for a single ``(account_id, model_name)`` circuit."""

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

    Designed for single-threaded async contexts (FastAPI event loop).
    Thread safety is not guaranteed.

    Usage
    -----
    .. code-block:: python

        cb = CircuitBreaker()

        # Before request — skip if frozen
        if not cb.check(account_id, model_name):
            continue  # try next candidate

        # After successful request
        cb.record_success(account_id, model_name)

        # After failed request
        cb.record_failure(account_id, model_name, status_code, strategy)
    """

    def __init__(self):
        # Key: (account_id, model_name) → CircuitState
        self._states: Dict[Tuple[str, str], CircuitState] = {}

        # Tunable parameters (exposed so subclasses / callers can tweak)
        self.error_classification = dict(_ERROR_CLASSIFICATION)
        self.freeze_durations = dict(_FREEZE_DURATIONS)
        self.backoff_schedule = list(_BACKOFF_SCHEDULE)
        self.failure_threshold = _CONSECUTIVE_FAILURE_THRESHOLD

    # ----- public API ------------------------------------------------------

    def check(self, account_id: str, model_name: str) -> bool:
        """Return ``True`` if the request may proceed (circuit is closed).

        Returns ``False`` if the circuit is open (frozen).  Once the freeze
        expires the circuit enters *half-open* state — the next call returns
        ``True`` so a probe request is allowed.
        """
        state = self._states.get((account_id, model_name))
        if state is None:
            return True

        if state.escalated:
            return False

        if time.time() < state.frozen_until:
            return False

        # Freeze expired → half-open: allow probe
        if state.consecutive_failures > 0:
            logger.info(
                "Circuit breaker half-open for %s/%s: "
                "freeze expired, allowing probe request",
                account_id, model_name,
            )
        return True

    def record_failure(
        self,
        account_id: str,
        model_name: str,
        status_code: int,
        strategy: Any = None,
    ) -> None:
        """Record a failure and (possibly) freeze the circuit.

        Parameters
        ----------
        account_id:
            The account that failed.
        model_name:
            The model that failed.
        status_code:
            HTTP status code or a negative number for network errors
            (e.g. ``-1`` for timeout, ``-2`` for connection error).
        strategy:
            Optional ``RateLimitStrategy`` that will be notified when the
            failure threshold is reached.
        """
        key = (account_id, model_name)
        state = self._states.get(key)
        if state is None:
            state = CircuitState(account_id=account_id, model_name=model_name)
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
            logger.warning(
                "Circuit breaker: %s/%s reached %d consecutive failures, "
                "escalating to supplier strategy",
                account_id, model_name, state.consecutive_failures,
            )
            self._escalate(strategy, account_id, model_name, state.error_type)
            return

        # ----- Freeze -----
        freeze_seconds = self._get_freeze_seconds(
            state.error_type, state.consecutive_failures,
        )
        state.frozen_until = time.time() + freeze_seconds

        logger.warning(
            "Circuit breaker: %s/%s failed (status=%s, type=%s, "
            "failures=%d), freezing for %.0fs",
            account_id, model_name,
            status_code, state.error_type,
            state.consecutive_failures, freeze_seconds,
        )

    def record_success(self, account_id: str, model_name: str) -> None:
        """Record a successful request and reset the circuit.

        Only has an effect when the circuit was in a failure state
        (half-open probe).  If the circuit is healthy this is a no-op.
        """
        key = (account_id, model_name)
        state = self._states.get(key)
        if state is None or state.consecutive_failures == 0:
            return

        logger.info(
            "Circuit breaker: %s/%s recovered after %d failures, resetting state",
            account_id, model_name, state.consecutive_failures,
        )
        del self._states[key]

    # ----- introspection ---------------------------------------------------

    def get_state(self, account_id: str, model_name: str) -> Optional[CircuitState]:
        """Return the current ``CircuitState`` (or ``None``)."""
        return self._states.get((account_id, model_name))

    def get_all_states(self) -> List[Dict[str, Any]]:
        """Return a list of all tracked states (for admin display)."""
        return [
            {
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
        self._states.clear()

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