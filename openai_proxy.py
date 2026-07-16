# ModelScope Proxy Service
# A fully OpenAI-compatible proxy that forwards requests to ModelScope API
# with automatic account switching based on quota

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai._streaming import AsyncStream
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types import CompletionUsage
from datetime import datetime
import json
import asyncio
import logging
from typing import AsyncIterator, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create file handler for detailed logs
import os
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "proxy_requests.log")

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

# Create a special logger for request/response details
request_logger = logging.getLogger('proxy_requests')
request_logger.addHandler(file_handler)
request_logger.setLevel(logging.DEBUG)


class AsyncIteratorWrapper:
    """
    Wrapper to make an async generator compatible with OpenAI's AsyncStream interface.
    """
    
    def __init__(self, async_gen):
        self._async_gen = async_gen
    
    def __aiter__(self):
        return self._async_gen.__aiter__()
    
    async def __anext__(self):
        return await self._async_gen.__anext__()


class AccountRegion(Enum):
    CHINA = "china"
    OVERSEAS = "overseas"


@dataclass
class ModelScopeAccount:
    """ModelScope account configuration."""
    account_id: str
    api_key: str
    base_url: str
    region: AccountRegion
    quota_remaining: int = 0
    quota_limit: int = 0
    unavailable_models: set = field(default_factory=set)

    def get_openai_client(self) -> AsyncOpenAI:
        """Create an OpenAI-compatible client for this account."""
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )


