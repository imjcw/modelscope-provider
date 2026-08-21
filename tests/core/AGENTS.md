# tests/core — 核心逻辑层测试

## 职责

测试数据库、配置、HTTP 客户端、服务初始化等核心模块。

## 文件说明

| 文件 | 测试目标 |
|------|----------|
| test_config.py | 配置读写 |
| test_database.py | 数据库连接与会话 |
| test_database_mapping_models.py | 模型映射持久化 |
| test_database_vacuum.py | 数据库 VACUUM |
| test_http_client_keys.py | HTTP 客户端 Key 管理 |
| test_http_client_stream.py | HTTP 流式请求 |
| test_service_init.py | 服务初始化流程 |
| migrations/ | 迁移测试 |
