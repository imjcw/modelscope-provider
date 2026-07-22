<script setup>
/**
 * ProgressBar — 配额进度条。
 * 轨道色对齐 demo 的 #0d0d1a（--ls-elevated）。
 *
 * Usage:
 *   <ProgressBar :pct="usagePct(acc)" />                                    w-20 h-1（卡片行/表格）
 *   <ProgressBar :pct="usagePct(acc)" width="w-24" />                       w-24（网格卡片）
 *   <ProgressBar :pct="98.6" width="w-full" height="h-1.5"
 *                bar-class="bg-gradient-to-r from-green-400 to-green-500" />  demo 成功率条
 */
defineProps({
  pct: { type: Number, default: 0 },
  width: { type: String, default: 'w-20' },
  height: { type: String, default: 'h-1' },
  barClass: { type: String, default: 'bg-ls-accent' },
})
</script>

<template>
  <div class="bg-ls-elevated rounded-full overflow-hidden" :class="[width, height]">
    <div class="h-full rounded-full" :class="barClass"
      :style="{ width: Math.min(100, Math.max(0, pct)) + '%' }"></div>
  </div>
</template>
