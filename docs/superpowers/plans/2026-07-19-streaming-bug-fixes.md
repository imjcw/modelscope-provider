# Streaming 错误处理与日志 Bug 修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 4 个 streaming 模式下的 Bug：错误响应格式、status_code 硬编码、日志写入崩溃、变量命名误导。

**Architecture:** 全部改动集中在 `api/routes.py` 的两个函数中（`stream_response` 和 `stream_response_with_logging`），不涉及架构变动，不改数据库 schema，不改对外接口。

**Tech Stack:** Python / FastAPI / httpx / pytest

## Global Constraints

- Python 3.12+
- 所有测试用 `pytest` 运行，必须带 `-v` 标志
- 不添加新依赖
- 所有测试在 `D:/workspace/ai/modelscope-provider` 根目录执行
- git commit message 用 `fix:` 前缀

---

## 文件清单

| 操作 | 文件 | 涉及行数 |
|---|---|---|
| 修改 | `api/routes.py` | `stream_response` (~179-181), `stream_response_with_logging` (~233-323) |
| 新增 | `tests/api/test_streaming_error.py` | 新文件，测试 streaming 错误路径 |

---

### Task 1: 修复 streaming 错误响应格式（Bug 4）

**问题：** `stream_response` 在非 200 时 yield `{"error": "API error: 403"}`（字符串），ZCode 客户端期望 `{"error": {"message": "...", "type": "server_error", "code": "403"}}`（对象），导致 schema 校验失败。

**文件：**
- 修改：`api/routes.py:179-181`

**接口：**
- 不变。`stream_response` 仍然 `yield str`。

- [ ] **Step 1: 修改 `stream_response` 中的错误响应格式**

将 `api/routes.py` 中 `stream_response` 函数的错误处理部分：

```python
    if response.status_code != 200:
        yield f"data: {json.dumps({'error': f'API error: {response.status_code}'})}\n\n"
        return
```

改为：

```python
    if response.status_code != 200:
        error_body = {
            "error": {
                "message": f"API error: {response.status_code}",
                "type": "server_error",
                "code": str(response.status_code),
            }
        }
        yield f"data: {json.dumps(error_body)}\n\n"
        return
```

- [ ] **Step 2: 运行现有测试确保不破坏**

```bash
cd D:/workspace/ai/modelscope-provider && python -m pytest tests/api/test_routes.py -v
```

预期：全部 PASS（不涉及 streaming 路径的测试应保持不变）。

- [ ] **Step 3: Commit**

```bash
git add api/routes.py
git commit -m "fix(streaming): OpenAI-compatible error response format"
```

---

### Task 2: 传递真实 status_code 到日志（Bug 2）

**问题：** `stream_response_with_logging` 在 `log_request` 中硬编码 `status_code=200`，403 等失败请求也被记录为成功，导致统计和 token 计数失真。

**方案：** 让 `stream_response` 通过一个特殊标记 chunk 把状态码传给 `stream_response_with_logging`。沿用已有的 `__hdrs__` 模式——非 200 时 yield 一个 `{"__status_code__": 403}` 的 chunk。

**文件：**
- 修改：`api/routes.py:179-181`（Task 1 已改过这行，继续改）
- 修改：`api/routes.py:240-257`（`stream_response_with_logging` 的循环体）

**接口：**
- `stream_response` 仍然 yield `str`，但在非 200 时额外 yield 一个 `{"__status_code__": <int>}` 标记 chunk。

- [ ] **Step 1: 修改 `stream_response`，在错误时 yield status_code 标记**

在 Task 1 已修改的 `stream_response` 函数中，错误响应 yield 之后、return 之前，注入 status_code 标记：

```python
    if response.status_code != 200:
        error_body = {
            "error": {
                "message": f"API error: {response.status_code}",
                "type": "server_error",
                "code": str(response.status_code),
            }
        }
        yield f"data: {json.dumps(error_body)}\n\n"
        # 传递真实状态码供日志使用
        yield f"data: {json.dumps({'__status_code__': response.status_code})}\n\n"
        return
```

- [ ] **Step 2: 修改 `stream_response_with_logging` 解析 `__status_code__`**

