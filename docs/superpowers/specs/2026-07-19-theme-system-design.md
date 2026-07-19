# 多主题 + 明暗切换系统设计

> **日期:** 2026-07-19
> **项目:** ModelScope Proxy — web 前端
> **状态:** Draft / 待用户审阅

---

## 1. 目标

为现有的 Vue 3 + Tailwind CSS 单页应用（当前使用 Linear 暗色风格）增加**主题切换**和**明暗模式**功能，使用户可以在不改变页面结构和行为的前提下，切换整个应用的视觉风格。

---

## 2. 需求

| # | 需求 | 说明 |
|---|------|------|
| R1 | **多主题切换** | 支持 3 套主题：Linear、Cyberpunk Neon、Playful |
| R2 | **每套主题有亮/暗模式** | 主题与明暗是两个独立维度，3×2=6 套完整配色 |
| R3 | **切换后全页即时生效** | 无需刷新，所有组件颜色、边框、强调色即时更新 |
| R4 | **偏好持久化** | 用户选择存入 localStorage，下次打开自动恢复 |
| R5 | **切换 UI 集成到设置** | 通过设置页面/侧边栏提供切换入口 |
| R6 | **图标统一为线条 SVG** | 切换 UI 及主题相关组件均使用 stroke 风格线条 SVG icon，不使用 emoji |

---

## 3. 架构概览

```
┌─────────────────────────────────────────────────┐
│  App.vue                                         │
│  ┌───────────────────────────────────────────┐  │
│  │  <Sidebar />   ← 侧边栏（含主题切换入口） │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │  <router-view />                    │  │  │
│  │  │  （各页面使用 ls-* token，自动换肤） │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  :root { CSS 变量（默认 = Linear Dark） }        │
│  [data-theme="cyberpunk"] { 覆盖变量 }           │
│  [data-brightness="light"] { 覆盖变量 }          │
│                                                  │
│  tailwind.config.js → ls-* 色板 = var(--ls-*)    │
│  main.css → 主题特效层                           │
└─────────────────────────────────────────────────┘
```

**核心机制：** Tailwind 自定义色板 `ls-*` 改为引用 CSS 自定义属性，切换主题只需改变 CSS 变量值，所有 `.bg-ls-bg`、`.text-ls-accent` 等类名自动跟随。

---

## 4. 配色方案

### 4.1 CSS 变量定义

| Token | 语义 |
|-------|------|
| `--ls-bg` | 页面背景 |
| `--ls-card` | 卡片/容器背景 |
| `--ls-elevated` | 悬浮/嵌入层背景（比 card 更深/更浅一层） |
| `--ls-accent` | 主强调色（按钮、链接、激活态） |
| `--ls-accentHover` | 强调色 hover 态 |
| `--ls-border` | 边框颜色 |

### 4.2 6 套配色（3 主题 × 2 明暗）

| Token | Linear Dark (默认) | Linear Light | Cyberpunk Dark | Cyberpunk Light | Playful Dark | Playful Light (默认) |
|-------|-------------------|-------------|---------------|-----------------|-------------|---------------------|
| `--ls-bg` | `#0e0e10` | `#ffffff` | `#0a0a0f` | `#e8eef0` | `#0f0f14` | `#f7f3e8` |
| `--ls-card` | `#1a1a1e` | `#f5f5f7` | `#13131a` | `#cdd5d8` | `#1a1a20` | `#ffffff` |
| `--ls-elevated` | `#232329` | `#ececef` | `#1f1f2e` | `#bcc7cb` | `#25252d` | `#fffde7` |
| `--ls-accent` | `#5e6ad2` | `#5e6ad2` | `#00ffff` | `#00b8d4` | `#ff6b6b` | `#ff6b6b` |
| `--ls-accentHover` | `#6b7bf2` | `#4a56b8` | `#33ffff` | `#00c8e0` | `#ff4444` | `#ff4444` |
| `--ls-border` | `#1f1f23` | `#e0e0e3` | `#2a2a3e` | `#9bb0b8` | `#2a2a35` | `#000000` |

### 4.3 CSS 变量源码结构

