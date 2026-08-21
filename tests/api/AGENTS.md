# tests/api — API 路由层测试

## 职责

测试三个协议入口的路由逻辑:OpenAI、Anthropic、Admin API。

## 文件说明

| 文件 | 测试目标 |
|------|----------|
| test_admin_routes.py | 管理后台 CRUD API |
| test_routes.py | OpenAI 协议请求/响应 |
| test_dual_protocol.py | 双协议兼容性 |
| test_circuit_breaker.py | 熔断器 API 交互 |
| test_429_backoff.py | 429 退避逻辑 |
| test_fallback_behavior.py | 兜底/降级行为 |
| test_streaming_error.py | 流式请求错误处理 |
| test_supplier_models.py | 供应商模型列表 |
| test_routes_performance.py | 路由性能基准 |
| test_window_stats.py | 窗口统计 API |

## 关键约定

- 使用 TestClient 模拟 HTTP 请求
- 测试数据库在 fixture 中创建,测试结束后清理
