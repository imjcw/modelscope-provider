# AI Provider

兼容 OpenAI API 格式的 AI Provider 网关，支持多供应商账户负载均衡、动态模型别名解析、智能路由和管理后台。

## 功能特性

- ✅ OpenAI API 格式兼容（聊天补全，支持流式与非流式）
- ✅ 多账户负载均衡（轮询 / 随机 / 最少连接策略）
- ✅ 动态模型别名解析（虚拟模型 → 多个供应商模型）
- ✅ 多供应商类型与可插拔限流策略（header 被动式 / 固定窗口 / 按模型窗口）
- ✅ 配额监控、熔断（Circuit Breaker）与自动标记模型为不可用
- ✅ SQLite 数据持久化（自研幂等迁移框架）
- ✅ 健康检查和管理端点
- ✅ Web 管理后台（仪表盘 / 供应商 / 映射 / 日志 / 告警 / 测试 / 配置）

## 安装

```bash
# Clone repository
git clone <repository-url>
cd provider

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies and build
cd web
npm install && npm run build
cd ..
```

## 配置

编辑 `.env` 文件（可复制 `.env.example`）：

```bash
MODELSCOPE_ACCOUNTS_JSON='[
  {
    "account_id": "account1",
    "api_key": "your-api-key-1",
    "base_url": "https://api-inference.modelscope.cn/v1"
  },
  {
    "account_id": "account2",
    "api_key": "your-api-key-2",
    "base_url": "https://api-inference.modelscope.cn/v1"
  }
]'

# Anthropic 原生供应商（provider_type=anthropic）：base_url 为根地址，不带 /v1
#   "base_url": "https://api.anthropic.com", "provider_type": "anthropic"

DATABASE_URL="D:/workspace/third/provider/modelscope_proxy.db"
LOG_LEVEL="INFO"
```

> **OpenAI 与 Anthropic 双地址供应商**：`.env` 仅支持单一 `base_url`。若一个供应商的 OpenAI 接口与 Anthropic 接口地址不同，请改用 Web 管理后台（供应商管理）或 `POST /api/admin/suppliers` 添加，并通过 `anthropic_base_url` 字段单独指定 Anthropic 侧地址。`provider_type` 是**供应商的类型**（限流策略/展示），**不决定协议**；协议由客户端入口决定：`/openai/...` 走 OpenAI 协议（用 `base_url`），`/anthropic/...` 走 Anthropic 协议（用 `anthropic_base_url`，未填则回落 `base_url`）。

> 账户也可通过 Web 管理后台（供应商管理）维护；数据库优先于 `.env`，首次启动会自动将 `.env` 中的账户迁移进数据库。

## 运行

```bash
# ⚠️ 启动前确保 web/dist/ 已存在（运行 npm run build）

# 推荐：使用 main.py（带管理后台 API + 静态文件托管）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 或直接运行（main.py 内置 uvicorn 启动）
python main.py
```

## 访问管理后台

打开浏览器访问：`http://localhost:8000/#/`

页面说明：
- `/` 仪表盘 — 配额概览、账户/模型状态、统计趋势（"使用统计"已并入仪表盘）
- `/suppliers` 供应商管理 — 添加/编辑/删除账户（旧文档曾称 `/accounts`）
- `/provider-types` 供应商类型 — 限流策略类型管理
- `/mappings` 模型映射 — 别名到供应商模型的绑定
- `/logs` 请求日志 — 筛选、详情查看
- `/alerts` 告警 — 配额/错误告警（实时从日志派生）
- `/test` 在线测试 — 直接调 API
- `/config` 系统配置 — 全局参数

## 使用

### 健康检查

```bash
curl http://localhost:8000/api/health
```

### 聊天完成

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hy3",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 管理 API

```bash
# 查询所有账户
curl http://localhost:8000/api/admin/accounts

# 查询日志
curl http://localhost:8000/api/admin/logs?page=0&page_size=20

# 查询窗口统计（仪表盘使用）
curl http://localhost:8000/api/admin/stats/window

# 查询所有账户配额信息
curl http://localhost:8000/api/admin/quota
```

## 测试

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/services/test_load_balancer.py -v
```

## 前端开发

```bash
cd web
npm run dev   # 开发模式，hot reload
npm run build # 生产构建 → web/dist/
```

## 架构

详细设计文档见：[设计文档](docs/superpowers/specs/2026-07-15-modelscope-proxy-design.md)

## 许可证

MIT
