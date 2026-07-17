# 前端组件抽取与代码优化 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽取 PageHeader / Drawer / ConfirmModal / Toast 四个组件，替换 8 页重复模板，替换所有 alert()，并修复已知代码质量问题。

**Architecture:** 4 个新组件互相独立。Toast 通过 app.provide 全局注册。PageHeader/Drawer/ConfirmModal 是纯容器组件。各页面逐个替换，不产生级联改动。

**Tech Stack:** Vue 3 (Composition API + `<script setup>`), Tailwind CSS, Vite

## Global Constraints

- Vue 3 `<script setup>` 语法，`defineProps`/`defineEmits`
- 样式用现有 `.drawer-*` / `.modal-*` / `.btn` / `.card` / `.tag` / `.action-icon` 全局类（定义在 `web/src/assets/main.css`）
- 组件放在 `web/src/components/`
- API 调用统一走 `web/src/api/index.js`，不直接用 `fetch`（Toast 组件除外）
- 深色主题 token：`--surface` / `--border` / `--accent` / `--bg`（定义在 `main.css`）
- Toast 通过 `app.provide('$toast', toastFn)` 全局注册，页面用 `inject('$toast')`
- 所有新组件保持与现有 CSelect 一致的交互模式（ESC 关闭、点击外部关闭）

---

### Task 1: Toast 组件 + 全局注册

**Files:**
- Create: `web/src/components/Toast.vue`
- Modify: `web/src/main.js:24` (添加 provide)

**Interfaces:**
- Produces: `toast(message, type)` 函数，type ∈ {'success', 'error', 'warning', 'info'}，通过 `app.provide('$toast', ...)` 全局注册

- [ ] **Step 1: 创建 Toast.vue 组件**

在 `web/src/components/Toast.vue` 中创建：

```vue
<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '' },
  type: { type: String, default: 'info' },
  duration: { type: Number, default: 3000 },
})

const emit = defineEmits(['update:visible'])

const timer = ref(null)

const typeStyles = {
  success: { bar: 'bg-green-400', icon: 'text-green-400', bg: 'bg-green-500/10' },
  error:   { bar: 'bg-red-400',   icon: 'text-red-400',   bg: 'bg-red-500/10'   },
  warning: { bar: 'bg-yellow-400', icon: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  info:    { bar: 'bg-[#89b4fa]', icon: 'text-[#89b4fa]',   bg: 'bg-[#89b4fa]/10'   },
}

const clearTimer = () => {
  if (timer.value) { clearTimeout(timer.value); timer.value = null }
}

const close = () => {
  clearTimer()
  emit('update:visible', false)
}

// Watch visible: start auto-close when shown
import { watch } from 'vue'
watch(
  () => props.visible,
  (val) => {
    if (val) {
      clearTimer()
      timer.value = setTimeout(() => close(), props.duration)
    } else {
      clearTimer()
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="toast-enter animate-in"
      :class="typeStyles[type]?.bg || typeStyles.info.bg"
      style="
        position: fixed; right: 24px; bottom: 24px;
        display: flex; align-items: center; gap: 12px;
        padding: 12px 16px; border-radius: 10px;
        border: 1px solid var(--border);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        z-index: 100; max-width: 420px;
        backdrop-filter: blur(8px);
      "
    >
      <div class="w-1 h-8 rounded-full" :class="typeStyles[type]?.bar || typeStyles.info.bar"></div>
      <span class="text-sm text-white flex-1">{{ message }}</span>
      <button @click="close" class="text-gray-500 hover:text-white flex-shrink-0" style="background:none;border:none;cursor:pointer;padding:4px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  </Teleport>
</template>

<style>
@keyframes toastIn {
  from { opacity: 0; transform: translateY(8px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.toast-enter {
  animation: toastIn .2s ease-out;
}
</style>
```

- [ ] **Step 2: 在 main.js 中全局注册 toast**

修改 `web/src/main.js`，在 `createApp(App).use(router).mount('#app')` 之前，注入一个 `provide('$toast', fn)`：

```js
import { ref } from 'vue'

// Toast 全局实例
const toastMessage = ref('')
const toastType = ref('info')
const toastVisible = ref(false)
let toastTimer = null

const toast = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  toastVisible.value = true
}

const app = createApp(App)
app.provide('$toast', toast)

// 在 App.vue 中渲染 <Toast> 组件，通过 app.component 全局注册
app.component('Toast', () => import('./components/Toast.vue'))

// 在挂载前，用 provide 把状态也传进去 —— 改用 inject 模式
// 更简洁：直接在 App.vue 里用 <Toast :message :type :visible>
```