```css
/* 默认 = Linear Dark */
:root {
  --ls-bg: #0e0e10;
  --ls-card: #1a1a1e;
  --ls-elevated: #232329;
  --ls-accent: #5e6ad2;
  --ls-accentHover: #6b7bf2;
  --ls-border: #1f1f23;
}

/* ── Linear Light ── */
[data-theme="linear"][data-brightness="light"] {
  --ls-bg: #ffffff;
  --ls-card: #f5f5f7;
  --ls-elevated: #ececef;
  --ls-accent: #5e6ad2;
  --ls-accentHover: #4a56b8;
  --ls-border: #e0e0e3;
}

/* ── Cyberpunk Dark (默认) ── */
[data-theme="cyberpunk"] {
  --ls-bg: #0a0a0f;
  --ls-card: #13131a;
  --ls-elevated: #1f1f2e;
  --ls-accent: #00ffff;
  --ls-accentHover: #33ffff;
  --ls-border: #2a2a3e;
}

/* ── Cyberpunk Light ── */
[data-theme="cyberpunk"][data-brightness="light"] {
  --ls-bg: #e8eef0;
  --ls-card: #cdd5d8;
  --ls-elevated: #bcc7cb;
  --ls-accent: #00b8d4;
  --ls-accentHover: #00c8e0;
  --ls-border: #9bb0b8;
}

/* ── Playful Dark ── */
[data-theme="playful"][data-brightness="dark"] {
  --ls-bg: #0f0f14;
  --ls-card: #1a1a20;
  --ls-elevated: #25252d;
  --ls-accent: #ff6b6b;
  --ls-accentHover: #ff4444;
  --ls-border: #2a2a35;
}

/* ── Playful Light (默认) ── */
[data-theme="playful"] {
  --ls-bg: #f7f3e8;
  --ls-card: #ffffff;
  --ls-elevated: #fffde7;
  --ls-accent: #ff6b6b;
  --ls-accentHover: #ff4444;
  --ls-border: #000000;
}
```

---

## 5. Tailwind 配置改造

`web/tailwind.config.js` 中的 `ls-*` 色板从硬编码十六进制改为引用 CSS 变量：

```js
// 改造前
colors: {
  ls: {
    bg: '#0e0e10',
    card: '#1a1a1e',
    // ...
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

## 6. 主题特效层

颜色和 token 解决 ~80% 的换肤。每套主题特有的视觉特效通过 CSS 注入，通过 `data-theme` 选择器控制。

### 6.1 Cyberpunk 特效

```css
/* Cyberpunk 暗色：扫描线 + 霓虹光晕 */
[data-theme="cyberpunk"][data-brightness="dark"] body::after {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,255,255,0.015) 2px, rgba(0,255,255,0.015) 4px
  );
}

[data-theme="cyberpunk"] .card-glow:hover {
  box-shadow: 0 0 15px rgba(0,255,255,0.1), 0 0 30px rgba(255,0,255,0.05);
}

/* Cyberpunk 亮色：扫描线（更淡） */
[data-theme="cyberpunk"][data-brightness="light"] body::after {
  /* 同结构，opacity 降低 */
}
```

### 6.2 Playful 特效

```css
/* Playful 暗色：粗边框硬阴影保留（亮色默认已有） */
[data-theme="playful"] .card-style {
  border-width: 1px;
  box-shadow: none;
}

[data-theme="playful"] .card-style {
  border-width: 4px;
  box-shadow: 6px 6px 0px currentColor; /* 硬阴影风格 */
}
```

### 6.3 特效层策略

- **不修改现有组件的 class**，仅通过 `data-theme` 选择器为已有类名增强样式
- 如果组件需要 Playful 特有的旋转/偏移效果（`rotate-[-1deg]`），需要为该类名添加 `[data-theme="playful"]` 下的规则
- **Cyberpunk 扫描线**作用于 `body::after`，影响全页面
- 所有特效均使用 Tailwind 兼容的类名或已有 HTML 结构

---

## 7. useTheme composable

新建 `web/src/composables/useTheme.js`：

```js
import { ref, readonly } from 'vue'

const THEMES = ['linear', 'cyberpunk', 'playful']

// 单例状态
const currentTheme = ref(localStorage.getItem('theme') || 'linear')
const currentBrightness = ref(localStorage.getItem('brightness') || 'dark')