class ModelScopeProxy:
    """
    ModelScope proxy that is fully compatible with OpenAI SDK.
    Automatically switches accounts when quota is exhausted.
    Supports both streaming and non-streaming responses.
    
    IMPORTANT: ModelScope API returns SSE format for ALL responses,
    even for non-streaming requests. This proxy handles that conversion.
    """

    def __init__(self, accounts: List[ModelScopeAccount]):
        self.accounts = accounts
        self._current_index = 0

    def _parse_modelscope_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse ModelScope response to extract JSON data.
        
        ModelScope returns raw JSON for non-streaming requests,
        or SSE format (data: {...}) for streaming requests.
        Sometimes the response contains concatenated JSON objects.
        """
        # Try to parse as raw JSON first (non-streaming)
        try:
            data = json.loads(response_text)
            return data
        except json.JSONDecodeError:
            pass
        
        # Try SSE format (data: {...})
        for line in response_text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    data = json.loads(data_str)
                    return data
                except json.JSONDecodeError:
                    continue
        
        # Handle concatenated JSON objects (no separators)
        # Find the last complete JSON object
        decoder = json.JSONDecoder()
        idx = 0
        last_valid = None
        
        while idx < len(response_text):
            try:
                obj, end_idx = decoder.raw_decode(response_text, idx)
                last_valid = obj
                idx = end_idx
                # Skip whitespace
                while idx < len(response_text) and response_text[idx].isspace():
                    idx += 1
            except json.JSONDecodeError:
                break
        
        if last_valid is not None:
            return last_valid
            
        raise ValueError(f"Could not parse ModelScope response. Text preview: {response_text[:200]}")

    def _select_account(self, model: str) -> Optional[ModelScopeAccount]:
        """Select an available account using round-robin strategy."""
        available = [
            acc for acc in self.accounts
            if model not in acc.unavailable_models and acc.quota_remaining >= 0
        ]
        
        if not available:
            return None
        
        # Round-robin selection
        account = available[self._current_index % len(available)]
        self._current_index += 1
        return account

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[str] = None,
        **kwargs
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        """
        Create a chat completion using the OpenAI-compatible API.
        
        This method is fully compatible with OpenAI SDK's chat.completions.create()
        and supports both streaming and non-streaming modes.
        """
        account = self._select_account(model)
        
        if not account:
            raise RuntimeError(
                f"All accounts have exhausted quota for model '{model}'. "
                f"Please check your ModelScope account limits."
            )

        logger.info(f"Using account {account.account_id} for model '{model}'")
        
        # Log request details
        request_info = {
            "account": account.account_id,
            "region": account.region.value,
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stop": stop,
            "url": f"{account.base_url}/chat/completions"
        }
        request_logger.info(f"REQUEST: {json.dumps(request_info, ensure_ascii=False)}")

        if stream:
            return await self._stream_completion(
                account=account,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stop=stop,
                **kwargs
            )
        else:
            return await self._non_stream_completion(
                account=account,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stop=stop,
                **kwargs
            )

    async def _non_stream_completion(
        self,
        account: ModelScopeAccount,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[str] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Handle non-streaming completion using raw HTTP request.
        ModelScope returns SSE format even for non-streaming, so we parse it manually.
        """
        import httpx
        
        url = f"{account.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {account.api_key}",
            "Content-Type": "application/json"
        }

        body = {
            "model": model,
            "messages": messages
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if top_p is not None:
            body["top_p"] = top_p
        if stop is not None:
            body["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                
                # Parse SSE response to get JSON
                response_text = response.text
                
                # Log response details
                response_info = {
                    "status_code": response.status_code,
                    "response_text_preview": response_text[:500],
                    "response_headers": {k: v for k, v in response.headers.items() if 'ratelimit' in k.lower() or 'quota' in k.lower()}
                }
                request_logger.info(f"RESPONSE (non-stream): {json.dumps(response_info, ensure_ascii=False)}")
                
                if response_text.startswith("data:"):
                    ms_response = self._parse_modelscope_response(response_text)
                else:
                    ms_response = self._parse_modelscope_response(response_text)

                # Create ChatCompletion object from response
                completion = ChatCompletion(**ms_response)
                
                # Log completion details
                completion_info = {
                    "id": completion.id,
                    "model": completion.model,
                    "message": completion.choices[0].message.content if completion.choices else None,
                    "usage": completion.usage.model_dump() if completion.usage else None
                }
                request_logger.info(f"COMPLETION: {json.dumps(completion_info, ensure_ascii=False)}")
                
                # Update quota from response headers
                self._update_quota_from_headers(account, model, response.headers)

                return completion

        except httpx.HTTPStatusError as e:
            # Log error details
            error_info = {
                "error": "HTTP_STATUS_ERROR",
                "status_code": e.response.status_code,
                "response_text": e.response.text[:500]
            }
            request_logger.error(f"ERROR: {json.dumps(error_info, ensure_ascii=False)}")
            
            if e.response.status_code == 429:
                logger.warning(f"Quota exhausted for {account.account_id}, marking unavailable")
                account.unavailable_models.add(model)
                return await self.chat_completions_create(
                    model=model,
                    messages=messages,
                    stream=False,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stop=stop
                )
            raise

    async def _stream_completion(
        self,
        account: ModelScopeAccount,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Optional[str] = None,
        **kwargs
    ) -> AsyncStream[ChatCompletionChunk]:
        """
        Handle streaming completion using raw HTTP request with SSE streaming.
        """
        import httpx
        
        url = f"{account.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {account.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

        body = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if top_p is not None:
            body["top_p"] = top_p
        if stop is not None:
            body["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    response.raise_for_status()
                    
                    # Read all content first
                    full_content = await response.aread()
                    response_text = full_content.decode("utf-8")
                    
                    # Log stream response details
                    request_logger.info(f"STREAM RESPONSE: {response_text[:500]}")
                    
                    # Parse and yield chunks
                    async def chunk_generator():
                        chunks = []
                        for line in response_text.split("\n"):
                            line = line.strip()
                            if line.startswith("data:"):
                                try:
                                    chunk_data = json.loads(line[5:].strip())
                                    if chunk_data == "[DONE]":
                                        break
                                    # Skip empty chunks
                                    if chunk_data.get("choices") is None:
                                        continue
                                    if chunk_data.get("object") != "chat.completion.chunk":
                                        continue
                                    chunk = ChatCompletionChunk(**chunk_data)
                                    chunks.append(chunk)
                                    yield chunk
                                except json.JSONDecodeError:
                                    continue
                                except Exception as e:
                                    logger.debug(f"Failed to parse chunk: {e}")
                                    continue
                        
                        # Log final chunks summary
                        if chunks:
                            request_logger.info(f"STREAM CHUNKS: {len(chunks)} chunks received")
                    
                    # Return as AsyncStream-like object
                    return AsyncIteratorWrapper(chunk_generator())

        except httpx.HTTPStatusError as e:
            # Log error details
            error_info = {
                "error": "HTTP_STATUS_ERROR_STREAM",
                "status_code": e.response.status_code,
                "response_text": e.response.text[:500]
            }
            request_logger.error(f"ERROR: {json.dumps(error_info, ensure_ascii=False)}")
            
            if e.response.status_code == 429:
                logger.warning(f"Quota exhausted for {account.account_id}, marking unavailable")
                account.unavailable_models.add(model)
                return await self.chat_completions_create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stop=stop
                )
            raise

    def _update_quota_from_headers(
        self,
        account: ModelScopeAccount,
        model: str,
        headers: Dict[str, str]
    ):
        """
        Update quota information from ModelScope response headers.
        """
        # ModelScope returns quota info in headers:
        # modelscope-ratelimit-requests-remaining: 100
        # modelscope-ratelimit-requests-limit: 1000
        # modelscope-ratelimit-model-requests-remaining: 50
        # modelscope-ratelimit-model-requests-limit: 100
        
        remaining_header = "modelscope-ratelimit-requests-remaining"
        limit_header = "modelscope-ratelimit-requests-limit"
        
        if remaining_header in headers:
            try:
                account.quota_remaining = int(headers[remaining_header])
                account.quota_limit = int(headers.get(limit_header, 0))
                
                if account.quota_remaining == 0:
                    account.unavailable_models.add(model)
                    logger.warning(f"Quota exhausted for {account.account_id} with model {model}")
            except ValueError:
                pass

    async def get_quota_info(self) -> List[Dict[str, Any]]:
        """Get quota information for all accounts."""
        info = []
        for account in self.accounts:
            info.append({
                "account_id": account.account_id,
                "region": account.region.value,
                "quota_remaining": account.quota_remaining,
                "quota_limit": account.quota_limit,
                "unavailable_models": list(account.unavailable_models)
            })
        return info


# Example usage and testing
async def main():
    """Test the ModelScope proxy with OpenAI SDK."""
    
    # Configure accounts
    accounts = [
        ModelScopeAccount(
            account_id="china-account",
            api_key="ms-ef15676c-7ad4-49b5-8b55-2c2ae7101b8c",
            base_url="https://api-inference.modelscope.cn/v1",
            region=AccountRegion.CHINA,
            quota_remaining=1000,
            quota_limit=2000
        ),
        ModelScopeAccount(
            account_id="overseas-account",
            api_key="ms-ff949c01-ac4f-4854-b7ba-9c43b0c02c53",
            base_url="https://api-inference.modelscope.ai/v1",
            region=AccountRegion.OVERSEAS,
            quota_remaining=1000,
            quota_limit=2000
        )
    ]

    # Create proxy
    proxy = ModelScopeProxy(accounts)

    # Test non-streaming completion
    print("Testing non-streaming completion...")
    completion = await proxy.chat_completions_create(
        model="Tencent-Hunyuan/Hy3",
        messages=[{"role": "user", "content": "你好，请介绍一下你自己"}],
        temperature=0.7,
        max_tokens=100
    )
    
    print(f"Response: {completion.choices[0].message.content}")
    print(f"Usage: {completion.usage}")
    print()

    # Test streaming completion
    print("Testing streaming completion...")
    stream = await proxy.chat_completions_create(
        model="Tencent-Hunyuan/Hy3",
        messages=[{"role": "user", "content": "请写一首短诗"}],
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()

    # Test quota info
    print("\nQuota info:")
    quota_info = await proxy.get_quota_info()
    for info in quota_info:
        print(f"  {info}")


if __name__ == "__main__":
    asyncio.run(main())
