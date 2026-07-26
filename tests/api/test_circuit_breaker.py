"""Tests for the Circuit Breaker service.

Tests cover:
- Basic state machine (closed → open → half-open → closed)
- Error classification by HTTP status code
- Exponential backoff for transient errors
- Long freeze for auth/bad request errors
- Escalation to supplier strategy after threshold
- Half-open state allows probe requests
- Success resets the circuit
- Integration with _try_candidate (failure recording)
- Integration with fallback loop (skip frozen candidates)
- Admin endpoint
"""
import json
import os
import time
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from provider.main import create_app
from services.circuit_breaker import CircuitBreaker, CircuitState

# ---------------------------------------------------------------------------
# Unit tests — pure CircuitBreaker logic
# ---------------------------------------------------------------------------


class TestErrorClassification:
    """Classify HTTP status codes correctly."""

    def test_400_is_bad_request(self):
        cb = CircuitBreaker()
        assert cb._classify_error(400) == "bad_request"
        assert cb._classify_error(404) == "bad_request"
        assert cb._classify_error(422) == "bad_request"

    def test_401_403_is_auth_error(self):
        cb = CircuitBreaker()
        assert cb._classify_error(401) == "auth_error"
        assert cb._classify_error(403) == "auth_error"

    def test_500_series_is_server_error(self):
        cb = CircuitBreaker()
        assert cb._classify_error(500) == "server_error"
        assert cb._classify_error(502) == "server_error"
        assert cb._classify_error(503) == "server_error"

    def test_negative_is_network_error(self):
        cb = CircuitBreaker()
        assert cb._classify_error(-1) == "network_error"
        assert cb._classify_error(-2) == "network_error"

    def test_unknown_status_falls_back_to_server_error(self):
        cb = CircuitBreaker()
        assert cb._classify_error(999) == "server_error"


class TestFreezeDuration:
    """Exponential backoff for transient errors, fixed for auth/bad_request."""

    def test_bad_request_uses_fixed_long_duration(self):
        cb = CircuitBreaker()
        # Even with many failures, bad_request is always 1800s
        assert cb._get_freeze_seconds("bad_request", 1) == 1800.0
        assert cb._get_freeze_seconds("bad_request", 5) == 1800.0
        assert cb._get_freeze_seconds("bad_request", 10) == 1800.0

    def test_auth_error_uses_fixed_long_duration(self):
        cb = CircuitBreaker()
        assert cb._get_freeze_seconds("auth_error", 1) == 3600.0
        assert cb._get_freeze_seconds("auth_error", 3) == 3600.0

    def test_server_error_first_failure_is_60s(self):
        cb = CircuitBreaker()
        assert cb._get_freeze_seconds("server_error", 1) == 60.0

    def test_server_error_exponential_backoff(self):
        cb = CircuitBreaker()
        # 1st → 60s, 2nd → 60s, 3rd → 120s, 4th → 240s, 5th → 480s, 6th+ → 480s
        assert cb._get_freeze_seconds("server_error", 1) == 60.0
        assert cb._get_freeze_seconds("server_error", 2) == 60.0
        assert cb._get_freeze_seconds("server_error", 3) == 120.0
        assert cb._get_freeze_seconds("server_error", 4) == 240.0
        assert cb._get_freeze_seconds("server_error", 5) == 480.0
        assert cb._get_freeze_seconds("server_error", 6) == 480.0  # capped

    def test_network_error_exponential_backoff(self):
        cb = CircuitBreaker()
        assert cb._get_freeze_seconds("network_error", 1) == 60.0
        assert cb._get_freeze_seconds("network_error", 3) == 120.0


