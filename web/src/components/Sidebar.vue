<template>
  <aside class="w-56 bg-ls-bg border-r border-ls-border flex flex-col flex-shrink-0 h-screen">
    <!-- Logo -->
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

    <!-- Navigation -->
    <SidebarNav @select="() => {}" />

    <!-- Footer -->
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

<style scoped>
</style>
