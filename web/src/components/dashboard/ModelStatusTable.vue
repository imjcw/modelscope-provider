<script setup>
/**
 * ModelStatusTable — 模型状态表（demo「模型状态 // Models」区块）。
 * 数据融合：/model-quota（配额/平台/可用性）× /stats/window.models（窗口内调用量/成功率），
 * 按 COALESCE(actual_model_id, model) 与 model_name 对齐。
 * 行状态：is_unavailable → 不可用；配额用满 ≥90% → 冷却中；其余 → 可用。
 */
import { computed } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'

const props = defineProps({
  quotas: { type: Array, default: () => [] },     // /model-quota
  modelStats: { type: Array, default: () => [] }, // /stats/window → models
})

const STATUS = {
  ok:       { dot: 'bg-green-400',  pill: 'bg-green-500/10 text-green-400 border-green-500/20',  label: '可用' },
  cooldown: { dot: 'bg-yellow-400', pill: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', label: '冷却中' },
  down:     { dot: 'bg-red-400',    pill: 'bg-red-500/10 text-red-400 border-red-500/20',        label: '不可用' },
}

const rows = computed(() => {
  const statsByModel = new Map((props.modelStats || []).map(m => [m.model, m]))
  const seen = new Set()
  const out = []

  for (const q of props.quotas || []) {
    const key = q.model_name
    if (!key || seen.has(key)) continue
    seen.add(key)
    const st = statsByModel.get(key)
    const limit = q.quota_limit || 0
    const remaining = q.quota_remaining || 0
    const usedPct = limit > 0 ? Math.round(((limit - remaining) / limit) * 100) : null
    out.push({
      model: key,
      group: q.model_type || '—',
      platform: q.supplier_name || '—',
      calls: st ? st.total : 0,
      successRate: st ? st.success_rate : null,
      usedPct,
      status: q.is_unavailable ? 'down' : (usedPct !== null && usedPct >= 90 ? 'cooldown' : 'ok'),
    })
  }
  // 窗口内有调用但没有配额记录的模型
  for (const m of props.modelStats || []) {
    if (seen.has(m.model)) continue
    seen.add(m.model)
    out.push({
      model: m.model, group: '—', platform: '—',
      calls: m.total, successRate: m.success_rate, usedPct: null, status: 'ok',
    })
  }
  return out.sort((a, b) => b.calls - a.calls)
})

const rateClass = (r) => {
  if (r === null || r === undefined) return 'text-ls-muted'
  return r >= 95 ? 'text-green-400' : r >= 85 ? 'text-yellow-400' : 'text-red-400'
}
const barClass = (pct) =>
  pct < 50 ? 'bg-green-400' : pct < 90 ? 'bg-yellow-400' : 'bg-red-400'
const pctLabelClass = (pct) =>
  pct < 50 ? 'text-ls-muted' : pct < 90 ? 'text-yellow-400' : 'text-red-400'
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border neon-glow">
    <div class="flex items-center justify-between px-5 py-4 border-b border-ls-border">
      <div>
        <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">模型状态 // Models</h3>
        <p class="text-xs text-ls-muted mt-0.5">// 各模型健康度、调用次数与限流状态</p>
      </div>
      <div class="hidden sm:flex items-center gap-4 text-xs">
        <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded bg-green-400"></span>可用</span>
        <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded bg-yellow-400"></span>冷却</span>
        <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded bg-red-400"></span>不可用</span>
      </div>
    </div>

    <!-- 单元格内边距由 main.css .c-table 统一管理（勿写 px-/py- 类） -->
    <div class="overflow-x-auto">
      <table class="c-table head-dense hover-full">
        <thead>
          <tr>
            <th class="text-left">模型</th>
            <th class="text-left hidden md:table-cell">分组</th>
            <th class="text-left hidden sm:table-cell">平台</th>
            <th class="text-center">状态</th>
            <th class="text-right hidden sm:table-cell">调用次数</th>
            <th class="text-right hidden md:table-cell">成功率</th>
            <th class="text-center">限流</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.model">
            <td>
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded" :class="STATUS[row.status].dot"></span>
                <span class="text-sm font-medium text-ls-text">{{ row.model }}</span>
              </div>
            </td>
            <td class="hidden md:table-cell"><span class="text-xs text-ls-dim">{{ row.group }}</span></td>
            <td class="hidden sm:table-cell">
              <span class="text-xs px-1.5 py-0.5 rounded text-ls-accent bg-ls-accent/10">{{ row.platform }}</span>
            </td>
            <td class="text-center">
              <span class="text-xs px-2 py-0.5 rounded-full border font-medium" :class="STATUS[row.status].pill">
                {{ STATUS[row.status].label }}
              </span>
            </td>
            <td class="text-right hidden sm:table-cell">
              <span class="text-sm font-mono text-ls-text">{{ row.calls.toLocaleString() }}</span>
            </td>
            <td class="text-right hidden md:table-cell">
              <span class="text-sm font-mono" :class="rateClass(row.successRate)">
                {{ row.successRate === null || row.successRate === undefined ? '—' : row.successRate + '%' }}
              </span>
            </td>
            <td class="text-center">
              <div v-if="row.usedPct !== null" class="w-20 mx-auto">
                <ProgressBar :pct="row.usedPct" width="w-20" height="h-1.5" :bar-class="barClass(row.usedPct)" />
                <span class="text-xs mt-1 inline-block" :class="pctLabelClass(row.usedPct)">{{ row.usedPct }}%</span>
              </div>
              <span v-else class="text-xs text-ls-muted">—</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="7" class="py-8 text-center text-xs text-ls-muted">暂无模型数据</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