在 `stream_response_with_logging` 中，将初始化部分：

```python
    total_tokens = 0
    input_tokens = 0
    response_headers = {}
    raw_chunks = []
    first_response = None
    request_start = datetime.now(timezone.utc).isoformat()
```

改为（同时修复 Bug 5 的变量名）：

```python
    output_tokens = 0
    input_tokens = 0
    response_headers = {}
    raw_chunks = []
    first_response = None
    request_start = datetime.now(timezone.utc).isoformat()
    stream_status_code = 200  # 默认 200，由 stream_response 的 __status_code__ 标记覆盖
```

将 `stream_response_with_logging` 中**现有的 `__hdrs__` 解析块 + yield + token 提取逻辑**整体替换为以下结构。

**关键点：** `__status_code__` 和 `__hdrs__` 的解析必须在 `yield` 和 `raw_chunks.append` **之前**执行，否则会泄露给客户端和污染日志。

找到这段代码（约 line 243-271）：

```python
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
```

替换为：

```python
        data_str = chunk_data.replace("data: ", "").strip()
        is_special_chunk = False

        # Strip out injected marker chunks (do NOT yield or log them)
        if data_str:
            try:
                dec = json.JSONDecoder()
                obj, _ = dec.raw_decode(data_str)
                if "__status_code__" in obj:
                    stream_status_code = obj["__status_code__"]
                    is_special_chunk = True
                elif "__hdrs__" in obj:
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

        # Try to extract token count from usage in each chunk
        try:
            if data_str:
                decoder = json.JSONDecoder()
                json_data, _ = decoder.raw_decode(data_str)
                usage = json_data.get("usage", {})
                # Only take the latest usage (last chunk has final counts)
                input_tokens = usage.get("prompt_tokens", 0) or input_tokens
                output_tokens = usage.get("completion_tokens", 0) or output_tokens
        except Exception:
            pass
```

- [ ] **Step 3: 修改 token 提取部分，使用新变量名 `output_tokens`**

在 token 提取循环中（约 line 261-271），将：

```python
            json_data, _ = decoder.raw_decode(data_str)
            usage = json_data.get("usage", {})
            # Only take the latest usage (last chunk has final counts)
            input_tokens = usage.get("prompt_tokens", 0) or input_tokens
            total_tokens = usage.get("completion_tokens", 0) or total_tokens
```

改为：

```python
            json_data, _ = decoder.raw_decode(data_str)
            usage = json_data.get("usage", {})
            # Only take the latest usage (last chunk has final counts)
            input_tokens = usage.get("prompt_tokens", 0) or input_tokens
            output_tokens = usage.get("completion_tokens", 0) or output_tokens
```

- [ ] **Step 4: 修改日志写入，使用 `stream_status_code` 并修复 `tool_calls_found` 崩溃（Bug 3）**

在 `stream_response_with_logging` 的日志部分（约 line 273-307），将：

```python
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
```

改为（移除 `tool_calls_found` 死代码，使用真实 status_code 和新变量名）：

```python
    # Log after streaming completes
    end_time = datetime.now(timezone.utc).isoformat()
    logger.info(f"Streaming completed for {account.account_id}: status={stream_status_code} input={input_tokens} output={output_tokens} chunks={len(raw_chunks)} admin_svc={'yes' if admin_service else 'no'}")
    if admin_service:
        try:
            admin_service.log_request(
                model=model_name,
                actual_model_id=actual_model_id,
                account_id=account.account_id,
                account_name=account.name,
                status_code=stream_status_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
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
            logger.error(f"Failed to log streaming request: {e}")
```

注意：`logger.warning` → `logger.error`，因为日志写入失败是需要关注的错误。

- [ ] **Step 5: 修改配额更新部分，使用新变量名 `output_tokens`**

在配额更新部分（约 line 309-322），将：

```python
    # Update quota from streaming usage data
    if quota_updater and hasattr(account, 'api_key'):
        try:
            if input_tokens > 0 or total_tokens > 0:
                quota_updater.update_quota_from_usage(
                    account, input_tokens, total_tokens, model_name
                )
```

改为：

