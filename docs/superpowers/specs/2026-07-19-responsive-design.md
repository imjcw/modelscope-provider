# Frontend 响应式适配设计规格

**日期**: 2026-07-19
**状态**: 已定稿
**范围**: Web 前端（Vue 3 + Tailwind CSS），13 文件

---

## 1. 背景与目标

### 1.1 当前状态

ModelScope Provider 管理后台是一个 Catppuccin 暗色风格的全手写组件 Web 应用，目前**完全无移动端适配**：

- Sidebar 固定 224px — 在 320px 手机上占 70% 屏幕
- 表格 6–10 列，无横向滚动兜底
- LogDetailPanel 固定 1300px — 超过任何移动/Pad 视口
- Drawer 默认 780px — Pad 上勉强、手机上溢出
- 筛选栏内元素固定宽度（w-56, w-36, w-20）

### 1.2 目标

| 维度 | 目标 |
|------|------|
| 使用场景 | 中间路线 — 浏览/查看/状态切换优先，复杂编辑桌面端做 |
| Pad（768–1024px） | 侧边栏收合为抽屉，图表不变形，双列 grid |
| 手机（< 768px） | 全屏抽屉，表格变卡片列表，详情面板堆叠 |
| 桌面（≥1024px） | 保持原样零回归 |
| 实现策略 | 分四阶段交付，每阶段独立可测 |

### 1.3 技术约束

- 不引入新 npm 依赖
- 不改变桌面端现有 class / 行为
- 单一断点 `lg:`（1024px）分界
- CSS 变量（暗色主题）不变
- Hash 路由不变

---

## 2. 核心设计决策

### 2.1 断点策略

采用 Tailwind 默认 `lg:` 断点（1024px）作为唯一分界：

| 范围 | 模式 | 侧边栏 | 表格 | 抽屉 | 详情面板 |
|------|------|--------|------|------|---------|
| ≥ 1024px | 桌面 | 固定 224px | 原生 table | 780px 侧抽 | 900px 双栏 |
| < 1024px | 移动/Pad | 覆盖式抽屉 | 纵向卡片列表 | 全屏 | 全屏堆叠 |

**为什么不拆成 sm/md/lg 三档？** Pad（768–1024px）与手机有相同诉求（侧边栏需收合、表格需简化），用单一断点降低复杂度。

### 2.2 表格 → 卡片：双渲染模式

在模板中写两套 `v-for`，通过 `hidden lg:block` / `lg:hidden` 互斥切换：

```html
<table class="hidden lg:block">
  <tr v-for="item in data" @click="open(item)">...</tr>
</table>
<div class="lg:hidden space-y-3">
  <div v-for="item in data" class="card-list-item" @click="open(item)">
    <!-- 卡片内容 -->
  </div>
</div>
```

**为什么不用 JS 动态切换？** 避免 hydration mismatch 风险，无需新 composable，与现有 Tailwind 习惯一致。

**性能考量：** pageSize=20，双渲染仅 40 条 DOM，现代浏览器完全无感。

### 2.3 侧边栏：双组件策略

| 组件 | 渲染位置 | 可见条件 | 行为 |
|------|---------|---------|------|
| `Sidebar.vue`（现有） | flex 内联 | `hidden lg:flex` | 固定 224px，永不收合 |
| `SidebarDrawer.vue`（新建） | Teleport to body | `lg:hidden` + v-model | 覆盖式抽屉，背景遮罩 |

内部导航结构抽取为 `SidebarNav` 被两者复用，避免重复。

### 2.4 抽屉全屏（mobileFull prop）

```js
// Drawer.vue 新增
const props = defineProps({
  mobileFull: { type: Boolean, default: true },
})
const isMobile = useMatchMedia('(max-width: 1023px)')
```

模板：
```html
<div class="drawer-right"
     :class="{ 'drawer-full': mobileFull && isMobile }"
     :style="!(mobileFull && isMobile) ? { width: props.width } : {}">
```

- `mobileFull=true`（默认）：移动端忽略 width prop 全屏
- `mobileFull=false`：保持自定义 width（未来扩展用）
- 已有 ESC 关闭、遮罩点击关闭逻辑不变

