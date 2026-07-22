# Responsive Design Implementation Plan (Pad Tier)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ModelScope Provider admin dashboard responsive for Pad (768–1024px). Desktop stays unchanged. Phone is out of scope.

**Architecture:** Single `lg:` (1024px) breakpoint. Below 1024px, Sidebar collapses to a teleported drawer, Drawers go full-screen, LogDetailPanel stacks vertically with collapsible stats, and tables get horizontal scroll wrappers. Tables do NOT become card lists — Pad width accommodates them with horizontal scrolling.

**Tech Stack:** Vue 3, Tailwind CSS v3.4, Vite 5 — no new dependencies.

## Global Constraints

- **Single breakpoint:** Tailwind `lg:` (1024px) is the ONLY breakpoint used
- **Zero desktop regression:** Every new class is scoped to `lg:` below; existing desktop classes remain untouched
- **No new npm dependencies**
- **Dark theme CSS variables unchanged** (`:root` vars in main.css)
- **Hash routing unchanged** (`createWebHashHistory`)
- **Tables keep native `<table>` markup** — wrapped in `overflow-x-auto` below lg, no card-list conversion

---

## File Structure

```
web/src/
├── App.vue                          [MODIFY] — sidebar state + lg condition
├── assets/
│   └── main.css                     [MODIFY] — .drawer-full utility only
├── components/
│   ├── Sidebar.vue                  [MODIFY] — extract SidebarNav
│   ├── SidebarDrawer.vue            [CREATE] — Pad teleported drawer
│   ├── SidebarNav.vue               [CREATE] — shared nav links
│   ├── PageHeader.vue               [MODIFY] — hamburger + action wrap
│   └── Drawer.vue                   [MODIFY] — mobileFull + isMobile
└── pages/
    ├── Logs.vue                     [MODIFY] — table scroll wrapper + filter responsive
    ├── Mappings.vue                 [MODIFY] — table scroll wrapper
    ├── Accounts.vue                 [MODIFY] — table scroll wrapper
    ├── LogDetailPanel.vue           [MODIFY] — fullscreen stacked + stats collapse
    ├── Dashboard.vue                [MODIFY] — SVG preserveAspectRatio
    ├── Config.vue                   [MODIFY] — breakpoint shift
    └── Test.vue                     [MODIFY] — breakpoint shift
```

---

## Task 1: Drawer-Full CSS Utility

**Files:**
- Modify: `web/src/assets/main.css`

**Produces:** `.drawer-full` class consumed by Task 6 (Drawer.vue).

- [ ] **Step 1: Add utility class at end of main.css**

```css
/* === Responsive: drawer full-screen on Pad/mobile === */
.drawer-full {
  width: 100% !important;
  max-width: 100%;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/assets/main.css
git commit -m "feat(responsive): add drawer-full CSS utility"
```

---

## Task 2: SidebarNav Shared Component

**Files:**
- Create: `web/src/components/SidebarNav.vue`
- Modify: `web/src/components/Sidebar.vue`

**Produces:** `SidebarNav` component used by both inline Sidebar and teleported SidebarDrawer.

- [ ] **Step 1: Create SidebarNav.vue**

```vue
<template>
  <nav class="px-2 mt-2 space-y-0.5 flex-1">
    <router-link to="/" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      仪表盘
    </router-link>
    <router-link to="/suppliers" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
      供应商管理
    </router-link>
    <router-link to="/mappings" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      虚拟模型
    </router-link>
    <router-link to="/logs" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      请求日志
    </router-link>
    <router-link to="/alerts" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      告警历史
    </router-link>
    <router-link to="/test" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      在线测试
    </router-link>
    <router-link to="/guide" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14"/>
        <path d="M9 12h6"/><path d="M9 16h4"/>
      </svg>
      使用指南
    </router-link>
    <router-link to="/keys" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="8" cy="15" r="5"/><path d="M11.5 11.5L21 2"/><path d="M16 7l3 3"/>
      </svg>
      API Keys
    </router-link>
    <router-link to="/config" class="nav-item" @click="select">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06"/>
      </svg>
      系统配置
    </router-link>
  </nav>
</template>

<script setup>
defineEmits(['select'])
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-2.5 px-2.5 py-1.5 text-sm text-gray-400 hover:text-white hover:bg-ls-card rounded-md transition-colors;
}
.router-link-active {
  @apply bg-ls-card text-white;
}
</style>
```

