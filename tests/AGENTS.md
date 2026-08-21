# tests — 测试根目录

## 职责

项目全量测试,包括单元测试和集成测试。

## 目录结构

```
tests/
+-- api/              -- API 路由层测试
+-- core/             -- 核心逻辑层测试
|   +-- migrations/   -- 数据库迁移测试
+-- integration/      -- 端到端集成测试
+-- models/           -- 数据模型测试
+-- repositories/     -- 数据访问层测试
+-- services/         -- 业务逻辑层测试
    +-- providers/    -- 供应商适配层测试
```

## 文件说明

| 文件 | 职责 |
|------|------|
| conftest.py | 全局 fixture: test_db(测试数据库)、client(HTTP 客户端)、sample_data(测试数据种子) |
| test_body_limit.py | 请求体大小限制测试 |

## 关键约定

- 使用 pytest,测试数据库为独立 SQLite 文件
- 每个测试文件对应一个源模块
- fixture 在 conftest.py 中集中管理

## 运行测试

```bash
pytest tests/ -v
pytest tests/api/ -v  # 仅运行 API 测试
```
