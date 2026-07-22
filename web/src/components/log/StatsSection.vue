<script setup>
/**
 * StatsSection — 日志详情右侧栏小节（uppercase 小标题 + 内容）。
 * #action 插槽可放标题右侧的操作按钮（如响应头复制）。
 */
defineProps({
  title: { type: String, default: '' },
})
</script>

<template>
  <div class="p-4 border-b border-ls-border">
    <div v-if="$slots.action" class="flex items-center justify-between mb-3">
      <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide">{{ title }}</h3>
      <slot name="action" />
    </div>
    <h3 v-else class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">{{ title }}</h3>
    <slot />
  </div>
</template>
