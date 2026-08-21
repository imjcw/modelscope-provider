# config — 配置文件

## 职责

存放项目静态配置文件。

## 文件说明

| 文件 | 职责 |
|------|------|
| model_mappings.json | 模型映射关系定义,统一不同供应商的模型名 |

## 相关

- 运行时配置通过 /api/admin/config 接口管理,持久化在数据库 config 表
- 环境变量配置参考 .env.example