### 2.5 详情面板：fullscreen + stacked

**布局变化：**

```html
<div class="fixed inset-0 lg:inset-y-0 lg:right-0 lg:w-[900px]">
  <div class="flex-1 flex flex-col lg:flex-row overflow-hidden">
    <div class="flex-1 overflow-y-auto">  <!-- 对话 -->
    <div class="w-full lg:w-80">          <!-- 统计 -->
  </div>
</div>
```

**统计面板可折叠（新增）：**

移动端默认只显示摘要行（延迟 + Token 总数），点击展开显示完整统计信息。桌面端始终展开。

---

## 3. 各页面详细设计

### 3.1 App.vue

```
当前: <div class="flex h-screen overflow-hidden">
        <Sidebar />
        <main class="flex-1">...</main>
      </div>

改造: <div class="flex h-screen overflow-hidden">
        <Sidebar class="hidden lg:flex" />
        <main class="flex-1 overflow-y-auto min-w-0">
          <router-view />
        </main>
      </div>
      <SidebarDrawer v-model="sidebarOpen" class="lg:hidden" />
```

新增 `sidebarOpen = ref(false)`，PageHeader 的汉堡按钮通过 provide/inject 或 emit 触发。

### 3.2 SidebarDrawer.vue（新建）

```html
<Teleport to="body">
  <div v-if="modelValue" class="fixed inset-0 z-40 lg:hidden">
    <!-- 遮罩 -->
    <div class="absolute inset-0 bg-black/50 backdrop-blur-sm"
         @click="close"></div>
    <!-- 抽屉面板 -->
    <aside class="absolute top-0 left-0 bottom-0 w-56 bg-ls-bg border-r border-ls-border
                  flex flex-col transform transition-transform"
           :class="isOpen ? 'translate-x-0' : '-translate-x-full'">
      <!-- header logo 区域 -->
      <!-- SidebarNav 组件 -->
      <!-- footer 版本区域 -->
    </aside>
  </div>
</Teleport>
```

### 3.3 PageHeader.vue

```html
<header>
  <div class="flex items-center gap-2">
    <button class="lg:hidden" @click="$emit('toggle-sidebar')">☰</button>
    <slot name="title-prefix" />
    <h1>{{ title }}</h1>
    <p class="truncate lg:truncate-none">{{ subtitle }}</p>
  </div>
  <div class="flex items-center gap-2.5 flex-wrap">
    <slot name="action" />
  </div>
</header>
```

### 3.4 Logs.vue

**筛选栏：**
- 移除 `w-56`、`w-36`、`w-20`
- 改为 `min-w-0 flex-1` 或 `w-full sm:w-auto`

**卡片内容（每条日志）：**
```
┌─────────────────────────────────────────────────┐
│ 2026-07-19 14:23:01              [200]          │
│ claude-sonnet-4 · Anthropic                     │
│ req_abc123def...                                │
│ Input: 1,234   Output: 567   Cache: 890         │
│ 延迟 1,234ms  │  [P] 流式                       │
└─────────────────────────────────────────────────┘
```

取舍：保留 时间/状态/模型/请求ID/Token/延迟/流式，舍弃 Cache 拆分展示。

### 3.5 Mappings.vue

**卡片内容：**
```
┌─────────────────────────────────────────────────┐
│ claude-sonnet-4              [● 已启用]          │
│ 用于代码生成的虚拟模型描述...                      │
│ [3 个模型]              创建于 2026-07-19         │
│ [📋 日志]  [✏️ 编辑]  [🗑 删除]                   │
└─────────────────────────────────────────────────┘
```

### 3.6 Accounts.vue

仅 table 视图需添加卡片列表；row/grid 视图已有 `sm:`/`lg:` 响应式。

**卡片内容：**
```
┌─────────────────────────────────────────────────┐
│ [A] Anthropic                [● 已启用]          │
│ ak_xxxx****abcd                                │
│ ████████████░░░░ 72%  │  配额 1,000,000         │
│ 5 个模型  [查看用量]  [✏️] [🗑]                   │
└─────────────────────────────────────────────────┘
```

### 3.7 LogDetailPanel.vue