- [ ] **Step 2: Refactor Sidebar.vue to use SidebarNav**

Replace the entire `<nav class="px-2 mt-2 space-y-0.5 flex-1">...</nav>` block (lines 18–80) with `<SidebarNav @select="() => {}" />`.

Add to `<script setup>`:

```js
import SidebarNav from './SidebarNav.vue'
```

The full Sidebar.vue template becomes:

```vue
<template>
  <aside class="w-56 bg-ls-bg border-r border-ls-border flex flex-col flex-shrink-0 h-screen">
    <div class="px-5 py-5">
      <div class="flex items-center gap-2.5">
        <div class="w-7 h-7 rounded-lg bg-[#0c0c0c] border border-gray-800 flex items-center justify-center font-bold text-[11px] tracking-tight">
          <span class="text-ls-accent">A</span><span class="text-[#89b4fa]">P</span>
        </div>
        <span class="font-semibold tracking-tight text-sm">
          <span class="text-ls-accent">A</span><span class="text-white">I</span>
          <span class="text-white">&nbsp;</span>
          <span class="text-[#89b4fa]">P</span><span class="text-white">rovider</span>
        </span>
      </div>
    </div>
    <SidebarNav @select="() => {}" />
    <div class="px-4 py-3 border-t border-ls-border">
      <div class="flex items-center gap-2">
        <div class="w-2 h-2 rounded-full bg-ls-accent"></div>
        <span class="text-xs text-gray-500">v0.2.0 · 运行中</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import SidebarNav from './SidebarNav.vue'
</script>
```

- [ ] **Step 3: Verify build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add web/src/components/SidebarNav.vue web/src/components/Sidebar.vue
git commit -m "feat(responsive): extract SidebarNav shared component"
```

---

## Task 3: SidebarDrawer (Pad) + App Wiring + PageHeader Hamburger

**Files:**
- Create: `web/src/components/SidebarDrawer.vue`
- Modify: `web/src/App.vue`
- Modify: `web/src/components/PageHeader.vue`

**Proposes:** Teleported sidebar drawer below lg + state management in App + hamburger in PageHeader.

- [ ] **Step 1: Create SidebarDrawer.vue**

```vue
<template>
  <Teleport to="body">
    <div v-if="modelValue" class="fixed inset-0 z-40 lg:hidden">
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="close"></div>
      <aside class="absolute top-0 left-0 bottom-0 w-56 bg-ls-bg border-r border-ls-border
                    flex flex-col transform transition-transform duration-200"
             :class="isOpen ? 'translate-x-0' : '-translate-x-full'">
        <div class="px-5 py-5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-[#0c0c0c] border border-gray-800 flex items-center justify-center font-bold text-[11px] tracking-tight">
              <span class="text-ls-accent">A</span><span class="text-[#89b4fa]">P</span>
            </div>
            <span class="font-semibold tracking-tight text-sm">
              <span class="text-ls-accent">A</span><span class="text-white">I</span>
              <span class="text-white">&nbsp;</span>
              <span class="text-[#89b4fa]">P</span><span class="text-white">rovider</span>
            </span>
          </div>
        </div>
        <SidebarNav @select="close" />
        <div class="px-4 py-3 border-t border-ls-border">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-ls-accent"></div>
            <span class="text-xs text-gray-500">v0.2.0 · 运行中</span>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import SidebarNav from './SidebarNav.vue'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const isOpen = ref(false)

watch(() => props.modelValue, (val) => {
  if (val) requestAnimationFrame(() => { isOpen.value = true })
  else isOpen.value = false
})

function close() {
  emit('update:modelValue', false)
}
</script>
```

- [ ] **Step 2: Modify App.vue**

Current:
```vue
<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar />
    <main class="flex-1 bg-ls-bg overflow-y-auto min-w-0">
      <router-view />
    </main>
    <Toast />
  </div>
</template>

<script setup>
import Sidebar from '@/components/Sidebar.vue'
import Toast from '@/components/Toast.vue'
</script>
```

Replace with:
```vue
<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar class="hidden lg:flex" />
    <main class="flex-1 bg-ls-bg overflow-y-auto min-w-0">
      <router-view />
    </main>
    <Toast />
  </div>
  <SidebarDrawer v-model="sidebarOpen" />
