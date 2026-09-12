# core/migrations/migrations — 数据库迁移脚本

## 职责

存放所有版本化迁移脚本,按编号排列(001~030)。每个文件对应一次 Schema 变更。

## 迁移列表

| 编号 | 描述 |
|------|------|
| 001~010 | 初始表结构、请求日志、模型映射、排序等基础能力 |
| 011~020 | 供应商类型、速率窗口、Key 管理、API Key ID 关联 |
| 021~029 | 错误来源、熔断字段、Anthropic 认证样式/上游协议、窗口/配额 Key ID |
| 030 | 历史数据修正:把上游单独上报的缓存 token 折回 input_tokens,统一命中率口径 |

## 约定

- 编号必须连续,不可跳跃
- 不可修改已发布的迁移脚本
- 新增迁移时复制最近的模板,修改 upgrade() / downgrade()

## 相关

- 迁移框架: core/migrations/
- 迁移执行: python -m core.migrations.cli upgrade
