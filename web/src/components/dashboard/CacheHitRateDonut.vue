<script setup>
/**
 * CacheHitRateDonut — 缓存命中率环形图（手写 SVG，无图表库依赖）。
 * 展示 input_tokens 中缓存命中的占比，三段弧线分段表示：
 *   - 缓存命中（绿色）
 *   - 未命中但请求成功（蓝色）
 * 中心显示命中率百分比。
 */
import { computed } from 'vue'

const props = defineProps({
  /** 输入 token 总数 */
  inputTokens: { type: Number, default: 0 },
  /** 缓存命中 token 数 */
  cachedTokens: { type: Number, default: 0 },
  /** 输出 token 总数 */
  outputTokens: { type: Number, default: 0 },
})

const CIRCUMFERENCE = 2 * Math.PI * 48 // ≈ 301.6

const hitRate = computed(() => {
  if (!props.inputTokens) return 0
  return (props.cachedTokens / props.inputTokens) * 100
})

/** 缓存命中弧长 */
const hitLen = computed(() => {
  if (!props.inputTokens) return 0
  return (props.cachedTokens / props.inputTokens) * CIRCUMFERENCE
})

/** 未命中弧长（剩余输入） */
const missLen = computed(() => CIRCUMFERENCE - hitLen.value)

const missTokens = computed(() => props.inputTokens - props.cachedTokens)

// ── 数值格式化（不带单位，使用千分位便于阅读）──
function fmtToken(v) {
  return Math.round(v).toLocaleString('en-US')
}
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
    <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">
      缓存命中率 // Cache Hit
    </h3>
    <p class="text-xs text-ls-muted mt-0.5">// 输入 Token 中缓存命中的占比</p>

    <!-- 环形图 -->
    <div class="mt-4 flex items-center justify-center">
      <div class="relative">
        <svg class="w-32 h-32" viewBox="0 0 120 120">
          <!-- 底环（灰色）-->
          <circle cx="60" cy="60" r="48" fill="none" stroke="var(--ls-elevated)" stroke-width="14" />
          <!-- 未命中弧（暗淡蓝） -->
          <circle v-if="missLen > 0"
            cx="60" cy="60" r="48" fill="none" stroke="#60a5fa" stroke-width="14"
            :stroke-dasharray="`${missLen.toFixed(1)} ${CIRCUMFERENCE}`" stroke-dashoffset="0"
            transform="rotate(-90 60 60)" stroke-linecap="butt" stroke-opacity="0.35" />
          <!-- 缓存命中弧（绿色，覆盖在 top） -->
          <circle v-if="hitLen > 0"
            cx="60" cy="60" r="48" fill="none" stroke="#22c55e" stroke-width="14"
            :stroke-dasharray="`${hitLen.toFixed(1)} ${CIRCUMFERENCE}`"
            :stroke-dashoffset="String(-CIRCUMFERENCE + hitLen.value)"
            transform="rotate(-90 60 60)" stroke-linecap="round" />
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <span class="text-xl font-bold text-ls-text">{{ hitRate.toFixed(1) }}</span>
          <span class="text-[10px] text-ls-muted uppercase tracking-[0.15em]">命中率</span>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="mt-3 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded bg-green-400"></span>
          <span class="text-xs text-ls-dim">缓存命中</span>
        </div>
        <span class="text-sm font-mono text-ls-text">{{ fmtToken(cachedTokens) }}</span>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded bg-blue-400 opacity-35"></span>
          <span class="text-xs text-ls-dim">未命中</span>
        </div>
        <span class="text-sm font-mono text-ls-text">{{ fmtToken(missTokens) }}</span>
      </div>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded" style="background:#eab308"></span>
          <span class="text-xs text-ls-dim">输出 Token</span>
        </div>
        <span class="text-sm font-mono text-ls-text">{{ fmtToken(outputTokens) }}</span>
      </div>
    </div>
  </div>
</template>
