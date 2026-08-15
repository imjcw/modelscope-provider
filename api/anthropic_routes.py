"""Anthropic Messages API protocol routes.

Adapts Anthropic ``/v1/messages`` requests to OpenAI-compatible upstream
providers. The gateway sends OpenAI-formatted requests upstream and
converts the response back to Anthropic format — transparently to the
client, which talks Anthropic natively.

Protocol reference: https://docs.anthropic.com/en/api/messages
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, AsyncGenerator, Any, Union
import copy
import json
import asyncio
import logging
import time
from datetime import datetime, timezone
import uuid
import httpx

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request schema ──────────────────────────────────────────────────────

class AnthropicMessagesRequest(BaseModel):
    """Anthropic Messages API request.

    Mirrors the Anthropic Messages endpoint shape. Uses ``Any`` for
    ``messages`` content so multi-modal blocks (images, files, tool results)
    pass through without schema rejection.
    """
    model: str = Field(..., description="Model name or alias (e.g. claude-sonnet-4-20250514)")
    messages: List[Any] = Field(..., description="Message array (Anthropic format)")
    max_tokens: int = Field(..., description="Maximum output tokens")
    system: Optional[Any] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None
    metadata: Optional[dict] = None


# ── Helpers ─────────────────────────────────────────────────────────────

def _extract_cache_usage(usage) -> tuple:
    """Extract (cached_tokens, prompt_partial_cached) from usage dict."""
    if not isinstance(usage, dict):
        return 0, 0
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        details = {}
    cached = details.get("cached_tokens")
    if cached is None:
        cached = usage.get("prompt_cache_hit_tokens", 0) or 0
    partial = details.get("prompt_partial_cached_tokens") or 0
    return int(cached or 0), int(partial or 0)


async def _safe_read_response_body(response, max_len: int = 50000) -> str:
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


async def _safe_aclose(response) -> None:
    try:
        await response.aclose()
    except Exception:
        pass


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


def get_admin_service(request: Request):
    try:
        svc = request.app.state.admin_service
    except AttributeError:
        return None
    return svc


def get_services(request: Request):
    try:
        services = request.app.state.services
    except AttributeError:
        raise HTTPException(status_code=503, detail="Services not initialized")
    if services is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return services


def _authenticate_client_key(request: Request):
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


# ── Anthropic ↔ OpenAI adapters ─────────────────────────────────────────

def _anthropic_content_to_openai(content: Any) -> str:
    """Convert Anthropic content (str or block array) to OpenAI content string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                # Ignore non-text blocks (images, tool results) for the
                # OpenAI upstream — multi-modal passthrough would need
                # base64-image handling which varies by provider.
        return "\n".join(parts) if parts else ""
    return str(content) if content else ""


def _openai_message_to_anthropic(message: dict) -> dict:
    """Convert an OpenAI assistant message to Anthropic content blocks."""
    if not isinstance(message, dict):
        return {"content": []}
    blocks = []
    content = message.get("content", "") or ""
    if content:
        blocks.append({"type": "text", "text": content})
    tool_calls = message.get("tool_calls") or []
    for tc in tool_calls:
        if isinstance(tc, dict):
            function = tc.get("function", {})
            blocks.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": function.get("name", ""),
                "input": function.get("arguments"),
            })
            if isinstance(function.get("arguments"), str):
                try:
                    blocks[-1]["input"] = json.loads(function["arguments"])
                except Exception:
                    pass
    return {"content": blocks}


def _openai_finish_to_anthropic_stop(finish_reason: str) -> str:
    """Map OpenAI finish_reason to Anthropic stop_reason."""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "stopped_by",
    }
    return mapping.get(finish_reason, "end_turn")


