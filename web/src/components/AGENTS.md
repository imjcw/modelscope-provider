# web/src/components — 前端通用组件

## 职责

存放可复用的 UI 组件,基于 shadcn/vue 设计体系。

## 关键约定

- 组件命名: PascalCase,单文件组件
- 每个组件职责单一,通过 props 接受数据
- 使用 v-model 实现双向绑定(如适用)
- emit 事件命名: kebab-case

## 组件列表

| 组件 | 用途 |
|------|------|
| AlertLevelIcon | 告警级别图标 |
| Avatar | 用户头像 |
| CCard / CCheckbox / CSelect 等 | 基础 UI 组件(C 前缀=自定义) |
| CodeBlock | 代码高亮块 |
| ConfirmModal | 确认对话框 |
| CopyButton | 复制按钮 |
| DateRangePicker | 日期范围选择器 |
| Drawer / Sidebar 等 | 布局组件 |
| EmptyState | 空状态占位 |
| FilterField | 筛选字段组件 |
| MarkdownRender | Markdown 渲染 |
| ModelListEditor | 模型列表编辑器 |
| PageHeader / PageState | 页面框架组件 |
| Pagination | 分页器 |
| ProgressBar / StatCard | 数据展示 |
| StatusBadge / StatusCodeBadge | 状态标签 |
| ThemeToggle | 主题切换 |
| Toast | 消息提示 |
| TokenStack | Token 堆叠展示 |
| ViewToggle | 视图切换 |

## 相关子目录

- dashboard/ — Dashboard 仪表盘专用组件
- log/ — 日志详情专用组件
