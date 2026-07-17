# 前端组件抽取与代码优化 — Design Spec

**Date:** 2026-07-17
**Branch:** batch-task-5-8

## 1. 背景

当前前端（Vue 3 + Tailwind）有 8 个页面，页面头部、抽屉、确认弹窗等模板代码在各页面重复手写，`alert()` 全局弹窗体验差，部分代码风格不一致（绕过 api/ 层、串行请求、硬编码选项等）。

## 2. 目标

- 消除跨页面重复模板代码（页面头部、抽屉、确认弹窗）
- 替换所有 `alert()` 为统一 Toast 通知
- 统一使用已定义的全局语义类（`.btn`/`.card`/`.tag`/`.action-icon`）
- 修复已知代码质量问题

## 3. 新组件

### 3.1 PageHeader

统一所有页面的顶部标题栏。

```vue
<PageHeader
  title="供应商管理"
  subtitle="添加、编辑和删除 ModelScope 供应商"
>
  <template #action>
    <button @click="openAdd" class="btn btn-primary">
      <IconPlus /> 添加供应商
    </button>
  </template>
</PageHeader>
```

- 固定结构：左侧标题（`text-lg`）+ 副标题（`text-xs text-gray-500`），右侧 `#action` slot
- 内置 sticky header 样式：`bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3`
- `#action` slot 可选，无 slot 时右侧留空
- 纯展示组件，无状态，无依赖

**影响页面（8 个）**：Dashboard, Accounts, Mappings, Logs, Stats, Alerts, Test, Config

### 3.2 Drawer

统一抽屉组件，替代手写 `<Teleport>` + `.drawer-overlay` + `.drawer-panel`。

```vue
<Drawer v-model="showAdd" :title="isEditing ? '编辑映射' : '添加映射'">
  <!-- 表单内容 -->
</Drawer>
```

- Props:
  - `modelValue` (Boolean) — 控制显隐
  - `title` (String) — 标题文字
  - `width` (String, default `'780px'`) — 抽屉宽度
- 内置：`<Teleport to="body">`、overlay backdrop、slide-in/out 动画
- 退出动画在组件内部处理：关闭时先加 `.exiting` 类，250ms 后再隐藏（不再各页手写）
- ESC 键关闭（`document.addEventListener('keydown')`）
- 复用现有 `.drawer-*` / `.drawer-header` / `.drawer-body` / `.drawer-footer` 类
- 表单 slot 默认放在 drawer-body 区域
- 支持 `#footer` slot 自定义底部按钮（可选，默认无 footer）

**影响页面**：Accounts（添加+编辑 2 处）, Mappings（添加/编辑 1 处）

### 3.3 ConfirmModal

统一确认删除/操作弹窗。

```vue
<ConfirmModal
  v-model="showDelete"
  :title="confirmTitle"
  :message="confirmMessage"
  danger
  :confirm-text="deleting ? '删除中...' : '确认删除'"
  :disabled="deleting"
  @confirm="handleDelete"
/>
```

- Props:
  - `modelValue` (Boolean) — 控制显隐
  - `title` (String) — 弹窗标题
  - `message` (String) — 弹窗正文，支持 `<strong>`/`<br>`（用 `v-html`）
  - `danger` (Boolean) — 红色图标 + 红色按钮
  - `confirmText` (String, default `'确认'`)
  - `cancelText` (String, default `'取消'`)
  - `disabled` (Boolean) — 确认按钮 disabled 状态
- 事件：`confirm`（用户点确认时触发，组件自动关闭）
- 复用现有 `.modal-*` 类
- 复用 `<svg>` 图标：danger 用垃圾桶，warning 用警示

**影响页面**：Accounts（删除供应商 + 删除模型 2 处）, Mappings（删除映射 1 处）

### 3.4 Toast

全局消息提示，替换所有 `alert()`。

- 位置：右下角，固定
- 4 种类型：`success`（绿）/ `error`（红）/ `warning`（黄）/ `info`（蓝/indigo）
- 每条自动 3s 消失，可手动关闭（X 按钮）
- 支持队列：多条同时触发时排队显示，每条 3s 间隔
- 调用方式：`app.provide('$toast', toastFn)` 或通过 composable `useToast()` 调用
  ```js
  // 在页面内：
  const toast = inject('$toast')
  toast('保存成功', 'success')
  toast('删除失败: ' + err.message, 'error')
  ```
- 样式：`bg-ls-card border border-ls-border rounded-lg px-4 py-3 shadow-lg`，左侧色条标识类型
- 自动 `body overflow: hidden` 防止滚动

**替换位置（8 处 alert）**：
| 文件 | 位置 | 类型 |
|------|------|------|
| Accounts | 添加校验 | error |
| Accounts | 添加失败 | error |
| Accounts | 保存失败 | error |
| Accounts | 操作失败(toggle) | error |
| Accounts | 删除失败 | error |
| Mappings | 填写校验 | error |
| Mappings | 保存失败 | error |
| Mappings | 删除失败 | error |
| Config | 保存成功 | success |
| Config | 保存失败 | error |

## 4. 代码质量修复

| # | 问题 | 修复方式 |
|---|------|---------|
| 1 | 10 处 `alert()` | 全部替换为 `toast()` 调用 |
| 2 | 手抄内联样式（按钮/标签等） | 迁移到 `.btn` / `.card` / `.tag` / `.action-icon.edit` |
| 3 | `Config.vue` 绕过 `api/` 用原生 `fetch` | 改用 `api.updateConfig()` |
| 4 | Accounts `loadData` 串行请求 models | 改 `Promise.all(suppliers.map(...))` 并发 |
| 5 | `Logs.vue` 硬编码 `ACCOUNT_OPTIONS` / `MODEL_OPTIONS` | 从 API 动态加载供应商和模型列表填充 |
| 6 | `Dashboard` 空 statCard（today 显示 `—`） | 对接 stats API 填充真实数据 |
| 7 | `Test.vue` 假 latency/tokens（`Math.random()`） | 从真实响应中提取或显示 loading 状态 |

## 5. 不做什么

- `CSelect` 不动 — 已完善，5 页在用，重构风险大于收益
- `Sidebar` 不动 — 已独立成组件
- Tailwind/设计 token 不动 — 已完善
- `Stats.vue` mock 数据（heatmap）不动 — 后端数据问题，前端逻辑正确

## 6. 组件依赖关系

```
Toast (顶层, provide 全局)
  ├── PageHeader (纯展示, 无依赖)
  ├── Drawer (纯容器, 无依赖)
  ├── ConfirmModal (纯容器, 无依赖)
  └── 各页面 (依赖上述 3 组件 + CSelect + $toast)
```

所有新组件互相独立，可逐个替换，无级联改动风险。

## 7. 实施顺序

1. Toast 组件（先做，后面步骤要用）
2. PageHeader + 8 页面接入
3. Drawer + Accounts/Mappings 接入
4. ConfirmModal + Accounts/Mappings 接入
5. alert() → toast() 替换
6. 代码质量修复（语义类、Config fetch、串行请求、硬编码选项、Dashboard stat、Test 假数据）
7. 清理（删除不再需要的重复代码，验证所有页面正常）