async def _anthropic_to_openai_body(data: AnthropicMessagesRequest, actual_model_id: str) -> dict:
    """Convert an Anthropic MessagesRequest to an OpenAI-compatible upstream body."""
    body = {
        "model": actual_model_id,
        "max_tokens": data.max_tokens,
    }
    if data.temperature is not None:
        body["temperature"] = data.temperature
    if data.top_p is not None:
        body["top_p"] = data.top_p
    if data.stop_sequences is not None:
        body["stop"] = data.stop_sequences
    if data.top_k is not None:
        body["top_k"] = data.top_k

    # Build messages array: merge top-level system + per-message system
    openai_messages = []

    # Top-level system prompt
    if data.system is not None:
        sys_content = data.system if isinstance(data.system, str) else json.dumps(data.system)
        openai_messages.append({"role": "system", "content": sys_content})

    # Per-message conversion
    for msg in data.messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content")
        if content is None:
            continue

        # Anthropic tool_result blocks → OpenAI tool role message
        if role == "tool_use" or role == "tool_result":
            # Anthropic puts tool results in user messages; skip raw tool_use role
            # from Anthropic SDK (it doesn't actually send tool_use role)
            pass

        openai_content = _anthropic_content_to_openai(content)

        # Tool use blocks in assistant messages
        if role == "assistant" and isinstance(content, list):
            tool_calls = []
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            if tool_calls:
                openai_messages.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                    "tool_calls": tool_calls,
                })
            elif text_parts:
                openai_messages.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                })
            continue

        # Tool result blocks in user messages → separate tool messages
        if role == "user" and isinstance(content, list):
            text_parts = []
            tool_results = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_results.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            if tool_results:
                for tr in tool_results:
                    tool_call_id = tr.get("tool_use_id", f"toolu_{uuid.uuid4().hex[:24]}")
                    content_val = tr.get("content", "")
                    if isinstance(content_val, list):
                        content_val = "\n".join(
                            b.get("text", "") for b in content_val if isinstance(b, dict) and b.get("type") == "text"
                        )
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": str(content_val),
                    })
            if text_parts:
                openai_messages.append({
                    "role": "user",
                    "content": "\n".join(text_parts),
                })
            continue

        openai_messages.append({
            "role": role,
            "content": openai_content,
        })

    body["messages"] = openai_messages

    # Tools conversion: Anthropic format → OpenAI format
    if data.tools:
        openai_tools = []
        for tool in data.tools:
            if isinstance(tool, dict):
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
        if openai_tools:
            body["tools"] = openai_tools

    # tool_choice conversion
    if data.tool_choice is not None:
        tc = data.tool_choice
        if isinstance(tc, dict):
            tc_type = tc.get("type")
            if tc_type == "auto":
                body["tool_choice"] = "auto"
            elif tc_type == "any":
                body["tool_choice"] = "any"
            elif tc_type == "tool" and tc.get("name"):
                body["tool_choice"] = {"type": "function", "function": {"name": tc["name"]}}
        elif tc == "auto":
            body["tool_choice"] = "auto"
        elif tc == "none":
            body["tool_choice"] = "none"

    return body


def _openai_to_anthropic_response(resp_json: dict, model_name: str) -> dict:
    """Convert an OpenAI chat completion response to Anthropic Messages format."""
    choices = resp_json.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}
    finish_reason = first.get("finish_reason", "stop")

    anthro_content = _openai_message_to_anthropic(message)

    usage = resp_json.get("usage", {}) or {}
    input_tokens = usage.get("prompt_tokens", 0) or 0
    output_tokens = usage.get("completion_tokens", 0) or 0
    cached_tokens, prompt_partial_cached = _extract_cache_usage(usage)

    result = {
        "id": f"msg_{uuid.uuid4().hex[:32]}",
        "type": "message",
        "role": "assistant",
        "content": anthro_content["content"],
        "model": resp_json.get("model", model_name),
        "stop_reason": _openai_finish_to_anthropic_stop(finish_reason),
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }

    if cached_tokens > 0:
        result["usage"]["cache_creation_input_tokens"] = cached_tokens
    if prompt_partial_cached > 0:
        result["usage"]["cache_read_input_tokens"] = prompt_partial_cached

    return result


