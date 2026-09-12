"""Shared Anthropic protocol adapters.

Centralized conversion and utility functions used by both
``anthropic_routes.py`` (Anthropic entry) and ``openai_routes.py``
(OpenAI entry). Keeping them in one module prevents drift between
the two conversion paths.
"""
from typing import Any
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

try:
    from anthropic.types import Message as _SDKMessage
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


# ── Header helpers ──────────────────────────────────────────────────────

def emit_sse_event(event_type: str, data: dict) -> str:
    """Format a complete SSE event: ``event: <type>\\ndata: <json>\\n\\n``."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ── Upstream base resolution ─────────────────────────────────────────────
# NOTE: the protocol (OpenAI vs Anthropic) is decided solely by the client's
# entry point (``/openai/...`` vs ``/anthropic/...``) — ``provider_type`` is the
# supplier's *type* (rate-limit strategy / display) and is NOT the protocol. A
# single supplier can expose both protocols at different URLs.

def resolve_upstream_base(account, protocol: str) -> str:
    """Resolve the upstream base URL for a given protocol.

    A single supplier may expose an OpenAI-compatible endpoint and an
    Anthropic-native endpoint at DIFFERENT URLs. We therefore keep two base
    URLs: ``base_url`` (OpenAI) and the optional ``anthropic_base_url``.

    - ``protocol == "anthropic"`` → prefer ``account.anthropic_base_url``,
      falling back to ``account.base_url`` when unset.
    - ``protocol == "openai"`` → ``account.base_url``.

    The returned value has no trailing slash (the caller appends the path).
    """
    if protocol == "anthropic":
        base = getattr(account, "anthropic_base_url", "") or account.base_url
    else:
        base = account.base_url
    return (base or "").rstrip("/")


# ── Usage extraction (shared by both routes) ────────────────────────────

def extract_cache_usage(usage) -> tuple:
    """Extract cache-related token counts from an upstream usage dict.

    Returns ``(cached_tokens, prompt_partial_cached)``.

    Reads whichever convention the upstream uses: OpenAI's
    ``prompt_tokens_details.cached_tokens`` / ``prompt_partial_cached_tokens``,
    DeepSeek's OpenAI-compatible top-level ``prompt_cache_hit_tokens``, and
    Anthropic's ``cache_read_input_tokens`` / ``cache_creation_input_tokens``.
    The Anthropic keys matter here — ``/v1/messages`` returns them, and
    ``_openai_to_anthropic_response`` produces them, so the non-streaming
    branch of the Anthropic routes must find the cache regardless of which
    upstream path served the request.
    """
    if not isinstance(usage, dict):
        return 0, 0
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        details = {}
    cached = (
        details.get("cached_tokens")
        or usage.get("prompt_cache_hit_tokens")
        or usage.get("cache_read_input_tokens")
    )
    partial = (
        details.get("prompt_partial_cached_tokens")
        or usage.get("cache_creation_input_tokens")
    )
    try:
        return int(cached or 0), int(partial or 0)
    except (TypeError, ValueError):
        return 0, 0


# ── Safe IO helpers ─────────────────────────────────────────────────────

async def safe_read_response_body(response, max_len: int = 50000) -> str:
    """Read the full response body as text, with a length cap.

    Handles both real httpx responses and test mocks that set ``.text``
    directly.
    """
    try:
        try:
            text = response.text
        except Exception:
            await response.aread()
            text = response.text
        if text and len(text) > max_len:
            return text[:max_len] + "...(truncated)"
        return text or ""
    except Exception:
        return ""


async def safe_aclose(response) -> None:
    """Safely close an httpx response."""
    try:
        await response.aclose()
    except Exception:
        pass


# ── Finish reason / stop reason mapping ─────────────────────────────────

def openai_finish_to_anthropic_stop(finish_reason: str) -> str:
    """Map OpenAI ``finish_reason`` to Anthropic ``stop_reason``.

    Values must come from the Anthropic enum (``end_turn`` / ``max_tokens`` /
    ``stop_sequence`` / ``tool_use`` / ``pause_turn`` / ``refusal``); clients
    reject unknown ones. ``content_filter`` has no exact equivalent — the
    closest semantic is ``refusal``.
    """
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "refusal",
    }
    return mapping.get(finish_reason, "end_turn")


def anthropic_stop_to_openai_finish(stop_reason: str) -> str:
    """Map Anthropic ``stop_reason`` to OpenAI ``finish_reason``."""
    mapping = {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "refusal": "content_filter",
    }
    return mapping.get(stop_reason, "stop")


# ── SDK-assisted response parsing ───────────────────────────────────────

def parse_anthropic_response(resp_json: dict) -> dict:
    """Parse an Anthropic-format response using the SDK's Message model if available.

    Returns a validated dict (via ``model_validate`` / ``model_dump``) or
    the raw dict unchanged if SDK is unavailable or parsing fails.
    """
    if _HAS_SDK:
        try:
            msg = _SDKMessage.model_validate(resp_json)
            return msg.model_dump(exclude_none=True)
        except Exception:
            pass
    return resp_json


# ── App-state / request helpers (shared by both route files) ─────────────

def get_admin_service(request: Request):
    """Get the admin service from the FastAPI app state."""
    try:
        svc = request.app.state.admin_service
    except AttributeError:
        return None
    return svc


def get_services(request: Request):
    """Get the services dict from the request's app state."""
    try:
        services = request.app.state.services
    except AttributeError:
        raise HTTPException(status_code=503, detail="Services not initialized")
    if services is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return services


