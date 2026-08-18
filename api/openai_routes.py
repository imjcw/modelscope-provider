"""OpenAI-compatible service protocol routes.

This module holds the protocol-level endpoints (OpenAI format) that
proxies upstream to supplier providers.

Future extensions (``/anthropic``, ``/gemini``, ``/custom``) will be
added as sibling modules — each with their own router mounted at a
protocol-prefixed prefix.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, AsyncGenerator, Any, Union
import copy
import json
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from services.models_cache import get_models

logger = logging.getLogger(__name__)

from .anthropic_adapters import (
    resolve_upstream_base,
    extract_cache_usage,
    safe_read_response_body,
    safe_aclose,
    anthropic_stop_to_openai_finish,
    get_admin_service,
    get_services,
    _authenticate_client_key,
    _log_error_request,
    request_with_429_backoff,
)

router = APIRouter()


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Uses `Any` for messages to achieve full OpenAI API compatibility.
    The official OpenAI SDK defines messages as a union of several
    message types (SystemMessageParam, UserMessageParam,
    AssistantMessageParam, ToolMessageParam, FunctionMessageParam),
    each with different required/optional fields. Hard-coding a single
    Pydantic model would reject valid requests that contain fields like
    `tool_calls`, `function_call`, `name`, etc.
    """
    model: str = Field(..., description="Model name or alias")
    messages: Any = Field(..., description="Chat messages (full OpenAI format)")
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    n: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    logit_bias: Optional[dict] = None
    logprobs: Optional[Union[bool, int]] = None
    top_logprobs: Optional[int] = None
    response_format: Optional[Any] = None
    seed: Optional[int] = None
    service_tier: Optional[str] = None
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None
    functions: Optional[Any] = None
    parallel_tool_calls: Optional[bool] = None
    stream_options: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Error response format."""
    error: dict


def _is_openai_response(resp_json: dict) -> bool:
    """Check if a response already follows the OpenAI chat completion format.

    A valid OpenAI response has:
      - ``choices``: non-empty list
      - ``choices[0].message.role``: present
      - ``usage``: dict

    Non-OpenAI responses (e.g. raw ModelScope format) fall through so the
    ``ResponseConverter`` can normalize them — but we never touch an already-valid
    OpenAI response, which would otherwise strip useful fields like
    ``prompt_tokens_details`` (and break cache-usage tracking).
    """
    if not isinstance(resp_json, dict):
        return False
    choices = resp_json.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    message = first.get("message")
    if not isinstance(message, dict):
        return False
    if "role" not in message:
        return False
    usage = resp_json.get("usage")
    if not isinstance(usage, dict):
        return False
    return True


def _normalize_response(response_converter, resp_json: dict) -> dict:
    """Normalize a non-OpenAI upstream response to the OpenAI format.

    If the response already looks like a standard OpenAI chat completion,
    return it unchanged — converting it would lose fields like
    ``prompt_tokens_details`` that cache-usage tracking depends on.

    If the response is in a non-standard format (e.g. raw ModelScope),
    apply the ``ResponseConverter`` to translate it. Conversion failures are
    swallowed so the original payload is returned as a fallback.
    """
    if _is_openai_response(resp_json):
        return resp_json
    try:
        return response_converter.convert_to_openai(resp_json)
    except Exception:
        return resp_json


def refresh_load_balancer(request: Request):
    """Refresh the LoadBalancer with current accounts from the database.

    Called by admin routes when accounts are added, updated, or deleted.
    """
    try:
        services = request.app.state.services
    except AttributeError:
        return
    if services is None:
        return

    try:
        db = services.get("database")
        supplier_model_repo = services.get("supplier_model_repo")

        if db and supplier_model_repo is not None:
            from models.account import ModelScopeAccount, DEFAULT_PROVIDER_TYPE, build_ms_account
            from repositories.account_repository import AccountRepository

            repo = AccountRepository(db)
            db_accounts = repo.find_active()

            int_ids = [a["id"] for a in db_accounts]
            keys_by_id = repo.find_api_keys_by_account_ids(int_ids)
            quota_repo = services.get("quota_repository")
            unavailable_map = {}
            if quota_repo is not None:
                try:
                    unavailable_map = quota_repo.get_unavailable_models_by_account(
                        [a["account_id"] for a in db_accounts]
                    )
                except Exception:
                    logger.warning("Failed to load unavailable_models for LB refresh",
                                   exc_info=True)

            accounts = []
            for a in db_accounts:
                accounts.append(build_ms_account(
                    a,
                    api_key_records=keys_by_id.get(a["id"]) or None,
                    unavailable_models=unavailable_map.get(a["account_id"], set()),
                ))

            from services.load_balancer import LoadBalancer
            services["load_balancer"] = LoadBalancer(
                accounts, supplier_model_repo=supplier_model_repo
            )

            # Keep the circuit-breaker window-mode resolvers in sync with the
            # refreshed account set — otherwise count-window accounts added or
            # edited via admin would keep falling back to token behaviour (429
            # freezes on the 2nd hit, escalation threshold 10) until a restart.
            cb = services.get("circuit_breaker")
            rls = services.get("rate_limit_strategies")
            if cb is not None and rls is not None:
                from core.service_init import _build_circuit_breaker_resolvers
                (
                    cb.window_mode_resolver,
                    cb.window_seconds_resolver,
                ) = _build_circuit_breaker_resolvers(accounts, rls)

            logger.info(
                f"LoadBalancer refreshed with {len(accounts)} accounts"
            )
    except Exception:
        logger.warning("Failed to refresh load balancer", exc_info=True)


async def stream_response(
    response,
    _capture_headers: bool = False,
) -> AsyncGenerator[str, None]:
    """Generate streaming response from a pre-made upstream response.

    If the upstream produces no valid data chunks (e.g. only heartbeat
    messages, only ``[DONE]``, or a non-SSE body), an error data chunk is
    yielded at the end so the client sees a clear error instead of a
    silent empty stream.
    """
    if _capture_headers:
        hdrs = {}
        try:
            hdrs = dict(response.headers)
        except Exception:
            pass
        yield f"data: {json.dumps({'__hdrs__': hdrs})}\n\n"

    decoder = json.JSONDecoder()
    yielded_any = False
    saw_done = False
    _closed = False

    try:
        async for line in response.aiter_lines():
            stripped = line.strip()
            if stripped in ("[DONE]", "data: [DONE]"):
                yield "data: [DONE]\n\n"
                saw_done = True
                return

            if stripped.startswith("data:"):
                data_str = stripped[5:].strip()
                if not data_str:
                    continue

                try:
                    chunk, _ = decoder.raw_decode(data_str)
                except json.JSONDecodeError:
                    # Non-JSON data — forward it raw so the client sees it.
                    yield f"data: {data_str}\n\n"
                    yielded_any = True
                    continue

                if chunk and chunk.get("choices") is None:
                    # Non-choices chunk (heartbeat / keepalive) — skip silently.
                    continue

                yielded_any = True
                yield f"data: {json.dumps(chunk)}\n\n"
    except GeneratorExit:
        # Client disconnected. Yield is illegal inside `finally` during
        # close (RuntimeError "async generator ignored GeneratorExit" on
        # Python 3.12+), so skip the empty-stream marker.
        _closed = True
        raise
    except asyncio.CancelledError:
        _closed = True
        raise
    finally:
        await safe_aclose(response)
        # If the stream produced no useful data at all (no data: lines, or
        # only non-choices heartbeat chunks), emit an error marker so the
        # client sees a clear error instead of a silent empty stream.
        if not _closed and not yielded_any and not saw_done:
            error_json = json.dumps({
                "error": {
                    "message": "Upstream returned empty stream (no data received)",
                    "type": "upstream_error",
                    "param": None,
                    "code": "empty_stream",
                }
            })
            yield f"data: {error_json}\n\n"


async def stream_response_with_logging(
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
    """Streaming response wrapper that logs and updates quota after completion."""
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
        async for chunk_data in stream_response(response, _capture_headers=True):
            data_str = chunk_data.removeprefix("data: ").strip()
            is_special_chunk = False

            if data_str:
                try:
                    dec = json.JSONDecoder()
                    obj, _ = dec.raw_decode(data_str)
                    if "__hdrs__" in obj:
                        response_headers = obj["__hdrs__"]
                        is_special_chunk = True
                except Exception:
                    pass

            if is_special_chunk:
                continue

            # Detect the empty-stream error marker emitted by stream_response
            # when the upstream produced no valid data chunks.
            if data_str:
                try:
                    err_obj, _ = json.JSONDecoder().raw_decode(data_str)
                    if isinstance(err_obj, dict) and err_obj.get("error") and err_obj.get("error", {}).get("code") == "empty_stream":
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
                    decoder = json.JSONDecoder()
                    json_data, _ = decoder.raw_decode(data_str)
                    usage = json_data.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0) or input_tokens
                    output_tokens = usage.get("completion_tokens", 0) or output_tokens
                    _cached, _partial = extract_cache_usage(usage)
                    cached_tokens = _cached or cached_tokens
                    prompt_partial_cached = _partial or prompt_partial_cached
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
        # Release in-flight connection slot
        if alias_router is not None:
            try:
                alias_router.release(key_id, actual_model_id or model_name)
            except Exception:
                pass

        # Circuit-breaker success recorded here; empty stream is a failure
        if not stream_failed and len(raw_chunks) > 0 and circuit_breaker is not None:
            try:
                circuit_breaker.record_success(key_id, actual_model_id or model_name,)
            except Exception:
                pass

        # The empty-stream error marker was detected inside the for loop (not in
        # an except block), so record the circuit-breaker failure here.
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
            else f"Empty stream: upstream returned 0 chunks (status={stream_status_code})"
            if _is_empty
            else None
        )
        raw_response_fallback = None
        if len(raw_chunks) == 0 and not stream_failed and not stream_interrupted:
            try:
                _lost_body = await safe_read_response_body(response, max_len=50000)
                if _lost_body:
                    logger.warning(
                        "Stream produced 0 chunks for %s/%s — captured body: %s",
                        account.account_id, actual_model_id or model_name, _lost_body,
                    )
                    raw_response_fallback = _lost_body
            except Exception:
                raw_response_fallback = None
            if circuit_breaker is not None:
                try:
                    circuit_breaker.record_failure(
                        key_id, account.account_id, actual_model_id or model_name, 502,
                    )
                except Exception:
                    pass
        # 与非流式对齐：raw_response 同样截断到 50KB，避免长流撑大列（B11/P8）
        _raw_response_text = raw_response_fallback or "".join(raw_chunks)
        if len(_raw_response_text) > 50000:
            _raw_response_text = _raw_response_text[:50000] + "...(truncated)"

        logger.info(
            f"Streaming finished for {account.account_id}: "
            f"status={log_status} input={input_tokens} output={output_tokens} "
            f"chunks={len(raw_chunks)} interrupted={stream_interrupted} "
            f"admin_svc={'yes' if admin_service else 'no'}"
        )
        if admin_service:
            try:
                await asyncio.to_thread(admin_service.log_request,
                    model=model_name,
                    actual_model_id=actual_model_id or model_name,
                    account_id=account.account_id,
                    account_name=account.name,
                    status_code=log_status,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    is_stream=True,
                    latency_ms=None,
                    error_message=log_error,
                    raw_request=json.dumps(request_body, ensure_ascii=False),
                    raw_response=_raw_response_text,
                    request_start=request_start,
                    first_response=first_response,
                    end_time=end_time,
                    cached_tokens=cached_tokens,
                    prompt_partial_cached=prompt_partial_cached,
                    client_key_name=client_key_name,
                    api_key_id=key_id,
                    response_headers=json.dumps(response_headers, ensure_ascii=False) if response_headers else None,
                )
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Failed to log streaming request: {e}")

    # Update quota via the legacy quota_updater. The pluggable provider
    # strategy from services.strategy was never implemented, so `strategy`
    # was always None (B1) — quota_updater is the real working path.
    if quota_updater:
        try:
            if input_tokens > 0 or output_tokens > 0:
                await asyncio.to_thread(quota_updater.update_quota_from_usage,
                    account, input_tokens, output_tokens, actual_model_id or model_name,
                    key_id,
                )
            if response_headers:
                await asyncio.to_thread(quota_updater.update_quota_after_request,
                    account, response_headers, actual_model_id or model_name,
                    None,
                    key_id,
                )
        except Exception as e:
            logger.warning(f"Failed to update streaming quota: {e}")


async def stream_response_with_logging_anthropic_upstream(
    response, account, model_name, request_body, actual_model_id,
    admin_service, request_start,
    quota_updater=None, client_key_name=None,
    circuit_breaker=None, alias_router=None, key_id: int = 0,
):
    """Log quota for an Anthropic-native SSE stream, converting to OpenAI SSE.

    Anthropic upstream emits its own event types (message_start,
    content_block_delta, message_delta, message_stop) — we convert
    these to OpenAI-compatible SSE (``{"choices": [{"delta": ...}]}``).
    """
    output_tokens = 0
    input_tokens = 0
    response_headers = {}
    raw_chunks = []
    first_response = None
    stream_status_code = 200
    stream_failed = False
    stream_interrupted = False
    interrupt_reason = None

    try:
        async for chunk_data in _stream_openai_from_anthropic(response, actual_model_id, _capture_headers=True):
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

            if first_response is None:
                first_response = datetime.now(timezone.utc).isoformat()
            yield chunk_data
            raw_chunks.append(chunk_data)

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
                circuit_breaker.record_failure(key_id, account.account_id, actual_model_id or model_name, -1)
            except Exception:
                pass
        raise
    finally:
        await safe_aclose(response)

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
                circuit_breaker.record_failure(key_id, account.account_id, actual_model_id or model_name, 502)
            except Exception:
                pass

        end_time = datetime.now(timezone.utc).isoformat()
        _stream_ended = stream_interrupted or stream_failed
        _is_empty = len(raw_chunks) == 0
        log_status = -1 if (_stream_ended or _is_empty) else stream_status_code
        log_error = (
            f"Streaming interrupted: {interrupt_reason}"
            if interrupt_reason
            else f"Empty stream" if _is_empty else None
        )

        _raw_response_text = "\n".join(raw_chunks[:100]) if raw_chunks else ""
        if len(_raw_response_text) > 50000:
            _raw_response_text = _raw_response_text[:50000] + "...(truncated)"

        if admin_service:
            try:
                await asyncio.to_thread(admin_service.log_request,
                    model=model_name,
                    actual_model_id=actual_model_id or model_name,
                    account_id=account.account_id,
                    account_name=account.name,
                    status_code=log_status,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    is_stream=True,
                    error_message=log_error,
                    raw_request=json.dumps(request_body, ensure_ascii=False),
                    raw_response=_raw_response_text,
                    request_start=request_start,
                    first_response=first_response,
                    end_time=end_time,
                    client_key_name=client_key_name,
                    api_key_id=key_id,
                    response_headers=json.dumps(response_headers, ensure_ascii=False) if response_headers else None,
                    error_source=None if log_status == 200 else "upstream",
                )
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Failed to log Anthropic upstream stream: {e}")

        if quota_updater:
            try:
                if input_tokens > 0 or output_tokens > 0:
                    await asyncio.to_thread(quota_updater.update_quota_from_usage,
                        account, input_tokens, output_tokens, actual_model_id or model_name,
                        key_id,
                    )
                if response_headers:
                    await asyncio.to_thread(quota_updater.update_quota_after_request,
                        account, response_headers, actual_model_id or model_name,
                        None,
                        key_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to update streaming quota: {e}")


# ── Endpoints ────────────────────────────────────────────────────────────


async def _build_request_body(data: ChatCompletionRequest, actual_model_id: str) -> dict:
    """Build the upstream request body from a ChatCompletionRequest."""
    body = {
        "model": actual_model_id,
        "messages": data.messages,
    }
    if data.temperature is not None:
        body["temperature"] = data.temperature
    if data.max_tokens is not None:
        body["max_tokens"] = data.max_tokens
    if data.top_p is not None:
        body["top_p"] = data.top_p
    if data.stop is not None:
        body["stop"] = data.stop
    if data.n is not None:
        body["n"] = data.n
    if data.frequency_penalty is not None:
        body["frequency_penalty"] = data.frequency_penalty
    if data.presence_penalty is not None:
        body["presence_penalty"] = data.presence_penalty
    if data.logit_bias is not None:
        body["logit_bias"] = data.logit_bias
    if data.logprobs is not None:
        body["logprobs"] = data.logprobs
    if data.top_logprobs is not None:
        body["top_logprobs"] = data.top_logprobs
    if data.response_format is not None:
        body["response_format"] = data.response_format
    if data.seed is not None:
        body["seed"] = data.seed
    if data.service_tier is not None:
        body["service_tier"] = data.service_tier
    if data.tools is not None:
        body["tools"] = data.tools
    if data.tool_choice is not None:
        body["tool_choice"] = data.tool_choice
    if data.functions is not None:
        body["functions"] = data.functions
    if data.parallel_tool_calls is not None:
        body["parallel_tool_calls"] = data.parallel_tool_calls
    if data.stream_options is not None:
        body["stream_options"] = dict(data.stream_options)
    # stream is controlled server-side, not forwarded
    return body


# ── OpenAI ↔ Anthropic conversion (for Anthropic upstreams) ─────────────


def _openai_message_to_anthropic(msg: dict) -> dict:
    """Convert one OpenAI message to Anthropic format."""
    if not isinstance(msg, dict):
        return {}
    role = msg.get("role", "user")
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls") or []
    tool_call_id = msg.get("tool_call_id")

    # OpenAI tool role → Anthropic tool_result in user message
    if role == "tool":
        tool_content = content
        if isinstance(content, list):
            # Convert OpenAI content-block array to Anthropic format
            anthro_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        anthro_parts.append({"type": "text", "text": block.get("text", "")})
                    elif block.get("type") == "image_url":
                        url_data = block.get("image_url", {})
                        url = url_data if isinstance(url_data, str) else url_data.get("url", "")
                        anthro_parts.append({"type": "image", "source": {"type": "url", "url": url}})
            tool_content = anthro_parts if anthro_parts else ""
        blocks = [{"type": "tool_result", "tool_use_id": tool_call_id or "",
                   "content": [{"type": "text", "text": str(tool_content)}] if isinstance(tool_content, str) else tool_content}]
        return {"role": "user", "content": blocks}

    if role == "assistant":
        blocks = []
        if content:
            blocks.append({"type": "text", "text": content})
        for tc in tool_calls:
            if isinstance(tc, dict):
                fc = tc.get("function", {})
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fc.get("name", ""),
                    "input": fc.get("arguments"),
                })
                if isinstance(fc.get("arguments"), str):
                    try:
                        blocks[-1]["input"] = json.loads(fc["arguments"])
                    except Exception:
                        # Anthropic requires tool_use.input to be an object;
                        # never forward the raw JSON string (upstream 400).
                        blocks[-1]["input"] = {}
        return {"role": "assistant", "content": blocks}

    # user/system messages: convert to Anthropic text blocks
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}]
    elif isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    blocks.append({"type": "text", "text": item.get("text", "")})
                elif item.get("type") == "image_url":
                    url_data = item.get("image_url", {})
                    if isinstance(url_data, str):
                        blocks.append({"type": "image", "source": {"type": "url", "url": url_data}})
                    elif isinstance(url_data, dict):
                        blocks.append({"type": "image", "source": {"type": "url", "url": url_data.get("url", "")}})
            else:
                blocks.append({"type": "text", "text": str(item)})
    else:
        blocks = [{"type": "text", "text": str(content)}]

    return {"role": role, "content": blocks}


def _anthropic_message_to_openai(msg_dict: dict, model_name: str) -> dict:
    """Convert an Anthropic Message response to OpenAI ChatCompletion format."""
    content_blocks = msg_dict.get("content", []) or []
    stop_reason = msg_dict.get("stop_reason", "end_turn")
    usage = msg_dict.get("usage", {}) or {}

    # Convert content blocks to OpenAI message
    text_parts = []
    tool_calls = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                },
            })

    message = {"role": "assistant", "content": "\n".join(text_parts) if text_parts else None}
    if tool_calls:
        message["tool_calls"] = tool_calls

    itokens = usage.get("input_tokens", 0) or 0
    otokens = usage.get("output_tokens", 0) or 0

    return {
        "id": msg_dict.get("id", f"chatcmpl_{uuid.uuid4().hex[:24]}"),
        "object": "chat.completion",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "model": msg_dict.get("model", model_name),
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": anthropic_stop_to_openai_finish(stop_reason),
        }],
        "usage": {
            "prompt_tokens": itokens,
            "completion_tokens": otokens,
            "total_tokens": itokens + otokens,
        },
    }


async def _openai_to_anthropic_body(data, actual_model_id: str) -> dict:
    """Convert an OpenAI ChatCompletionRequest to an Anthropic-format request body."""
    body = {
        "model": actual_model_id,
        "max_tokens": data.max_tokens or 4096,
    }
    if data.temperature is not None:
        body["temperature"] = data.temperature
    if data.top_p is not None:
        body["top_p"] = data.top_p
    if data.stop is not None:
        body["stop_sequences"] = data.stop if isinstance(data.stop, list) else [data.stop]
    if data.tools is not None:
        body["tools"] = [
            {"name": t.get("function", {}).get("name", ""),
             "description": t.get("function", {}).get("description", ""),
             "input_schema": t.get("function", {}).get("parameters", {})}
            for t in data.tools if isinstance(t, dict)
        ]
    if data.tool_choice is not None:
        tc = data.tool_choice
        if tc == "auto":
            body["tool_choice"] = {"type": "auto"}
        elif tc == "required":
            body["tool_choice"] = {"type": "any"}
        elif tc == "none":
            pass  # no equivalent; just don't forward
        elif isinstance(tc, dict) and tc.get("type") == "function":
            fn = tc.get("function", {})
            body["tool_choice"] = {"type": "tool", "name": fn.get("name", "")}

    # Extract system messages to Anthropic's top-level `system` field.
    # Anthropic does NOT allow role:system in the messages array.
    system_parts = []
    messages = []
    for msg in (data.messages or []):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
            elif isinstance(content, list):
                # OpenAI system content can be a list of content blocks
                # (text, image_url, etc.). Extract the text parts.
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            system_parts.append(text)
        else:
            anthro_msg = _openai_message_to_anthropic(msg)
            if anthro_msg:
                messages.append(anthro_msg)
    if system_parts:
        body["system"] = "\n".join(system_parts)
    if messages:
        body["messages"] = messages

    if data.stream:
        body["stream"] = True

    return body


async def _stream_openai_from_anthropic(
    response,
    actual_model_id: str,
    _capture_headers: bool = False,
) -> AsyncGenerator[str, None]:
    """Convert an Anthropic-native SSE stream to OpenAI-compatible SSE format.

    Anthropic events → OpenAI:
      content_block_delta(text) → data: {"choices": [{"delta": {"content": "..."}}]}
      content_block_delta(input_json_delta) → data: {"choices": [{"delta": {"tool_calls": [...]}}]}
      message_delta           → data: {"choices": [{"finish_reason": "..."}], "usage": {...}}
      message_stop            → data: [DONE]

    Anthropic SSE pairs each ``event: <type>`` with a ``data: <json>`` line.
    We iterate line-by-line with a simple state machine: when we see an
    ``event:`` line we store the type; when we see the following ``data:``
    line we dispatch on the stored type. This avoids calling
    ``await anext()`` on a separate iterator inside the main ``async for``
    loop (which would create a second independent iterator over the same
    httpx stream and cause data loss / race conditions).
    """
    decoder = json.JSONDecoder()
    first_chunk = True
    saw_finish = False
    yielded_any = False
    total_output_tokens = 0
    total_input_tokens = 0
    tool_idx = 0
    pending_event_type: str | None = None
    _closed = False

    if _capture_headers:
        hdrs = {}
        try:
            hdrs = dict(response.headers)
        except Exception:
            pass
        yield f"data: {json.dumps({'__hdrs__': hdrs})}\n\n"

    try:
        async for line in response.aiter_lines():
            stripped = line.strip()
            if not stripped:
                # Blank line = SSE event delimiter; reset pending event
                pending_event_type = None
                continue

            if stripped.startswith("event:"):
                pending_event_type = stripped[6:].strip()
                continue

            if not stripped.startswith("data:"):
                continue

            data_str = stripped[5:].strip()
            if not data_str:
                continue

            try:
                obj, _ = decoder.raw_decode(data_str)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            event_type = pending_event_type
            pending_event_type = None  # consumed

            if event_type == "content_block_delta":
                delta = obj.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        if first_chunk:
                            yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': text}}]})}\n\n"
                            first_chunk = False
                        else:
                            yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': text}}]})}\n\n"
                        yielded_any = True
                elif delta.get("type") == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    if partial:
                        yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': tool_idx - 1, 'function': {'arguments': partial}}]}}]})}\n\n"
                        yielded_any = True

            elif event_type == "content_block_start":
                content_block = obj.get("content_block", {})
                if content_block.get("type") == "tool_use":
                    # Emit the tool call header with id, name, and index
                    tc_id = content_block.get("id", "")
                    tc_name = content_block.get("name", "")
                    yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': tool_idx, 'id': tc_id, 'type': 'function', 'function': {'name': tc_name, 'arguments': ''}}]}}]})}\n\n"
                    if first_chunk:
                        first_chunk = False
                    yielded_any = True
                    tool_idx += 1

            elif event_type == "message_start":
                message = obj.get("message", {})
                usage = message.get("usage", {}) or {}
                total_input_tokens = usage.get("input_tokens", 0) or 0

            elif event_type == "message_delta":
                if not saw_finish:
                    saw_finish = True
                    delta = obj.get("delta", {})
                    stop_reason = delta.get("stop_reason", "end_turn")
                    usage = obj.get("usage", {})
                    total_output_tokens = usage.get("output_tokens", 0) or 0
                    finish_reason = anthropic_stop_to_openai_finish(stop_reason)
                    openai_delta = {"finish_reason": finish_reason}
                    if total_output_tokens or total_input_tokens:
                        openai_delta["usage"] = {
                            "prompt_tokens": total_input_tokens,
                            "completion_tokens": total_output_tokens,
                            "total_tokens": total_input_tokens + total_output_tokens,
                        }
                    yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': openai_delta}]})}\n\n"
                    yielded_any = True

            elif event_type == "message_stop":
                if not saw_finish:
                    yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'finish_reason': 'stop'}}]})}\n\n"
                yield "data: [DONE]\n\n"
                yielded_any = True

            elif event_type == "error":
                yield f"data: {json.dumps(obj)}\n\n"
                yielded_any = True

    except GeneratorExit:
        # Client disconnected mid-stream. Yield is illegal inside `finally`
        # during close (Python 3.12+ RuntimeError), so skip the marker.
        _closed = True
        raise
    except asyncio.CancelledError:
        _closed = True
        raise
    finally:
        await safe_aclose(response)
        if not _closed and not yielded_any and not saw_finish:
            empty_err = json.dumps({"error": {"code": "empty_stream", "message": "Upstream returned empty stream"}})
            yield f"data: {empty_err}\n\n"


async def _try_candidate(
    *,
    request: ChatCompletionRequest,
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
    """Try one candidate supplier. Returns a response (JSONResponse / StreamingResponse)
    or raises HTTPException to trigger fallback to the next candidate.

    Sets ``body["model"]`` for the upstream call.
    """
    if candidate_idx > 0 or total_candidates > 1:
        logger.info(
            "Candidate %d/%d: account=%s model=%s stream=%s",
            candidate_idx + 1, total_candidates,
            account.account_id, actual_model_id, request.stream,
        )

    key_id = getattr(account, "_key_id", 0) or 0
    api_key = getattr(account, "_key_string", None) or account.api_key

    # Pre-request rate-limit check
    request_start = datetime.now(timezone.utc).isoformat()
    provider_type = account.provider_type or "modelscope"
    strategies = services.get("rate_limit_strategies", {})
    rate_strategy = strategies.get(provider_type)
    if rate_strategy and not rate_strategy.check_rate_limit(
            account.account_id, actual_model_id, key_id=key_id):
        await _log_error_request(
            admin_service, request.model, actual_model_id, account,
            client_key_name, 429,
            f"供应商 {account.name or account.account_id} 的 {request.model} 配额已耗尽",
            body, request_start, is_stream=request.stream, key_id=key_id,
            error_source="rate_limit",
        )
        raise HTTPException(status_code=429, detail={
            "error": {"message": f"供应商 {account.name or account.account_id} 的 {request.model} 配额已耗尽",
                      "type": "rate_limit_exceeded", "param": None, "code": "rate_limit_exceeded"}})

    # The client reached the OpenAI entry point, so we ALWAYS speak the OpenAI
    # protocol to the upstream here. ``provider_type`` is the *supplier's type*
    # (used for rate-limit strategy / display) — it is NOT the protocol, and a
    # single supplier can expose both OpenAI and Anthropic endpoints. The OpenAI
    # endpoint is always ``base_url``.
    is_anthropic = False  # /openai entry → upstream speaks OpenAI; no conversion
    body["model"] = actual_model_id
    if request.stream:
        body["stream"] = True
        existing = body.get("stream_options")
        if isinstance(existing, dict):
            existing = dict(existing)
            existing["include_usage"] = True
            body["stream_options"] = existing
        else:
            body["stream_options"] = {"include_usage": True}
    url = f"{resolve_upstream_base(account, 'openai')}/chat/completions"
    auth_style = "bearer"

    # Make upstream request via the injected http_client service.
    # On upstream 429 the same candidate is retried with exponential backoff
    # (honoring Retry-After); the final response is returned for the normal
    # error path below to record + fall back if it is still a 429.
    async def _do_upstream_request():
        return await http_client.request(
            account,
            "POST",
            url,
            json=body,
            stream=request.stream,
            key_string=api_key,
            auth_style=auth_style,
        )

    try:
        response = await request_with_429_backoff(
            _do_upstream_request,
            account_id=account.account_id,
            actual_model_id=actual_model_id,
            close_fn=safe_aclose,
        )
        first_response = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(
                    key_id, account.account_id, actual_model_id, -1,
                )
            except Exception:
                pass
        error_msg = f"Failed to reach supplier: {exc}"
        await _log_error_request(
            admin_service, request.model, actual_model_id, account,
            client_key_name, 502, error_msg, body, request_start,
            error_source="upstream",
        )
        raise HTTPException(status_code=502, detail=error_msg)

    # 4xx / 5xx from upstream → record failure and raise to trigger fallback
    if response.status_code >= 400:
        error_body = await safe_read_response_body(response)
        error_code = response.status_code
        detail_msg = f"Supplier error {error_code}: {error_body[:200]}" if error_body else f"Supplier error {error_code}"

        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(
                    key_id, account.account_id, actual_model_id, error_code,
                )
            except Exception:
                pass

        await safe_aclose(response)
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
            # Read the full response body for parsing. `response.text` works for
            # both real httpx responses and test mocks (where `.text` is set
            # directly on the Mock).
            raw_text = getattr(response, "text", None) or ""
            if raw_text:
                resp_json = json.loads(raw_text)
            else:
                raw_text = await safe_read_response_body(response)
                resp_json = json.loads(raw_text) if raw_text else {}

            # Validate the response body. An empty body or a body with no
            # ``choices`` means the upstream returned a 200 but no content —
            # treat it as a 502 Bad Gateway so the caller can try another
            # candidate or surface a clear error to the client.
            if not resp_json:
                if circuit_breaker is not None:
                    try:
                        circuit_breaker.record_failure(
                            key_id, account.account_id, actual_model_id, 502,
                        )
                    except Exception:
                        pass
                await _log_error_request(
                    admin_service, request.model, actual_model_id, account,
                    client_key_name, 502,
                    "Empty response body from upstream", body,
                    request_start, first_response, is_stream=request.stream,
                    key_id=key_id, error_source="upstream",
                )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": {
                            "message": "Supplier returned empty response",
                            "type": "server_error",
                            "param": None,
                            "code": "empty_response",
                        }
                    },
                )
            # For Anthropic upstreams, the response is in Anthropic format
            # (has ``content`` blocks, no ``choices``). Skip the OpenAI-
            # specific validation and convert to OpenAI format below.
            if not is_anthropic:
                choices = resp_json.get("choices")
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    if circuit_breaker is not None:
                        try:
                            circuit_breaker.record_failure(
                                key_id, account.account_id, actual_model_id, 502,
                            )
                        except Exception:
                            pass
                    await _log_error_request(
                        admin_service, request.model, actual_model_id, account,
                        client_key_name, 502,
                        f"Invalid response from upstream: no choices in {resp_json.get('id', '?')}",
                        body, request_start, first_response, is_stream=request.stream,
                        key_id=key_id, error_source="upstream",
                    )
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error": {
                                "message": "Supplier returned response with no choices",
                                "type": "server_error",
                                "param": None,
                                "code": "no_choices",
                            }
                        },
                    )
                # Verify the first choice has a message block. Some upstreams
                # return ``choices`` without ``message`` (e.g. only ``finish_reason``),
                # which is not a valid OpenAI response.
                first_choice = choices[0]
                if not isinstance(first_choice, dict) or not first_choice.get("message"):
                    if circuit_breaker is not None:
                        try:
                            circuit_breaker.record_failure(
                                key_id, account.account_id, actual_model_id, 502,
                            )
                        except Exception:
                            pass
                    await _log_error_request(
                        admin_service, request.model, actual_model_id, account,
                        client_key_name, 502,
                        f"Invalid response from upstream: no message in {resp_json.get('id', '?')}",
                        body, request_start, first_response, is_stream=request.stream,
                        key_id=key_id, error_source="upstream",
                    )
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error": {
                                "message": "Supplier returned response with no message",
                                "type": "server_error",
                                "param": None,
                                "code": "no_message",
                            }
                        },
                    )
        except HTTPException:
            raise
        except Exception:
            await _log_error_request(
                admin_service, request.model, actual_model_id, account,
                client_key_name, 502, "Invalid response format", body,
                request_start, first_response, is_stream=request.stream,
                key_id=key_id, error_source="upstream",
            )
            raise HTTPException(status_code=502, detail="Invalid response from supplier")
        # Normalize non-OpenAI responses to the OpenAI format. Already-valid
        # OpenAI responses pass through unchanged so fields like
        # ``prompt_tokens_details`` (needed for cache-usage tracking) are not
        # stripped by the converter.
        # Record the raw upstream response BEFORE normalization so the log
        # captures what the supplier actually sent — useful for debugging when
        # the converter transforms non-standard formats.
        raw_upstream_response = json.dumps(resp_json, ensure_ascii=False)

        # Convert Anthropic-format response to OpenAI format
        if is_anthropic:
            resp_json = _anthropic_message_to_openai(resp_json, actual_model_id)

        response_converter = services.get("response_converter")
        if response_converter is not None:
            resp_json = _normalize_response(response_converter, resp_json)
        try:
            await response.aclose()
        except Exception:
            pass

        resp_usage = resp_json.get("usage", {}) or {}
        input_tokens = resp_usage.get("prompt_tokens", 0) or 0
        output_tokens = resp_usage.get("completion_tokens", 0) or 0
        cached_tokens, prompt_partial_cached = extract_cache_usage(resp_usage)
        end_time = datetime.now(timezone.utc).isoformat()

        if admin_service:
            try:
                resp_hdrs = {}
                for k in [
                    "x-ratelimit-remaining", "x-ratelimit-limit",
                    "modelscope-ratelimit-requests-remaining",
                    "modelscope-ratelimit-requests-limit",
                ]:
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
                    raw_response=raw_upstream_response[:50000] + ("...(truncated)" if len(raw_upstream_response) > 50000 else ""),
                    request_start=request_start, first_response=first_response, end_time=end_time,
                    cached_tokens=cached_tokens, prompt_partial_cached=prompt_partial_cached,
                    client_key_name=client_key_name,
                    response_headers=json.dumps(resp_hdrs if resp_hdrs else dict(response.headers), ensure_ascii=False),
                    api_key_id=key_id,
                )
            except Exception as le:
                logger.error(f"Failed to log non-stream request: {le}", exc_info=True)

        # Quota update — the legacy QuotaUpdater is the working path (B1:
        # the pluggable services.strategy was never implemented, so the
        # `strategy` branch above was always skipped).
        try:
            if quota_updater and (input_tokens > 0 or output_tokens > 0):
                await asyncio.to_thread(
                    quota_updater.update_quota_from_usage,
                    account, input_tokens, output_tokens, actual_model_id,
                    key_id,
                )
            if quota_updater and response is not None:
                await asyncio.to_thread(
                    quota_updater.update_quota_after_request,
                    account, dict(response.headers), actual_model_id,
                    None,
                    key_id,
                )
        except Exception as qe:
            logger.warning(f"Failed to update quota: {qe}")

        # Circuit breaker success
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

        # Release the least_conn in-flight slot for this now-completed
        # non-streaming request. (The streaming path releases inside the
        # generator's finally instead, so the two never double-release.)
        if alias_router is not None:
            try:
                alias_router.release(key_id, actual_model_id)
            except Exception:
                pass

        try:
            latency_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(request_start)).total_seconds() * 1000)
        except Exception:
            latency_ms = 0
        return JSONResponse(
            content=resp_json,
            headers={
                "X-Upstream-Account": account.account_id,
                "X-Upstream-Model": actual_model_id or "",
                "X-Latency-Ms": str(latency_ms),
            },
        )

    # ── Streaming success ──
    if is_anthropic:
        # Anthropic upstream → convert Anthropic SSE → OpenAI SSE
        stream_gen = stream_response_with_logging_anthropic_upstream(
            response, account, request.model, body,
            actual_model_id, admin_service, request_start,
            quota_updater=quota_updater, client_key_name=client_key_name,
            circuit_breaker=circuit_breaker,
            alias_router=alias_router, key_id=key_id,
        )
    else:
        stream_gen = stream_response_with_logging(
            response, account, request.model, body,
            actual_model_id, admin_service, request_start,
            quota_updater=quota_updater, client_key_name=client_key_name,
            circuit_breaker=circuit_breaker,
            alias_router=alias_router, key_id=key_id,
        )
    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
    )


@router.post("/v1/chat/completions")
async def chat_completions(data: ChatCompletionRequest, fastapi_request: Request):
    """OpenAI-compatible chat completion endpoint.

    Routes through AliasRouter candidates with fallback: when one supplier fails
    the request falls back to the next candidate. The circuit breaker is checked
    before each attempt and frozen candidates are skipped.
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

        # 1. Try alias-router candidates with fallback
        if alias_router is not None:
            try:
                candidates = alias_router.get_candidates(data.model)
            except Exception:
                candidates = []

            if candidates:
                body = await _build_request_body(data, data.model)
                last_error = None

                for candidate_idx, candidate in enumerate(candidates):
                    account = candidate.account
                    actual_model_id = candidate.model_name

                    # Store key identity on the account for _try_candidate
                    account._key_id = candidate.key_id
                    account._key_string = candidate.key_string

                    # Check circuit breaker — skip frozen candidates
                    if circuit_breaker is not None and not circuit_breaker.check(
                            candidate.key_id, actual_model_id):
                        logger.info(
                            "Skipping frozen candidate %d/%d: account=%s model=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id,
                        )
                        cb_req_body = await _build_request_body(data, actual_model_id)
                        now = datetime.now(timezone.utc).isoformat()
                        await _log_error_request(
                            admin_service, data.model, actual_model_id, account,
                            client_key_name, 503,
                            f"供应商 {account.name or account.account_id} 的 {actual_model_id} 模型已被冻结(熔断)",
                            cb_req_body, now, None, is_stream=data.stream,
                            error_source="circuit_open",
                        )
                        last_error = last_error or HTTPException(
                            status_code=503, detail={
                                "error": {
                                    "message": f"供应商 {account.name or account.account_id} 的 {actual_model_id} 模型已被冻结",
                                    "type": "circuit_open", "param": None, "code": "circuit_open",
                                }
                            }
                        )
                        continue

                    # Acquire an in-flight slot for least_conn accounting. The
                    # matching release happens when the request finishes: the
                    # stream path releases inside stream_response_with_logging's
                    # finally; the non-stream path releases below in _try_candidate;
                    # a failed candidate releases here before falling back.
                    if alias_router is not None:
                        try:
                            alias_router.acquire(candidate.key_id, actual_model_id)
                        except Exception:
                            pass

                    try:
                        # Deep-copy body per candidate so per-candidate mutations
                        # (``model``, ``stream_options``, etc.) in ``_try_candidate``
                        # don't leak into the next candidate in the fallback chain.
                        body_copy = copy.deepcopy(body)
                        result = await _try_candidate(
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
                        # Release the in-flight slot for the failed candidate so
                        # least_conn counting stays accurate across fallbacks.
                        if alias_router is not None:
                            try:
                                alias_router.release(candidate.key_id, actual_model_id)
                            except Exception:
                                pass
                        logger.warning(
                            "Candidate %d/%d failed: account=%s model=%s status=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id,
                            getattr(e, "status_code", "??"),
                        )
                        continue
                    except Exception as e:
                        # Non-HTTPException (e.g. ValueError from http_client
                        # when no usable key exists). Release the in-flight slot
                        # to avoid leaking the least_conn counter, then re-raise.
                        if alias_router is not None:
                            try:
                                alias_router.release(candidate.key_id, actual_model_id)
                            except Exception:
                                pass
                        logger.error(
                            "Candidate %d/%d failed with non-HTTP error: "
                            "account=%s model=%s error=%s",
                            candidate_idx + 1, len(candidates),
                            account.account_id, actual_model_id,
                            f"{type(e).__name__}: {e}",
                        )
                        raise
                    else:
                        return result

                # All candidates exhausted
                raise last_error or HTTPException(
                    status_code=503, detail={
                        "error": {
                            "message": f"所有供应商的 {data.model} 模型请求均失败",
                            "type": "all_failed", "param": None, "code": "all_failed",
                        }
                    }
                )

        # 2. No alias binding → fall back to old-style load balancer selection
        actual_model_id = model_name
        try:
            selected_account = lb.select_account(model_name)
            # Resolve alias if possible
            alias_resolver = services.get("alias_resolver")
            if alias_resolver is not None:
                actual_model_id = await alias_resolver.resolve_alias(selected_account, model_name)
        except Exception:
            raise HTTPException(status_code=503, detail=f"Model {model_name} not available")

        # In the non-candidate fallback path the key_id is 0 (primary key).
        selected_account._key_id = 0
        selected_account._key_string = selected_account.api_key

        if circuit_breaker is not None and not circuit_breaker.check(
                0, actual_model_id):
            now = datetime.now(timezone.utc).isoformat()
            await _log_error_request(
                admin_service, data.model, actual_model_id, selected_account,
                client_key_name, 503,
                f"供应商 {selected_account.name or selected_account.account_id} 的 {actual_model_id} 模型已被冻结(熔断)",
                {"model": actual_model_id, "messages": data.messages}, now,
                is_stream=data.stream, error_source="circuit_open",
            )
            raise HTTPException(status_code=503, detail={
                "error": {
                    "message": f"供应商 {selected_account.name or selected_account.account_id} 的 {actual_model_id} 模型已被冻结",
                    "type": "circuit_open", "param": None, "code": "circuit_open",
                }
            })

        body = await _build_request_body(data, actual_model_id)
        logger.info(f"Resolved model {data.model} to {actual_model_id}")
        return await _try_candidate(
            request=data, account=selected_account,
            actual_model_id=actual_model_id, body=body,
            http_client=http_client,
            admin_service=admin_service,
            quota_updater=quota_updater, services=services,
            client_key_name=client_key_name,
            circuit_breaker=circuit_breaker, alias_router=alias_router,
            candidate_idx=0, total_candidates=1,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"ModelScope API error: {e}")
        if admin_service:
            try:
                now = datetime.now(timezone.utc).isoformat()
                await asyncio.to_thread(admin_service.log_request,
                    model=data.model, actual_model_id=data.model,
                    account_id="unknown", account_name="unknown",
                    status_code=500, input_tokens=0, output_tokens=0,
                    is_stream=data.stream,
                    error_message=f"ValueError: {e}",
                    raw_request=json.dumps(data.model_dump(), ensure_ascii=False),
                    raw_response="", request_start=now, first_response=None, end_time=now,
                    cached_tokens=0, prompt_partial_cached=0,
                    client_key_name=client_key_name,
                )
            except Exception as le:
                logger.error(f"Failed to log error request: {le}", exc_info=True)
        raise HTTPException(status_code=500, detail={
            "error": {"message": str(e), "type": "api_error", "param": None, "code": "api_error"}})
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Non-HTTP error ({error_type}) during request for model={data.model}: {e}", exc_info=True)
        if admin_service:
            try:
                now = datetime.now(timezone.utc).isoformat()
                await asyncio.to_thread(admin_service.log_request,
                    model=data.model, actual_model_id=data.model,
                    account_id="unknown", account_name="unknown",
                    status_code=500, input_tokens=0, output_tokens=0,
                    is_stream=data.stream,
                    error_message=f"Non-HTTP error ({error_type}): {e}",
                    raw_request=json.dumps(data.model_dump(), ensure_ascii=False),
                    raw_response="", request_start=now, first_response=None, end_time=now,
                    cached_tokens=0, prompt_partial_cached=0,
                    client_key_name=client_key_name,
                )
            except Exception as le:
                logger.error(f"Failed to log error request: {le}", exc_info=True)
        raise HTTPException(status_code=500, detail={
            "error": {"message": "Internal server error", "type": "internal_error",
                      "param": None, "code": "internal_error"}})


def _load_active_models(admin_service) -> list:
    """Build the OpenAI-compatible model list from active mapping rows.

    Extracted so the result can be cached (see ``services.models_cache``) and
    reused by both the list and single-model endpoints (P3).
    """
    mappings = admin_service.mapping_repo.find_all()
    created = int(datetime.now(timezone.utc).timestamp())
    data = []
    for m in mappings:
        if m.get("status", "active") != "active":
            continue
        data.append({
            "id": m["alias_name"],
            "object": "model",
            "created": created,
            "owned_by": "provider",
        })
    return data


@router.get("/v1/models")
async def list_models(fastapi_request: Request):
    """OpenAI-compatible list models endpoint (cached, see P3)."""
    _authenticate_client_key(fastapi_request)

    admin_service = get_admin_service(fastapi_request)
    try:
        data = get_models(lambda: _load_active_models(admin_service))
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Failed to list models",
                    "type": "internal_error",
                    "param": None,
                    "code": "internal_error"
                }
            }
        )

    return {"object": "list", "data": data}


@router.get("/v1/models/{model_id}")
async def get_model(
    model_id: str,
    fastapi_request: Request,
):
    """OpenAI-compatible single model query endpoint (cached, see P3)."""
    _authenticate_client_key(fastapi_request)

    admin_service = get_admin_service(fastapi_request)
    try:
        models = get_models(lambda: _load_active_models(admin_service))
    except Exception as e:
        logger.error(f"Failed to list models for {model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": "Failed to list models", "type": "internal_error", "param": None, "code": "internal_error"}}
        )

    for m in models:
        if m.get("id") == model_id:
            return m

    raise HTTPException(
        status_code=404,
        detail={"error": {"message": f"Model {model_id} not found", "type": "invalid_request_error", "param": "model", "code": "model_not_found"}}
    )