async def stream_response_anthropic(
    response,
    actual_model_id: str,
    _capture_headers: bool = False,
) -> AsyncGenerator[str, None]:
    """Convert an OpenAI SSE stream to Anthropic SSE stream format.

    Anthropic stream events:
      - message_start       (on first delta)
      - content_block_start (on first delta per content block)
      - content_block_delta (per delta chunk)
      - content_block_stop  (on finish)
      - message_delta       (on finish with usage)
      - message_stop        (on finish)
    """
    decoder = json.JSONDecoder()
    block_idx = 0
    first_delta = True
    saw_finish = False
    saw_done = False
    yielded_any = False
    total_output_tokens = 0
    block_types = []  # track block types for this stream

    if _capture_headers:
        hdrs = {}
        try:
            hdrs = dict(response.headers)
        except Exception:
            pass
        yield f"data: {json.dumps({'__hdrs__': hdrs})}\n\n"

    def _emit(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    try:
        async for line in response.aiter_lines():
            stripped = line.strip()
            if stripped == "[DONE]":
                saw_done = True
                if not saw_finish:
                    # Force close any open block
                    if block_types:
                        yield _emit("content_block_stop", {"index": 0})
                    yield _emit("message_delta", {
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": total_output_tokens},
                    })
                    yield _emit("message_stop", {})
                # If no content was ever yielded, emit an error marker
                if not yielded_any:
                    error_data = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Upstream returned empty stream",
                        },
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                return

            if not stripped.startswith("data:"):
                continue
            data_str = stripped[5:].strip()
            if not data_str:
                continue

            try:
                chunk, _ = decoder.raw_decode(data_str)
            except json.JSONDecodeError:
                yield f"data: {data_str}\n\n"
                yielded_any = True
                continue

            if not isinstance(chunk, dict):
                continue

            choices = chunk.get("choices")
            if not choices:
                continue  # heartbeat

            delta = (choices[0] or {}).get("delta") or {}
            finish_reason = (choices[0] or {}).get("finish_reason")
            usage = chunk.get("usage")

            # Update output token count from usage in final chunk
            if usage and isinstance(usage, dict):
                total_output_tokens = usage.get("completion_tokens", total_output_tokens) or total_output_tokens

            # Emit message_start on first delta
            if first_delta and delta:
                msg_id = f"msg_{uuid.uuid4().hex[:32]}"
                yield _emit("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": actual_model_id,
                    },
                })
                first_delta = False
                yielded_any = True

            # Detect tool_use delta
            if finish_reason:
                if not saw_finish:
                    saw_finish = True
                    # Close current block
                    yield _emit("content_block_stop", {"index": block_idx})
                    yield _emit("message_delta", {
                        "delta": {"stop_reason": _openai_finish_to_anthropic_stop(finish_reason),
                                  "stop_sequence": None},
                        "usage": {"output_tokens": total_output_tokens},
                    })
                    yield _emit("message_stop", {})
                continue

            # Emit content_block_start on first text delta for this block
            if delta.get("content") or delta.get("role"):
                if delta.get("role") == "assistant":
                    # First delta has role but no content
                    if first_delta:
                        first_delta = False
                    yield _emit("content_block_start", {
                        "type": "content_block_start",
                        "index": block_idx,
                        "content_block": {"type": "text", "text": ""},
                    })
                    block_types.append("text")
                    yielded_any = True
                    continue

                text = delta.get("content", "") or ""
                if text:
                    if block_types and block_types[-1] != "text":
                        block_idx += 1
                        yield _emit("content_block_start", {
                            "type": "content_block_start",
                            "index": block_idx,
                            "content_block": {"type": "text", "text": ""},
                        })
                        block_types.append("text")

                    yield _emit("content_block_delta", {
                        "type": "content_block_delta",
                        "index": block_idx,
                        "delta": {"type": "text_delta", "text": text},
                    })
                    yielded_any = True

            # Tool use deltas
            tool_calls = delta.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fc = tc.get("function", {})
                    tc_name = fc.get("name", "")
                    tc_args = fc.get("arguments", "") or ""

                    if tc_name:
                        # New tool_use block
                        block_idx += 1
                        yield _emit("content_block_start", {
                            "type": "content_block_start",
                            "index": block_idx,
                            "content_block": {
                                "type": "tool_use",
                                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                                "name": tc_name,
                                "input": {},
                            },
                        })
                        block_types.append("tool_use")
                        yielded_any = True

                    if tc_args:
                        yield _emit("content_block_delta", {
                            "type": "content_block_delta",
                            "index": block_idx,
                            "delta": {"type": "input_json_delta", "partial_json": tc_args},
                        })
                        yielded_any = True

    finally:
        await _safe_aclose(response)
        if not yielded_any and not saw_done and not saw_finish:
            error_data = {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "Upstream returned empty stream",
                },
            }
            yield f"data: {json.dumps(error_data)}\n\n"


# ── Candidate loop ──────────────────────────────────────────────────────

