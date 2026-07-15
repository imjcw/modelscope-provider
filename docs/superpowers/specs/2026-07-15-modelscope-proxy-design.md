# ModelScope 代理服务设计文档

**日期**: 2026-07-15
**技术栈**: Python + FastAPI + SQLite
**目标**: 构建一个兼容 OpenAI API 格式的 ModelScope 代理服务，自动管理多账户配额并实现负载均衡

---

## 1. 需求概述

### 1.1 核心功能
- 接收兼容 OpenAI API 格式的请求
- 自动从多个 ModelScope 账户中选择可用账户
- 监控配额使用情况，当配额耗尽时自动切换账户
- 将 ModelScope 响应转换为 OpenAI 兼容格式
- 按轮询策略进行负载均衡，避免单账户故障导致服务不可用
- 支持模型别名解析（自动查询 ModelScope API）
- 自动处理配额重置（每日）

### 1.2 背景场景
用户拥有多个 ModelScope 账户，每个账户有每日免费请求限额。需要构建代理服务：
1. 使用指定模型别名（如 "hy3"）
2. 自动查询 ModelScope API，获取别名对应的实际模型 ID（中国版/海外版可能不同）
3. 将别名请求转发为实际模型 ID
4. 当一个账户配额用尽时，自动切换到下一个账户
5. 直到所有账户配额都耗尽
6. 支持长期运行，自动处理配额重置（每日）

### 1.3 模型别名机制
ModelScope 支持为模型设置别名，不设置别名时别名就是模型 ID 本身：
- 用户请求: `{"model": "hy3", ...}`
- ModelScope 返回别名映射: `"hy3" -> "hy3"`（实际模型 ID）
- 转发请求: `{"model": "hy3", ...}`（使用别名，因为别名等于实际模型 ID）

**场景示例**:
- 中国版账户: `hy3` → 实际模型 ID: `hy3`
- 海外版账户: `hy3` → 实际模型 ID: `hy3 overseas`

代理服务会自动查询每个账户的别名映射，根据请求的别名找到对应账户的实际模型 ID。

---

## 2. 技术选型

### 2.1 后端框架
- **FastAPI**: 高性能异步框架，原生支持 OpenAPI 文档
- **httpx**: 异步 HTTP 客户端，用于转发请求到 ModelScope

### 2.2 数据存储
- **SQLite**: 持久化存储账户配额状态和模型不可用标记
- **Redis**（可选）：未来分布式场景可替换

### 2.3 负载均衡策略
- **轮询 (Round-Robin)**: 按顺序依次使用可用账户，避免单账户压力不均

---

## 3. 系统架构

### 3.1 架构图

```
客户端请求
    ↓
FastAPI 入口 (/v1/chat/completions)
    ↓
模型别名解析（查询 ModelScope API，获取实际模型 ID）
    ↓
OpenAI 兼容响应转换中间件
    ↓
模型可用性检查中间件
    ↓
配额检查中间件
    ↓
账户负载均衡器（轮询策略）
    ↓
ModelScope 客户端 A
    ↓
ModelScope 客户端 B
    ↓
...
    ↓
响应转换（ModelScope → OpenAI）
    ↓
配额更新（SQLite）
    ↓
返回响应
```

### 3.2 核心组件

#### 3.2.1 ModelScopeAccount
账户配置类，存储单个账户的信息：

```python
class ModelScopeAccount:
    account_id: str          # 账户唯一标识
    api_key: str             # ModelScope API Key
    base_url: str            # ModelScope API Base URL
    quota_limit: int         # 每日限额（从响应头读取）
    quota_remaining: int     # 今日剩余额度
    last_reset_date: str     # 配额重置日期 YYYY-MM-DD
    unavailable_models: Set[str]  # 已耗尽配额的模型列表
```

#### 3.2.2 ModelAvailabilityChecker
模型可用性检查器：

```python
class ModelAvailabilityChecker:
    def is_model_available(account: ModelScopeAccount, model_name: str) -> bool
    def mark_model_unavailable(account: ModelScopeAccount, model_name: str) -> None
```

