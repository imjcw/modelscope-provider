<template>
  <!-- 横向三段：太阳(白天) / 电脑(系统) / 月亮(夜间)，默认选中月亮 -->
  <div class="flex items-center gap-1 bg-transparent rounded-lg border border-ls-border p-1">
    <button v-for="opt in MODES" :key="opt.value" type="button"
      @click="setMode(opt.value)"
      :title="opt.label" :aria-label="opt.label"
      :aria-pressed="currentMode === opt.value"
      class="flex-1 h-7 rounded-md flex items-center justify-center transition-all duration-150"
      :class="currentMode === opt.value
        ? 'bg-ls-accent/10 text-ls-accent'
        : 'text-ls-muted hover:text-ls-text hover:bg-ls-card'">
      <!-- 太阳（线条） -->
      <svg v-if="opt.value === 'light'" width="14" height="14" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
      </svg>
      <!-- 电脑（线条） -->
      <svg v-else-if="opt.value === 'system'" width="14" height="14" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
      <!-- 月亮（线条） -->
      <svg v-else width="14" height="14" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { useTheme } from '@/composables/useTheme.js'

const { currentMode, setMode } = useTheme()

const MODES = [
  { value: 'light', label: '白天' },
  { value: 'system', label: '系统' },
  { value: 'dark', label: '夜间' },
]
</script>
