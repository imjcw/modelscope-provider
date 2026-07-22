<script setup>
/**
 * FilterField — 列表页筛选栏的筛选项容器（label + 定宽控件）。
 *
 * Usage:
 *   <FilterField label="供应商" width="lg:w-36">
 *     <CSelect v-model="filters.accountId" :options="ACCOUNT_OPTIONS" size="sm" placeholder="选择供应商" />
 *   </FilterField>
 */
defineProps({
  label: { type: String, default: '' },
  width: { type: String, default: '' }, // 控件在 lg 断点的宽度，如 'lg:w-36'
})
</script>

<template>
  <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
    <label class="text-xs text-gray-500 flex-shrink-0">{{ label }}</label>
    <div class="flex-1 min-w-0" :class="width">
      <slot />
    </div>
  </div>
</template>