见 2.5 节。抽屉宽度从 1300px 降为 900px（桌面），手机端全屏。

### 3.8 其余页面

| 页面 | 改动 |
|------|------|
| Dashboard.vue | SVG `preserveAspectRatio="xMidYMid meet"` |
| Config.vue | `lg:grid-cols-2` → `md:grid-cols-2` |
| Test.vue | 同上 |
| Guide.vue | `<pre>` 加 `overflow-x-auto` |
| Alerts.apiKeys | 验证已有断点无需改动 |

---

## 4. CSS 工具类（main.css 新增）

```css
/* === 卡片列表 === */
.card-list-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color .15s;
}
.card-list-item:active { border-color: var(--accent); }
.card-list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.card-list-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: .05em;
}

/* === 抽屉全屏 === */
.drawer-full { width: 100% !important; max-width: 100%; }
```

---

## 5. 实施阶段

### Phase 1：全局响应式骨架
- App.vue 添加 Sidebar 状态管理
- SidebarDrawer.vue 新建
- PageHeader 集成汉堡按钮
- 验证：375px 视口下滑动侧边栏可开闭

### Phase 2：表格卡片化
- Logs.vue、Mappings.vue、Accounts.vue 添加卡片视图
- main.css 添加卡片工具类
- 验证：表格在 lg 以下显示为卡片，点击仍打开详情

### Phase 3：详情面板 + 抽屉全屏
- LogDetailPanel 全屏堆叠 + 统计折叠
- Drawer.vue 添加 mobileFull + isMobile
- 验证：手机端表单全屏、详情面板堆叠

### Phase 4：其余页面 + 测试
- Dashboard/Config/Test/Guide 微调
- 全视口回归测试（375/768/1024/1440px）

---

## 6. 测试矩阵

| 视口 | 验证项 |
|------|--------|
| 375px | 侧边栏抽屉、表格卡片、分页、抽屉全屏、日志详情堆叠 |
| 768px | 侧边栏抽屉、表格卡片、图表不变形、双列 grid、抽屉全屏 |
| 1024px | 侧边栏永久展开、布局过渡无突变 |
| 1440px | 桌面端零回归 |

---

## 7. 文件变更清单

| # | 文件 | 阶段 | 性质 |
|---|------|------|------|
| 1 | `App.vue` | P1 | 添加 lg 条件包裹 + 侧边栏状态 |
| 2 | `Sidebar.vue` | P1 | 拆出 SidebarNav 为可复用部分 |
| 3 | `SidebarDrawer.vue` | P1 | **新建** |
| 4 | `PageHeader.vue` | P1 | 集成汉堡按钮 + action 换行 |
| 5 | `Drawer.vue` | P3 | mobileFull + isMobile |
| 6 | `Logs.vue` | P2 | 卡片列表 + 筛选栏响应式 |
| 7 | `LogDetailPanel.vue` | P3 | 全屏堆叠 + 统计折叠 |
| 8 | `Mappings.vue` | P2 | 卡片列表 |
| 9 | `Accounts.vue` | P2 | table 视图卡片列表 |
| 10 | `Dashboard.vue` | P4 | SVG preserveAspectRatio |
| 11 | `Config.vue` | P4 | 断点下移 |
| 12 | `Test.vue` | P4 | 断点下移 |
| 13 | `main.css` | P2/P4 | 工具类 + drawer-full |

---

## 8. 风险与回退

| 风险 | 概率 | 缓解 |
|------|------|------|
| 桌面端被意外覆盖 | 极低 | 所有改动仅 `lg:` 以下生效，桌面 class 不变 |
| 双渲染性能 | 极低 | pageSize=20，双渲染仅 40 条 DOM |
| Teleport z-index 冲突 | 低 | 已有系统验证过层级，新增统一用 z-40/z-50 |
| matchMedia SSR 报错 | 无 | 非 SSR 应用，静态文件 hash 路由 |

---

## 9. 不在范围内

- 后端 API 改动
- 新增页面或功能
- 暗色/亮色主题切换
- 复杂拖拽交互在触摸设备上的适配（"中间路线"决策）
- 服务端渲染或 PWA
