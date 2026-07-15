from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ResponseConverter:
    """Convert ModelScope responses to OpenAI format."""

    def convert_to_openai(self, ms_response: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ModelScope response to OpenAI format."""
        try:
            choices = ms_response.get("choices", [])
            message = choices[0].get("message", {}) if choices else {}
            usage = ms_response.get("usage", {})
            openai_response = {
                "id": ms_response.get("id", ""),
                "object": "chat.completion",
                "created": ms_response.get("created", 0),
                "model": ms_response.get("model", ""),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": message.get("role", "assistant"),
                        "content": message.get("content", "")
                    },
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
