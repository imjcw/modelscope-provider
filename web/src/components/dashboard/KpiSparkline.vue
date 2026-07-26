<script setup>
/**
 * KpiSparkline — KPI 卡底部的迷你趋势线（平滑曲线）。
 * 精确对齐 demo：viewBox 0 0 120 32、preserveAspectRatio="none"。
 * null 值（空桶）跳过。
 */
import { computed } from 'vue'
import { smoothLinePath } from '@/utils/chart'

const props = defineProps({
  values: { type: Array, default: () => [] },
  stroke: { type: String, default: '#00ffff' },
})

const pts = computed(() => {
  const vals = props.values || []
  const filtered = vals.filter(v => v !== null && v !== undefined)
  if (!filtered.length) return ''
  const max = Math.max(...filtered, 1)
  const n = vals.length
  const points = vals.map((v, i) => {
    if (v === null || v === undefined) return null
    const x = n > 1 ? (i / (n - 1)) * 120 : 0
    const y = 32 - 2 - (v / max) * (32 - 4)
    return [x, y]
  }).filter(Boolean)
  return smoothLinePath(points)
})
</script>

<template>
  <svg class="w-full h-8" viewBox="0 0 120 32" preserveAspectRatio="none">
    <path class="sparkline" fill="none" :stroke="stroke" opacity="0.7" :d="pts" />
  </svg>
</template>
