<script setup>
/**
 * RecentAlerts — 最近告警卡（demo「最近告警 // Alerts」区块）。
 * 入参由 Dashboard 过滤为最近 1 小时、倒序、cap 5。
 */
import AlertLevelIcon from '@/components/AlertLevelIcon.vue'
import { timeAgoUtc } from '@/utils/format'

defineProps({
  alerts: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">最近告警 // Alerts</h3>
        <p class="text-xs text-ls-muted mt-0.5">// 过去 1 小时内触发的告警事件</p>
      </div>
      <span class="text-xs px-2 py-0.5 rounded-full border font-medium"
        :class="alerts.length
          ? 'bg-red-500/10 text-red-400 border-red-500/20'
          : 'bg-ls-elevated text-ls-muted border-ls-border'">
        {{ alerts.length }} 条
      </span>
    </div>

    <div v-if="alerts.length" class="space-y-3">
      <div v-for="(a, i) in alerts" :key="i"
        class="flex items-start gap-3 p-3 rounded-lg bg-ls-elevated border"
        :class="a.level === 'error' ? 'border-red-500/20' : 'border-yellow-500/20'">
        <div class="w-8 h-8 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
          :class="a.level === 'error' ? 'bg-red-500/10' : 'bg-yellow-500/10'">
          <AlertLevelIcon :level="a.level" :size="16" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-medium text-ls-text truncate">{{ a.message }}</span>
            <span class="text-xs text-ls-muted flex-shrink-0">{{ timeAgoUtc(a.timestamp) }}</span>
          </div>
          <p class="text-xs text-ls-dim mt-1 leading-relaxed">{{ a.model }} · 供应商 {{ a.account_id }}</p>
        </div>
      </div>
    </div>
    <p v-else class="text-xs text-ls-muted py-4 text-center">过去 1 小时无告警</p>
  </div>
</template>