实际上更简洁的方案：在 App.vue 里放 Toast 实例，toast 函数通过 provide 暴露。

修改 `web/src/main.js`：
```js
// 在 createApp 之前
import { createApp, ref, provide } from 'vue'

const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const toast = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  toastVisible.value = true
}
```

修改 `web/src/App.vue`：
```vue
<script setup>
import { inject } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Toast from './components/Toast.vue'

const toastVisible = inject('toastVisible')
const toastMessage = inject('toastMessage')
const toastType = inject('toastType')
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar />
    <main class="flex-1 bg-ls-bg overflow-y-auto min-w-0">
      <router-view />
    </main>
    <Toast v-model:visible="toastVisible" :message="toastMessage" :type="toastType" />
  </div>
</template>
```

修改 `web/src/main.js` 在 createApp 后：
```js
const app = createApp(App)
app.provide('toastVisible', toastVisible)
app.provide('toastMessage', toastMessage)
app.provide('toastType', toastType)
app.provide('$toast', toast)
app.use(router).mount('#app')
```

- [ ] **Step 3: 验证** — 在任意页面 `inject('$toast')` 调用，确认右下角弹出

---

### Task 2: PageHeader 组件 + 8 页面接入

**Files:**
- Create: `web/src/components/PageHeader.vue`
- Modify: `Dashboard.vue`, `Accounts.vue`, `Mappings.vue`, `Logs.vue`, `Stats.vue`, `Alerts.vue`, `Test.vue`, `Config.vue`

**Interfaces:**
- Consumes: 无
- Produces: `<PageHeader title subtitle>` 组件，`#action` slot

- [ ] **Step 1: 创建 PageHeader.vue**

```vue
<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
    <div>
      <h1 class="text-lg font-semibold tracking-tight text-white">{{ title }}</h1>
      <p v-if="subtitle" class="text-xs text-gray-500 mt-0.5">{{ subtitle }}</p>
    </div>
    <div class="flex items-center gap-2">
      <slot name="action"></slot>
    </div>
  </header>
</template>
```

- [ ] **Step 2: 逐个替换 8 个页面的 header**

每个页面：
1. 把 `<template>` 最外层的 `<div>` 内的 `<header>` 整段替换为 `<PageHeader ...>`
2. header 内的内容移到 slot 或 props
3. 添加 `import PageHeader from '@/components/PageHeader.vue'`

以 Accounts.vue 为例：
```vue
<!-- 替换前（删除） -->
<header class="bg-ls-bg/80 backdrop-blur-md ...">
  <div>
    <h1 class="text-lg ...">供应商管理</h1>
    <p class="text-xs ...">添加、编辑和删除 ModelScope 供应商</p>
  </div>
  <button @click="openAdd" class="bg-ls-accent ...">...</button>
</header>

<!-- 替换后 -->
<PageHeader title="供应商管理" subtitle="添加、编辑和删除 ModelScope 供应商">
  <template #action>
    <button @click="openAdd" class="btn btn-primary">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      添加供应商
    </button>
  </template>
</PageHeader>
```

各页面 header 内容映射：

| 页面 | title | subtitle | action slot 内容 |
|------|-------|----------|-----------------|
| Dashboard | "Dashboard" | `{ today }` (computed) | 健康状态标签 |
| Accounts | "供应商管理" | "添加、编辑和删除 ModelScope 供应商" | 添加供应商按钮 |
| Mappings | "模型映射" | "管理模型别名与实际模型 ID 的映射关系" | 添加映射按钮 |
| Logs | "日志" | — | 刷新按钮（注：Logs 标题里有 SVG 图标，放在 title 前或去掉） |
| Stats | "使用统计" | "Token 消耗与模型使用分布" | 时间范围 CSelect |
| Alerts | "告警历史" | "配额耗尽、请求失败等告警记录" | 类型过滤 CSelect |
| Test | "在线测试" | "直接发送请求测试 API 代理" | 无 |
| Config | "系统配置" | "全局参数和服务设置" | 无 |

对于 Logs 页面（header 有 SVG 刷新图标），title 前加 SVG：
```vue
<PageHeader subtitle="刷新">
  <template #title-prefix>
    <svg .../>
  </template>
  <template #action>
    <button class="btn btn-primary" @click="refresh">↻ 刷新</button>
  </template>
</PageHeader>
```

