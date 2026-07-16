# FastAPI wrapper for OpenAI-compatible ModelScope proxy
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, AsyncIterator
import json
import asyncio
import logging
from contextlib import asynccontextmanager

from openai_proxy import ModelScopeProxy, ModelScopeAccount, AccountRegion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global proxy instance
proxy = None


def load_proxy():
    global proxy
    if proxy is None:
        accounts = [
            ModelScopeAccount(
                account_id="china-account",
                api_key="ms-ef15676c-7ad4-49b5-8b55-2c2ae7101b8c",
                base_url="https://api-inference.modelscope.cn/v1",
                region=AccountRegion.CHINA,
                quota_remaining=2000,
                quota_limit=2000
            ),
            ModelScopeAccount(
                account_id="overseas-account",
                api_key="ms-ff949c01-ac4f-4854-b7ba-9c43b0c02c53",
                base_url="https://api-inference.modelscope.ai/v1",
                region=AccountRegion.OVERSEAS,
                quota_remaining=2000,
                quota_limit=2000
            )
        ]
        proxy = ModelScopeProxy(accounts)


@asynccontextmanager
async def lifespan(app):
    load_proxy()
    logger.info("ModelScope Proxy service started")
    yield
    logger.info("ModelScope Proxy service stopped")


app = FastAPI(
    title="ModelScope Proxy",
    description="OpenAI-compatible proxy for ModelScope API",
    version="1.0.0",
    lifespan=lifespan
)


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="Model name")
    messages: List[Message] = Field(..., description="Chat messages")
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[str] = None


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint."""
    try:
        if request.stream:
            # Return streaming response
            async def generate():
                stream = await proxy.chat_completions_create(
                    model=request.model,
                    messages=[{"role": m.role, "content": m.content} for m in request.messages],
                    stream=True,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    stop=request.stop
                )
                async for chunk in stream:
                    # Convert chunk to SSE format
                    chunk_dict = chunk.model_dump()
                    yield f"data: {json.dumps(chunk_dict)}\n\n"
                    await asyncio.sleep(0)  # Yield control
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Return non-streaming response
            completion = await proxy.chat_completions_create(
                model=request.model,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                stream=False,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                stop=request.stop
            )
            return completion.model_dump()

    except RuntimeError as e:
        raise HTTPException(status_code=429, detail={"error": str(e)})
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/admin/quota")
async def quota_info():
    """Get quota information for all accounts."""
    return await proxy.get_quota_info()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
