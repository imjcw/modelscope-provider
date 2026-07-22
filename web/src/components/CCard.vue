<script setup>
/**
 * CCard — 赛博朋克霓虹卡片容器。
 * 对齐 demo/cyberpunk-dark.html 的写法：
 *   bg-ls-card rounded-lg border border-ls-border neon-glow
 * 头部三种形态：
 *   1. title（+ #action 插槽）— 标准头部（px-5 py-4 + 下边框）
 *   2. #header 插槽 — 完全自定义头部（组件提供下边框）
 *   3. 无头部
 * 主体默认 p-5，可用 body-class 定制，no-padding 自管布局。
 *
 * Usage:
 *   <CCard title="服务设置">...</CCard>
 *   <CCard title="供应商列表" no-padding><template #action><router-link .../></template>...</CCard>
 */
defineProps({
  title: { type: String, default: '' },
  bodyClass: { type: String, default: '' },
  noPadding: { type: Boolean, default: false },
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border neon-glow">
    <div v-if="title || $slots.action"
      class="px-5 py-4 border-b border-ls-border flex items-center justify-between">
      <h2 class="text-sm uppercase tracking-[0.15em] text-ls-text">{{ title }}</h2>
      <slot name="action" />
    </div>
    <div v-else-if="$slots.header" class="border-b border-ls-border">
      <slot name="header" />
    </div>
    <div v-if="!noPadding" :class="bodyClass || 'p-5'">
      <slot />
    </div>
    <slot v-else />
  </div>
</template>