PageHeader 需要加一个 `#title-prefix` slot 支持 SVG。修改 PageHeader：

```vue
<template>
  <header class="...">
    <div class="flex items-center gap-2">
      <slot name="title-prefix"></slot>
      <div>
        <h1 class="...">{{ title }}</h1>
        <p v-if="subtitle" class="...">{{ subtitle }}</p>
      </div>
    </div>
    ...
  </header>
</template>
```

- [ ] **Step 3: 逐个替换并验证** — 8 个页面 header 替换完后，检查无 console error

---

### Task 3: Drawer 组件 + Accounts/Mappings 接入

**Files:**
- Create: `web/src/components/Drawer.vue`
- Modify: `Accounts.vue` (2 处 drawer 替换), `Mappings.vue` (1 处 drawer 替换)

**Interfaces:**
- Consumes: 无
- Produces: `<Drawer v-model :title>` 组件，`#footer` slot

- [ ] **Step 1: 创建 Drawer.vue**

```vue
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '780px' },
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const exiting = ref(false)
const exitingTimer = ref(null)

const close = () => {
  if (exiting.value) return
  exiting.value = true
  exitingTimer.value = setTimeout(() => {
    visible.value = false
    exiting.value = false
  }, 250)
}

const closeImmediate = () => {
  if (exitingTimer.value) clearTimeout(exitingTimer.value)
  visible.value = false
  exiting.value = false
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      visible.value = true
      exiting.value = false
    } else {
      close()
    }
  }
)

const handleEsc = (e) => {
  if (e.key === 'Escape' && visible.value) close()
}

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEsc)
  if (exitingTimer.value) clearTimeout(exitingTimer.value)
})

// 在 visible 变为 true 时注册 ESC 监听
watch(visible, (val) => {
  if (val) document.addEventListener('keydown', handleEsc)
  else document.removeEventListener('keydown', handleEsc)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="drawer-overlay" @click.self="close">
      <div class="drawer drawer-right" :style="{ width: props.width }">
        <div class="drawer-panel" :class="{ 'exiting': exiting }">
          <div class="drawer-header">
            <h2 class="drawer-title">{{ title }}</h2>
            <button @click="close" class="drawer-close btn-esc">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="drawer-body">
            <slot></slot>
          </div>
          <div v-if="$slots.footer" class="drawer-footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 2: 替换 Accounts.vue 的添加/编辑 drawer**

删除 Accounts.vue 中两段 `<Teleport to="body"><div class="drawer-overlay">...</div></Teleport>`（约 86-159 行和 162-253 行），替换为：

```vue
<!-- 添加供应商 Drawer -->
<Drawer v-model="showAddDrawer" title="添加供应商">
  <!-- drawer-body 内容（原 .drawer-body space-y-4 内的所有内容） -->
  <template #footer>
    <button @click="closeAdd" class="btn btn-secondary btn-esc">取消</button>
    <button @click="addSupplier" class="btn btn-primary" :disabled="adding">
      {{ adding ? '添加中...' : '添加' }}
    </button>
  </template>
</Drawer>

<!-- 编辑供应商 Drawer -->
<Drawer v-model="showEditDrawer" title="编辑供应商">
  <!-- drawer-body 内容 -->
  <template #footer>
    <button @click="closeEdit" class="btn btn-secondary btn-esc">取消</button>
    <button @click="saveEdit" class="btn btn-primary" :disabled="saving">
      {{ saving ? '保存中...' : '保存' }}
    </button>
  </template>
</Drawer>
```

对应的 JS：
- `showAddDrawer` / `showEditDrawer` 直接绑定到 Drawer 的 `v-model`，Drawer 内部处理退出动画
- 删除 `addExiting` / `editExiting` ref
- 简化 `closeAdd` / `closeEdit` 为：`showAddDrawer.value = false`（Drawer 内部处理动画）
- 删除 Accounts.vue 中 `<style scoped>.drawer-panel.exiting{...}</style>`（已不需要，退出动画在 Drawer 内部）

- [ ] **Step 3: 替换 Mappings.vue 的 drawer**

同样删除 `<Teleport to="body">` 包裹的 drawer 整段，替换为：

```vue
<Drawer v-model="showFormDrawer" :title="isEditing ? '编辑映射' : '添加映射'">
  <!-- drawer-body 内容 -->
  <template #footer>
    <button @click="closeForm" class="btn btn-secondary btn-esc">取消</button>
    <button @click="submitForm" class="btn btn-primary" :disabled="submitting">
      {{ submitting ? '保存中...' : isEditing ? '保存' : '添加' }}
    </button>
  </template>