```python
    # Update quota from streaming usage data
    if quota_updater and hasattr(account, 'api_key'):
        try:
            if input_tokens > 0 or output_tokens > 0:
                quota_updater.update_quota_from_usage(
                    account, input_tokens, output_tokens, model_name
                )
```

- [ ] **Step 6: 运行现有测试确保不破坏**

```bash
cd D:/workspace/ai/modelscope-provider && python -m pytest tests/ -v
```

预期：全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add api/routes.py
git commit -m "fix(streaming): propagate real status_code and remove dead tool_calls_found code"
```

---

### Task 3: 编写 streaming 错误路径测试

**问题：** 目前没有测试覆盖 streaming 模式下上游返回 403 的场景。

**文件：**
- 新增：`tests/api/test_streaming_error.py`

**接口：**
- 复用 `test_routes.py` 中的 `client` fixture（通过 `conftest.py` 的 provider namespace）。

- [ ] **Step 1: 创建测试文件 `tests/api/test_streaming_error.py`**

```python
import json
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    """Lifespan-aware client so services / admin service are initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_streaming_error_response_format(client):
    """When upstream returns non-200, the streaming error chunk should be
    OpenAI-compatible with error as an object (not a string)."""

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))

    app = client.app
    http_client = app.state.services["http_client"]

    with patch.object(http_client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "ap-hy3",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    # Collect SSE chunks from the response
    chunks = []
    for line in resp.iter_lines():
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str and data_str != "[DONE]":
                chunks.append(json.loads(data_str))

    # The error chunk should have error as an object, not a string
    error_chunks = [c for c in chunks if "error" in c]
    assert len(error_chunks) >= 1, "Expected at least one error chunk"
    error_chunk = error_chunks[0]
    error_obj = error_chunk["error"]
    assert isinstance(error_obj, dict), f"Expected error to be a dict, got {type(error_obj)}"
    assert "message" in error_obj
    assert "code" in error_obj
    assert error_obj["code"] == "403"
    assert error_obj["type"] == "server_error"


def test_streaming_error_logs_real_status_code(client):
    """When upstream returns 403 in streaming mode, the log entry should
    record status_code=403 (not 200) and input/output tokens as 0."""

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))

    app = client.app
    http_client = app.state.services["http_client"]
    log_repo = app.state.admin_service.log_repo
    logs_before, _ = log_repo.find_all()
    before_ids = {r["id"] for r in logs_before}

    with patch.object(http_client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "ap-hy3",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        # Consume response to trigger logging
        for _ in resp.iter_lines():
            pass

    logs_after, _ = log_repo.find_all()
    assert len(logs_after) > len(logs_before), "Expected a new log entry"

    # Find the new streaming log
    new_streaming = [
        r for r in logs_after
        if r["id"] not in before_ids and r.get("is_stream")
    ]
    assert len(new_streaming) >= 1, "Expected a streaming log entry"
    latest = new_streaming[0]

    assert latest["status_code"] == 403, f"Expected status_code=403, got {latest['status_code']}"
    assert latest["input_tokens"] == 0, f"Expected 0 input tokens on error, got {latest['input_tokens']}"
    assert latest["output_tokens"] == 0, f"Expected 0 output tokens on error, got {latest['output_tokens']}"
```

- [ ] **Step 2: 运行新测试**

```bash
cd D:/workspace/ai/modelscope-provider && python -m pytest tests/api/test_streaming_error.py -v
```

预期：2 个测试全部 PASS。

- [ ] **Step 3: 运行全部测试确保无回归**

```bash
cd D:/workspace/ai/modelscope-provider && python -m pytest tests/ -v
```

预期：全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add tests/api/test_streaming_error.py
git commit -m "test(streaming): add tests for error response format and status_code logging"
```

---

## 最终验证清单

- [ ] `python -m pytest tests/ -v` 全部通过
- [ ] 日志文件中不再出现 `Failed to log streaming request: name 'tool_calls_found' is not defined`
- [ ] 上游 403 时，日志记录的 status_code 为 403（非 200）
- [ ] streaming 错误 chunk 的 `error` 字段是对象（含 message/code/type）
- [ ] `output_tokens` 变量名替换完成，无残留 `total_tokens` 引用
