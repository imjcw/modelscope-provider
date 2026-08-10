# Project Memory — modelscope-provider

## 项目本质
OpenAI 格式兼容的多供应商代理服务（不止 ModelScope，已扩展到商汤/SenseTime 等）。
核心：多账户负载均衡 + 动态模型别名解析 + 配额管理 + 熔断 + 客户端 API Key(多租户) + Vue 管理后台。
技术栈：Python 3.13 / FastAPI / SQLite(WAL) / httpx / Pydantic v2 / Vue 前端(web/dist)。

## 关键架构事实（非显而易见）
- 路由文件实际为 `api/openai_routes.py`（非 `api/routes.py`）；管理后台在 `api/admin_routes.py`。
- 现代主链路：`main.py` → `api/openai_routes.py` + `api/admin_routes.py` + `services/*` + `models/alias_resolver.py`，由 `core/service_init.ServiceInitializer` 组装，数据库驱动、可配置。生产用此链路。
- 限流策略可插拔：`services/providers/`（header_based=ModelScope, fixed_window=SenseTime, per_model 等），由 `provider_types` 表 + 硬编码内置类型共同决定。
- 路由核心：`services/alias_router.py`（虚拟模型 alias → 绑定条目 → 按 round_robin/random/least_conn 选 account+实际模型名）。
- 后台周期任务（main.py lifespan）：日志清理(300s)、限流计数落库(60s)、配置同步(300s)。
- 遗留 `server.py` / `openai_proxy.py` **已不存在**（2026-08 核查），不要按旧记忆去找它们。

## 安全隐患（2026-08-10 处理）
- 真实 ModelScope API Key 曾硬编码在 `demo/test_models.py`（3 个：`ms-ef15676c-...`、`ms-115faeda-...`、`ms-ff949c01-...`）。
- ✅ 2026-08-10 已将 `demo/test_models.py` 改为从环境变量 `MODELSCOPE_ACCOUNTS_JSON` 读取账户，源码已无明文 Key。
- ⚠️ 仍待办：**这三个 Key 已泄露，必须由用户在 ModelScope 后台轮换（revoke/重新生成）**，因为可能残留在 git 历史或其他副本中。代码修复无法撤销已泄露的凭据。

## 部署形态（重要：影响优先级判断）
- **用户明确：本项目仅本地自用、不商用。** 因此安全类问题（管理后台无鉴权、base_url SSRF）对单用户本地场景威胁低，优先级降级；真正仍值得修的是**代码正确性/健壮性**类问题。
- ⚠️ 但需注意：README 文档的运行命令是 `uvicorn main:app --host 0.0.0.0`（main.py 本身无 `uvicorn.run`，须靠该命令启动），意味着默认监听所有网卡、在局域网内可被同网段其他机器访问。若所处网络不可信，仍建议绑定 127.0.0.1 或加个简单 admin token。

## 当前开发重心（2026-07-26）
性能优化计划：启用 SQLite WAL、LRU 缓存(alias_resolver / get_services)、修复 AliasRouter N+1 查询、流式响应日志序列化 bug。

## 约定（来自 CLAUDE.md）
- DB 单元测试必须用 `tests/conftest.py` 的 fixture 或 tmp_path 临时库；严禁硬编码路径或连 .env 的 DATABASE_URL。测试结束必须清理。
- 根目录遗留多个 DB 文件：`modelscope_proxy_prod.db`(~152MB，生产)、`modelscope_proxy.db`(开发)、`modelscope_proxy_test.db`(测试)、`modelscope.db`/`test_window_stats.db`(空占位)。

## README 问题
- 2026-08-10 核查：README.md **未发现重复段落**（旧记忆中的"重复"应为已修复的旧状态）。设计文档提到 Dockerfile 但实际未提供，属文档与实现不一致，非紧急。
