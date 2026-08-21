# api — FastAPI 路由层

## 职责

提供三个协议入口的路由:
1. **OpenAI 兼容协议** — `/v1/chat/completions`, `/v1/models` 等
2. **Anthropic 兼容协议** — `/v1/messages`(原生直连 + 转换两种路径)
3. **管理后台 API** — `/api/admin/*`(配置、统计、熔断控制等)

## 文件说明

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `openai_routes.py` | OpenAI 协议端点,流式/非流式请求转发 | 处理 chat/completions,轮询 Key,429 退避 |
| `anthropic_routes.py` | Anthropic 协议端点 | 永远走原生直连(硬编码 v1/messages) |
| `anthropic_adapters.py` | Anthropic 协议转换 + 通用 429 退避函数 | 通用退避函数住在此模块,被所有路由共享,不限于 Anthropic |
| `admin_routes.py` | 管理后台 CRUD API | 配置、统计、Key 管理、熔断重置等 |

## 协议入口

```
OpenAI:    /v1/chat/completions -> openai_routes.py
Anthropic: /v1/messages -> anthropic_routes.py (原生直连)
           /anthropic/v1/messages -> 同上(兼容路由)
Admin:     /api/admin/* -> admin_routes.py
```

## 关键约定

- anthropic_adapters.py 的 request_with_429_backoff 是通用函数,被各路由共享
- 流式 SSE 响应使用 StreamingResponse,数据格式因协议而异
- 错误响应统一返回 error_source 字段区分上游/策略/限流

## 常见陷阱

- Anthropic 路由的 token 统计在流式/非流式路径下可能存在差异
- 对商汤等供应商,Anthropic 入口需设置 Authorization: Bearer
- 429 退避对限流型 429 原地重试同 Key 3 次,效率可能不高

## 相关测试

tests/api/ — 每个路由文件对应独立的测试文件