</Drawer>
```

删除 `formExiting` ref，简化 `closeForm` 为 `showFormDrawer.value = false`。
删除 Mappings.vue 中 `<style scoped>.drawer-panel.exiting{...}</style>`。

- [ ] **Step 4: 验证** — 打开/关闭 drawer，检查动画、ESC 关闭、点击 backdrop 不关闭（Drawer 用 `@click.self` 但 Drawer 点击 backdrop 会 close，与原来一致吗？原来 drawer-overlay 没有 @click.self，所以 backdrop 不关闭。修改 Drawer：去掉 `@click.self="close"`，只保留 ESC 关闭）

修正 Drawer template 的 `@click.self`：删除，因为原始设计中 backdrop 点击不关闭 drawer。

---

### Task 4: ConfirmModal 组件 + Accounts/Mappings 接入

**Files:**
- Create: `web/src/components/ConfirmModal.vue`
- Modify: `Accounts.vue` (2 处 modal 替换), `Mappings.vue` (1 处 modal 替换)

**Interfaces:**
- Consumes: 无
- Produces: `<ConfirmModal v-model :title :message :danger @confirm>` 组件

- [ ] **Step 1: 创建 ConfirmModal.vue**

```vue
<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '确认' },
  message: { type: String, default: '' },
  danger: { type: Boolean, default: false },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const handleConfirm = () => {
  emit('confirm')
  close()
}

const close = () => {
  emit('update:modelValue', false)
}

const handleEsc = (e) => {
  if (e.key === 'Escape' && props.modelValue) close()
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) document.addEventListener('keydown', handleEsc)
    else document.removeEventListener('keydown', handleEsc)
  }
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEsc)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-overlay" @click.self="close">
      <div class="modal">
        <div class="modal-icon" :class="danger ? 'modal-icon-danger' : 'modal-icon-warning'">
          <svg v-if="danger" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <h3 class="modal-title">{{ title }}</h3>
        <p class="modal-message" v-html="message"></p>
        <div class="modal-actions">
          <button @click="close" class="btn btn-secondary btn-esc">{{ cancelText }}</button>
          <button @click="handleConfirm" class="btn" :class="danger ? 'btn-danger' : 'btn-primary'" :disabled="disabled">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 2: 替换 Accounts.vue 的两个删除确认 modal**

删除 Accounts.vue 中两段 `<Teleport to="body"><div class="modal-overlay">...</div></Teleport>`（约 256-301 行），替换为：

