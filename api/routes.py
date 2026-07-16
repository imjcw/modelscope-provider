from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, AsyncGenerator
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class Message(BaseModel):
    """Chat message."""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = Field(..., description="Model name or alias")
    messages: List[Message] = Field(..., description="Chat messages")
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[str] = None
    n: Optional[int] = 1


class ErrorResponse(BaseModel):
    """Error response format."""
    error: dict


def get_services():
    """Get services from app state."""
    from main import app
    try:
        services = app.state.services
        if services:
            return services
    except AttributeError:
        pass
    from main import _services
    return _services


async def stream_response(
    account,
    http_client,
    model_name: str,
    request_body: dict
) -> AsyncGenerator[str, None]:
    """Generate streaming response from ModelScope API."""
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
    
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            yield line + "\n\n"
        elif line == "[DONE]":
            yield "data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Chat completions endpoint compatible with OpenAI API."""
    services = get_services()
    alias_resolver = services["alias_resolver"]
    load_balancer = services["load_balancer"]
    response_converter = services["response_converter"]
    quota_updater = services["quota_updater"]
    http_client = services["http_client"]

    try:
        # Select account using load balancer
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
            "messages": [{"role": m.role, "content": m.content} for m in request.messages]
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

        # Handle streaming request
        if request.stream:
            # Add stream parameter for ModelScope
            request_body["stream"] = True
            return StreamingResponse(
                stream_response(selected_account, http_client, actual_model_id, request_body),
                media_type="text/event-stream"
            )

        # Non-streaming request
        url = f"{selected_account.base_url}/chat/completions"
        response = await http_client.request(
            selected_account,
            "POST",
            url,
            json=request_body
        )

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
                        "message": f"All accounts have exceeded daily quota for model {request.model}",
                        "type": "rate_limit_exceeded",
                        "param": None,
                        "code": "rate_limit_exceeded"
                    }
                }
            )

        response.raise_for_status()

        # Parse response - ModelScope may return SSE format
        response_text = response.text
        
        # Check if response is SSE format (starts with "data:")
        if response_text.startswith("data:"):
            # Parse SSE response to get final JSON
            for line in response_text.split("\n"):
                if line.startswith("data:"):
                    try:
                        ms_response = json.loads(line[5:].strip())
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                raise ValueError("Could not parse SSE response")
        else:
            ms_response = response.json()

        # Convert and return response
        openai_response = response_converter.convert_to_openai(ms_response)

        # Update quota
        quota_updater.update_quota_after_request(
            selected_account,
            dict(response.headers),
            request.model
        )

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
async def admin_quota_info():
    """Get quota information for all accounts."""
    # Simulate quota info (actual implementation in Task 12)
    return {
        "total_accounts": 0,
        "quota_status": []
    }
