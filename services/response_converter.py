from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ResponseConverter:
    """Convert ModelScope responses to OpenAI format."""

    def convert_to_openai(self, ms_response: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ModelScope response to OpenAI format."""
        try:
            # Handle null/missing choices (some upstream APIs return "choices": null)
            choices = ms_response.get("choices") or []
            message = choices[0].get("message", {}) if choices else {}
            usage = ms_response.get("usage") or {}

            # Build message dict, preserving tool_calls when present
            openai_message: Dict[str, Any] = {
                "role": message.get("role", "assistant"),
            }
            # content may be null when tool_calls are present
            content = message.get("content")
            if content is not None:
                openai_message["content"] = content
            # Preserve tool_calls from upstream response
            if "tool_calls" in message:
                openai_message["tool_calls"] = message["tool_calls"]

            openai_response = {
                "id": ms_response.get("id", ""),
                "object": "chat.completion",
                "created": ms_response.get("created", 0),
                "model": ms_response.get("model", ""),
                "choices": [{
                    "index": 0,
                    "message": openai_message,
                    "finish_reason": choices[0].get("finish_reason", "stop") if choices else "stop"
                }],
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
            }
            return openai_response
        except Exception as e:
            logger.error(f"Failed to convert response: {e}")
            raise ValueError(f"Response conversion failed: {str(e)}")
