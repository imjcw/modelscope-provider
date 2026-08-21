# web/src/api — 前端 API 客户端

## 职责

封装对后端管理 API 的 HTTP 调用。

## 文件说明

| 文件 | 职责 |
|------|------|
| index.js | API 客户端,包含所有后端接口的调用函数 |

## 关键约定

- 使用 fetch API,无额外 HTTP 库
- 基础 URL 从环境变量或相对路径获取
- 所有请求包含 Content-Type: application/json
- 错误处理统一在调用方进行
