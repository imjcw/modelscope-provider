# core — 核心逻辑层

## 职责

提供项目的基础设施能力:数据库管理、HTTP 客户端、配置系统、服务初始化。

## 文件说明

| 文件 | 职责 | 关键点 |
|------|------|--------|
| database.py | SQLAlchemy 引擎与会话管理 | 支持 SQLite WAL 模式,自动检测 WSL 降级 |
| config.py | 系统配置的读写与缓存 | 通过 ConfigService 操作 |
| http_client.py | 异步 HTTP 客户端(基于 httpx) | 超时、重试、代理配置 |
| service_init.py | 服务初始化逻辑 | 初始化别名解析器、缓存、模型列表、数据库连接池等 |
| timezone.py | 时区工具 | 时间转换与格式化 |
| migrations/ | 数据库迁移框架 | 版本化 Schema 变更 |

## 常见陷阱

- WSL 下 /mnt/d/ 挂载的 SQLite WAL 模式可能失败,会自动降级为 DELETE
- 数据库迁移请通过 core/migrations/cli.py 执行,不要手动改表

## 相关测试

tests/core/ — 覆盖配置、数据库、HTTP 客户端、服务初始化