async def _try_anthropic_candidate(
    *,
    request: AnthropicMessagesRequest,
    account,
    actual_model_id: str,
    body: dict,
    http_client,
    admin_service,
    quota_updater,
    services: dict,
    client_key_name: str,
    circuit_breaker,
    alias_router,
    candidate_idx: int,
    total_candidates: int,
):
    """Try one candidate supplier for Anthropic protocol."""
    if candidate_idx > 0 or total_candidates > 1:
        logger.info(
            "Anthropic candidate %d/%d: account=%s model=%s stream=%s",
            candidate_idx + 1, total_candidates,
            account.account_id, actual_model_id, request.stream,
        )

    key_id = getattr(account, "_key_id", 0) or 0
    api_key = getattr(account, "_key_string", None) or account.api_key

    request_start = datetime.now(timezone.utc).isoformat()
    provider_type = account.provider_type or "modelscope"
    strategies = services.get("rate_limit_strategies", {})
    rate_strategy = strategies.get(provider_type)
    if rate_strategy and not rate_strategy.check_rate_limit(
            account.account_id, actual_model_id):
        await _log_error_request(
            admin_service, request.model, actual_model_id, account,
            client_key_name, 429,
            f"Supplier {account.name or account.account_id} quota exhausted",
            body, request_start, is_stream=request.stream, key_id=key_id,
            error_source="rate_limit",
        )
        raise HTTPException(status_code=429, detail={
            "error": {"message": f"Rate limit exceeded",
                      "type": "rate_limit_error", "param": None, "code": "rate_limit_exceeded"}})

    body["model"] = actual_model_id
    if request.stream:
        body["stream"] = True

    url = f"{account.base_url.rstrip('/')}/chat/completions"

    try:
        response = await http_client.request(
            account, "POST", url, json=body,
            stream=request.stream, key_string=api_key,
        )
        first_response = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(key_id, account.account_id, actual_model_id, -1)
            except Exception:
                pass
        error_msg = f"Failed to reach supplier: {exc}"
        await _log_error_request(
            admin_service, request.model, actual_model_id, account,
            client_key_name, 502, error_msg, body, request_start,
            error_source="upstream",
        )
        raise HTTPException(status_code=502, detail=error_msg)

    if response.status_code >= 400:
        error_body = await _safe_read_response_body(response)
        error_code = response.status_code
        detail_msg = f"Supplier error {error_code}: {error_body[:200]}" if error_body else f"Supplier error {error_code}"
        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(key_id, account.account_id, actual_model_id, error_code)
            except Exception:
                pass
        await _safe_aclose(response)
        await _log_error_request(
            admin_service, request.model, actual_model_id, account,
            client_key_name, error_code, detail_msg, body, request_start,
            raw_response=error_body, is_stream=request.stream, key_id=key_id,
            error_source="upstream",
        )
        raise HTTPException(status_code=error_code, detail=detail_msg)

    # ── Non-streaming success ──
    if not request.stream:
        try:
            raw_text = getattr(response, "text", None) or ""
            if raw_text:
                resp_json = json.loads(raw_text)
            else:
                raw_text = await _safe_read_response_body(response)
                resp_json = json.loads(raw_text) if raw_text else {}

            if not resp_json:
                if circuit_breaker is not None:
                    try:
                        circuit_breaker.record_failure(key_id, account.account_id, actual_model_id, 502)
                    except Exception:
                        pass
                await _log_error_request(
                    admin_service, request.model, actual_model_id, account,
                    client_key_name, 502, "Empty response body from upstream", body,
                    request_start, first_response, is_stream=False, key_id=key_id,
                    error_source="upstream",
                )
                raise HTTPException(status_code=502, detail={
                    "error": {"message": "Supplier returned empty response",
                              "type": "api_error", "param": None, "code": "empty_response"}})
            choices = resp_json.get("choices")
            if not choices or not isinstance(choices, list) or len(choices) == 0:
                if circuit_breaker is not None:
                    try:
                        circuit_breaker.record_failure(key_id, account.account_id, actual_model_id, 502)
                    except Exception:
                        pass
                await _log_error_request(
                    admin_service, request.model, actual_model_id, account,
                    client_key_name, 502,
                    f"No choices in upstream response", body,
                    request_start, first_response, is_stream=False, key_id=key_id,
                    error_source="upstream",
                )
                raise HTTPException(status_code=502, detail={
                    "error": {"message": "Supplier returned response with no choices",
                              "type": "api_error", "param": None, "code": "no_choices"}})

        except HTTPException:
            raise
        except Exception:
            await _log_error_request(
                admin_service, request.model, actual_model_id, account,
                client_key_name, 502, "Invalid response format", body,
                request_start, first_response, is_stream=False, key_id=key_id,
                error_source="upstream",
            )
            raise HTTPException(status_code=502, detail={
                "error": {"message": "Invalid response from supplier",
                          "type": "api_error", "param": None, "code": "invalid_response"}})

        # Convert OpenAI response to Anthropic format
        anthro_resp = _openai_to_anthropic_response(resp_json, actual_model_id)

        try:
            await response.aclose()
        except Exception:
            pass

        usage = anthro_resp.get("usage", {}) or {}
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cached_tokens, prompt_partial_cached = _extract_cache_usage(usage)
        end_time = datetime.now(timezone.utc).isoformat()

        if admin_service:
            try:
                resp_hdrs = {}
                for k in ["x-ratelimit-remaining", "x-ratelimit-limit"]:
                    if k in response.headers:
                        resp_hdrs[k] = response.headers[k]
                await asyncio.to_thread(admin_service.log_request,
                    model=request.model,
                    actual_model_id=actual_model_id,
                    account_id=account.account_id,
                    account_name=account.name,
                    status_code=200,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    is_stream=False,
                    raw_request=json.dumps(body, ensure_ascii=False),
                    raw_response=json.dumps(resp_json, ensure_ascii=False)[:50000],
                    request_start=request_start, first_response=first_response, end_time=end_time,
                    cached_tokens=cached_tokens, prompt_partial_cached=prompt_partial_cached,
                    client_key_name=client_key_name,
                    response_headers=json.dumps(resp_hdrs if resp_hdrs else dict(response.headers), ensure_ascii=False),
                    api_key_id=key_id,
                )
            except Exception as le:
                logger.error(f"Failed to log non-stream Anthropic request: {le}", exc_info=True)

        try:
            if quota_updater and (input_tokens > 0 or output_tokens > 0):
                await asyncio.to_thread(
                    quota_updater.update_quota_from_usage,
                    account, input_tokens, output_tokens, actual_model_id,
                )
            if quota_updater and response is not None:
                await asyncio.to_thread(
                    quota_updater.update_quota_after_request,
                    account, dict(response.headers), actual_model_id,
                )
        except Exception as qe:
            logger.warning(f"Failed to update quota: {qe}")

        if circuit_breaker is not None:
            try:
                circuit_breaker.record_success(key_id, actual_model_id)
            except Exception:
                pass
        if alias_router is not None:
            try:
                alias_router.record_usage(actual_model_id, client_key_name or "")
            except Exception:
                pass
        if alias_router is not None:
            try:
                alias_router.release(key_id, actual_model_id)
            except Exception:
                pass

        return JSONResponse(content=anthro_resp)

    # ── Streaming success ──
    return StreamingResponse(
        _stream_anthropic_with_logging(
            response, account, request.model, body, actual_model_id,
            admin_service, request_start, quota_updater=quota_updater,
            client_key_name=client_key_name, circuit_breaker=circuit_breaker,
            alias_router=alias_router, key_id=key_id,
        ),
        media_type="text/event-stream",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache",
            "X-Upstream-Account": account.account_id,
            "X-Upstream-Model": actual_model_id or "",
        },
    )