def _authenticate_client_key(request: Request):
    """Authenticate request using client API key (Authorization / X-API-Key)."""
    admin_service = get_admin_service(request)
    if admin_service is None or admin_service.client_key_repo is None:
        return None, None
    auth_header = request.headers.get("Authorization", "")
    client_key = None
    if auth_header.startswith("Bearer "):
        client_key = auth_header[7:].strip()
    elif auth_header.startswith("bearer "):
        client_key = auth_header[7:].strip()
    if not client_key:
        client_key = request.headers.get("X-API-Key", "").strip()
    if not client_key:
        return None, None
    key_record = admin_service.client_key_repo.find_by_key_value(client_key)
    if not key_record:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key",
                }
            },
        )
    if key_record["status"] != "active":
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "message": "API key is disabled",
                    "type": "permission_denied",
                    "param": None,
                    "code": "key_disabled",
                }
            },
        )
    return key_record["name"], client_key


async def _log_error_request(
    admin_service,
    request_model: str,
    actual_model_id: str,
    selected_account,
    client_key_name: str,
    status_code: int,
    error_message: str,
    request_body: dict,
    request_start: str,
    first_response: str = None,
    raw_response: str = None,
    is_stream: bool = False,
    key_id: int = 0,
    error_source: str = None,
):
    """Log a failed request to the admin service.

    ``error_source`` marks where the error came from:
    - ``"upstream"`` - upstream supplier returned the error
    - ``"circuit_open"`` - circuit breaker rejected
    - ``"rate_limit"`` - rate limit / quota exhausted
    - ``"internal"`` - self-generated error
    """
    if not admin_service:
        return
    end_time = datetime.now(timezone.utc).isoformat()
    try:
        await asyncio.to_thread(admin_service.log_request,
            model=request_model,
            actual_model_id=actual_model_id,
            account_id=selected_account.account_id,
            account_name=selected_account.name,
            status_code=status_code,
            input_tokens=0,
            output_tokens=0,
            is_stream=is_stream,
            error_message=error_message,
            raw_request=json.dumps(request_body, ensure_ascii=False),
            raw_response=raw_response or "",
            request_start=request_start,
            first_response=first_response,
            end_time=end_time,
            cached_tokens=0,
            prompt_partial_cached=0,
            client_key_name=client_key_name,
            api_key_id=key_id,
            error_source=error_source,
        )
    except Exception as le:
        logger.error(f"Failed to log error request: {le}", exc_info=True)


# ── Upstream 429 retry-with-backoff ────────────────────────────────────────
# 上游返回 429（限流）时，对**同一候选**做指数退避重试；用尽后再由调用方落到下一候选。
# 预请求配额耗尽的 429（账户窗口）不在此重试 —— 调用方让其直接落下一候选。

# 额外重试次数（不含首次请求）
UPSTREAM_429_MAX_RETRIES = 3
# 指数退避基准（秒），第 n 次重试 = base * 2**n，封顶 CAP
UPSTREAM_429_BACKOFF_BASE = 1.0
UPSTREAM_429_BACKOFF_CAP = 30.0


def parse_retry_after(value: Any, default: float) -> float:
    """Parse an HTTP ``Retry-After`` header into seconds.

    Accepts a delta-seconds integer or an HTTP-date; falls back to ``default``
    when missing or unparseable. Result is always clamped to
    ``UPSTREAM_429_BACKOFF_CAP``.
    """
    if not value:
        return default
    text = str(value).strip()
    try:
        return min(float(text), UPSTREAM_429_BACKOFF_CAP)
    except (TypeError, ValueError):
        pass
    # HTTP-date form: "Fri, 31 Dec 2030 23:59:59 GMT"
    for fmt in ("%a, %d %b %Y %H:%M:%S GMT", "%a, %d-%b-%Y %H:%M:%S GMT"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            delay = (dt - datetime.now(timezone.utc)).total_seconds()
            return min(max(delay, 0.0), UPSTREAM_429_BACKOFF_CAP)
        except ValueError:
            continue
    return default


async def request_with_429_backoff(
    request_fn,
    *,
    max_retries: int = UPSTREAM_429_MAX_RETRIES,
    account_id: str = "?",
    actual_model_id: str = "?",
    close_fn=None,
):
    """Invoke ``request_fn`` and retry on upstream HTTP 429 with backoff.

    Retries happen against the **same candidate**. The upstream ``Retry-After``
    header is honored when present; otherwise the delay is
    ``UPSTREAM_429_BACKOFF_BASE * 2**attempt`` (capped at
    ``UPSTREAM_429_BACKOFF_CAP``). Once retries are exhausted the final
    (possibly still-429) response is returned so the caller's normal error
    path can record the failure and fall back to the next candidate.

    Network errors raised by ``request_fn`` are intentionally NOT retried here —
    they propagate so the caller can treat them as a 502/upstream failure.
    """
    response = await request_fn()
    attempt = 0
    while getattr(response, "status_code", None) == 429 and attempt < max_retries:
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
        delay = parse_retry_after(
            retry_after,
            min(UPSTREAM_429_BACKOFF_BASE * (2 ** attempt), UPSTREAM_429_BACKOFF_CAP),
        )
        logger.warning(
            "Upstream returned 429 for account=%s model=%s — retrying in %.1fs "
            "(attempt %d/%d)",
            account_id, actual_model_id, delay, attempt + 1, max_retries,
        )
        if close_fn is not None:
            try:
                await close_fn(response)
            except Exception:
                pass
        await asyncio.sleep(delay)
        response = await request_fn()
        attempt += 1
    return response
