# 主题切换（白天 / 夜间 / 系统）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ModelScope Proxy 前端添加白天/夜间/系统三种主题切换，切换后全页颜色即时生效。

**Architecture:** 核心机制是将 Tailwind `ls-*` 色板改为引用 CSS 自定义属性，切换时只改变 CSS 变量值，所有 `.bg-ls-bg`、`.text-ls-accent` 等类自动跟随。主题状态由 `useTheme` composable 管理，切换 UI 为侧边栏底部下拉按钮。

**Tech Stack:** Vue 3 + Tailwind CSS 3.4 + Vite

## Global Constraints

- 亮色配色必须使用 Catppuccin Latte（`--ls-bg: #eff1f5`, `--ls-card: #e6e9ef` 等）
- 暗色配色保持当前 Catppuccin Mocha（`--ls-bg: #0e0e10` 等）
- 切换 UI 必须放在侧边栏底部 footer 区域
- 切换形式必须是下拉菜单（`<select>` 或自定义下拉），三个选项：☀️ 白天 / 🌙 夜间 / 💻 系统
- 偏好持久化到 `localStorage`，key 为 `themeMode`
- 系统模式必须监听 `prefers-color-scheme` 变化自动同步
- 图标统一使用线条 SVG，禁止 emoji
- 颜色切换瞬时生效，不做动画过渡
- 不修改现有页面布局和路由

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `web/src/composables/useTheme.js` | 新建 | 主题状态管理 composable |
| `web/src/components/ThemeToggle.vue` | 新建 | 下拉切换 UI 组件 |
| `web/src/assets/main.css` | 修改 | 追加亮色 CSS 变量覆盖 + `@media` 查询 |
| `web/tailwind.config.js` | 修改 | `ls-*` 色板改为 CSS 变量引用 |
| `web/src/components/Sidebar.vue` | 修改 | 底部 footer 区域加入 ThemeToggle |

---

## Task 1: Tailwind 色板改造为 CSS 变量引用

**这是整个方案的根基**——只有把 Tailwind 色板改成 `var(--ls-*)` 形式，后续才只需要改 CSS 变量就能换肤。

- [ ] **Step 1: 修改 `web/tailwind.config.js`**

将 `ls` 色板中的硬编码 hex 改为 CSS 变量引用：

```js
colors: {
  ls: {
    bg: 'var(--ls-bg)',
    card: 'var(--ls-card)',
    elevated: 'var(--ls-elevated)',
    accent: 'var(--ls-accent)',
    accentHover: 'var(--ls-accentHover)',
    border: 'var(--ls-border)',
  },
},
```

- [ ] **Step 2: 在 `web/src/assets/main.css` 中定义暗色 CSS 变量**

在 `:root` 中追加（已有 `:root` 块，在其内部或旁边新增 `--ls-*` 变量）：

```css
:root {
  --ls-bg: #0e0e10;
  --ls-card: #1a1a1e;
  --ls-elevated: #232329;
  --ls-accent: #5e6ad2;
  --ls-accentHover: #6b7bf2;
  --ls-border: #1f1f23;
}
```

- [ ] **Step 3: 验证无回归**

运行 `npm run build` 确认无编译错误，页面暗色外观不变。

- [ ] **Step 4: Commit**

```bash
git add web/tailwind.config.js web/src/assets/main.css
git commit -m "chore(theme): convert Tailwind ls-* tokens to CSS variables"
```

---

## Task 2: useTheme composable

**Files:**
- Create: `web/src/composables/useTheme.js`

**Interfaces:**
- Produces: `useTheme()` 返回 `{ currentMode, prefersColorScheme, setMode }`
  - `currentMode`: readonly ref, 值域 `"light" | "dark" | "system"`
  - `prefersColorScheme`: readonly ref, 值域 `"light" | "dark"`
  - `setMode(mode)`: 切换主题模式，同步 `localStorage` 和 `data-theme` 属性

- [ ] **Step 1: 创建 `web/src/composables/useTheme.js`**