**职责**:
- 检查模型在当前账户是否可用（有配额且不在不可用列表）
- 标记模型为不可用（配额耗尽时调用）

#### 3.2.2.1 ModelAliasResolver
模型别名解析器：

```python
class ModelAliasResolver:
    def resolve_alias(account: ModelScopeAccount, alias: str) -> str
    def cache_alias_mapping(account: ModelScopeAccount, alias: str, actual_model_id: str)
```

**职责**:
- 根据别名查询 ModelScope API，获取实际模型 ID
- 将别名映射结果缓存到数据库（减少 API 调用）
- 处理别名不存在的情况

**实现逻辑**:

1. **查询缓存**: 先从 `model_alias_cache` 表查找是否有缓存记录
2. **缓存命中**: 如果缓存存在且未过期，直接返回实际模型 ID
3. **缓存未命中**: 调用 ModelScope API 查询别名映射
   - 请求: `GET /models/{alias}`
   - 响应: `{"data": [{"alias": "hy3", "id": "hy3 overseas"}]}`
4. **存储缓存**: 将映射结果写入 `model_alias_cache` 表
5. **返回实际模型 ID**

**缓存策略**:
- 缓存有效期: 24 小时（与配额重置周期一致）
- 缓存键: `(account_id, alias_name, cache_date)`
- 自动清理: 每次请求时检查缓存日期，过期的缓存自动失效

#### 3.2.3 QuotaRepository
配额状态存储接口：

```python
class QuotaRepository:
    def get_or_create_daily_quota(account_id: str, date: str) -> QuotaInfo
    def update_quota(account_id: str, date: str, remaining: int, limit: int)
    def mark_model_unavailable(account_id: str, model_name: str)
    def reset_unavailable_models(account_id: str, date: str)
```

**数据表结构**:

```sql
-- 账户配额表
CREATE TABLE account_quotas (
    account_id TEXT PRIMARY KEY,
    quota_date TEXT NOT NULL,
    quota_remaining INTEGER,
    quota_limit INTEGER,
    unavailable_models TEXT,  -- JSON 格式存储 Set[model_name]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, quota_date)
);

CREATE INDEX idx_quota_date ON account_quotas(quota_date);

-- 模型别名缓存表（可选，用于缓存别名映射，减少 API 调用）
CREATE TABLE model_alias_cache (
    account_id TEXT NOT NULL,
    alias_name TEXT NOT NULL,
    actual_model_id TEXT NOT NULL,
    cache_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id, alias_name, cache_date),
    FOREIGN KEY (account_id) REFERENCES account_quotas(account_id) ON DELETE CASCADE
);

CREATE INDEX idx_alias_cache ON model_alias_cache(alias_name, cache_date);
```

#### 3.2.4 LoadBalancer
账户负载均衡器：

```python
class LoadBalancer:
    def select_account(accounts: List[ModelScopeAccount], model_name: str) -> ModelScopeAccount
```

**职责**:
- 轮询选择可用账户
- 过滤掉标记为不可用的账户
- 如果所有账户都不可用，抛出异常

#### 3.2.5 ResponseConverter
响应格式转换器：

```python
class ResponseConverter:
    def convert_to_openai(ms_response: dict) -> dict
```

**职责**:
- 将 ModelScope 响应转换为 OpenAI 格式
- 处理流式响应（SSE 格式转换）
- 提取并转换 usage 字段（如果存在）

#### 3.2.6 ConfigManager
配置管理器：

```python
class ConfigManager:
    def load_accounts_from_env() -> List[ModelScopeAccount]
```

**环境变量配置示例**:

```bash
# 多个账户配置
MODELSCOPE_ACCOUNTS_JSON='[
  {
    "account_id": "account1",
    "api_key": "your-api-key-1",
    "base_url": "https://api-inference.modelscope.cn/v1/chat/completions"
  },
  {
    "account_id": "account2",
    "api_key": "your-api-key-2",
    "base_url": "https://api-inference.modelscope.cn/v1/chat/completions"
  },
  {
    "account_id": "account3",
    "api_key": "your-api-key-3",
    "base_url": "https://api-inference.modelscope.cn/v1/chat/completions"
  }
]'
```