```vue
<!-- 删除供应商确认 -->
<ConfirmModal
  v-model="showDeleteModal"
  title="确认删除"
  :message="`确定要删除供应商 <strong class='text-white'>${deletingSupplier?.name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
  danger
  :confirm-text="deleting ? '删除中...' : '确认删除'"
  :disabled="deleting"
  @confirm="confirmDelete"
/>

<!-- 删除模型确认 -->
<ConfirmModal
  v-model="showModelDeleteModal"
  title="确认删除模型"
  :message="`确定要删除模型 <strong class='text-white font-mono'>${pendingModelDelete?.name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
  danger
  :confirm-text="'确认删除'"
  @confirm="confirmModelDelete"
/>
```

注意：`confirmDelete` 和 `confirmModelDelete` 方法原本会在方法内部 `closeDeleteConfirm()`，现在组件自动关闭，需从方法中移除 `closeDeleteConfirm()` / `closeModelDeleteConfirm()` 调用。

删除 Accounts.vue 中的 `closeDeleteConfirm` / `closeModelDeleteConfirm` 方法（或简化为空）。

- [ ] **Step 3: 替换 Mappings.vue 的删除确认 modal**

删除 `<Teleport to="body">` 包裹的 modal，替换为：

```vue
<ConfirmModal
  v-model="showDeleteModal"
  title="确认删除"
  :message="`确定删除别名 <strong class='text-white'>${deletingItem?.alias_name || ''}</strong> 的映射吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
  danger
  :confirm-text="deleting ? '删除中...' : '确认删除'"
  :disabled="deleting"
  @confirm="confirmDelete"
/>
```

从 `confirmDelete` 方法中移除 `closeDeleteConfirm()` 调用。

- [ ] **Step 4: 验证** — 点击删除按钮，确认弹窗显示、ESC 关闭、confirm 触发

---

### Task 5: 替换所有 alert() 为 toast

**Files:**
- Modify: `Accounts.vue`, `Mappings.vue`, `Config.vue`

**Interfaces:**
- Consumes: `$toast` (from Task 1)

- [ ] **Step 1: Accounts.vue** — 在每个 `<script setup>` 顶部添加 `const toast = inject('$toast')`，然后替换：

```js
// 原: alert('请填写别名和 API Key')
// 改: toast('请填写别名和 API Key', 'error')

// 原: alert('添加失败: ' + (e.response?.data?.detail || e.message || ''))
// 改: toast('添加失败: ' + (e.response?.data?.detail || e.message || ''), 'error')

// 原: alert('保存失败: ' + ...)
// 改: toast('保存失败: ' + ..., 'error')

// 原: alert('操作失败: ' + (e.message || ''))
// 改: toast('操作失败: ' + (e.message || ''), 'error')

// 原: alert('删除失败: ' + (e.message || ''))
// 改: toast('删除失败: ' + (e.message || ''), 'error')
```

- [ ] **Step 2: Mappings.vue** — 同样添加 `const toast = inject('$toast')`，替换 3 处 alert：

```js
alert('请填写别名和实际模型 ID') → toast('请填写别名和实际模型 ID', 'error')
alert('保存失败: ...') → toast('保存失败: ...', 'error')
alert('删除失败: ...') → toast('删除失败: ...', 'error')
```

- [ ] **Step 3: Config.vue** — 添加 `const toast = inject('$toast')`，替换 2 处：

```js
alert('配置已保存') → toast('配置已保存', 'success')
alert('保存失败: ' + e.message) → toast('保存失败: ' + e.message, 'error')
```

- [ ] **Step 4: 验证** — 触发各错误路径，确认 toast 弹出而非 alert

---

### Task 6: Config.vue 改用 api.updateConfig()

**Files:**
- Modify: `web/src/pages/Config.vue`

**Interfaces:**
- Consumes: `updateConfig(config)` from `@/api`

- [ ] **Step 1: 替换 Config.vue 的 saveConfig 方法**

```js
// 替换前:
import { ref } from 'vue'
// ...
await fetch('/api/admin/config', { method: 'PUT', ... })

// 替换后:
import { ref, inject } from 'vue'
import { updateConfig as apiUpdateConfig } from '@/api'
// ...
const toast = inject('$toast')

const saveConfig = async () => {
  const payload = {
    log_level: config.value.logLevel,
    load_balancer_strategy: config.value.lbStrategy,
    request_timeout_ms: String(config.value.timeoutMs),
    retry_count: String(config.value.retryCount),
    auto_disable_on_quota: String(config.value.autoDisable),
    auto_reset_daily: String(config.value.autoReset),
  }
  try {
    await apiUpdateConfig(payload)
    toast('配置已保存', 'success')
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}
```

---

### Task 7: Accounts loadData 串行改并发 + Logs 选项动态加载

**Files:**
- Modify: `web/src/pages/Accounts.vue`, `web/src/pages/Logs.vue`

**Interfaces:**
- Consumes: `getSuppliers()`, `getSupplierModels(id)` from `@/api`

- [ ] **Step 1: Accounts loadData 并发化**

```js
// 原:
for (const s of suppliers.value) {
  try {
    const mRes = await getSupplierModels(s.id)
    s.models = mRes.data || []
  } catch { s.models = [] }
}

// 改:
const modelResults = await Promise.allSettled(
  suppliers.value.map(s => getSupplierModels(s.id))
)
suppliers.value.forEach((s, i) => {
  s.models = modelResults[i].status === 'fulfilled'
    ? (modelResults[i].value.data || [])
    : []
})
```

- [ ] **Step 2: Logs.vue 动态加载供应商/模型选项**

在 Logs.vue 中添加 `loadFilterOptions`，在 `onMounted` 中先加载：

```js
const ACCOUNT_OPTIONS = ref([{ label: '选择供应商', value: '' }])
const MODEL_OPTIONS = ref([{ label: '选择模型', value: '' }])

const loadFilterOptions = async () => {
  try {
    const res = await getSuppliers()
    const sups = res.data || []
    ACCOUNT_OPTIONS.value = [
      { label: '选择供应商', value: '' },
      ...sups.map(s => ({ label: s.name || s.account_id, value: s.account_id || s.id })),
    ]
  } catch { /* 保持默认选项 */ }
}
```

onMounted 改为：
```js
onMounted(async () => {
  await loadFilterOptions()
  loadLogs()
})
```

---

### Task 8: Dashboard 对接真实 stats 数据 + Test 真实响应

**Files:**
- Modify: `web/src/pages/Dashboard.vue`, `web/src/pages/Test.vue`

**Interfaces:**
- Consumes: `getStats(days)`, `getLogs(params)`, `getSuppliers()` from `@/api`

- [ ] **Step 1: Dashboard statCards 对接真实数据**

当前 `statCards.value[3].value = '—'`（avg latency 没对接）。如果 stats API 返回 latency 数据则使用，否则保持从日志估算。当前保留已有逻辑，只确保 no silent `—`：

```js
// statsRes 的数据若有 avg_latency 则使用
if (statsRes.status === 'fulfilled') {
  const s = statsRes.value.data || {}
  statCards.value[3].value = s.avg_latency ? `${s.avg_latency}ms` : '—'
  statCards.value[3].sub = s.avg_latency ? 'avg' : 'no data'
}
```

`acc.today` 从 logs 中统计当天请求数（如果 API 支持的话），否则保持 `—`，标注 "today"。

- [ ] **Step 2: Test.vue 真实 latency/tokens**

```js
// 原:
latency: Math.floor(Math.random() * 500 + 100) + 'ms',
tokens: '1,240',

// 改:
latency: res.headers.get('x-latency-ms') || '—',
tokens: extractTokensFromResponse(text),
```

如果后端不返回这些 header，则从响应 body 中尝试提取 `usage.total_tokens`，否则显示 `—`。

---

### Task 9: 统一使用全局语义类

**Files:**
- Modify: `Accounts.vue`, `Mappings.vue`, `Logs.vue`, `Dashboard.vue`

**Interfaces:**
- Consumes: `.btn` / `.card` / `.tag` / `.action-icon.edit` (from main.css)

- [ ] **Step 1: 按钮样式迁移**

各页面中手抄的 `<button class="bg-ls-accent text-white ...">` 统一改为 `<button class="btn btn-primary">` 或 `<button class="btn btn-secondary">`。

特别注意：
- Accounts 的 "添加供应商" 按钮 → `.btn .btn-primary`
- Mappings 的 "添加映射" 按钮 → `.btn .btn-primary`
- Logs 的 "刷新" 按钮 → `.btn .btn-primary`（需加 SVG 图标）
- 编辑/删除 action-icon → 用 `.action-icon` / `.action-icon.edit`

- [ ] **Step 2: 状态标签迁移**

活跃/禁用标签用 `.tag`：
```vue
<!-- 原: -->
<span class="inline-flex items-center rounded-md px-2 py-0.5 bg-green-500/10 text-green-400 text-xs">
  <span class="w-1.5 h-1.5 rounded-full mr-1.5 bg-green-400"></span>
  活跃
</span>

<!-- 可保留（因为 CSS tag 没带圆点），或者新增 .tag 变体。先不强制迁移，避免过度改动。 -->
```

状态标签（带圆点）结构特殊，`.tag` 类不带圆点，暂不强制替换。只替换纯文字标签。

- [ ] **Step 3: 验证** — 所有按钮视觉一致，无 regressions

---

### Task 10: 最终验证 + 清理

**Files:** 所有修改过的文件

- [ ] **Step 1: 运行前端 dev server 验证所有页面**

```bash
cd /mnt/d/workspace/third/provider/web
npm run dev
```

逐个访问：
- `/` Dashboard — header 正常，stat cards 有数据
- `/suppliers` Accounts — drawer/confirm/toast 正常
- `/mappings` Mappings — drawer/confirm/toast 正常
- `/logs` Logs — header/过滤器/详情 drawer 正常
- `/stats` Stats — header/热力图正常
- `/alerts` Alerts — header/列表正常
- `/test` Test — 请求/响应正常
- `/config` Config — 表单/保存 toast 正常

- [ ] **Step 2: 删除不再需要的重复 CSS**

检查各页面中是否还有 `@keyframes slideOutRight` 等已在 `main.css` 定义的动画，删除页面级 `<style>` 中的冗余。

- [ ] **Step 3: 检查 console error / warning**

确认无 Vue warning、无 unused variable、无 import 未使用。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: extract PageHeader, Drawer, ConfirmModal, Toast components; replace alert() with toast; fix code quality issues"
```
