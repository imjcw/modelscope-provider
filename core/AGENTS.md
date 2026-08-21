# core — 核心逻辑层

## 职责

提供项目的基础设施能力:数据库管理、HTTP 客户端、配置系统、桌面 Widget、服务初始化。

## 文件说明

| 文件 | 职责 | 关键点 |
|------|------|--------|
| database.py | SQLAlchemy 引擎与会话管理 | 支持 SQLite WAL 模式,自动检测 WSL 降级 |
| config.py | 系统配置的读写与缓存 | 通过 ConfigService 操作 |
| http_client.py | 异步 HTTP 客户端(基于 httpx) | 超时、重试、代理配置 |
| desktop_widget.py | Windows 桌面 Token 卡片 | 钉在 WorkerW 桌面层,显示今日 Token 与缓存命中率 |
| service_init.py | 服务初始化逻辑 | 初始化别名解析器、缓存、模型列表、数据库连接池等 |
| timezone.py | 时区工具 | 时间转换与格式化 |
| migrations/ | 数据库迁移框架 | 版本化 Schema 变更 |

## 桌面 Widget 说明

- 仅 Windows 可用(依赖 pywin32)
- 钉在桌面层(WorkerW 子窗口),位于所有应用窗口之后
- 数据来自 /api/admin/stats/window?seconds=0
- 5 分钟轮询一次,30 秒检查一次设置开关

## 常见陷阱

- WSL 下 /mnt/d/ 挂载的 SQLite WAL 模式可能失败,会自动降级为 DELETE
- 桌面 Widget 与托盘线程、uvicorn 线程互不阻塞
- 数据库迁移请通过 core/migrations/cli.py 执行,不要手动改表

## 相关测试

tests/core/ — 覆盖配置、数据库、HTTP 客户端、服务初始化
