# web/src/components/log — 日志详情组件

## 职责

请求日志详情页专用的展示组件。

## 组件列表

| 组件 | 用途 |
|------|------|
| MessageCard | 消息卡片(流式/非流式响应) |
| RoleBadge | 角色标签(system/user/assistant/tool) |
| StatsSection | 统计信息区域 |
| ToolCallCard | 工具调用卡片 |
| ToolIO | 工具输入/输出展示 |

## 辅助文件

| 文件 | 用途 |
|------|------|
| toolType.js | 工具类型定义 |

## 关键约定

- MessageCard 处理 content/reasoning/toolCalls 三种消息类型
- 空 assistant 消息(无 content/reasoning/toolCalls)自动过滤
- SSE 流式数据通过 useResponseParser composable 解析