</template>

<script setup>
import { ref, provide } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import SidebarDrawer from '@/components/SidebarDrawer.vue'
import Toast from '@/components/Toast.vue'

const sidebarOpen = ref(false)
provide('sidebarOpen', sidebarOpen)
</script>
```

- [ ] **Step 3: Modify PageHeader.vue — add hamburger + action wrap**

Add `inject` import and `toggleSidebar` function to `<script setup>`:

```js
import { inject } from 'vue'
const props = defineProps({
  title: String,
  subtitle: { type: String, default: '' },
})
const sidebarOpen = inject('sidebarOpen', null)
function toggleSidebar() {
  if (sidebarOpen) sidebarOpen.value = true
}
```

Modify the header's left block:

```html
<header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-4 py-3 lg:px-6 flex items-center justify-between sticky top-0 z-10">
  <div class="flex items-center gap-2 min-w-0">
    <button @click="toggleSidebar"
            class="lg:hidden p-1.5 -ml-1.5 text-gray-400 hover:text-white rounded-md hover:bg-ls-card transition-colors flex-shrink-0"
            aria-label="菜单">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>
    <slot name="title-prefix" />
    <div class="min-w-0">
      <h1 class="text-lg font-semibold tracking-tight text-white">{{ title }}</h1>
      <p v-if="subtitle" class="text-xs text-gray-500 mt-0.5 truncate max-w-[200px] lg:max-w-none">{{ subtitle }}</p>
    </div>
  </div>
  <div class="flex items-center gap-2.5 flex-wrap">
    <slot name="action" />
  </div>
</header>
```

Note: existing header padding is `px-6 py-3`. Add `px-4 lg:px-6` to give slightly tighter mobile padding.

- [ ] **Step 4: Verify build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add web/src/components/SidebarDrawer.vue web/src/App.vue web/src/components/PageHeader.vue
git commit -m "feat(responsive): add Pad sidebar drawer + hamburger toggle"
```

---

## Task 4: Tables — Horizontal Scroll Wrappers

**Files:**
- Modify: `web/src/pages/Logs.vue`
- Modify: `web/src/pages/Mappings.vue`
- Modify: `web/src/pages/Accounts.vue`

**Produces:** Tables scroll horizontally below lg instead of clipping. Filter bar widths made flexible in Logs.

- [ ] **Step 1: Logs.vue — replace fixed-width filter controls**

In the filter bar (lines 29–48), replace inner fixed-width wrappers:

```html
<!-- Before: <div class="w-56"> -->
<!-- After:  <div class="flex-1 min-w-0 lg:w-56"> -->
```

Full filter bar:
```html
<div class="flex flex-wrap gap-3 mb-5 items-center">
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">时间</label>
    <div class="flex-1 min-w-0 lg:w-56"><DateRangePicker @update="onTimeChange" /></div>
  </div>
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">供应商</label>
    <div class="flex-1 min-w-0 lg:w-36"><CSelect v-model="filters.accountId" :options="ACCOUNT_OPTIONS" size="sm" placeholder="选择供应商" /></div>
  </div>
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">模型</label>
    <div class="flex-1 min-w-0 lg:w-36"><CSelect v-model="filters.model" :options="MODEL_OPTIONS" size="sm" placeholder="选择模型" /></div>
  </div>
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">状态</label>
    <div class="flex-1 min-w-0 lg:w-20"><CSelect v-model="filters.statusCode" :options="STATUS_CODE_OPTIONS" size="sm" placeholder="全部" /></div>
  </div>
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">流式</label>
    <div class="flex-1 min-w-0 lg:w-20"><CSelect v-model="filters.isStream" :options="STREAM_OPTIONS" size="sm" placeholder="全部" /></div>
  </div>
</div>
```

- [ ] **Step 2: Logs.vue — wrap table in horizontal scroll**

Change the table wrapper from:
```html
<div v-else class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
```
To:
```html
<div v-else class="bg-ls-card rounded-lg border border-ls-border overflow-hidden overflow-x-auto">
```

This single class addition makes the table scroll horizontally below its container's width.

- [ ] **Step 3: Mappings.vue — wrap table in horizontal scroll**

Change the table wrapper (line 23) from:
```html
<div v-if="mappings.length > 0" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
```
To:
```html
<div v-if="mappings.length > 0" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden overflow-x-auto">
```

