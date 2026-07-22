<template>
  <aside class="fixed top-0 left-0 bottom-0 w-60 bg-ls-shell border-r border-ls-border flex flex-col z-40">
    <!-- Logo -->
    <div class="px-6 py-5 border-b border-ls-border flex items-center gap-2">
      <span class="font-bold tracking-tight text-lg">
        <span class="gradient-neon">AI</span>
        <span class="text-ls-text"> Provider</span>
      </span>
    </div>

    <!-- Nav（分组标签在 SidebarNav 内，SidebarDrawer 共用） -->
    <div class="flex-1 px-3 py-4 overflow-y-auto">
      <SidebarNav @select="() => {}" />
    </div>

    <!-- Footer：用户块（demo 布局）+ 版本 + 主题切换 -->
    <div class="border-t border-ls-border px-3 py-4">
      <div class="flex items-center gap-3 px-3 mb-3">
        <div class="w-7 h-7 rounded-lg bg-ls-border border border-ls-borderLight flex items-center justify-center text-xs font-medium text-ls-text">J</div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-ls-text truncate">imjcw</p>
          <p class="text-xs text-ls-muted truncate">admin@modelscope.ai</p>
        </div>
      </div>
      <div class="flex items-center gap-2 mb-2">
        <div class="w-2 h-2 rounded-full bg-green-400"></div>
        <span class="text-xs text-ls-muted">v0.2.0 · 运行中</span>
      </div>
      <ThemeToggle />
    </div>
  </aside>
</template>

<script setup>
import SidebarNav from './SidebarNav.vue'
import ThemeToggle from './ThemeToggle.vue'
</script>