```js
import { ref, readonly, watch, onMounted, onUnmounted } from 'vue'

// 单例状态
const currentMode = ref(localStorage.getItem('themeMode') || 'dark')
const prefersColorScheme = ref('dark')

function getSystemTheme() {
  return (
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark'
  )
}

function applyTheme() {
  const mode = currentMode.value
  let brightness = 'dark'

  if (mode === 'light') {
    brightness = 'light'
  } else if (mode === 'system') {
    brightness = prefersColorScheme.value
  } else {
    brightness = 'dark'
  }

  document.documentElement.setAttribute('data-theme', brightness)
}

function onSystemThemeChange(e) {
  prefersColorScheme.value = e.matches ? 'light' : 'dark'
}

export function useTheme() {
  onMounted(() => {
    // 初始化系统主题检测
    prefersColorScheme.value = getSystemTheme()
    applyTheme()

    // 监听系统偏好变化
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
      mediaQuery.addEventListener('change', onSystemThemeChange)
      onUnmounted(() => mediaQuery.removeEventListener('change', onSystemThemeChange))
    }
  })

  // 当 system 模式下系统主题变化时自动同步
  watch(prefersColorScheme, () => {
    if (currentMode.value === 'system') {
      applyTheme()
    }
  })

  const setMode = (mode) => {
    currentMode.value = mode
    localStorage.setItem('themeMode', mode)
    applyTheme()
  }

  return {
    currentMode: readonly(currentMode),
    prefersColorScheme: readonly(prefersColorScheme),
    setMode,
  }
}
```

- [ ] **Step 2: 验证**

在浏览器 DevTools Console 中测试：

```js
// 切换为亮色
import { useTheme } from './src/composables/useTheme.js'
// 手动测试 data-theme 是否正确设置
document.documentElement.getAttribute('data-theme') // 应为 'light' 或 'dark'
```

- [ ] **Step 3: Commit**

```bash
git add web/src/composables/useTheme.js
git commit -m "feat(theme): add useTheme composable with localStorage persistence"
```

---

## Task 3: 亮色 CSS 变量覆盖

**Files:**
- Modify: `web/src/assets/main.css`

- [ ] **Step 1: 在 `web/src/assets/main.css` 底部追加亮色覆盖规则**

```css
/* ── 亮色主题（Catppuccin Latte）─ */
[data-theme="light"] {
  --ls-bg: #eff1f5;
  --ls-card: #e6e9ef;
  --ls-elevated: #dce0e8;
  --ls-accent: #89b4fa;
  --ls-accentHover: #74c7ec;
  --ls-border: #bcc0cc;
}

/* ── 亮色主题下的额外覆盖（白色背景相关）─ */
[data-theme="light"] .sidebar-bg {
  background: var(--ls-bg);
}

/* ── 亮色主题下的文字颜色覆盖（暗色下默认白字）─ */
[data-theme="light"] .text-white {
  color: #4c4f69;
}
[data-theme="light"] .text-gray-400 {
  color: #6c7086;
}
[data-theme="light"] .text-gray-500 {
  color: #8c8fa1;
}
```

- [ ] **Step 2: 验证**

手动设置 `<html data-theme="light">`，观察页面颜色是否变为亮色。

- [ ] **Step 3: Commit**

```bash
git add web/src/assets/main.css
git commit -m "style(theme): add Catppuccin Latte light theme CSS variables"
```

---

## Task 4: ThemeToggle 组件

**Files:**
- Create: `web/src/components/ThemeToggle.vue`

**Interfaces:**
- Consumes: `useTheme()` from `@/composables/useTheme.js`
- Emits: 无

- [ ] **Step 1: 创建 `web/src/components/ThemeToggle.vue`**

