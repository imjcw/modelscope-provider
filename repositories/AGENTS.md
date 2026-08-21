# repositories — 数据访问层(Repository 模式)

## 职责

封装对数据库表的 CRUD 操作,隔离业务逻辑与 SQLAlchemy 细节。

## 文件说明

| 文件 | 操作对象 |
|------|----------|
| account_repository.py | accounts 表,供应商账号管理 |
| client_api_key_repository.py | 客户端 API Key 认证 |
| config_repository.py | config 表,系统配置读写 |
| log_repository.py | request_logs 表,请求日志与统计查询 |
| mapping_repository.py | 模型映射关系 |
| mapping_model_repository.py | 映射模型详情 |
| provider_type_repository.py | 供应商类型管理 |
| quota_repository.py | 配额管理 |
| supplier_model_repository.py | 供应商模型管理 |

## 关键约定

- 每个 Repository 对应一个或一组相关的表
- 接受 Session 作为参数,不管理事务生命周期
- 查询方法返回模型对象或字典,不返回原始 SQL

## 常见陷阱

- account_api_keys 有逻辑序号(0基)和自增 ID 两种标识,查询时注意区分
- request_logs 表数据量大,统计查询注意性能

## 相关测试

tests/repositories/ — 覆盖各 Repository 的 CRUD 操作
