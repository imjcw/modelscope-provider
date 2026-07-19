# 主题切换（白天 / 夜间 / 系统）设计

> **日期**: 2026-07-19
> **项目**: ModelScope Proxy — web 前端
> **技术栈**: Vue 3 + Tailwind CSS
> **状态**: Draft / 待用户审阅

---

## 1. 目标

为现有暗色 Linear 风格单页应用增加**主题切换**功能，支持三种模式：
- **白天（light）**：切换到 Catppuccin Latte 亮色配色
- **夜间（dark）**：保持当前暗色配色（Catppuccin Mocha）
- **系统（system）**：跟随操作系统偏好，自动切换亮/暗

---

## 2. 需求

| # | 需求 | 说明 |
|---|------|------|
| R1 | **三种主题模式** | 白天 / 夜间 / 系统 |
| R2 | **切换后全页即时生效** | 无需刷新，所有组件颜色、边框、强调色即时更新 |
| R3 | **偏好持久化** | 用户选择存入 localStorage，下次打开自动恢复 |
| R4 | **UI 集成到侧边栏底部** | 侧边栏底部 footer 区域提供切换按钮 |
| R5 | **下拉菜单形式** | 点击图标展开选项，紧凑布局 |

---

## 3. 架构概览

```
┌─────────────────────────────────────────────────┐
│  App.vue                                         │
│  ┌───────────────────────────────────────────┐  │
│  │  <Sidebar />   ← 底部新增主题切换按钮     │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │  <router-view />                    │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  :root { CSS 变量（默认 = Catppuccin Mocha）}   │
│  [data-theme="light"] { 覆盖为 Catppuccin Latte} │
│  [data-theme="system"] { 跟随 prefers-color-scheme } │
│                                                  │
│  web/src/composables/useTheme.js                 │
│  web/src/components/ThemeToggle.vue              │
└─────────────────────────────────────────────────┘
```

**核心机制：** Tailwind 自定义色板 `ls-*` 改为引用 CSS 自定义属性，切换主题只需改变 CSS 变量值，所有 `.bg-ls-bg`、`.text-ls-accent` 等类名自动跟随。

---

## 4. 配色方案

### 4.1 CSS 变量定义（暗色 — 默认，保持现状）

沿用现有 Catppuccin Mocha 配色：

| Token | 语义 | 值 |
|-------|------|----|
| `--ls-bg` | 页面背景 | `#0e0e10` |
| `--ls-card` | 卡片/容器背景 | `#1a1a1e` |
| `--ls-elevated` | 悬浮/嵌入层背景 | `#232329` |
| `--ls-accent` | 主强调色 | `#5e6ad2` |
| `--ls-accentHover` | 强调色 hover 态 | `#6b7bf2` |
| `--ls-border` | 边框颜色 | `#1f1f23` |

### 4.2 CSS 变量定义（亮色 — Catppuccin Latte）

| Token | 语义 | 值 |
|-------|------|----|
| `--ls-bg` | 页面背景 | `#eff1f5` |
| `--ls-card` | 卡片/容器背景 | `#e6e9ef` |
| `--ls-elevated` | 悬浮/嵌入层背景 | `#dce0e8` |
| `--ls-accent` | 主强调色 | `#89b4fa` |
| `--ls-accentHover` | 强调色 hover 态 | `#74c7ec` |
| `--ls-border` | 边框颜色 | `#bcc0cc` |

### 4.3 系统模式（system）

- 读取 `prefers-color-scheme` 系统偏好
- `light` → 应用亮色变量
- `dark` → 应用暗色变量
- 监听系统偏好变化，自动同步

---

## 5. Tailwind 配置改造

`web/tailwind.config.js` 中的 `ls-*` 色板从硬编码十六进制改为引用 CSS 变量：

```js
// 改造前
colors: {
  ls: {
    bg: '#0e0e10',
    card: '#1a1a1e',
    elevated: '#232329',
    accent: '#5e6ad2',
    accentHover: '#6b7bf2',
    border: '#1f1f23',
  },
},

// 改造后
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

**效果：** 所有已存在 `.bg-ls-bg`、`.border-ls-border`、`.text-ls-accent` 等类名无需任何改动，自动跟随 CSS 变量变化。

---

## 6. useTheme composable

新建 `web/src/composables/useTheme.js`：

```js
import { ref, readonly, watch } from 'vue'