---

## 4. 数据流

### 4.1 请求处理流程

1. **接收请求**: FastAPI 接收 OpenAI 格式的 chat completion 请求
2. **提取别名**: 从请求中提取模型别名（如 `model = "hy3"`）
3. **别名解析**: 使用 `ModelAliasResolver` 查询该别名对应的实际模型 ID
   - 先查询缓存：检查 `model_alias_cache` 表
   - 缓存未命中：调用 ModelScope API 查询别名映射
   - 存储缓存：将映射结果写入数据库
4. **请求准备**: 准备转发到 ModelScope 的请求体（使用实际模型 ID）
5. **可用性检查**: 检查模型在当前账户是否可用
6. **配额检查**: 检查今日剩余配额
7. **负载均衡**: 选择可用账户（轮询策略）
8. **请求转发**: 使用 httpx 发送异步请求到选定的 ModelScope 账户
9. **响应转换**: 将 ModelScope 响应转换为 OpenAI 格式
10. **配额更新**: 更新剩余配额到 SQLite
11. **返回响应**: 返回转换后的响应给客户端

### 4.1.1 模型别名解析示例

**用户请求**:
```json
{
  "model": "hy3",
  "messages": [{"role": "user", "content": "你好"}]
}
```

**处理流程**:
1. FastAPI 接收请求，提取 `model = "hy3"`（别名）
2. 选择账户 `account1`（通过轮询）
3. 调用 `ModelAliasResolver.resolve_alias(account1, "hy3")`
   - 查询缓存：`model_alias_cache` 表中无记录
   - 调用 API: `GET https://api-inference.modelscope.cn/v1/models/hy3`
   - 响应: `{"data": [{"alias": "hy3", "id": "hy3 overseas"}]}`
   - 缓存: 存储记录 `(account1, "hy3", "hy3 overseas", cache_date)`
4. 转发请求到 `account1`，使用 `"hy3 overseas"` 模型
5. ModelScope 返回响应
6. 将响应转换回 OpenAI 格式，返回给客户端

**结果**:
- 客户端看到请求的模型是 `"hy3"`（别名）
- 实际调用的是 `"hy3 overseas"`（实际模型 ID）
- 响应格式完全兼容 OpenAI

### 4.2 配额耗尽处理流程

1. **检测配额耗尽**: 读取响应头 `modelscope-ratelimit-model-requests-remaining == 0`
2. **标记不可用**: 将模型添加到该账户的 `unavailable_models` 集合
3. **存入数据库**: 持久化到 SQLite
4. **切换账户**: 下次请求时跳过该账户，尝试下一个可用账户
5. **返回错误**: 向客户端返回 429 错误，提示可用账户列表

### 4.3 配额重置流程

1. **日期检查**: 每次请求时检查 `quota_date` 是否为今日
2. **加载今日配额**: 从 SQLite 加载今日配额状态
3. **重置不可用列表**: 如果是新的一天，清空 `unavailable_models`
4. **更新配额**: 将 `quota_remaining` 更新为从响应头读取的新值
5. **持久化**: 保存到 SQLite

---

## 5. API 设计

### 5.1 主接口：兼容 OpenAI Chat Completions

**端点**: `POST /v1/chat/completions`

**请求体** (OpenAI 格式):

```json
{
  "model": "hy3",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 100
}
```

**响应** (OpenAI 格式):

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1677858242,
  "model": "hy3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么我可以帮你的吗？"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

**错误响应** (429 Too Many Requests):

```json
{
  "error": {
    "message": "All ModelScope accounts have exceeded daily quota for model hy3",
    "type": "rate_limit_exceeded",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}
```

**错误响应** (500 Internal Server Error):

```json
{
  "error": {
    "message": "No available ModelScope accounts for model hy3",
    "type": "service_unavailable",
    "param": null,
    "code": "service_unavailable"
  }
}
```

### 5.2 健康检查端点

**端点**: `GET /health`

**响应**:

```json
{
  "status": "healthy",
  "accounts": 3,
  "available_accounts": 2,
  "unavailable_models": {
    "account1": ["hy3"],
    "account2": []
  }
}
```

### 5.3 管理端点（可选）

**端点**: `GET /admin/quota`

**响应**:

```json
{
  "quota_status": [
    {
      "account_id": "account1",
      "quota_limit": 2000,
      "quota_remaining": 180,
      "unavailable_models": ["hy3"],
      "last_reset_date": "2026-07-15"
    },
    {
      "account_id": "account2",
      "quota_limit": 2000,
      "quota_remaining": 500,
      "unavailable_models": [],
      "last_reset_date": "2026-07-15"
    }
  ]
}
```

---

## 6. 配额重置策略

### 6.1 实现方式
- **无需定时任务**: 每次请求时检查日期
- **懒加载**: 如果 `quota_date` 不是今日，则从 API 重新加载配额并持久化

### 6.2 重置时机
1. 首次请求
2. 检测到日期变更（从 SQLite 读取配额时发现日期不同）
3. 手动触发重置（可选：添加 `/admin/reset` 端点）

### 6.3 重置流程
```
请求到来
  ↓
从 SQLite 加载配额状态
  ↓
检查 quota_date 是否为今日
  ↓
如果不是今日:
  - 清空 unavailable_models
  - 更新 quota_date 为今日
  - 重新调用 ModelScope API 获取最新配额
  - 持久化到 SQLite
  ↓
继续处理请求
```

---

## 7. 错误处理

### 7.1 错误类型

| 错误类型 | HTTP 状态码 | 处理策略 |
|---------|------------|---------|
| 配额耗尽 (429) | 429 | 标记模型不可用，切换账户，返回错误 |
| 所有账户不可用 | 500 | 返回服务不可用错误 |
| 网络错误 | 502/503 | 切换到下一个账户，重试 |
| API 错误 | 400/422 | 转发给客户端，不切换账户 |
| 认证失败 | 401 | 转发给客户端，不切换账户 |

### 7.2 错误处理流程

1. **配额耗尽**:
   - 读取响应头 `modelscope-ratelimit-model-requests-remaining == 0`
   - 标记模型为不可用
   - 返回 429 错误，包含可用账户列表

2. **网络错误**:
   - 记录错误日志
   - 从可用账户列表中移除当前账户
   - 尝试下一个账户
   - 如果所有账户都失败，返回 503 错误

3. **API 错误**:
   - 直接转发 ModelScope 的错误响应给客户端
   - 不切换账户（除非是网络相关错误）

---

## 8. 安全考虑

### 8.1 API Key 安全
- 从环境变量加载，不写入代码
- 支持密钥加密存储（可选）

### 8.2 请求验证
- 验证请求体格式
- 限制请求大小（防止过大 payload）

### 8.3 CORS 配置
- 仅允许指定域名跨域请求
- 可选：支持所有域名（开发环境）

### 8.4 日志记录
- 记录请求、响应、错误信息
- 不记录敏感数据（如完整 API Key）

---

## 9. 性能优化

### 9.1 缓存策略
- **内存缓存**: 使用 `lru_cache` 或内存字典缓存可用性状态（单进程场景）
- **数据库索引**: 为 `account_id` 和 `quota_date` 添加索引

### 9.2 并发处理
- 使用 FastAPI 的异步特性
- httpx 使用连接池
- 限制最大并发请求数（防止压垮 ModelScope API）

### 9.3 连接池配置
```python
http_client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
)
```

---

## 10. 部署方案

### 10.1 开发环境
```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 10.2 生产环境 (Gunicorn + Uvicorn)
```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### 10.3 Docker 部署
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

### 10.4 环境变量
```bash
export MODELSCOPE_ACCOUNTS_JSON='[
  {"account_id": "account1", "api_key": "xxx", "base_url": "https://api-inference.modelscope.cn/v1/chat/completions"},
  {"account_id": "account2", "api_key": "yyy", "base_url": "https://api-inference.modelscope.cn/v1/chat/completions"}
]'
export DATABASE_URL="sqlite:///modelscope_proxy.db"
```

