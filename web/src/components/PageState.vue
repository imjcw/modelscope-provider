<script setup>
/**
 * PageState — 页面「加载中 / 出错 / 内容」三态统一包装。
 * 替代 6 个页面里复制的 loading / error / v-else 三件套。
 *
 * Usage:
 *   <PageState :loading="loading" :error="error">...正常内容...</PageState>
 *   <PageState :loading="loading" loading-text="加载中..." error-prefix="错误: ">...</PageState>
 */
defineProps({
  loading: { type: Boolean, default: false },
  error: { type: [String, Object], default: null },
  loadingText: { type: String, default: 'Loading...' },
  errorPrefix: { type: String, default: 'Error: ' },
  height: { type: String, default: 'h-64' },
})
</script>

<template>
  <div v-if="loading" class="flex items-center justify-center" :class="height">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="2" stroke-linecap="round" class="text-ls-muted animate-spin">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
  </div>
  <div v-else-if="error" class="text-red-400 text-sm p-4">{{ errorPrefix }}{{ error }}</div>
  <slot v-else />
</template>
