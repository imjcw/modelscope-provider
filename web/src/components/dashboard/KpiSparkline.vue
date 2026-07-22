<script setup>
/**
 * KpiSparkline — KPI 卡底部的迷你趋势线。
 * 精确对齐 demo：viewBox 0 0 120 32、preserveAspectRatio="none"、
 * polyline opacity 0.7。null 值（空桶）跳过。
 */
import { computed } from 'vue'
import { polylinePoints } from '@/utils/chart'

const props = defineProps({
  values: { type: Array, default: () => [] },
  stroke: { type: String, default: '#00ffff' },
})

const pts = computed(() => polylinePoints(props.values, 120, 32))
</script>

<template>
  <svg class="w-full h-8" viewBox="0 0 120 32" preserveAspectRatio="none">
    <polyline class="sparkline" fill="none" :stroke="stroke" opacity="0.7" :points="pts" />
  </svg>
</template>