---

## 11. 测试策略

### 11.1 单元测试
- 测试每个组件的独立功能
- Mock 外部依赖（ModelScope API、数据库）

### 11.2 集成测试
- 测试完整请求流程
- 测试配额切换逻辑
- 测试错误处理

### 11.3 测试用例
1. **正常请求**: 成功调用模型并返回结果
2. **配额耗尽**: 验证账户切换和错误返回
3. **所有账户耗尽**: 验证最终错误
4. **配额重置**: 验证新日期自动重置
5. **网络错误**: 验证重试和账户切换
6. **并发请求**: 验证多请求场景

---

## 12. 监控与可观测性

### 12.1 指标
- 请求成功率
- 平均响应时间
- 各账户配额使用情况
- 各账户负载均衡次数

### 12.2 日志
- 记录每次请求的账户选择
- 记录配额更新事件
- 记录错误和警告
- 记录性能指标

### 12.3 健康检查
- `/health` 端点返回服务状态
- 检查数据库连接
- 检查配置加载

---

## 12.4 模型别名解析详解

### 12.4.1 为什么要使用别名

ModelScope 支持模型别名功能，允许为模型设置别名，不设置别名时别名就是模型 ID 本身：

**场景示例**:
- **中国版账户**: 模型 ID `hy3`，别名 `"hy3"`（与 ID 相同）
- **海外版账户**: 模型 ID `hy3 overseas`，别名 `"hy3"`

通过别名解析机制，用户可以：
1. 使用统一的别名（如 `"hy3"`）请求模型
2. 代理服务自动查询 ModelScope API，获取每个账户的别名映射
3. 根据账户实际使用的模型 ID 转发请求
4. 对外暴露统一的接口，隐藏底层差异

### 12.4.2 别名解析流程

```
用户请求 {"model": "hy3", ...}
    ↓
选择账户（轮询）
    ↓
查询别名缓存
    ↓
缓存命中？
├─ 是 → 返回实际模型 ID → 转发请求
└─ 否 → 调用 ModelScope API
         ↓
    GET /v1/models/hy3
         ↓
    响应: {"data": [{"alias": "hy3", "id": "hy3 overseas"}]}
         ↓
    存储缓存 → 返回实际模型 ID → 转发请求
```

### 12.4.3 缓存策略

**缓存表**: `model_alias_cache`

**字段说明**:
- `account_id`: 账户 ID
- `alias_name`: 别名（用户请求的模型别名）
- `actual_model_id`: 实际模型 ID（ModelScope API 返回的 ID）
- `cache_date`: 缓存日期（YYYY-MM-DD）

**缓存有效期**: 24 小时（与配额重置周期一致）

**缓存查询逻辑**:
```python
def resolve_alias(account, alias):
    # 1. 查询缓存
    cache_entry = db.query(
        "SELECT actual_model_id FROM model_alias_cache "
        "WHERE account_id = ? AND alias_name = ? AND cache_date = ?",
        (account.account_id, alias, today_date)
    )

    # 2. 缓存命中
    if cache_entry:
        return cache_entry.actual_model_id

    # 3. 缓存未命中，调用 API
    api_response = api_client.get(f"{account.base_url}/models/{alias}")
    actual_model_id = api_response.data[0].id

    # 4. 存储缓存
    db.execute(
        "INSERT INTO model_alias_cache VALUES (?, ?, ?, ?)",
        (account.account_id, alias, actual_model_id, today_date)
    )

    return actual_model_id
```

### 12.4.4 运行时示例

**场景 1: 混合区域账户**
- `account1`: 中国版账户，模型 ID `hy3`，别名 `"hy3"`
- `account2`: 海外版账户，模型 ID `hy3 overseas`，别名 `"hy3"`

**请求流程**:
1. 接收请求 `{"model": "hy3", "messages": [...]}`（使用别名）
2. 选择账户 `account1`（轮询选中）
3. 查询缓存：无记录
4. 调用 API: `GET https://api-inference.modelscope.cn/v1/models/hy3`
5. 响应: `{"data": [{"alias": "hy3", "id": "hy3"}]}`
6. 缓存: `(account1, "hy3", "hy3", cache_date)`
7. 转发请求: `{"model": "hy3", ...}`（使用实际模型 ID `hy3`）