async def _stream_anthropic_with_logging(
    response,
    account,
    model_name: str,
    request_body: dict,
    actual_model_id: str,
    admin_service,
    request_start: str,
    quota_updater=None,
    client_key_name: str = None,
    circuit_breaker=None,
    alias_router=None,
    key_id: int = 0,
):
    """Streaming response wrapper for Anthropic protocol — logs and updates quota."""
    output_tokens = 0
    input_tokens = 0
    cached_tokens = 0
    prompt_partial_cached = 0
    response_headers = {}
    raw_chunks = []
    first_response = None
    stream_status_code = 200
    stream_failed = False
    stream_interrupted = False
    interrupt_reason = None

    try:
        async for chunk_data in stream_response_anthropic(response, actual_model_id, _capture_headers=True):
            data_str = chunk_data.removeprefix("data: ").strip()
            is_special_chunk = False

            if data_str:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(data_str)
                    if isinstance(obj, dict) and "__hdrs__" in obj:
                        response_headers = obj["__hdrs__"]
                        is_special_chunk = True
                except Exception:
                    pass

            if is_special_chunk:
                continue

            # Detect error marker
            if data_str:
                try:
                    err_obj, _ = json.JSONDecoder().raw_decode(data_str)
                    if isinstance(err_obj, dict) and err_obj.get("type") == "error":
                        stream_failed = True
                        interrupt_reason = "empty_stream"
                except Exception:
                    pass

            if first_response is None:
                first_response = datetime.now(timezone.utc).isoformat()
            yield chunk_data
            raw_chunks.append(chunk_data)

            try:
                if data_str:
                    # Try to extract usage from message_delta events
                    obj, _ = json.JSONDecoder().raw_decode(data_str)
                    if isinstance(obj, dict) and obj.get("type") == "message_delta":
                        usage = obj.get("usage", {})
                        input_tokens = usage.get("input_tokens", 0) or input_tokens
                        output_tokens = usage.get("output_tokens", 0) or output_tokens
            except Exception:
                pass
    except GeneratorExit:
        stream_interrupted = True
        interrupt_reason = "client disconnected"
        raise
    except asyncio.CancelledError:
        stream_interrupted = True
        interrupt_reason = "client disconnected"
        raise
    except Exception as stream_exc:
        stream_failed = True
        stream_interrupted = True
        interrupt_reason = str(stream_exc)
        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(
                    key_id, account.account_id, actual_model_id or model_name, -1,
                )
            except Exception:
                pass
        raise
    finally:
        if alias_router is not None:
            try:
                alias_router.release(key_id, actual_model_id or model_name)
            except Exception:
                pass

        if not stream_failed and len(raw_chunks) > 0 and circuit_breaker is not None:
            try:
                circuit_breaker.record_success(key_id, actual_model_id or model_name)
            except Exception:
                pass

        if stream_failed and not stream_interrupted and circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(
                    key_id, account.account_id, actual_model_id or model_name, 502,
                )
            except Exception:
                pass

        end_time = datetime.now(timezone.utc).isoformat()
        _stream_ended = stream_interrupted or stream_failed
        _is_empty = len(raw_chunks) == 0
        log_status = -1 if (_stream_ended or _is_empty) else stream_status_code
        log_error = (
            f"Streaming interrupted: {interrupt_reason}"
            if interrupt_reason
            else (f"Stream ended: status={log_status} raw_chunks={len(raw_chunks)}" if not stream_failed else None)
        )

        try:
            if admin_service:
                raw_response = "\n".join(raw_chunks[:100]) if raw_chunks else ""
                if len(raw_response) > 50000:
                    raw_response = raw_response[:50000] + "...(truncated)"
                await asyncio.to_thread(admin_service.log_request,
                    model=model_name,
                    actual_model_id=actual_model_id,
                    account_id=account.account_id,
                    account_name=account.name,
                    status_code=log_status,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    is_stream=True,
                    error_message=log_error,
                    raw_request=json.dumps(request_body, ensure_ascii=False),
                    raw_response=raw_response,
                    request_start=request_start, first_response=first_response, end_time=end_time,
                    cached_tokens=cached_tokens, prompt_partial_cached=prompt_partial_cached,
                    client_key_name=client_key_name,
                    response_headers=json.dumps(response_headers if response_headers else {}, ensure_ascii=False),
                    api_key_id=key_id,
                    error_source=None if log_status == 200 else "upstream",
                )
        except Exception as le:
            logger.error(f"Failed to log stream request: {le}", exc_info=True)

        try:
            if quota_updater and (input_tokens > 0 or output_tokens > 0):
                await asyncio.to_thread(
                    quota_updater.update_quota_from_usage,
                    account, input_tokens, output_tokens, actual_model_id or model_name,
                )
            if quota_updater and response_headers:
                await asyncio.to_thread(quota_updater.update_quota_after_request,
                    account, response_headers, actual_model_id or model_name)
        except Exception as e:
            logger.warning(f"Failed to update streaming quota: {e}")


