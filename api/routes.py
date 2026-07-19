from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, AsyncGenerator, Any
import json
import logging
import time
from datetime import datetime, timezone

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
    functions: Optional[Any] = None  # deprecated but still accepted
    parallel_tool_calls: Optional[bool] = None


class ErrorResponse(BaseModel):
    """Error response format."""
    error: dict


def get_admin_service(request: Request):
    """Get admin service from app state."""
    try:
        svc = request.app.state.admin_service
    except AttributeError:
        return None
    return svc


def _authenticate_client_key(request: Request):
    """Authenticate request using client API key.

    Checks Authorization: Bearer <key> and X-API-Key headers.
    Returns (client_key_name, key_value) or raises HTTPException.
    Returns (None, None) if no key provided (backward compatible).
    """
    admin_service = get_admin_service(request)
    if admin_service is None or admin_service.client_key_repo is None:
        return None, None

    # Try Authorization header first
    auth_header = request.headers.get("Authorization", "")
    client_key = None
    if auth_header.startswith("Bearer "):
        client_key = auth_header[7:].strip()
    elif auth_header.startswith("bearer "):
        client_key = auth_header[7:].strip()

    # Fall back to X-API-Key header
    if not client_key:
        client_key = request.headers.get("X-API-Key", "").strip()

    if not client_key:
        return None, None

    # Validate key
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

    # Refresh load balancer with current accounts from database
    # This ensures newly added accounts are available for load balancing
    try:
        db = services.get("database")
        supplier_model_repo = services.get("supplier_model_repo")

        if db and supplier_model_repo is not None:
            from models.account import ModelScopeAccount
            from repositories.account_repository import AccountRepository

            repo = AccountRepository(db)
            db_accounts = repo.find_active()

            # Convert to ModelScopeAccount objects
            accounts = []
            for a in db_accounts:
                accounts.append(ModelScopeAccount(
                    account_id=a["account_id"],
                    name=a.get("name", ""),
                    api_key=a["api_key"],
                    base_url=a["base_url"],
                ))

            from services.load_balancer import LoadBalancer
            services["load_balancer"] = LoadBalancer(accounts, supplier_model_repo=supplier_model_repo)
    except Exception:
        # If refresh fails, continue with existing load balancer
        logger.warning("Failed to refresh load balancer accounts")

    return services


async def stream_response(
    account,
    http_client,
    model_name: str,
    request_body: dict,
    _capture_headers: bool = False,
) -> AsyncGenerator[str, None]:
    """Generate streaming response from ModelScope API.

    If _capture_headers is True, the first yielded chunk carries the
    HTTP response headers as a JSON blob prefixed with "__hdrs__:" so
    the caller can extract them without breaking the SSE protocol.
    """
    url = f"{account.base_url}/chat/completions"
    response = await http_client.request(
        account,
        "POST",
        url,
        json=request_body
    )

    if response.status_code != 200:
        yield f"data: {json.dumps({'error': f'API error: {response.status_code}'})}\n\n"
        return

    # Inject headers as first chunk (consumer strips them out)
    if _capture_headers:
        hdrs = {}
        try:
            hdrs = dict(response.headers)
        except Exception:
            pass
        yield f"data: {json.dumps({'__hdrs__': hdrs})}\n\n"

    # Skip Tencent's initial empty chunks (choices=null) which break validation
    decoder = json.JSONDecoder()

    async for line in response.aiter_lines():
        stripped = line.strip()
        if stripped == "[DONE]":
            yield "data: [DONE]\n\n"
            return

        if stripped.startswith("data:"):
            data_str = stripped[5:].strip()
            # Skip empty data lines
            if not data_str:
                continue

            try:
                chunk, _ = decoder.raw_decode(data_str)
            except json.JSONDecodeError:
                # Fall back to forwarding raw line
                yield f"data: {data_str}\n\n"
                continue

            # Skip initial empty chunks from Tencent where choices is null
            if chunk and chunk.get("choices") is None:
                continue

            # Forward valid chunks
            yield f"data: {json.dumps(chunk)}\n\n"


