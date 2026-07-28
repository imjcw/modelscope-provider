<script setup>
/**
 * StatusDonut — 请求结果分布环形图 + HTTP 状态码芯片。
 * 精确对齐 demo：r48 stroke14、rotate(-90)、round linecap、中心成功率。
 * 0 值段不渲染（round linecap 会在 0% 处留下圆点残影）。
 * 芯片规则：2xx 逐个（204 蓝、其余绿）、4xx 黄、5xx 聚合成一个红芯片。
 */
import { computed } from 'vue'

const props = defineProps({
  success: { type: Number, default: 0 },
  failed: { type: Number, default: 0 },
  statusCodes: { type: Object, default: () => ({}) }, // { '200': n, ... }
})

const C = 2 * Math.PI * 48 // ≈ 301.6
const total = computed(() => props.success + props.failed)
const pct = computed(() => (total.value ? (props.success / total.value) * 100 : 0))
const succLen = computed(() => (pct.value / 100) * C)
const failLen = computed(() => C - succLen.value)

const TONE = {
  green: 'bg-green-500/10 text-green-400 border-green-500/20',
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  red: 'bg-red-500/10 text-red-400 border-red-500/20',
}

const chips = computed(() => {
  const out = []
  let s5xx = 0
  for (const [code, count] of Object.entries(props.statusCodes)) {
    const c = Number(code)
    if (c >= 500) { s5xx += count; continue }
    out.push({
      label: `${code}: ${count.toLocaleString()}`,
      tone: c === 204 ? 'blue' : c < 400 ? 'green' : 'yellow',
    })
  }
  if (s5xx > 0) out.push({ label: `5xx: ${s5xx.toLocaleString()}`, tone: 'red' })
  return out
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
    <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">请求结果分布 // Status</h3>
    <p class="text-xs text-ls-muted mt-0.5">// 成功与失败请求占比</p>

    <!-- 环形图 -->
    <div class="mt-4 flex items-center justify-center">
      <div class="relative">
        <svg class="w-32 h-32" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="48" fill="none" stroke="var(--ls-elevated)" stroke-width="14" />
          <circle v-if="success > 0" cx="60" cy="60" r="48" fill="none" :style="{ stroke: 'var(--chart-green)' }" stroke-width="14"
            :stroke-dasharray="`${succLen} ${C}`" stroke-dashoffset="0"
            transform="rotate(-90 60 60)" stroke-linecap="round" />
          <circle v-if="failed > 0" cx="60" cy="60" r="48" fill="none" :style="{ stroke: 'var(--chart-red)' }" stroke-width="14"
            :stroke-dasharray="`${failLen} ${C}`" :stroke-dashoffset="String(-succLen)"
            transform="rotate(-90 60 60)" stroke-linecap="round" />
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <span class="text-xl font-bold text-ls-text">{{ pct.toFixed(1) }}%</span>
          <span class="text-[10px] text-ls-muted uppercase tracking-[0.15em]">成功率</span>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="mt-3 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded bg-green-400"></span>
          <span class="text-xs text-ls-dim">成功</span>
        </div>
        <span class="text-sm font-mono text-ls-text">{{ success.toLocaleString() }}</span>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded bg-red-400"></span>
          <span class="text-xs text-ls-dim">失败</span>
        </div>
        <span class="text-sm font-mono text-ls-text">{{ failed.toLocaleString() }}</span>
      </div>
    </div>

    <!-- HTTP 状态码 -->
    <div class="mt-4 pt-4 border-t border-ls-border">
      <span class="text-[10px] text-ls-dim uppercase tracking-[0.15em]">HTTP 状态码</span>
      <div class="mt-2 flex flex-wrap gap-1.5">
        <span v-for="chip in chips" :key="chip.label"
          class="text-xs px-2 py-0.5 rounded border" :class="TONE[chip.tone]">{{ chip.label }}</span>
        <span v-if="!chips.length" class="text-xs text-ls-muted">—</span>
      </div>
    </div>
  </div>
</template>
