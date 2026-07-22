<script setup>
/**
 * EmptyState — 虚线边框空态（icon 插槽 + 文案 + action 插槽）。
 *
 * Usage:
 *   <EmptyState text="暂无虚拟模型">
 *     <template #icon><CIcon name="link" :size="32" class="text-gray-600" /></template>
 *     <template #action><button ...>添加第一个虚拟模型 →</button></template>
 *   </EmptyState>
 */
defineProps({
  text: { type: String, default: '' },
})
</script>

<template>
  <div class="bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
    <slot name="icon" />
    <p class="text-sm text-ls-muted">{{ text }}</p>
    <slot name="action" />
  </div>
</template>