- [ ] **Step 4: Accounts.vue — wrap table in horizontal scroll**

In the table view section (~line 159), find:
```html
<div v-if="viewMode === 'table'" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
```
Change to:
```html
<div v-if="viewMode === 'table'" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden overflow-x-auto">
```

- [ ] **Step 5: Verify build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Logs.vue web/src/pages/Mappings.vue web/src/pages/Accounts.vue
git commit -m "feat(responsive): tables get horizontal scroll + flexible filters on Pad"
```

---

## Task 5: LogDetailPanel — Full-Screen Stacked Layout

**Files:**
- Modify: `web/src/pages/LogDetailPanel.vue`

**Produces:** Full-screen drawer below lg, vertical stacking, collapsible stats header on Pad.

- [ ] **Step 1: Modify drawer container width**

Current (line 7):
```html
<div v-show="modelValue" class="fixed top-0 right-0 bottom-0 w-[1300px] bg-ls-bg border-l border-ls-border z-50 flex flex-col shadow-2xl"
     :class="showDrawer ? 'translate-x-0' : 'translate-x-full'"
     :style="{ transition: 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)' }">
```

Replace with:
```html
<div v-show="modelValue" class="fixed inset-0 lg:inset-y-0 lg:right-0 lg:w-[900px] bg-ls-bg border-l border-ls-border z-50 flex flex-col shadow-2xl"
     :class="showDrawer ? 'translate-x-0' : 'translate-x-full'"
     :style="{ transition: 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)' }">
```

- [ ] **Step 2: Add mobile detection + statsExpanded ref to script**

Add to `<script setup>`:

```js
const statsExpanded = ref(false)

const isMobile = ref(false)
onMounted(() => {
  const mq = window.matchMedia('(max-width: 1023px)')
  isMobile.value = mq.matches
  const handler = (e) => { isMobile.value = e.matches }
  mq.addEventListener('change', handler)
  onUnmounted(() => mq.removeEventListener('change', handler))
})
```

- [ ] **Step 3: Modify body layout to stack vertically on Pad**

Current (line 32):
```html
<div class="flex-1 flex overflow-hidden">
```
Replace with:
```html
<div class="flex-1 flex flex-col lg:flex-row overflow-hidden">
```

- [ ] **Step 4: Modify stats panel to be collapsible**

Current (line 302):
```html
<div class="w-80 flex-shrink-0 border-l border-ls-border overflow-y-auto bg-ls-card">
```

Replace with:
```html
<div class="w-full lg:w-80 flex-shrink-0 border-t lg:border-t-0 lg:border-l border-ls-border overflow-y-auto bg-ls-card"
     :class="statsExpanded ? 'max-h-[60vh]' : 'max-h-[52px] lg:max-h-none'">
  <button @click="statsExpanded = !statsExpanded"
          class="lg:hidden w-full flex items-center justify-between p-3 text-left">
    <div class="flex items-center gap-4 text-xs">
      <span class="text-gray-400">延迟: <span class="text-white font-mono">{{ modelValue.latency_ms ? formatDuration(modelValue.latency_ms) : '-' }}</span></span>
      <span class="text-gray-400">Token: <span class="text-white font-mono">{{ ((modelValue.input_tokens || 0) + (modelValue.output_tokens || 0)).toLocaleString() }}</span></span>
    </div>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
         class="text-gray-400 transition-transform" :class="statsExpanded ? 'rotate-180' : ''">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  </button>
  <div :class="statsExpanded ? 'block' : 'hidden lg:block'">
```

And after the stats panel's closing `</div>` (line 389), wrap all the existing stats content inside the `<div :class="statsExpanded ? 'block' : 'hidden lg:block'">` block. The final structure is:

```html
<div class="w-full lg:w-80 ...">
  <button class="lg:hidden ...">...</button>
  <div :class="statsExpanded ? 'block' : 'hidden lg:block'">
    <!-- 模型信息 -->
    <div class="p-4 border-b border-ls-border">...</div>
    <!-- Token -->
    <div class="p-4 border-b border-ls-border">...</div>
    <!-- 请求时序 -->
    <div class="p-4 border-b border-ls-border">...</div>
    <!-- 性能指标 -->
    <div class="p-4 border-b border-ls-border">...</div>
    <!-- 响应头 -->
    <div v-if="responseHeaders" class="p-4 border-b border-ls-border">...</div>
  </div>
