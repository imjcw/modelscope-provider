# ModelScope 代理服务

兼容 OpenAI API 格式的 ModelScope 代理服务，支持多账户负载均衡、动态模型别名解析和 Web 管理后台。

## 功能特性

- ✅ OpenAI API 格式兼容
- ✅ 多账户自动负载均衡（轮询策略）
- ✅ 动态模型别名解析
- ✅ 配额监控和自动切换
- ✅ 配额耗尽自动标记模型为不可用
- ✅ SQLite 数据持久化
- ✅ 健康检查和管理端点
- ✅ Web 管理后台（账户/映射/日志/统计/告警/测试/配置）

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

编辑 `.env` 文件：

```bash
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
  }
]'

DATABASE_URL="D:/workspace/third/provider/modelscope_proxy.db"
LOG_LEVEL="INFO"
```

## 运行

```bash
# ⚠️ 启动前确保 web/dist/ 已存在（运行 npm run build）

# 推荐：使用 main.py（带管理后台 API + 静态文件托管）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 或：使用 server.py（仅代理功能 + 静态文件托管）
python server.py
```

## 访问管理后台

打开浏览器访问：`http://localhost:8000/#/`

页面说明：
- `/` 仪表盘 — 配额概览、账户状态
- `/accounts` 账户管理 — 添加/编辑/删除账户
- `/mappings` 模型映射 — 别名到模型 ID 的映射
- `/logs` 请求日志 — 筛选、详情查看
- `/stats` 使用统计 — 热力图、趋势、模型用量
- `/alerts` 告警历史 — 配额/错误告警
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

# 查询统计
curl http://localhost:8000/api/admin/stats?days=30
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

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your ModelScope account configurations
```

## 配置

编辑 `.env` 文件：

```bash
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
  }
]'

DATABASE_URL="D:/workspace/third/provider/modelscope_proxy.db"
LOG_LEVEL="INFO"
```

## 运行

```bash
# Development mode
python main.py

# Production mode with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

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

### 管理端点

```bash
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

## 架构

详细设计文档见：[设计文档](docs/superpowers/specs/2026-07-15-modelscope-proxy-design.md)

## 许可证

MIT
