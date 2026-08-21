# tests/services — 业务逻辑层测试

## 职责

测试核心业务逻辑:熔断器、负载均衡、路由、缓存、配额。

## 文件说明

| 文件 | 测试目标 |
|------|----------|
| test_circuit_breaker.py | 熔断器逻辑 |
| test_load_balancer.py | 负载均衡器 |
| test_load_balancer_model_filter.py | 按模型过滤 |
| test_alias_router.py | 别名路由 |
| test_cache.py | 缓存抽象层 |
| test_caching.py | 缓存穿透保护 |
| test_quota_updater.py | 配额更新 |
| test_response_converter.py | 响应格式转换 |
| test_admin_service_log_cleanup_vacuum.py | 日志清理 |
| test_admin_service_model_quotas.py | 模型配额管理 |
| test_admin_service_window_stats.py | 窗口统计 |
| providers/ | 供应商适配器测试 |