class TestStateMachine:
    """Closed → Open → Half-Open → Closed cycle."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.check("acc-1", "model-1") is True

    def test_single_failure_freezes_temporarily(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        # Should be frozen
        assert cb.check("acc-1", "model-1") is False
        # Other (account, model) is unaffected
        assert cb.check("acc-2", "model-1") is True

    def test_success_resets_circuit(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        assert cb.check("acc-1", "model-1") is False
        cb.record_success("acc-1", "model-1")
        assert cb.check("acc-1", "model-1") is True

    def test_half_open_allows_probe_after_freeze_expires(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        # Manually expire the freeze
        state = cb.get_state("acc-1", "model-1")
        assert state is not None
        state.frozen_until = time.time() - 1  # expired
        # Should be half-open → allow probe
        assert cb.check("acc-1", "model-1") is True

    def test_probe_success_resets(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        state = cb.get_state("acc-1", "model-1")
        state.frozen_until = time.time() - 1  # expired
        # Half-open → probe allowed
        assert cb.check("acc-1", "model-1") is True
        # Success resets
        cb.record_success("acc-1", "model-1")
        assert cb.get_state("acc-1", "model-1") is None

    def test_probe_failure_reopens(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)  # 1st failure
        state = cb.get_state("acc-1", "model-1")
        state.frozen_until = time.time() - 1  # expired
        # Half-open → probe allowed
        assert cb.check("acc-1", "model-1") is True
        # Probe fails → reopened with longer freeze
        cb.record_failure("acc-1", "model-1", 500)
        assert cb.check("acc-1", "model-1") is False
        state2 = cb.get_state("acc-1", "model-1")
        assert state2 is not None
        assert state2.consecutive_failures == 2
        # Second failure → 60s (backoff starts at index 0 for 2nd failure)
        assert state2.frozen_until > time.time()

    def test_10_consecutive_failures_escalates(self):
        cb = CircuitBreaker()
        strategy = Mock()
        for i in range(10):
            cb.record_failure("acc-1", "model-1", 500, strategy)
        state = cb.get_state("acc-1", "model-1")
        assert state is not None
        assert state.escalated is True
        assert cb.check("acc-1", "model-1") is False  # permanently blocked

    def test_escalation_notifies_strategy(self):
        cb = CircuitBreaker()
        strategy = Mock()
        strategy.on_circuit_breaker_escalation = Mock()
        for i in range(10):
            cb.record_failure("acc-1", "model-1", 500, strategy)
        strategy.on_circuit_breaker_escalation.assert_called_once_with(
            "acc-1", "model-1", "server_error"
        )

    def test_different_accounts_are_independent(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        assert cb.check("acc-1", "model-1") is False
        assert cb.check("acc-2", "model-1") is True
        assert cb.check("acc-1", "model-2") is True

    def test_get_all_states_returns_summary(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        cb.record_failure("acc-2", "model-2", 401)
        states = cb.get_all_states()
        assert len(states) == 2
        for s in states:
            assert "account_id" in s
            assert "model_name" in s
            assert "consecutive_failures" in s
            assert "frozen_remaining" in s

    def test_clear_resets_all_states(self):
        cb = CircuitBreaker()
        cb.record_failure("acc-1", "model-1", 500)
        cb.record_failure("acc-2", "model-2", 401)
        assert len(cb.get_all_states()) == 2
        cb.clear()
        assert len(cb.get_all_states()) == 0


# ---------------------------------------------------------------------------
# Integration tests — circuit breaker wired into the API
# ---------------------------------------------------------------------------

_TEST_ACCOUNTS_JSON = json.dumps(
    [
        {
            "account_id": "test-acc-" + uuid.uuid4().hex[:8],
            "name": "test-account",
            "api_key": "test-key",
            "base_url": "https://api.modelscope.test/v1",
        }
    ]
)


@pytest.fixture()
def client():
    """Lifespan-aware client so services / admin service are initialized."""
    os.environ["MODELSCOPE_ACCOUNTS_JSON"] = _TEST_ACCOUNTS_JSON
    app = create_app()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("MODELSCOPE_ACCOUNTS_JSON", None)


class TestIntegrationCircuitBreaker:
    """Circuit breaker wired into the API routes."""

    def test_circuit_breaker_initialized_in_services(self, client):
        """CircuitBreaker should be available in app services."""
        services = client.app.state.services
        assert "circuit_breaker" in services
        cb = services["circuit_breaker"]
        assert isinstance(cb, CircuitBreaker)

    def test_failure_recorded_on_400_error(self, client):
        """When a candidate returns 400, the circuit breaker should record it."""
        app = client.app
        http_client = app.state.services["http_client"]
        alias_router = app.state.alias_router
        alias_resolver = app.state.services["alias_resolver"]
        cb = app.state.services["circuit_breaker"]

        account1 = Mock()
        account1.account_id = "acc-1"
        account1.name = "Supplier 1"
        account1.api_key = "key1"
        account1.base_url = "https://api1.test.com"
        account1.provider_type = "modelscope"

        account2 = Mock()
        account2.account_id = "acc-2"
        account2.name = "Supplier 2"
        account2.api_key = "key2"
        account2.base_url = "https://api2.test.com"
        account2.provider_type = "modelscope"

        from provider.services.alias_router import RoutingResult
        candidates = [
            RoutingResult(account=account1, model_name="test-model"),
            RoutingResult(account=account2, model_name="test-model"),
        ]

        response_400 = Mock()
        response_400.status_code = 400
        response_400.text = '{"error": "Bad Request"}'
        response_400.headers = {}

        async def _success_lines():
            yield 'data: {"id":"cmpl-1","object":"chat.completion.chunk","choices":[{"delta":{"content":"ok"}}]}'
            yield "data: [DONE]"

        response_200 = Mock()
        response_200.status_code = 200
        response_200.text = ""
        response_200.headers = {}
        response_200.aiter_lines = _success_lines

        with (
            patch.object(alias_router, "get_candidates", return_value=candidates),
            patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
            patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
        ):
            mock_req.side_effect = [response_400, response_200]
            mock_resolve.return_value = "test-model"

            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )

        assert resp.status_code == 200
        # Should have recorded failure for acc-1
        state = cb.get_state("acc-1", "test-model")
        assert state is not None
        assert state.consecutive_failures == 1
        assert state.error_type == "bad_request"
        # Should NOT have recorded anything for acc-2 (it succeeded)
        assert cb.get_state("acc-2", "test-model") is None

    def test_admin_endpoint_shows_circuit_breaker_state(self, client):
        """The /api/admin/circuit-breaker endpoint should show state."""
        cb = client.app.state.services["circuit_breaker"]
        cb.record_failure("acc-1", "model-1", 500)
        cb.record_failure("acc-2", "model-2", 401)

        resp = client.get("/api/admin/circuit-breaker")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["frozen"] >= 2
        # Should list both circuits
        accounts = {c["account_id"] for c in data["circuits"]}
        assert "acc-1" in accounts
        assert "acc-2" in accounts