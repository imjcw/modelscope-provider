<script setup>
/**
 * RateLimitCard — 限流状态卡（demo「限流状态 // Rate Limit」区块）。
 * 数据源为 /model-quota 的 per-model 配额，包含两种来源：
 * 1. 被动配额（来自 modelscope-ratelimit-* 响应头 → quota_* 字段）
 * 2. 窗口计数（fixed_window 策略 → window_quota_* 字段，用于 sensetime、per-model 等）
 * 优先使用窗口计数，退回被动配额，取使用率 top 5 展示。
 */
import { computed } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'

const props = defineProps({
  quotas: { type: Array, default: () => [] }, // /model-quota
})

const CHIP = {
  green:  { cls: 'bg-green-500/10 text-green-400 border-green-500/20',  label: '正常' },
  yellow: { cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', label: '警告' },
  red:    { cls: 'bg-red-500/10 text-red-400 border-red-500/20',         label: '超限' },
}
const GRAD = {
  green: 'bg-gradient-to-r from-green-400 to-green-500',
  yellow: 'bg-gradient-to-r from-yellow-400 to-yellow-500',
  red: 'bg-gradient-to-r from-red-400 to-red-500',
}

const rows = computed(() => {
  return (props.quotas || [])
    .map(q => {
      // 限流以窗口计数优先，退回 token 配额（对齐 ModelStatusTable）
      const winLimit = q.window_quota_limit
      const winRem = q.window_quota_remaining
      const limit = (winLimit != null ? winLimit : q.quota_limit) || 0
      const remaining = (winLimit != null ? winRem : q.quota_remaining) || 0
      const used = Math.max(0, limit - remaining)
      const pct = limit > 0 ? Math.round((used / limit) * 100) : 0
      return {
        name: q.model_name,
        used,
        limit,
        pct,
        tone: pct >= 100 ? 'red' : pct >= 70 ? 'yellow' : 'green',
      }
    })
    .filter(r => r.limit > 0)
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 5)
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">限流状态 // Rate Limit</h3>
        <p class="text-xs text-ls-muted mt-0.5">// 各模型剩余配额</p>
      </div>
      <span class="text-xs text-ls-muted">实时刷新</span>
    </div>

    <div v-if="rows.length" class="space-y-4">
      <div v-for="row in rows" :key="row.name">
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-xs font-mono text-ls-dim truncate">{{ row.name }}</span>
            <span class="text-xs px-1.5 py-0.5 rounded border flex-shrink-0" :class="CHIP[row.tone].cls">
              {{ CHIP[row.tone].label }}
            </span>
          </div>
          <span class="text-xs text-ls-dim flex-shrink-0 ml-2">{{ row.used.toLocaleString() }} / {{ row.limit.toLocaleString() }}</span>
        </div>
        <ProgressBar :pct="row.pct" width="w-full" height="h-2" :bar-class="GRAD[row.tone]" />
      </div>
    </div>
    <p v-else class="text-xs text-ls-muted py-4 text-center">暂无配额数据</p>
  </div>
</template>
