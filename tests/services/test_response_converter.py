import pytest
from provider.services.response_converter import ResponseConverter


def test_convert_to_openai_success():
    """Test successful response conversion."""
    converter = ResponseConverter()

    ms_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677858242,
        "model": "hy3",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello!"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12
        }
    }

    openai_response = converter.convert_to_openai(ms_response)

    assert openai_response["id"] == "chatcmpl-123"
    assert openai_response["object"] == "chat.completion"
    assert openai_response["choices"][0]["message"]["content"] == "Hello!"
    assert openai_response["usage"]["total_tokens"] == 12


def test_convert_to_openai_missing_fields():
    """Test response conversion with missing fields."""
    converter = ResponseConverter()

    ms_response = {
        "choices": [{
            "message": {
                "content": "Test"
            }
        }]
    }

    openai_response = converter.convert_to_openai(ms_response)

    assert openai_response["id"] == ""
    assert openai_response["choices"][0]["message"]["content"] == "Test"
    assert openai_response["usage"]["total_tokens"] == 0


def test_convert_to_openai_empty_choices():
    """Test response conversion with empty choices."""
    converter = ResponseConverter()

    ms_response = {
        "id": "test",
        "choices": []
    }

    openai_response = converter.convert_to_openai(ms_response)

    assert openai_response["choices"][0]["message"]["content"] == ""
    assert openai_response["choices"][0]["finish_reason"] == "stop"
