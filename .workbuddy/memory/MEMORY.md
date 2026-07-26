# Project Memory — modelscope-provider

## 项目本质
OpenAI 格式兼容的多供应商代理服务（不止 ModelScope，已扩展到商汤/SenseTime 等）。
核心：多账户负载均衡 + 动态模型别名解析 + 配额管理 + 熔断 + 客户端 API Key(多租户) + Vue 管理后台。
技术栈：Python 3.13 / FastAPI / SQLite(WAL) / httpx / Pydantic v2 / Vue 前端(web/dist)。

## 关键架构事实（非显而易见）
- 存在两套并行实现（技术债）：
  - 现代主链路：`main.py` → `api/routes.py` + `api/admin_routes.py` + `services/*` + `models/alias_resolver.py`，由 `core/service_init.ServiceInitializer` 组装，数据库驱动、可配置。生产用此链路。
  - 遗留实现：`openai_proxy.py` 的 `ModelScopeProxy` 类 + `server.py`，**硬编码了两个真实 API Key 和账户**，仅作示例/兜底。
- 限流策略可插拔：`services/providers/`（header_based=ModelScope, fixed_window=SenseTime, per_model 等），由 `provider_types` 表 + 硬编码内置类型共同决定。
- 路由核心：`services/alias_router.py`（虚拟模型 alias → 绑定条目 → 按 round_robin/random/least_conn 选 account+实际模型名）。
- 后台周期任务（main.py lifespan）：日志清理(300s)、限流计数落库(60s)、配置同步(300s)。

## 安全隐患（已发现，待处理）
- `server.py` 与 `openai_proxy.py` 内**硬编码了真实 ModelScope API Key**（`ms-ef15676c-...`、`ms-ff949c01-...`），应移除/轮换。

## 当前开发重心（2026-07-26）
性能优化计划：启用 SQLite WAL、LRU 缓存(alias_resolver / get_services)、修复 AliasRouter N+1 查询、流式响应日志序列化 bug。

## 约定（来自 CLAUDE.md）
- DB 单元测试必须用 `tests/conftest.py` 的 fixture 或 tmp_path 临时库；严禁硬编码路径或连 .env 的 DATABASE_URL。测试结束必须清理。
- 根目录遗留多个 DB 文件：`modelscope_proxy_prod.db`(~152MB，生产)、`modelscope_proxy.db`(开发)、`modelscope_proxy_test.db`(测试)、`modelscope.db`/`test_window_stats.db`(空占位)。

## README 问题
`README.md` 内容重复（同一段落出现两次）；设计文档提到的 Dockerfile 实际未提供。
