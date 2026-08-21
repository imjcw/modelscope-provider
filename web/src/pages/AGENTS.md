# web/src/pages — 前端页面级组件

## 职责

每个路由对应的页面组件,是路由的终点。

## 页面列表

| 页面 | 路由 | 功能 |
|------|------|------|
| Dashboard.vue | / | 仪表盘首页,展示 Token 统计、缓存命中率、QPS 趋势 |
| Accounts.vue | /accounts | 供应商账号管理,Key 配置、熔断状态 |
| ApiKeys.vue | /api-keys | API Key 管理 |
| Logs.vue | /logs | 请求日志列表 |
| LogPanel.vue | /logs | 日志面板(子视图) |
| LogDetailPanel.vue | /logs/{id} | 日志详情,展示请求/响应、Token 用量 |
| Alerts.vue | /alerts | 告警列表与熔断事件 |
| Config.vue | /config | 系统配置 |
| Mappings.vue | /mappings | 模型映射管理 |
| ProviderTypes.vue | /provider-types | 供应商类型管理 |
| KeyDetailPanel.vue | /api-keys/{id} | Key 详情面板 |
| Guide.vue | /guide | 使用指南 |
| Test.vue | /test | API 测试工具,支持 OpenAI/Anthropic 协议 |

## 关键约定

- 页面组件负责:数据获取、状态管理、子组件调度
- 不直接操作 DOM,通过子组件 props 传递数据
- 使用 onBeforeRouteLeave(从 vue-router 导入)处理离开确认
