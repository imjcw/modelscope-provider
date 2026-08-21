# core/migrations — 数据库迁移框架

## 职责

提供版本化数据库迁移能力,确保 Schema 变更可追溯、可回滚。

## 文件说明

| 文件 | 职责 |
|------|------|
| base.py | 迁移基类,定义 upgrade() / downgrade() 接口 |
| migrator.py | 迁移执行器,管理迁移版本状态 |
| registry.py | 迁移注册表,自动发现迁移脚本 |
| cli.py | 命令行入口,执行迁移命令 |
| migrations/ | 具体迁移脚本,按编号排列 |

## 迁移脚本

迁移脚本位于 migrations/ 子目录,命名规则: {序号}_{描述}.py
- 序号从 001 开始递增
- 每个脚本必须实现 upgrade() 和 downgrade() 方法
- 执行迁移: python -m core.migrations.cli upgrade

## 常见陷阱

- 迁移脚本一旦提交,不要修改已发布的迁移(只能新建)
- 回滚时 downgrade() 必须精确还原 upgrade() 的变更
- 测试数据库和开发数据库的迁移版本需保持一致

## 相关测试

tests/core/migrations/ — 覆盖迁移执行、注册表、集成测试