async def stream_response_with_logging(
    account,
    http_client,
    model_name: str,
    request_body: dict,
    actual_model_id: str,
    admin_service,
    quota_updater=None,
    client_key_name: str = None,
):
    """Streaming response wrapper that logs and updates quota after completion."""
    total_tokens = 0
    input_tokens = 0
    response_headers = {}
    raw_chunks = []
    first_response = None
    request_start = datetime.now(timezone.utc).isoformat()

    async for chunk_data in stream_response(
        account, http_client, model_name, request_body, _capture_headers=True
    ):
        # Strip out the injected __hdrs__ chunk
        try:
            data_str = chunk_data.replace("data: ", "").strip()
            if data_str:
                dec = json.JSONDecoder()
                hdr_obj, _ = dec.raw_decode(data_str)
                if "__hdrs__" in hdr_obj:
                    response_headers = hdr_obj["__hdrs__"]
                    continue  # skip this chunk, don't yield to client
        except Exception:
            pass

        if first_response is None:
            first_response = datetime.now(timezone.utc).isoformat()
        yield chunk_data
        raw_chunks.append(chunk_data)

        # Try to extract token count from usage in each chunk
        try:
            data_str = chunk_data.replace("data: ", "").strip()
            if data_str:
                decoder = json.JSONDecoder()
                json_data, _ = decoder.raw_decode(data_str)
                usage = json_data.get("usage", {})
                # Only take the latest usage (last chunk has final counts)
                input_tokens = usage.get("prompt_tokens", 0) or input_tokens
                total_tokens = usage.get("completion_tokens", 0) or total_tokens
        except Exception:
            pass

    # Log after streaming completes
    end_time = datetime.now(timezone.utc).isoformat()
    logger.info(f"Streaming completed for {account.account_id}: input={input_tokens} output={total_tokens} chunks={len(raw_chunks)} admin_svc={'yes' if admin_service else 'no'}")
    if admin_service:
        try:
            # Deduplicate tool calls by id
            seen_ids = set()
            unique_tools = []
            for t in tool_calls_found:
                if t["id"] and t["id"] in seen_ids:
                    continue
                if t["id"]:
                    seen_ids.add(t["id"])
                unique_tools.append(t)

            admin_service.log_request(
                model=model_name,
                actual_model_id=actual_model_id,
                account_id=account.account_id,
                account_name=account.name,
                status_code=200,
                input_tokens=input_tokens,
                output_tokens=total_tokens,
                is_stream=True,
                latency_ms=None,
                raw_request=json.dumps(request_body, ensure_ascii=False),
                raw_response="".join(raw_chunks),
                request_start=request_start,
                first_response=first_response,
                end_time=end_time,
                client_key_name=client_key_name,
                response_headers=json.dumps(response_headers, ensure_ascii=False) if response_headers else None,
            )
        except Exception as e:
            logger.warning(f"Failed to log streaming request: {e}")

    # Update quota from streaming usage data
    if quota_updater and hasattr(account, 'api_key'):
        try:
            if input_tokens > 0 or total_tokens > 0:
                quota_updater.update_quota_from_usage(
                    account, input_tokens, total_tokens, model_name
                )
            # Also update quota remaining/limit from captured response headers
            if response_headers:
                quota_updater.update_quota_after_request(
                    account, response_headers, model_name
                )
        except Exception as e:
            logger.warning(f"Failed to update streaming quota: {e}")


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    fastapi_request: Request,
    services=Depends(get_services)
):
    """Chat completions endpoint compatible with OpenAI API."""
    alias_resolver = services["alias_resolver"]
    load_balancer = services["load_balancer"]
    response_converter = services["response_converter"]
    quota_updater = services["quota_updater"]
    http_client = services["http_client"]
    admin_service = get_admin_service(fastapi_request)

    # Authenticate client API key
    client_key_name, _ = _authenticate_client_key(fastapi_request)

    try:
        # Select supplier using load balancer
        selected_account = load_balancer.select_account(request.model)
        logger.info(f"Selected account {selected_account.account_id} for request")

        # Resolve model alias
        actual_model_id = await alias_resolver.resolve_alias(
            selected_account,
            request.model
        )
        logger.info(f"Resolved model {request.model} to {actual_model_id}")

        # Prepare request body (forward all OpenAI-compatible parameters)
        request_body = {
            "model": actual_model_id,
            "messages": request.messages,  # forward as-is for full compatibility
        }

        # Forward optional parameters
        if request.temperature is not None:
            request_body["temperature"] = request.temperature
        if request.max_tokens is not None:
            request_body["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            request_body["top_p"] = request.top_p
        if request.stop is not None:
            request_body["stop"] = request.stop
        if request.n is not None:
            request_body["n"] = request.n
        if request.frequency_penalty is not None:
            request_body["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            request_body["presence_penalty"] = request.presence_penalty
        if request.logit_bias is not None:
            request_body["logit_bias"] = request.logit_bias
        if request.logprobs is not None:
            request_body["logprobs"] = request.logprobs
        if request.top_logprobs is not None:
            request_body["top_logprobs"] = request.top_logprobs
        if request.response_format is not None:
            request_body["response_format"] = request.response_format
        if request.seed is not None:
            request_body["seed"] = request.seed
        if request.service_tier is not None:
            request_body["service_tier"] = request.service_tier
        if request.tools is not None:
            request_body["tools"] = request.tools
        if request.tool_choice is not None:
            request_body["tool_choice"] = request.tool_choice
        if request.functions is not None:
            request_body["functions"] = request.functions
        if request.parallel_tool_calls is not None:
            request_body["parallel_tool_calls"] = request.parallel_tool_calls

        # Handle streaming request
        if request.stream:
            # Add stream parameter for ModelScope
            request_body["stream"] = True
            return StreamingResponse(
                stream_response_with_logging(
                    selected_account, http_client, request.model, request_body, actual_model_id, admin_service,
                    quota_updater=quota_updater,
                    client_key_name=client_key_name,
                ),
                media_type="text/event-stream"
            )

        # Non-streaming request
        request_start = datetime.now(timezone.utc).isoformat()
        url = f"{selected_account.base_url}/chat/completions"
        response = await http_client.request(
            selected_account,
            "POST",
            url,
            json=request_body
        )
        first_response = datetime.now(timezone.utc).isoformat()

        # Check for rate limit errors
        if response.status_code == 429:
            quota_updater.update_quota_after_request(
                selected_account,
                dict(response.headers),
                request.model
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "message": f"所有供应商的 {request.model} 模型配额已耗尽",
                        "type": "rate_limit_exceeded",
                        "param": None,
                        "code": "rate_limit_exceeded"
                    }
                }
            )

        response.raise_for_status()

        # Parse response - ModelScope may return SSE format or concatenated JSON
        response_text = response.text
        decoder = json.JSONDecoder()

        # SSE format (starts with "data:")
        if response_text.startswith("data:"):
            last_valid = None
            for line in response_text.split("\n"):
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        obj, _ = decoder.raw_decode(data_str)
                        last_valid = obj
                    except json.JSONDecodeError:
                        continue
            if last_valid is not None:
                ms_response = last_valid
            else:
                raise ValueError("Could not parse SSE response")
        else:
            # Raw JSON (possibly concatenated) - use raw_decode to safely extract the first object
            try:
                ms_response, _ = decoder.raw_decode(response_text)
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse response")

        # Convert and return response
        try:
            openai_response = response_converter.convert_to_openai(ms_response)
        except Exception as conv_err:
            logger.error(f"Response conversion failed: {conv_err}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail={
                    "error": {
                        "message": f"Response conversion failed: {conv_err}",
                        "type": "conversion_error",
                        "param": None,
                        "code": "conversion_error"
                    }
                }
            )

        # Update quota
        try:
            quota_updater.update_quota_after_request(
                selected_account,
                dict(response.headers),
                request.model
            )
        except Exception as qe:
            logger.warning(f"Failed to update quota: {qe}")

        # Log the request (non-streaming)
        end_time = datetime.now(timezone.utc).isoformat()
        if admin_service:
            try:
                ms_usage = ms_response.get("usage", {}) or {}

                # Extract cached tokens from usage
                cached_tokens = 0
                prompt_partial_cached = 0
                pt_details = ms_usage.get("prompt_tokens_details", {}) or {}
                if pt_details:
                    cached_tokens = pt_details.get("cached_tokens", pt_details.get("prompt_cache_hit_tokens", 0)) or 0
                    prompt_partial_cached = pt_details.get("prompt_partial_cached_tokens", 0) or 0

                # Extract relevant response headers
                resp_hdrs = {}
                for k in ["x-ratelimit-remaining", "x-ratelimit-limit", "modelscope-ratelimit-requests-remaining", "modelscope-ratelimit-requests-limit"]:
                    if k in response.headers:
                        resp_hdrs[k] = response.headers[k]

                admin_service.log_request(
                    model=request.model,
                    actual_model_id=actual_model_id,
                    account_id=selected_account.account_id,
                    account_name=selected_account.name,
                    status_code=response.status_code,
                    input_tokens=ms_usage.get("prompt_tokens", 0),
                    output_tokens=ms_usage.get("completion_tokens", 0),
                    latency_ms=None,
                    is_stream=False,
                    raw_request=json.dumps(request_body, ensure_ascii=False),
                    raw_response=response_text,
                    request_start=request_start,
                    first_response=first_response,
                    end_time=end_time,
                    cached_tokens=cached_tokens,
                    prompt_partial_cached=prompt_partial_cached,
                    client_key_name=client_key_name,
                    response_headers=json.dumps(resp_hdrs if resp_hdrs else dict(response.headers), ensure_ascii=False),
                )
                logger.info(f"Logged non-streaming request: model={request.model} account={selected_account.account_id} status={response.status_code}")
            except Exception as le:
                logger.error(f"Failed to log request: {le}", exc_info=True)

        return openai_response

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"ModelScope API error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": str(e),
                    "type": "api_error",
                    "param": None,
                    "code": "api_error"
                }
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_error",
                    "param": None,
                    "code": "internal_error"
                }
            }
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0"
    }


@router.get("/admin/quota")
async def admin_quota_info(fastapi_request: Request):
    """Get quota information for all suppliers."""
    admin_svc = get_admin_service(fastapi_request)
    if admin_svc is None or admin_svc.quota_repo is None:
        return {"total_suppliers": 0, "quota_status": []}

    suppliers = admin_svc.account_repo.find_all()
    quota_status = []
    total_suppliers = len(suppliers)

    for s in suppliers:
        info = admin_svc.quota_repo.get_account_info(s["account_id"])
        quota_status.append({
            "supplier_id": s["id"],
            "supplier_name": s.get("name", ""),
            "account_id": s["account_id"],
            "quota_remaining": info["quota_remaining"] if info else 0,
            "quota_limit": info["quota_limit"] if info else 0,
            "unavailable_models": list(info.get("unavailable_models", [])) if info else [],
        })

    return {
        "total_suppliers": total_suppliers,
        "quota_status": quota_status,
    }
