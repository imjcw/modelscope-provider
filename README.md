# ModelScope 代理服务

兼容 OpenAI API 格式的 ModelScope 代理服务，支持多账户负载均衡和动态模型别名解析。

## 功能特性

- ✅ OpenAI API 格式兼容
- ✅ 多账户自动负载均衡（轮询策略）
- ✅ 动态模型别名解析
- ✅ 配额监控和自动切换
- ✅ 配额耗尽自动标记模型为不可用
- ✅ SQLite 数据持久化
- ✅ 健康检查和管理端点

## 安装

```bash
# Clone repository
git clone <repository-url>
cd provider

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