```vue
<template>
  <div class="theme-toggle">
    <select
      class="theme-select"
      :value="currentMode.value"
      @change="handleChange"
    >
      <option value="light">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <circle cx="12" cy="12" r="4"/>
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
        </svg>
        白天
      </option>
      <option value="dark">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
        夜间
      </option>
      <option value="system">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        系统
      </option>
    </select>
  </div>
</template>

<script setup>
import { useTheme } from '@/composables/useTheme.js'

const { currentMode, setMode } = useTheme()

const handleChange = (e) => {
  setMode(e.target.value)
}
</script>

<style scoped>
.theme-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  background: var(--ls-card);
  border: 1px solid var(--ls-border);
  border-radius: 6px;
  padding: 4px 22px 4px 8px;
  font-size: 11px;
  color: var(--text-dim);
  cursor: pointer;
  transition: all .15s;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
}
.theme-select:hover {
  border-color: var(--ls-accent);
  color: var(--text);
}
.theme-select:focus {
  outline: none;
  border-color: var(--ls-accent);
  box-shadow: 0 0 0 2px var(--ring);
}
</style>
```

- [ ] **Step 2: 验证**

在开发服务器中观察组件是否渲染正确，切换选项时 `localStorage` 是否更新，`data-theme` 是否正确设置。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ThemeToggle.vue
git commit -m "feat(theme): add ThemeToggle component"
```

---

## Task 5: 集成到 Sidebar

**Files:**
- Modify: `web/src/components/Sidebar.vue`

- [ ] **Step 1: 修改 `web/src/components/Sidebar.vue`**

在 footer 区域（`v0.2.0 · 运行中` 旁边）加入 `ThemeToggle`：

```html
<!-- Footer -->
<div class="px-4 py-3 border-t border-ls-border">
  <div class="flex items-center gap-2 mb-2">
    <div class="w-2 h-2 rounded-full bg-ls-accent"></div>
    <span class="text-xs text-gray-500">v0.2.0 · 运行中</span>
  </div>
  <ThemeToggle />
</div>
```

并在 script 中 import：

```js
import ThemeToggle from './ThemeToggle.vue'
```

- [ ] **Step 2: 验证**

开发服务器中观察侧边栏底部是否显示切换按钮，切换白天/夜间/系统是否生效。

- [ ] **Step 3: 完整功能测试**

1. 首次加载 → 默认暗色
2. 切换为白天 → 全页变为亮色
3. 切换为系统 → 跟随 OS 偏好
4. 刷新页面 → 上次选择恢复
5. 修改 localStorage `themeMode` 为 `"light"` → 刷新后应为亮色

- [ ] **Step 4: Commit**

```bash
git add web/src/components/Sidebar.vue
git commit -m "feat(theme): integrate ThemeToggle into sidebar footer"
```

---

## Task 6: 全局初始化（可选优化）

确保页面加载时主题就已经生效（避免闪屏）：

- [ ] **Step 1: 在 `web/src/main.js` 顶部同步应用初始主题**

在 `import App` 之后、`createApp` 之前，从 localStorage 读取并应用 `data-theme`，避免浏览器重绘时的主题闪烁：

```js
// 同步应用初始主题，避免闪屏
(function initTheme() {
  const saved = localStorage.getItem('themeMode')
  if (!saved) return
  let brightness = 'dark'
  if (saved === 'light') {
    brightness = 'light'
  } else if (saved === 'system') {
    brightness = window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  document.documentElement.setAttribute('data-theme', brightness)
})()
```

- [ ] **Step 2: Commit**

```bash
git add web/src/main.js
git commit -m "chore(theme): apply theme synchronously on initial load to prevent flash"
```

---

## Self-Review

1. **Spec coverage:** ✅ 三种模式（白天/夜间/系统）、localStorage 持久化、系统模式监听、侧边栏集成、Catppuccin Latte 配色均已覆盖
2. **Placeholder scan:** ✅ 无 TBD/TODO，所有步骤包含完整代码
3. **Type consistency:** ✅ `useTheme` 接口在 Task 2 定义，Task 4/5 使用，签名一致
4. **YAGNI:** ✅ 不做动画、不做主题自定义、不改页面布局

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-07-19-theme-toggle-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间 review，快速迭代

**2. Inline Execution** — 在本会话中按顺序执行所有 Task，带 checkpoint

Which approach?