**场景 2: 所有账户都是海外版**
- `account1`: 海外版账户，模型 ID `hy3 overseas`，别名 `"hy3"`
- `account2`: 海外版账户，模型 ID `hy3 overseas`，别名 `"hy3"`

**请求流程**:
1. 接收请求 `{"model": "hy3", ...}`
2. 选择账户 `account1`（轮询选中）
3. 查询缓存：无记录
4. 调用 API: `GET https://api-inference.modelscope.cn/v1/models/hy3`
5. 响应: `{"data": [{"alias": "hy3", "id": "hy3 overseas"}]}`
6. 缓存: `(account1, "hy3", "hy3 overseas", cache_date)`
7. 转发请求: `{"model": "hy3 overseas", ...}`（使用实际模型 ID）

**场景 3: 别名与 ID 相同**
- 模型 ID: `qwen2.5-7b`
- 别名: `"qwen2.5-7b"`（与 ID 相同）

**请求流程**:
1. 接收请求 `{"model": "qwen2.5-7b", ...}`
2. 选择账户 `account1`
3. 查询缓存: `qwen2.5-7b` → `qwen2.5-7b`（与请求模型 ID 相同）
4. 转发请求: `{"model": "qwen2.5-7b", ...}`（无需转换）

### 12.4.5 缓存更新策略

**自动更新**:
- 每次请求前检查缓存日期
- 如果缓存日期不是今日，自动清除旧缓存
- 重新查询 ModelScope API

**缓存过期时间**:
- 与配额重置时间一致（每天 0 点）
- 确保缓存总是最新的

### 12.4.6 API 调用示例

**ModelScope 模型列表 API**:
```
GET https://api-inference.modelscope.cn/v1/models/hy3
Authorization: Bearer your-api-key
```

**成功响应**:
```json
{
  "data": [
    {
      "id": "hy3 overseas",
      "object": "model",
      "created": 1234567890,
      "owned_by": "modelscope"
    }
  ],
  "object": "list"
}
```

**响应说明**:
- `id`: 实际模型 ID（用于转发请求）
- `alias`: 别名（用户请求的别名，用于验证）

### 12.4.7 管理接口

**获取缓存状态**:
```
GET /admin/alias-cache
```

**响应示例**:
```json
{
  "cache_hits": 15,
  "cache_misses": 3,
  "total_requests": 18,
  "hit_rate": "83.33%",
  "cached_accounts": [
    {
      "account_id": "account1",
      "cached_aliases": 5,
      "last_updated": "2026-07-15"
    }
  ]
}
```

**清除缓存**:
```
POST /admin/alias-cache/clear
```

**手动触发别名查询**:
```
POST /admin/alias-cache/refresh
{
  "account_id": "account1",
  "alias": "hy3"
}
```

---

## 13. 扩展性

### 13.1 未来优化
- **Redis 缓存**: 支持分布式部署
- **更多负载均衡策略**: 随机、最少连接、加权轮询
- **多模型支持**: 动态添加新模型
- **配额共享**: 支持跨账户共享配额
- **智能映射策略**: 根据请求内容自动选择最佳区域模型
- **自定义映射规则**: 支持正则表达式、函数式映射规则

### 13.2 配置灵活性
- 支持从文件、环境变量、数据库加载配置
- 支持热重载配置（无需重启服务）

---

## 14. 依赖项

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
aiofiles>=23.2.1  # 用于异步读取配置文件
```

---

## 15. 参考文档

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [ModelScope API 文档](https://help.aliyun.com/zh/modelscope/developer-reference/api-details)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference/chat)
- [Python httpx 文档](https://www.python-httpx.org/)

---

**设计文档版本**: 1.1
**最后更新**: 2026-07-15

**版本变更记录**:
- v1.1 (2026-07-15): 新增模型 ID 映射机制，支持海外版和中国版模型 ID 转换
- v1.0 (2026-07-15): 初始版本
