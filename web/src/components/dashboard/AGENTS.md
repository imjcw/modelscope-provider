# web/src/components/dashboard — Dashboard 仪表盘组件

## 职责

Dashboard 首页专用的数据可视化组件。

## 组件列表

| 组件 | 用途 |
|------|------|
| CacheHitRateDonut | 缓存命中率环形图 |
| KpiSparkline | KPI 迷你趋势线 |
| ModelStatusTable | 模型状态表格 |
| QpsTrendChart | QPS 趋势折线图 |
| RateLimitCard | 限流状态卡片 |
| RecentAlerts | 最近告警列表 |
| StatusDonut | 状态环形图 |
| TokenTrendBarChart | Token 趋势柱状图 |

## 数据来源

所有组件通过 props 从父组件(Dashboard.vue)接收数据,数据来自 /api/admin/stats/* 接口
