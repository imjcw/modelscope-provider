# models — 数据模型(SQLAlchemy)

## 职责

定义数据库表对应的 ORM 模型,使用 SQLAlchemy 2.0 声明式映射。

## 文件说明

| 文件 | 模型 | 对应表 |
|------|------|--------|
| account.py | Account, AccountApiKey | accounts, account_api_keys |
| alias_resolver.py | ModelAlias, MappingModel, SupplierModel | 模型别名与映射关系 |

## 关键约定

- 所有模型继承自 Base(在 core/database.py 中定义)
- 使用 Mapped 类型注解 + mapped_column() 定义字段
- 关系(Relationship)在模型类中显式声明

## 常见陷阱

- 修改模型后需创建对应迁移脚本,不会自动同步
- 某些字段在 account_api_keys 中有逻辑序号(key_index)和自增 ID(id)两种标识,注意区分
- 模型修改后检查 repositories/ 层是否有对应更新

## 相关

- 数据库初始化: core/database.py
- 数据访问: repositories/
- 迁移: core/migrations/
