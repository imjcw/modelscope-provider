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
from typing import Optional, List, AsyncGenerator, Any
import json
import asyncio
import logging
import time
import httpx
from datetime import datetime, timezone
from services.models_cache import get_models

logger = logging.getLogger(__name__)

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
    stop: Optional[str] = None
    n: Optional[int] = 1
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    logit_bias: Optional[dict] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None
    response_format: Optional[Any] = None
    seed: Optional[int] = None
    service_tier: Optional[str] = None
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None
    functions: Optional[Any] = None
    parallel_tool_calls: Optional[bool] = None


class ErrorResponse(BaseModel):
    """Error response format."""
    error: dict


def _extract_cache_usage(usage) -> tuple:
    """从上游 usage 提取 (cached_tokens, prompt_partial_cached)。

    兼容 OpenAI 风格 prompt_tokens_details.cached_tokens /
    prompt_partial_cached_tokens，以及 DeepSeek 风格顶层
    prompt_cache_hit_tokens。
    """
    if not isinstance(usage, dict):
        return 0, 0
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        details = {}
    cached = details.get("cached_tokens")
    if not cached:
        cached = usage.get("prompt_cache_hit_tokens", 0)
    partial = details.get("prompt_partial_cached_tokens", 0) or 0
    try:
        return int(cached or 0), int(partial)
    except (TypeError, ValueError):
        return 0, 0


async def _safe_read_response_body(response, max_len: int = 50000) -> str:
    """安全读取上游 HTTP 响应的 body 文本，失败时返回空字符串。"""
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
    """安全关闭上游流式响应，避免错误路径上的连接泄露。"""
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
    """记录失败请求到数据库，确保错误路径也有日志可查。

    error_source 标记错误来源:
      - None / ""     来自上游供应商的直接返回（上游本身返回了该状态码）
      - "upstream"    上游供应商直接返回的错误
      - "circuit_open" 熔断器主动拒绝（策略层拦截）
      - "rate_limit"  限流/配额耗尽（策略层拦截）
      - "internal"    服务自身产生的错误（非上游）
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


def get_admin_service(request: Request):
    """Get admin service from app state."""
    try:
        svc = request.app.state.admin_service
    except AttributeError:
        return None
    return svc


def _authenticate_client_key(request: Request):
    """Authenticate request using client API key."""
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


def get_services(request: Request):
    """Get services from the *request's* app state."""
    try:
        services = request.app.state.services
    except AttributeError:
        raise HTTPException(status_code=503, detail="Services not initialized")
    if services is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return services


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
                    unavailable_map = quota_repo.get_unavailable_models_batch(
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
            logger.info(
                f"LoadBalancer refreshed with {len(accounts)} accounts"
            )
    except Exception:
        logger.warning("Failed to refresh load balancer", exc_info=True)


async def stream_response(
    response,
    _capture_headers: bool = False,
) -> AsyncGenerator[str, None]:
    """Generate streaming response from a pre-made upstream response."""
    if _capture_headers:
        hdrs = {}
        try:
            hdrs = dict(response.headers)
        except Exception:
            pass
        yield f"data: {json.dumps({'__hdrs__': hdrs})}\n\n"

    decoder = json.JSONDecoder()

    try:
        async for line in response.aiter_lines():
            stripped = line.strip()
            if stripped == "[DONE]":
                yield "data: [DONE]\n\n"
                return

            if stripped.startswith("data:"):
                data_str = stripped[5:].strip()
                if not data_str:
                    continue

                try:
                    chunk, _ = decoder.raw_decode(data_str)
                except json.JSONDecodeError:
                    yield f"data: {data_str}\n\n"
                    continue

                if chunk and chunk.get("choices") is None:
                    continue

                yield f"data: {json.dumps(chunk)}\n\n"
    finally:
        await _safe_aclose(response)


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
                    _cached, _partial = _extract_cache_usage(usage)
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

        end_time = datetime.now(timezone.utc).isoformat()
        _stream_ended = stream_interrupted or stream_failed
        _is_empty = len(raw_chunks) == 0
        log_status = -1 if (_stream_ended or _is_empty) else stream_status_code
        log_error = (
            f"Streaming interrupted: {interrupt_reason}"
            if stream_interrupted
            else f"Empty stream: upstream returned 0 chunks (status={stream_status_code})"
            if _is_empty
            else None
        )
        raw_response_fallback = None
        if len(raw_chunks) == 0 and not stream_failed and not stream_interrupted:
            try:
                _lost_body = await _safe_read_response_body(response, max_len=50000)
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
                    account, input_tokens, output_tokens, actual_model_id or model_name
                )
            if response_headers:
                await asyncio.to_thread(quota_updater.update_quota_after_request,
                    account, response_headers, actual_model_id or model_name
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
    # stream is controlled server-side, not forwarded
    return body


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
            account.account_id, actual_model_id):
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

    url = f"{account.base_url.rstrip('/')}/chat/completions"

    # Make upstream request via the injected http_client service (pooled,
    # handles auth + base_url). stream=... is essential: without it httpx
    # buffers the entire upstream body and SSE arrives in one chunk at the
    # end (looks non-streaming to the client).
    try:
        response = await http_client.request(
            account,
            "POST",
            url,
            json=body,
            stream=request.stream,
            key_string=api_key,
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
        error_body = await _safe_read_response_body(response)
        error_code = response.status_code
        detail_msg = f"Supplier error {error_code}: {error_body[:200]}" if error_body else f"Supplier error {error_code}"

        if circuit_breaker is not None:
            try:
                circuit_breaker.record_failure(
                    key_id, account.account_id, actual_model_id, error_code,
                )
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
        first_response = datetime.now(timezone.utc).isoformat()
        try:
            # Read the full response body for parsing. `response.text` works for
            # both real httpx responses and test mocks (where `.text` is set
            # directly on the Mock).
            raw_text = getattr(response, "text", None) or ""
            if raw_text:
                resp_json = json.loads(raw_text)
            else:
                raw_text = await _safe_read_response_body(response)
                resp_json = json.loads(raw_text) if raw_text else {}
        except Exception:
            await _log_error_request(
                admin_service, request.model, actual_model_id, account,
                client_key_name, 502, "Invalid response format", body,
                request_start, first_response, is_stream=request.stream,
                key_id=key_id, error_source="upstream",
            )
            raise HTTPException(status_code=502, detail="Invalid response from supplier")
        try:
            await response.aclose()
        except Exception:
            pass

        resp_usage = resp_json.get("usage", {}) or {}
        input_tokens = resp_usage.get("prompt_tokens", 0) or 0
        output_tokens = resp_usage.get("completion_tokens", 0) or 0
        cached_tokens, prompt_partial_cached = _extract_cache_usage(resp_usage)
        end_time = datetime.now(timezone.utc).isoformat()
        raw_response = json.dumps(resp_json, ensure_ascii=False)

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
                    raw_response=raw_response[:50000] + ("...(truncated)" if len(raw_response) > 50000 else ""),
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
                )
            if quota_updater and response is not None:
                await asyncio.to_thread(
                    quota_updater.update_quota_after_request,
                    account, dict(response.headers), actual_model_id,
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
    return StreamingResponse(
        stream_response_with_logging(
            response, account, request.model, body,
            actual_model_id, admin_service, request_start,
            quota_updater=quota_updater, client_key_name=client_key_name,
            circuit_breaker=circuit_breaker,
            alias_router=alias_router, key_id=key_id,
        ),
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
                        cb_req_body = {"model": actual_model_id, "messages": data.messages}
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
                        return await _try_candidate(
                            request=data, account=account,
                            actual_model_id=actual_model_id, body=body,
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
