<script setup>
const props = defineProps({
  modelValue: { type: String, default: 'row' },
})
const emit = defineEmits(['update:modelValue'])

const VIEW_OPTIONS = [
  { value: 'row', label: '卡片行' },
  { value: 'grid', label: '网格卡片' },
  { value: 'table', label: '表格' },
]

const select = (v) => emit('update:modelValue', v)
</script>

<template>
  <div class="flex items-center gap-1 bg-transparent rounded-lg border border-ls-border p-1">
    <button v-for="opt in VIEW_OPTIONS" :key="opt.value"
      class="flex-1 h-7 rounded-md flex items-center justify-center transition-all duration-150"
      :class="modelValue === opt.value
        ? 'bg-ls-accent/10 text-ls-accent'
        : 'text-ls-muted hover:text-ls-text hover:bg-ls-card'"
      @click="select(opt.value)" :title="opt.label">
      <!-- 卡片行 -->
      <svg v-if="opt.value === 'row'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/>
      </svg>
      <!-- 网格卡片 -->
      <svg v-if="opt.value === 'grid'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      <!-- 表格 -->
      <svg v-if="opt.value === 'table'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="12" y1="3" x2="12" y2="21"/>
      </svg>
    </button>
  </div>
</template>