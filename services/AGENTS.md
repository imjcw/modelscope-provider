# services — 业务逻辑层

## 职责

实现核心业务逻辑:熔断器、负载均衡、别名路由、缓存、配额管理、响应转换等。

## 文件说明

| 文件 | 职责 | 关键点 |
|------|------|--------|
| circuit_breaker.py | 熔断器 | 按 Key 粒度,支持冻结/解冻,429 不冻结 |
| load_balancer.py | 负载均衡器 | RR 轮询+熔断感知,失败时轮转到下一个 |
| alias_router.py | 别名路由 | 根据模型名解析到具体供应商 |
| cache.py | 缓存抽象层 | 支持 SQLite 和内存两种后端 |
| caching.py | 缓存穿透保护 | 缓存命中率统计 |
| admin_service.py | 管理后台业务逻辑 | 日志清理、统计、配额管理 |
| quota_updater.py | 配额更新器 | 请求完成后更新 Token 用量 |
| response_converter.py | 响应格式转换 | OpenAI <-> Anthropic 协议转换 |
| models_cache.py | 模型列表缓存 | 供应商模型列表的缓存管理 |
| providers/ | 供应商适配层 | 各供应商的具体实现 |

## 关键约定

- 熔断器: 429(rate_limit) 不冻结,仅永久错误(auth_error/bad_request)冻结
- 负载均衡: Round Robin 每请求前进 1 格,回绕不跳过冻结 Key
- 缓存命中率在桌面 Widget 和 Dashboard 中展示

## 常见陷阱

- 熔断冻结是内存态(会自愈),与持久化告警分离
- "策略拒绝"=策略层不可用,与电路冻结不同
- 窗口计数模型(fixed_window)瞬时故障不冻结,仅永久错误冻结
- 429 退避函数在 api/anthropic_adapters.py 中,由各路由共享

## 相关测试

tests/services/ — 覆盖各服务的单元测试
