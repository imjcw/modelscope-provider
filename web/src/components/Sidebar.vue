<template>
  <aside class="fixed top-0 left-0 bottom-0 w-60 bg-ls-shell border-r border-ls-border flex flex-col z-40">
    <!-- Logo -->
    <div class="px-6 py-5 border-b border-ls-border flex items-center gap-2.5">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--ls-accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="4" r="2"/>
        <circle cx="4" cy="20" r="2"/>
        <circle cx="20" cy="20" r="2"/>
        <circle cx="12" cy="12" r="2"/>
        <line x1="12" y1="6" x2="12" y2="10"/>
        <line x1="5.5" y1="18.5" x2="10.5" y2="13.5"/>
        <line x1="18.5" y1="18.5" x2="13.5" y2="13.5"/>
      </svg>
      <span class="font-bold tracking-tight text-lg">
        <span class="text-ls-accent">A</span><span class="text-ls-text">I</span>
        <span class="text-ls-text">&nbsp;<span class="text-ls-fuchsia">P</span>rovider</span>
      </span>
    </div>

    <!-- Nav（分组标签在 SidebarNav 内，SidebarDrawer 共用） -->
    <div class="flex-1 px-3 py-4 overflow-y-auto">
      <SidebarNav @select="() => {}" />
    </div>

    <!-- Footer：主题切换 -->
    <div class="border-t border-ls-border px-3 py-4">
      <ThemeToggle />
    </div>
  </aside>
</template>

<script setup>
import SidebarNav from './SidebarNav.vue'
import ThemeToggle from './ThemeToggle.vue'
</script>