// 单例状态
const currentMode = ref(localStorage.getItem('themeMode') || 'dark')
const prefersColorScheme = ref('dark')

export function useTheme() {
  const setMode = (mode) => {
    currentMode.value = mode
    localStorage.setItem('themeMode', mode)
    applyMode()
  }

  function applyMode() {
    const mode = currentMode.value
    let brightness = 'dark'
    
    if (mode === 'light') {
      brightness = 'light'
    } else if (mode === 'system') {
      brightness = prefersColorScheme.value === '' ? 'light' : prefersColorScheme.value
    } else {
      brightness = 'dark'
    }
    
    document.documentElement.dataset.themeMode = mode
    document.documentElement.dataset.theme = brightness
  }

  // 监听系统偏好变化
  watch(() => prefersColorScheme.value, (newVal) => {
    if (currentMode.value === 'system') {
      applyMode()
    }
  })

  return {
    currentMode: readonly(currentMode),
    prefersColorScheme: readonly(prefersColorScheme),
    setMode,
  }
}
```

**设计要点：**
- `data-theme-mode` 标识用户选择（light/dark/system）
- `data-theme` 标识当前实际亮度（light/dark）
- 系统模式自动监听系统偏好变化并同步

---

## 7. ThemeToggle 组件

新建 `web/src/components/ThemeToggle.vue`。

### 7.1 UI 结构

```
┌──────────────────────────────┐
│  ☀️/🌙/💻  明暗切换 (select)  │  ← 线条 icon
├──────────────────────────────┤
│  ☀️ 白天    🌙 夜间    💻 系统 │
└──────────────────────────────┘
```

### 7.2 显示逻辑

- 渲染为侧边栏底部 footer 区域的切换按钮
- 点击图标展开下拉菜单，显示三个选项：白天 / 夜间 / 系统
- 当前模式显示在下拉菜单外（如标签），切换后即时生效，无页面刷新

### 7.3 集成位置

在 Sidebar.vue 底部 footer 区域加入主题切换按钮，放在 `v0.2.0 · 运行中` 旁边。

---

## 8. 改造文件清单

### 8.1 新建文件

| 文件 | 说明 |
|------|------|
| `web/src/composables/useTheme.js` | 主题状态管理 |
| `web/src/components/ThemeToggle.vue` | 主题切换 UI 组件 |

### 8.2 修改文件

| 文件 | 改动 |
|------|------|
| `web/tailwind.config.js` | `ls-*` 色板改为 CSS 变量引用（~6 行） |
| `web/src/assets/main.css` | 追加 CSS 变量定义（~20 行） + 亮色主题覆盖 |
| `web/src/components/Sidebar.vue` | 侧边栏 footer 区域加入主题切换按钮 |

### 8.3 无需修改的文件

所有使用 `.bg-ls-*`、`.border-ls-*`、`.text-ls-*` 等 Tailwind 类的页面组件——因 Tailwind 色板改为 CSS 变量引用后，这些类**自动跟随**主题变化，无需逐文件修改。

---

## 9. 用户故事

1. **首次使用**：应用默认显示暗色主题（当前状态）
2. **切换为白天**：用户点击侧边栏主题按钮 → 展开下拉 → 点击白天 → 页面瞬间切换为亮色模式
3. **切换为夜间**：用户点击侧边栏主题按钮 → 展开下拉 → 点击夜间 → 页面切换为暗色模式
4. **切换为系统**：用户点击侧边栏主题按钮 → 展开下拉 → 点击系统 → 页面跟随操作系统偏好自动切换
5. **刷新保持**：关闭浏览器重新打开 → 上次选择的主题模式自动恢复
6. **主题不冲突**：白天/夜间切换后，所有页面的布局、功能、交互保持不变

---

## 10. 未覆盖范围（明确不做）

- 不修改现有页面的布局结构
- 不做主题自定义（用户自选颜色）
- 不做动画过渡（颜色切换保持瞬时）
- 不改变现有导航结构和路由
- 不使用 emoji，全部使用线条 SVG icon

---

## 11. 附录：Catppuccin Latte 配色参考

```css
/* 亮色模式下的 CSS 变量映射 */
[data-theme="light"] {
  --ls-bg: #eff1f5;
  --ls-card: #e6e9ef;
  --ls-elevated: #dce0e8;
  --ls-accent: #89b4fa;
  --ls-accentHover: #74c7ec;
  --ls-border: #bcc0cc;
}
```
