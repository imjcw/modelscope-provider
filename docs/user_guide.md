# AI Provider 使用手册

> 兼容 OpenAI API 格式的 AI Provider 网关，支持多供应商账户负载均衡、动态模型别名解析和管理后台。
>
> 版本：0.2.0 | 数据库：SQLite

---

## 目录

1. [快速开始](#1-快速开始)
2. [代理 API 使用](#2-代理-api-使用)
3. [Web 管理后台](#3-web-管理后台)
4. [管理 API 参考](#4-管理-api-参考)
5. [配置说明](#5-配置说明)
6. [常见问题](#6-常见问题)
7. [数据库表结构](#7-数据库表结构)

---

## 1. 快速开始

### 1.1 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 前端依赖（首次使用管理后台时需要）
cd web && npm install && npm run build && cd ..
```

### 1.2 配置环境变量

复制示例配置文件并编辑：

```bash
cp .env.example .env
```

`.env` 主要内容：

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 否 | 数据库路径，默认 `sqlite:///modelscope_proxy.db` |
| `LOG_LEVEL` | 否 | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR`，默认 `INFO` |
| `MODELSCOPE_ACCOUNTS_JSON` | 否 | 仅在数据库为空时用于初始化供应商，格式见下文 |

`MODELSCOPE_ACCOUNTS_JSON` 示例（首次部署可选，也可直接在管理后台添加）：

```bash
MODELSCOPE_ACCOUNTS_JSON='[
  {
    "account_id": "account1",
    "name": "供应商A",
    "api_key": "ms-xxxxxxxxxxxxx",
    "base_url": "https://api-inference.modelscope.cn/v1"
  }
]'
```

> ⚠️ `base_url` 填到 `/v1` 即可，**不要**带 `/chat/completions`，代码会自行拼接。

### 1.3 启动服务

```bash
# 推荐：使用 start.sh
bash start.sh

# 或手动启动
python3 -m uvicorn provider.main:app --host 0.0.0.0 --port 37000
```

启动后服务监听 `0.0.0.0:37000`，浏览器打开 `http://127.0.0.1:37000/#/` 进入管理后台。

### 1.4 验证运行

```bash
# 健康检查
curl http://127.0.0.1:37000/api/health
# 返回: {"status":"healthy"}
```

---

## 2. 代理 API 使用

代理服务完全兼容 OpenAI API 格式，可直接替换 OpenAI SDK 的 base URL 使用。

### 2.1 聊天完成

**端点**：`POST /api/v1/chat/completions`

**请求体**：

```json
{
  "model": "hy3",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好，请介绍一下你自己"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 0.9,
  "stream": false
}
```

**参数说明**：

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `model` | 是 | string | 模型别名，如 `hy3`、`qwen2.5` |
| `messages` | 是 | array | 对话消息列表 |
| `stream` | 否 | boolean | 是否流式响应，默认 false |
| `temperature` | 否 | number | 采样温度 |
| `max_tokens` | 否 | integer | 最大输出 token 数 |
| `top_p` | 否 | number | 核采样参数 |
| `stop` | 否 | string / array | 停止词 |
| `n` | 否 | integer | 生成条数，默认 1 |

**使用示例（curl）**：

```bash
curl -X POST http://127.0.0.1:37000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hy3",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**使用示例（OpenAI Python SDK）**：

```python
from openai import OpenAI

client = OpenAI(
    api_key="任意值",              # 代理不需要真实 OpenAI key
    base_url="http://127.0.0.1:37000/api/v1",
)

response = client.chat.completions.create(
    model="hy3",
    messages=[{"role": "user", "content": "你好"}],
    temperature=0.7,
)

print(response.choices[0].message.content)
```

**使用示例（流式）**：

```python
for chunk in client.chat.completions.create(
    model="hy3",
    messages=[{"role": "user", "content": "写一首诗"}],
    stream=True,
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### 2.2 模型列表

**端点**：`GET /api/v1/models`

返回当前代理支持的所有模型别名（即管理后台中配置的 `model_mappings` 映射项），格式兼容 OpenAI `/v1/models`。

**使用示例（curl）**：

```bash
curl http://127.0.0.1:37000/api/v1/models
```

**响应示例**：

```json
{
  "object": "list",
  "data": [
    {
      "id": "hy3",
      "object": "model",
      "created": 1753670400,
      "owned_by": "provider"
    },
    {
      "id": "qwen2.5",
      "object": "model",
      "created": 1753670400,
      "owned_by": "provider"
    }
  ]
}
```

> **说明**：返回的 `id` 即为可在 `POST /api/v1/chat/completions` 中作为 `model` 字段使用的别名。该接口同样支持客户端 API Key 鉴权（`Authorization: Bearer <CLIENT_API_KEY>` 或 `X-API-Key`），未携带 Key 时按向后兼容逻辑放行。

### 2.3 请求流程说明

```
客户端请求 → 负载均衡选择供应商 → 别名解析 → 转发到 ModelScope → 响应转 OpenAI 格式 → 更新配额
```

1. **负载均衡**：从活跃供应商中按策略（轮询/最少连接/随机）选择一个；
2. **别名解析**：将用户传入的模型名（如 `hy3`）解析为 ModelScope 真实模型 ID；
3. **转发请求**：用选定供应商的 API Key 调用 ModelScope；
4. **响应转换**：将 ModelScope 响应转换为 OpenAI 标准格式返回；
5. **配额更新**：从响应 header 读取剩余配额，配额耗尽时自动标记该模型不可用。

### 2.3 错误处理

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | 成功 | 正常返回 |
| 400 | 请求错误 | 参数格式不正确 |
| 429 | 配额耗尽 | 所有供应商的配额都已用尽，返回标准 `rate_limit_exceeded` 错误 |
| 502 | 上游错误 | ModelScope 返回 5xx 错误 |
| 504 | 超时 | 请求超过配置超时时间 |

---

## 3. Web 管理后台

浏览器打开 `http://127.0.0.1:37000/#/` 进入管理后台。侧边栏提供 7 个功能页面。

### 3.1 仪表盘（Dashboard）

**路径**：`/#/` 或 `/#/dashboard`

**内容**：
- **统计卡片**：今日请求数、活跃供应商数、剩余配额、平均延迟
- **配额使用条**：各供应商当日配额使用情况
- **今日请求趋势**：按小时统计的请求量柱状图
- **供应商列表**：快速查看各供应商状态

### 3.2 供应商管理（Accounts）

**路径**：`/#/suppliers`

**功能**：
- **添加供应商**：填写名称、API Key、Base URL、区域（中国 / 海外）
- **编辑供应商**：修改名称、API Key、Base URL、区域、状态
- **删除供应商**：确认后删除
- **切换状态**：激活 / 禁用供应商
- **配额查看**：显示每个供应商的剩余配额 / 配额上限

**操作步骤**：

1. 点击右上角「添加供应商」按钮
2. 在弹出的抽屉中填写信息（API Key 可隐藏/显示切换）
3. 点击「保存」
4. 列表中新增供应商，可立即使用

> 💡 API Key 仅在创建和编辑时可见，列表中自动掩码显示（如 `ms-abc12****xyz78`）。

### 3.3 模型别名映射（Mappings）

**路径**：`/#/mappings`

**功能**：
- **添加映射**：创建模型别名 → 实际模型 ID 的映射
- **编辑映射**：修改别名对应的实际模型 ID
- **删除映射**：移除别名映射
- **批量更新**：一次性批量修改多条映射

**说明**：
- 用户调用代理时传入的是**别名**（如 `hy3`），映射表将其解析为 ModelScope 的真实模型 ID
- 如果映射表中未找到别名，代理会尝试调用 ModelScope API 动态解析；解析失败则直接使用别名作为模型 ID

### 3.4 请求日志（Logs）

**路径**：`/#/logs`

**功能**：
- **筛选**：按时间范围、供应商、状态码、模型名、是否流式筛选
- **分页**：每页 50 条，可翻页
- **详情查看**：点击单条日志查看完整详情，包括：
  - 原始请求 / 原始响应（JSON）
  - Token 用量（输入 / 输出）
  - 延迟、状态码、错误信息

### 3.5 使用统计（Stats）

**路径**：`/#/stats`

**内容**：
- **活跃热力图**：7 天 × 24 小时的请求分布热力图
- **Token 趋势**：按天统计的输入 + 输出 Token 总量柱状图
- **模型用量**：各模型 Token 消耗占比环形图

### 3.6 告警历史（Alerts）

**路径**：`/#/alerts`

**内容**：
- **今日 / 本周告警数**：概览统计
- **告警列表**：按类型分类
  - ⚠️ 配额耗尽（429）— 某供应商某模型配额用尽
  - ❌ 服务器错误（5xx）— 上游返回 5xx
  - ⚠️ 客户端错误（4xx）— 请求失败
- **筛选**：按告警类型过滤

### 3.7 系统配置（Config）

**路径**：`/#/config`

**可配置项**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 负载均衡策略 | `round_robin` | 轮询(round_robin) / 最少连接(least_conn) / 随机(random) |
| 请求超时(ms) | `30000` | 代理请求 ModelScope 的超时时间 |
| 重试次数 | `0` | 请求失败时的重试次数 |
| 配额耗尽自动禁用 | `true` | 配额耗尽时是否自动标记模型不可用 |
| 每日自动重置 | `true` | 是否每日自动重置配额计数 |
| 日志级别 | `INFO` | 日志输出级别 |

---

## 4. 管理 API 参考

所有管理 API 的前缀为 `/api/admin`。

### 4.1 供应商（Suppliers）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/suppliers` | 列出所有供应商 |
| POST | `/api/admin/suppliers` | 新增供应商 |
| PUT | `/api/admin/suppliers/{supplier_id}` | 更新供应商 |
| DELETE | `/api/admin/suppliers/{supplier_id}` | 删除供应商 |
| PATCH | `/api/admin/suppliers/{supplier_id}/status` | 切换供应商状态 |

**新增供应商**：

必填：`name`、`base_url`，以及 `api_keys`（字符串数组，至少 1 个）。
`provider_type` 是**供应商的类型**（用于限流策略 / 展示），如 `modelscope` / `sensetime` / `anthropic` / `per_model`，**它不决定协议**——协议由客户端入口决定（见下）。默认 `modelscope`。

可选：`anthropic_base_url`。当一个供应商**同时提供 OpenAI 兼容接口和 Anthropic 原生接口、且两者地址不同**时，用它单独指定 Anthropic 侧的地址；不填则 Anthropic 协议回落到 `base_url`。

> **协议由客户端入口决定**：网关对上游说哪种协议，取决于客户端访问的是哪个入口，与 `provider_type` 无关：
> - 客户端访问 **`/openai/...`** → 网关对上游说 **OpenAI 协议**，使用 `base_url`（`Authorization: Bearer`）。
> - 客户端访问 **`/anthropic/...`** → 网关对上游说 **Anthropic 协议**，使用 `anthropic_base_url`（回落到 `base_url`），`x-api-key` 鉴权。
>
> 因此「一个供应商两个协议、两个地址」只需配两行 URL：`base_url` 填 **OpenAI 端地址（末尾带 `/v1`）**，`anthropic_base_url` 填 **Anthropic 端地址（根地址、不带 `/v1`）**。`provider_type` 按供应商实际类型填写（若该供应商走 Anthropic 式限流就填 `anthropic`）即可，它与协议选择无关。

```bash
# OpenAI / ModelScope 兼容供应商（provider_type 省略即默认）
curl -X POST http://127.0.0.1:37000/api/admin/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "供应商A",
    "base_url": "https://api-inference.modelscope.cn/v1",
    "api_keys": ["ms-xxxxxxxxxxxxx"]
  }'

# Anthropic 原生供应商
curl -X POST http://127.0.0.1:37000/api/admin/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Anthropic官方",
    "base_url": "https://api.anthropic.com",
    "provider_type": "anthropic",
    "api_keys": ["sk-ant-xxxxxxxxxxxxx"]
  }'

# 同一供应商、OpenAI 与 Anthropic 接口地址不同（双地址）
#   base_url          → OpenAI 端（客户端走 /openai/... 时命中）
#   anthropic_base_url → Anthropic 端（客户端走 /anthropic/... 时命中）
curl -X POST http://127.0.0.1:37000/api/admin/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "双协议供应商",
    "base_url": "https://gateway.example.com/openai/v1",
    "anthropic_base_url": "https://gateway.example.com/anthropic",
    "provider_type": "anthropic",
    "api_keys": ["sk-xxxxxxxxxxxxx"]
  }'
```

> ⚠️ **两种协议的地址写法不同（最容易踩坑）**：
> 代码统一用 `url = {上游 base}/{url_path}` 拼接，`url_path` 由入口决定（`/openai` → `chat/completions`，`/anthropic` → `v1/messages`）：
> - **OpenAI 端用 `base_url`**：`url_path = "chat/completions"`，所以 `base_url` 要写到 **`/v1`**（如 `https://api-inference.modelscope.cn/v1`），最终请求 `.../v1/chat/completions`。
> - **Anthropic 端用 `anthropic_base_url`**（未填则回落 `base_url`）：`url_path = "v1/messages"`，所以该地址必须是**根地址、不带 `/v1`**（如 `https://api.anthropic.com`），最终请求 `https://api.anthropic.com/v1/messages`。
>
> 即：OpenAI 侧地址末尾带 `/v1`，Anthropic 侧地址**不带 `/v1`**。两者都不要自行带上 `chat/completions` 或 `v1/messages`，代码会自动追加。配置错误会导致路径重复（如 `.../v1/v1/messages`）而 404。

**更新供应商**：

```bash
curl -X PUT http://127.0.0.1:37000/api/admin/suppliers/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "disabled"}'
```

**切换状态**：

```bash
curl -X PATCH http://127.0.0.1:37000/api/admin/suppliers/1/status
```

### 4.2 模型映射（Mappings）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/mappings` | 列出所有映射 |
| PUT | `/api/admin/mappings/bulk` | 批量更新映射 |
| DELETE | `/api/admin/mappings/{alias_name}` | 删除映射 |

**批量更新映射**：

```bash
curl -X PUT http://127.0.0.1:37000/api/admin/mappings/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "mappings": {
      "hy3": {"alias_name": "hy3", "region": "china", "actual_model_id": "Qwen/Qwen2.5-3B"},
      "qwen2.5": {"alias_name": "qwen2.5", "region": "china", "actual_model_id": "Qwen/Qwen2.5-72B"}
    }
  }'
```

### 4.3 系统配置（Config）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/config` | 读取当前配置 |
| PUT | `/api/admin/config` | 批量更新配置 |

**更新配置**：

```bash
curl -X PUT http://127.0.0.1:37000/api/admin/config \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "load_balancer_strategy": "least_conn",
      "request_timeout_ms": "60000"
    }
  }'
```

### 4.4 请求日志（Logs）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/logs` | 查询日志（支持分页和筛选） |
| GET | `/api/admin/logs/{log_id}` | 查询单条日志详情 |

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码，从 0 开始 |
| `page_size` | int | 每页条数，默认 50 |
| `status_code` | int | 按状态码筛选 |
| `account_id` | string | 按供应商筛选 |
| `model` | string | 按模型名筛选 |
| `is_stream` | boolean | 按是否流式筛选 |
| `start_time` | string | 起始时间（ISO 格式） |
| `end_time` | string | 结束时间（ISO 格式） |

**使用示例**：

```bash
# 查询第 1 页，每页 20 条
curl "http://127.0.0.1:37000/api/admin/logs?page=0&page_size=20"

# 按状态码筛选（只看 429）
curl "http://127.0.0.1:37000/api/admin/logs?status_code=429"

# 按时间范围筛选
curl "http://127.0.0.1:37000/api/admin/logs?start_time=2026-07-16T00:00:00&end_time=2026-07-16T23:59:59"
```

### 4.5 统计（Stats）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/stats?days=30` | 查询使用统计 |

```bash
# 默认查询 30 天
curl "http://127.0.0.1:37000/api/admin/stats?days=30"
```

### 4.6 告警（Alerts）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/admin/alerts?days=7` | 查询告警历史 |

```bash
curl "http://127.0.0.1:37000/api/admin/alerts?days=7"
```

### 4.7 健康检查

```bash
curl http://127.0.0.1:37000/api/health
# 返回: {"status": "healthy"}
```

---

## 5. 配置说明

### 5.1 环境变量（`.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///modelscope_proxy.db` | SQLite 数据库路径 |
| `LOG_LEVEL` | `INFO` | 日志级别：DEBUG / INFO / WARNING / ERROR |

### 5.2 系统配置（通过管理后台或 API 修改）

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `log_level` | `INFO` | 日志级别 |
| `load_balancer_strategy` | `round_robin` | 负载均衡策略：round_robin / least_conn / random |
| `request_timeout_ms` | `30000` | 请求上游超时时间（毫秒） |
| `retry_count` | `0` | 请求失败重试次数 |
| `auto_disable_on_quota` | `true` | 配额耗尽时自动标记模型不可用 |
| `auto_reset_daily` | `true` | 每日自动重置配额计数 |

### 5.3 多供应商负载均衡

系统支持配置多个 ModelScope 供应商，按以下规则自动分发请求：

1. 只选择状态为 `active` 的供应商
2. 优先选择支持目标模型的供应商（基于供应商模型配置）
3. 自动排除已标记不可用的模型
4. 按配置的策略（轮询/最少连接/随机）在可用供应商中选择

---

## 6. 常见问题

### Q: 如何初始化第一个供应商？

**方式一**：在 `.env` 中配置 `MODELSCOPE_ACCOUNTS_JSON`，数据库为空时自动导入。

**方式二**：直接访问管理后台 `/#/suppliers`，点击「添加供应商」填写信息。

### Q: 模型别名（如 `hy3`）是什么？

别名是用户调用代理时使用的简短模型名。系统会按以下顺序解析：

1. 查询 `model_mappings` 表中的别名映射
2. 调用 ModelScope `/models/{别名}` API 动态解析
3. 直接使用别名作为模型 ID 调用

建议在管理后台的「模型映射」页面预先配置好别名映射，以获得最佳性能。

### Q: 配额耗尽后怎么办？

- 若 `auto_disable_on_quota = true`（默认），系统会自动将耗尽的模型标记为不可用，后续请求会分发到其他供应商。
- 在「告警」页面可以查看配额耗尽记录。
- 每日配额会自动重置（若 `auto_reset_daily = true`）。

### Q: 数据库文件在哪里？

默认在项目根目录下的 `modelscope_proxy.db`。可通过 `.env` 的 `DATABASE_URL` 修改路径。

### Q: 如何重置数据库？

删除 `modelscope_proxy.db` 文件，重启服务后会自动重新创建空数据库并注入默认配置。

### Q: 前端修改后需要重新构建吗？

需要。修改 `web/src/` 下的源码后运行：

```bash
cd web && npm run build && cd ..
```

然后刷新浏览器（建议 Ctrl+Shift+R 强制刷新，清除缓存）。

---

## 7. 数据库表结构

| 表名 | 说明 |
|------|------|
| `accounts` | 供应商/账户配置 |
| `model_mappings` | 模型别名映射 |
| `supplier_models` | 供应商支持的模型 |
| `system_config` | 系统配置键值对 |
| `request_logs` | 请求日志 |
| `account_quotas` | 账户配额记录 |
| `model_alias_cache` | 别名解析缓存 |

完整字段定义见开发规范：[docs/dev_guide.md](dev_guide.md)

---

*文档版本：v0.2.0 | 更新日期：2026-07-17*