export function useTheme() {
  /**
   * 主题列表（显示用）
   * 格式: [{ key: 'linear', label: 'Linear', icon }]
   */
  const themes = THEMES.map((key) => {
    const labelMap = {
      linear: 'Linear',
      cyberpunk: 'Cyberpunk',
      playful: 'Playful',
    }
    return { key, label: labelMap[key] }
  })

  const setTheme = (key) => {
    currentTheme.value = key
    document.documentElement.dataset.theme = key
    localStorage.setItem('theme', key)
    applyBrightness()
  }

  const toggleBrightness = () => {
    currentBrightness.value =
      currentBrightness.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('brightness', currentBrightness.value)
    applyBrightness()
  }

  function applyBrightness() {
    // Linear 暗色为默认，不需要设置 data-brightness
    const isDefaultDark =
      currentTheme.value === 'linear' && currentBrightness.value === 'dark'
    const isDefaultLight =
      currentTheme.value === 'playful' && currentBrightness.value === 'light'

    if (isDefaultDark || isDefaultLight) {
      document.documentElement.removeAttribute('data-brightness')
    } else {
      document.documentElement.dataset.brightness = currentBrightness.value
    }
  }

  // 初始化
  applyBrightness()

  return {
    themes: readonly(themes),
    currentTheme: readonly(currentTheme),
    currentBrightness: readonly(currentBrightness),
    setTheme,
    toggleBrightness,
  }
}
```

**设计要点：**
- `data-theme` 和 `data-brightness` 是两个独立的 DOM 属性
- 当主题+明暗组合等于默认值时，移除 `data-brightness` 以匹配 CSS `:root`（最精简）
- 使用单例模式（模块级 ref）确保全应用状态一致

---

## 8. ThemeSelector 组件

新建 `web/src/components/ThemeSelector.vue`。

### 8.1 显示逻辑

- 渲染为一个下拉面板：点击 icon 按钮展开
- 内容分为两部分：
  - **明暗切换**：单行 toggle，切换当前主题的亮/暗
  - **主题选择**：三列卡片列表（Linear / Cyberpunk / Playful），选中项高亮

### 8.2 UI 结构

```
┌──────────────────────────────┐
│  ☀️/🌙  明暗切换 (toggle)    │  ← 线条 icon
├──────────────────────────────┤
│  ┌────┐  ┌────┐  ┌────┐     │
│  │ 🟦 │  │ 🌙 │  │ 🎨 │     │  ← 选中的高亮
│  │Linear│Cyberpunk│Playful│  │
│  └────┘  └────┘  └────┘     │
└──────────────────────────────┘
```

**注意：所有 icon 使用线条 SVG，禁止 emoji。** 实际渲染用 stroke 风格的线条 icon。

### 8.3 集成位置

提供两种集成方式（择一或都提供）：

1. **侧边栏底部**：在 Sidebar 的 footer 区域加入主题切换按钮（小 icon）
2. **配置页面**：在 Config.vue 页面新增「外观」区块

---

## 9. 改造文件清单

### 9.1 新建文件

| 文件 | 说明 |
|------|------|
| `web/src/composables/useTheme.js` | 主题/明暗状态管理 |
| `web/src/components/ThemeSelector.vue` | 主题切换 UI 组件 |

### 9.2 修改文件

| 文件 | 改动 |
|------|------|
| `web/tailwind.config.js` | `ls-*` 色板改为 CSS 变量引用（~6 行） |
| `web/src/assets/main.css` | 追加 CSS 变量定义（~30 行） + 主题特效层 |
| `web/src/components/Sidebar.vue` | 侧边栏 footer 区域加入主题切换按钮 |
| `web/src/pages/Config.vue` | 新增「外观」区块（可选） |

### 9.3 无需修改的文件

所有使用 `.bg-ls-*`、`.border-ls-*`、`.text-ls-*` 等 Tailwind 类的页面组件——因 Tailwind 色板改为 CSS 变量引用后，这些类**自动跟随**主题变化，无需逐文件修改。

---

## 10. 图标规范

- **全部使用线条 SVG icon**（`stroke` 风格），禁止 emoji
- icon 尺寸统一 `16×16`（`w-4 h-4`）
- icon 颜色跟随 `currentColor` 或主题 accent
- 主题切换相关的 icon：
  - 🌙 暗色 → 月亮线条 icon（`<path d="M20 14.5C.../>`）
  - ☀️ 亮色 → 太阳线条 icon（`<circle> + <line>`）
  - 主题卡片的预览 icon：用对应主题的代表色填充方块 + 主题名文字

---

## 11. 用户故事

1. **首次使用**：应用默认显示 Linear 暗色主题（当前状态）
2. **切换主题**：用户点击侧边栏主题按钮 → 展开下拉 → 点击 Cyberpunk → 页面瞬间切换为 Cyberpunk 暗色
3. **切换明暗**：用户点击明暗 toggle → 当前主题切换亮色模式
4. **刷新保持**：关闭浏览器重新打开 → 上次选择的主题和明暗自动恢复
5. **主题不冲突**：3 套主题切换后，所有页面的布局、功能、交互保持不变

---

## 12. 未覆盖范围（明确不做）

- 不修改现有页面的布局结构
- 不为每套主题创建独立的 CSS 文件（统一在 `main.css` 中管理）
- 不做主题自定义（用户自选颜色）
- 不做动画过渡（颜色切换保持瞬时）
- 不改变现有导航结构和路由
