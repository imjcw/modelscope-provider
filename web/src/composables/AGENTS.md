# web/src/composables — Vue 3 可组合函数

## 职责

封装可复用的响应式逻辑,遵循 Vue 3 Composition API 的 composable 模式。

## 文件说明

| 文件 | 职责 |
|------|------|
| useResponseParser.js | SSE 流式响应解析器,支持 OpenAI SSE 和 Anthropic SSE 两种协议格式 |
| useTheme.js | 主题切换(深色/浅色),持久化到 localStorage |
| useViewPreference.js | 用户视图偏好设置 |
| useOverlayEsc.js | ESC 键关闭浮层/弹窗 |

## 关键约定

- composable 函数以 use 开头
- 返回响应式引用(ref/reactive/computed)
- 不产生副作用(除非通过 watchEffect / onMounted 显式管理)
- useResponseParser 回调链使用扁平化 API,避免嵌套
