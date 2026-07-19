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
  <div class="view-toggle">
    <button v-for="opt in VIEW_OPTIONS" :key="opt.value"
      :class="['view-toggle-btn', { active: modelValue === opt.value }]"
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

<style scoped>
.view-toggle {
  display: flex;
  align-items: center;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}
.view-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background .15s, color .15s;
}
.view-toggle-btn:hover {
  color: var(--text);
  background: var(--surface-2);
}
.view-toggle-btn.active {
  background: var(--surface-2);
  color: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
</style>
