"""Tests for HttpClient streaming support (stream=True).

Regression: the streaming branch in api/routes.py must get a response whose
body is NOT pre-read. httpx.AsyncClient.request() always buffers the whole
body, so HttpClient.request(stream=True) must go through
build_request + send(stream=True).
"""
from unittest.mock import AsyncMock, Mock

import pytest

from provider.core.http_client import HttpClient


def _make_account():
    account = Mock()
    account.api_key = "test-key"
    return account


@pytest.mark.asyncio
async def test_stream_true_uses_send_with_stream():
    hc = HttpClient()
    mock_client = Mock()
    built_request = Mock()
    mock_client.build_request = Mock(return_value=built_request)
    mock_client.send = AsyncMock(return_value=Mock(status_code=200))
    hc.client = mock_client

    resp = await hc.request(
        _make_account(), "POST", "https://api.test/v1/chat/completions",
        json={"stream": True}, stream=True,
    )

    # Must NOT use client.request (which buffers the body)
    mock_client.build_request.assert_called_once()
    mock_client.send.assert_awaited_once_with(built_request, stream=True)
    assert resp.status_code == 200

    # Auth header is passed to build_request
    _, kwargs = mock_client.build_request.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_stream_false_uses_plain_request():
    hc = HttpClient()
    mock_client = Mock()
    mock_client.request = AsyncMock(return_value=Mock(status_code=200))
    mock_client.build_request = Mock()
    mock_client.send = AsyncMock()
    hc.client = mock_client

    resp = await hc.request(
        _make_account(), "POST", "https://api.test/v1/chat/completions",
        json={"stream": False},
    )

    mock_client.request.assert_awaited_once()
    mock_client.build_request.assert_not_called()
    mock_client.send.assert_not_awaited()
    assert resp.status_code == 200
