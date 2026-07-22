<script setup>
import { inject } from 'vue'
const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
const sidebarOpen = inject('sidebarOpen', null)
function toggleSidebar() {
  if (sidebarOpen) sidebarOpen.value = true
}
</script>

<template>
  <header class="sticky top-0 z-30 bg-ls-shell/90 backdrop-blur-md border-b border-ls-border px-6 md:px-8 py-3">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <button @click="toggleSidebar"
                class="lg:hidden p-1.5 -ml-1.5 text-ls-dim hover:text-ls-accent rounded-md hover:bg-ls-accent/5 transition-colors flex-shrink-0"
                aria-label="菜单">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <slot name="title-prefix" />
        <div class="min-w-0">
          <h1 class="text-lg uppercase tracking-wider text-ls-text">{{ title }}</h1>
          <p v-if="subtitle" class="text-xs text-ls-muted mt-0.5 truncate max-w-[200px] lg:max-w-none">{{ subtitle }}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <slot name="action" />
      </div>
    </div>
  </header>
</template>