# ── Endpoint ────────────────────────────────────────────────────────────

@router.post("/v1/messages")
async def messages(data: AnthropicMessagesRequest, fastapi_request: Request):
    """Anthropic-compatible messages endpoint.

    Converts Anthropic format requests to OpenAI-compatible upstream format,
    and converts upstream responses back to Anthropic Messages format.
    """
    try:
        services = get_services(fastapi_request)
    except Exception:
        raise HTTPException(status_code=503, detail="Service unavailable")

    admin_service = get_admin_service(fastapi_request)
    client_key_name, _ = _authenticate_client_key(fastapi_request)

    try:
        lb = services.get("load_balancer")
        if lb is None:
            raise HTTPException(status_code=503, detail="No suppliers configured")

        model_name = data.model
        request_start = datetime.now(timezone.utc).isoformat()

        quota_updater = services.get("quota_updater")
        circuit_breaker = services.get("circuit_breaker")
        alias_router = services.get("alias_router")
        http_client = services.get("http_client")

        if alias_router is not None:
            try:
                candidates = alias_router.get_candidates(data.model)
            except Exception:
                candidates = []

            if candidates:
                body = await _anthropic_to_openai_body(data, data.model)
                last_error = None

                for candidate_idx, candidate in enumerate(candidates):
                    account = candidate.account
                    actual_model_id = candidate.model_name

                    account._key_id = candidate.key_id
                    account._key_string = candidate.key_string

                    if circuit_breaker is not None and not circuit_breaker.check(
                            candidate.key_id, actual_model_id):
                        logger.info(
                            "Skipping frozen candidate %d/%d: account=%s model=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id,
                        )
                        cb_req_body = await _anthropic_to_openai_body(data, actual_model_id)
                        now = datetime.now(timezone.utc).isoformat()
                        await _log_error_request(
                            admin_service, data.model, actual_model_id, account,
                            client_key_name, 503,
                            f"Supplier {account.name or account.account_id} {actual_model_id} frozen",
                            cb_req_body, now, None, is_stream=data.stream,
                            error_source="circuit_open",
                        )
                        last_error = last_error or HTTPException(
                            status_code=503, detail={
                                "error": {
                                    "message": f"Supplier {account.name or account.account_id} is temporarily unavailable",
                                    "type": "api_error", "param": None, "code": "circuit_open",
                                }
                            })
                        continue

                    if alias_router is not None:
                        try:
                            alias_router.acquire(candidate.key_id, actual_model_id)
                        except Exception:
                            pass

                    try:
                        body_copy = copy.deepcopy(body)
                        result = await _try_anthropic_candidate(
                            request=data, account=account,
                            actual_model_id=actual_model_id, body=body_copy,
                            http_client=http_client,
                            admin_service=admin_service,
                            quota_updater=quota_updater, services=services,
                            client_key_name=client_key_name,
                            circuit_breaker=circuit_breaker,
                            alias_router=alias_router,
                            candidate_idx=candidate_idx,
                            total_candidates=len(candidates),
                        )
                    except HTTPException as e:
                        last_error = e
                        if alias_router is not None:
                            try:
                                alias_router.release(candidate.key_id, actual_model_id)
                            except Exception:
                                pass
                        logger.warning(
                            "Anthropic candidate %d/%d failed: account=%s model=%s status=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id,
                            getattr(e, "status_code", "??"),
                        )
                        continue
                    except Exception as e:
                        if alias_router is not None:
                            try:
                                alias_router.release(candidate.key_id, actual_model_id)
                            except Exception:
                                pass
                        logger.error(
                            "Anthropic candidate %d/%d failed with non-HTTP error: "
                            "account=%s model=%s error=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id, e,
                            exc_info=True,
                        )
                        last_error = last_error or HTTPException(
                            status_code=500, detail=f"Internal error: {e}")
                        break

                if last_error is not None:
                    raise last_error
                else:
                    return None  # all candidates exhausted silently — shouldn't happen

        # Fallback: no alias router or no candidates — use load balancer
        if lb is not None and http_client is not None:
            try:
                account, actual_model_id = lb.select(data.model)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"No available supplier: {e}")

            if account is None:
                raise HTTPException(status_code=503, detail="No available supplier")

            if not getattr(account, "api_key", None):
                raise HTTPException(status_code=503, detail="Supplier has no API key")

            body = await _anthropic_to_openai_body(data, actual_model_id)

            return await _try_anthropic_candidate(
                request=data, account=account,
                actual_model_id=actual_model_id, body=body,
                http_client=http_client,
                admin_service=admin_service,
                quota_updater=quota_updater, services=services,
                client_key_name=client_key_name,
                circuit_breaker=circuit_breaker,
                alias_router=alias_router,
                candidate_idx=0,
                total_candidates=1,
            )

        raise HTTPException(status_code=503, detail="No available supplier")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anthropic messages endpoint failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={
            "error": {"message": f"Internal server error: {e}",
                      "type": "api_error", "param": None, "code": "internal_error"}})
