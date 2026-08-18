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

After the consecutive-failure threshold (``failure_threshold_token`` = 10 for
token-window models, ``failure_threshold_count`` = 20 for count-window models)
the circuit is *escalated*. Escalation does **not** mark the model unavailable —
it only lengthens the freeze: the exponential backoff ceiling rises from the
normal 8 min to a window-aware cap (the window duration for count-window models,
end-of-day 24:00 for token-window models). Once the freeze expires the circuit
goes half-open and can recover via a successful probe — escalation is no longer
permanent.

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
from datetime import datetime, timedelta
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
        cb.record_failure(key_id, account_id, model_name, status_code)
    """

    def __init__(self):
        # Key: (key_id, model_name) → CircuitState
        self._states: Dict[Tuple[int, str], CircuitState] = {}

        # Tunable parameters (exposed so subclasses / callers can tweak)
        self.error_classification = dict(_ERROR_CLASSIFICATION)
        self.freeze_durations = dict(_FREEZE_DURATIONS)
        self.backoff_schedule = list(_BACKOFF_SCHEDULE)
        self.failure_threshold = _CONSECUTIVE_FAILURE_THRESHOLD
        # Consecutive failures before escalation, per window mode:
        #  - token-window models keep the original 10.
        #  - count-window models (fixed_window / fixed_window_per_model) are
        #    raised to 20, because a 429 / rate_limited there is the *expected*
        #    "window full" signal, not a fault — we don't want a burst of
        #    rate-limit hits to mark the model unavailable.
        self.failure_threshold_token = _CONSECUTIVE_FAILURE_THRESHOLD  # 10
        self.failure_threshold_count = 20
        self.escalation_freeze_seconds = _ESCALATION_FREEZE_SECONDS
        # Optional resolver: ``(account_id, model_name) -> "count" | "token"``.
        # When set, ``record_failure`` uses it to pick the per-model freeze /
        # escalation thresholds instead of the default ``window_mode`` argument.
        # Installed by ``core/service_init.py`` from the supplier config so the
        # route layer doesn't need to thread the strategy through manually.
        self.window_mode_resolver = None
        # Optional resolver: ``(account_id, model_name) -> float`` (window
        # duration in seconds). When set and a count-window circuit escalates,
        # the freeze ceiling is this window duration instead of the default.
        # Token-window (no count window) models are capped at end-of-day
        # instead. Installed by ``core/service_init.py``.
        self.window_seconds_resolver = None

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
        window_mode: Optional[str] = None,
    ) -> None:
        """Record a failure and (possibly) freeze the circuit.

        ``key_id`` is the ``account_api_keys.id`` (0 = primary key).  ``account_id``
        is stored for display only.  ``status_code`` can be an HTTP status code
        or a negative number for network errors (e.g. ``-1`` for timeout,
        ``-2`` for connection error).

        ``window_mode`` is ``"count"`` for request-count-window models
        (``fixed_window`` / ``fixed_window_per_model``, metered by
        ``max_requests``) and ``"token"`` otherwise.  Count-window models get a
        higher escalation threshold and are never frozen on transient
        upstream faults (``rate_limited`` / ``server_error`` / ``network_error``
        / ``timeout``) — a 429 means the window is full, a 5xx/timeout is a
        transient upstream hiccup, and a single-account model has nothing to
        fail over to, so freezing would only amplify the outage.

        Escalation never marks a model unavailable — it only lengthens the
        freeze via exponential backoff, capped at the window duration
        (count-window) or end-of-day (token-window).
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

            # Resolve window mode (count vs token) unless explicitly provided.
            if window_mode is None:
                window_mode = self._resolve_window_mode(account_id, model_name)

            # ----- Escalation (threshold is window-mode aware) -----
            # Once the consecutive-failure threshold is hit, the circuit is
            # "escalated": it no longer uses the short backoff ceiling but backs
            # off exponentially up to a window-aware ceiling (see
            # ``_escalation_cap``).  Escalation does NOT mark the model
            # unavailable — it only lengthens the freeze.  The actual freeze is
            # applied below via ``_get_freeze_seconds``.
            esc_threshold = (
                self.failure_threshold_count
                if window_mode == "count"
                else self.failure_threshold_token
            )
            if (
                state.consecutive_failures >= esc_threshold
                and not state.escalated
            ):
                state.escalated = True
                logger.warning(
                    "Circuit breaker: key %s / %s (account %s, mode=%s) reached %d "
                    "consecutive failures — escalating (longer backoff, no mark-unavailable)",
                    key_id, model_name, account_id, window_mode,
                    state.consecutive_failures,
                )

            # Count-window models: transient upstream faults (rate_limited /
            # server_error / network_error / timeout) are the *expected* signal
            # for a request-count-metered model — the window being full, or a
            # brief upstream hiccup. Never freeze on them: a single-account
            # model (e.g. 商汤 GLM-5.2) has no fallback to fail over to, so a
            # freeze would just hard-block the whole model. Only permanent
            # errors (bad_request / auth_error) still freeze.
            if window_mode == "count" and state.error_type in (
                "rate_limited", "server_error", "network_error", "timeout",
            ):
                logger.info(
                    "Circuit breaker: key %s / %s (count-window) transient %s (status=%s), "
                    "not freezing — allowing client/retry instead of hard-block",
                    key_id, model_name, state.error_type, status_code,
                )
                return

            # 瞬时错误（server_error / network_error / timeout / rate_limited）第 1 次
            # 失败不冻结 — 允许下一次请求继续尝试，避免单一候选场景因一次上游抖动
            # （含偶发 429）就整条路由冻住。第 2 次起才进入冻结 + exponential backoff。
            # bad_request / auth_error 不在此列：这些错误重试无意义，立即冻结。
            # （count-window 模型的 rate_limited 已在上一个分支处理。）
            if state.consecutive_failures == 1 and state.error_type in (
                "server_error", "network_error", "timeout", "rate_limited",
            ):
                logger.info(
                    "Circuit breaker: key %s / %s first transient failure (status=%s), "
                    "not freezing — allowing next request to retry",
                    key_id, model_name, status_code,
                )
                return

            # ----- Freeze (exponential backoff, capped) -----
            # Non-escalated: capped at the normal backoff ceiling. Escalated:
            # capped at the window duration (count-window) or end-of-day (token).
            cap = (
                self._escalation_cap(window_mode, account_id, model_name)
                if state.escalated
                else self.backoff_schedule[-1]
            )
            freeze_seconds = self._get_freeze_seconds(
                state.error_type, state.consecutive_failures, cap=cap,
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

    def _resolve_window_mode(self, account_id: str, model_name: str) -> str:
        """Return ``"count"`` or ``"token"`` for a circuit, via the resolver.

        Falls back to ``"token"`` when no resolver is installed or it raises —
        token-window is the stricter (lower-threshold) behaviour, so it's the
        safe default.
        """
        if self.window_mode_resolver is None:
            return "token"
        try:
            return self.window_mode_resolver(account_id, model_name) or "token"
        except Exception:
            logger.exception(
                "Circuit breaker window_mode_resolver failed for %s/%s",
                account_id, model_name,
            )
            return "token"

    def _get_freeze_seconds(
        self,
        error_type: str,
        consecutive_failures: int,
        cap: Optional[float] = None,
    ) -> float:
        """Calculate freeze duration.

        * ``bad_request`` / ``auth_error``: a fixed long duration — retry
          won't resolve the issue.
        * Transient errors (``server_error``, ``timeout``, ``network_error``,
          ``rate_limited``): exponential backoff. ``cap`` bounds the ceiling —
          for escalated circuits this is the window duration (count) or
          end-of-day (token); for normal circuits it is the backoff schedule
          maximum.
        """
        base = self.freeze_durations.get(error_type, 60.0)

        if error_type in ("bad_request", "auth_error"):
            return base

        if consecutive_failures <= 1:
            return base

        idx = consecutive_failures - 2
        if idx < len(self.backoff_schedule):
            return self.backoff_schedule[idx]
        # Beyond the explicit schedule: keep doubling from the last step, bounded
        # by ``cap`` (falls back to the schedule maximum when ``cap`` is None).
        last = self.backoff_schedule[-1]
        extra = idx - len(self.backoff_schedule) + 1
        val = last * (2 ** extra)
        if cap is not None:
            val = min(val, cap)
        return val

    def _escalation_cap(self, window_mode: str, account_id: str, model_name: str) -> float:
        """Freeze ceiling once a circuit is escalated.

        Count-window models: the window duration (from ``window_seconds_resolver``,
        falling back to ``escalation_freeze_seconds``).  Token-window / no-window
        models: until the end of the current day (24:00).
        """
        if window_mode == "count":
            if self.window_seconds_resolver is not None:
                try:
                    w = self.window_seconds_resolver(account_id, model_name)
                    if w:
                        return float(w)
                except Exception:
                    logger.exception(
                        "Circuit breaker window_seconds_resolver failed for %s/%s",
                        account_id, model_name,
                    )
            return float(self.escalation_freeze_seconds)
        return self._seconds_until_end_of_day()

    @staticmethod
    def _seconds_until_end_of_day() -> float:
        """Seconds from now until 24:00 (start of the next day)."""
        now = datetime.now()
        end = datetime(now.year, now.month, now.day) + timedelta(days=1)
        return max(0.0, (end - now).total_seconds())