</div>
```

- [ ] **Step 5: Adjust padding on Pad**

Header (line 13) — add tighter padding:
```html
<div class="flex items-center justify-between px-4 py-3 lg:px-5 border-b border-ls-border bg-ls-card flex-shrink-0">
```

Conversation area (line 35):
```html
<div class="flex-1 overflow-y-auto p-3 lg:p-5">
```

- [ ] **Step 6: Verify build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/LogDetailPanel.vue
git commit -m "feat(responsive): LogDetailPanel fullscreen stacked + collapsible stats on Pad"
```

---

## Task 6: Drawer.vue — Mobile Full-Screen

**Files:**
- Modify: `web/src/components/Drawer.vue`

**Produces:** All Drawer instances go full-screen on Pad by default.

- [ ] **Step 1: Add isMobile + mobileFull to Drawer.vue**

Add to `<script setup>`:

```js
const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '' },
  width: { type: String, default: '780px' },
  mobileFull: { type: Boolean, default: true },
})

const isMobile = ref(false)
onMounted(() => {
  const mq = window.matchMedia('(max-width: 1023px)')
  isMobile.value = mq.matches
  const handler = (e) => { isMobile.value = e.matches }
  mq.addEventListener('change', handler)
  onUnmounted(() => mq.removeEventListener('change', handler))
})
```

- [ ] **Step 2: Modify drawer-right container**

Current:
```html
<div class="drawer drawer-right" :style="{ width: props.width }">
```

Replace with:
```html
<div class="drawer drawer-right"
     :class="{ 'drawer-full': mobileFull && isMobile }"
     :style="(mobileFull && isMobile) ? {} : { width: props.width }">
```

- [ ] **Step 3: Verify build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add web/src/components/Drawer.vue
git commit -m "feat(responsive): Drawer fullscreen on Pad"
```

---

## Task 7: Remaining Pages (Dashboard, Config, Test) + Final Verification

**Files:**
- Modify: `web/src/pages/Dashboard.vue`
- Modify: `web/src/pages/Config.vue`
- Modify: `web/src/pages/Test.vue`

**Produces:** SVG chart scaling fix, breakpoint shifts for grid layouts, final build verification.

- [ ] **Step 1: Dashboard.vue — fix SVG chart scaling**

Locate `<svg>` chart elements. Add `preserveAspectRatio="xMidYMid meet"` to prevent distortion on narrower viewports:

```html
<svg preserveAspectRatio="xMidYMid meet" viewBox="..." ...>
```

If SVGs currently use `preserveAspectRatio="none"`, change to `"xMidYMid meet"`.

- [ ] **Step 2: Config.vue — shift breakpoint**

Change `lg:grid-cols-2` to `md:grid-cols-2` so Pad gets two-column layout.

- [ ] **Step 3: Test.vue — shift breakpoint**

Change `lg:grid-cols-2` to `md:grid-cols-2`.

- [ ] **Step 4: Final build**

Run: `cd web && npm run build`
Expected: Build succeeds with no warnings

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Dashboard.vue web/src/pages/Config.vue web/src/pages/Test.vue
git commit -m "feat(responsive): Dashboard SVG scaling + Config/Test Pad breakpoint"
```

---

## Task 8: Final Verification

**Files:** none modified (read-only verification)

- [ ] **Step 1: Build**

Run: `cd web && npm run build`
Expected: `✓ built in X.XXs`

- [ ] **Step 2: Visual check**

Open `http://localhost:5173` in browser DevTools. Test at:
- 768px (iPad Mini): sidebar drawer works, tables scroll horizontally, drawer fullscreen, log panel stacked with collapsible stats
- 1024px (iPad Pro landscape): sidebar permanent, transition clean
- 1440px (desktop): completely unchanged from before

---

## Dependency Map

```
Task 1 (CSS .drawer-full) ──────────────┐
                                         ▼
Task 2 (SidebarNav) ──────────────► Task 3 (SidebarDrawer + App + PageHeader)
                                         │
Task 4 (table scroll wrappers)           │
Task 5 (LogDetailPanel)                  │
Task 6 (Drawer fullscreen) ◄── Task 1 ───┤
Task 7 (other pages)                     │
                                         ▼
Task 8 (verify)
```

Tasks 4–7 are independent and can run in parallel.
