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
  // Align by (model name, account_id). Stats are grouped by (model, account_id)
  // and quota rows carry account_id, so the same model name on different
  // suppliers is matched correctly instead of being merged.
  const statsByModel = new Map(
    (props.modelStats || []).map(m => [`${m.model}::${m.account_id}`, m])
  )
  const seen = new Set()
  const out = []

  for (const q of props.quotas || []) {
    const key = `${q.model_name}::${q.account_id}`
    if (!q.model_name || seen.has(key)) continue
    seen.add(key)
    const st = statsByModel.get(key)
    // 限流列优先用“按模型窗口”计数（window_quota_*）；非窗口策略退回 token 配额（quota_*）
    const winLimit = q.window_quota_limit
    const winRem = q.window_quota_remaining
    const limit = (winLimit != null ? winLimit : q.quota_limit) || 0
    const remaining = (winLimit != null ? winRem : q.quota_remaining) || 0
    const usedPct = limit > 0 ? Math.round(((limit - remaining) / limit) * 100) : null
    out.push({
      model: q.model_name,
      account_id: q.account_id,
      group: q.model_type || '—',
      platform: q.supplier_name || '—',
      calls: st ? st.total : 0,
      successRate: st ? st.success_rate : null,
      usedPct,
      status: q.is_unavailable ? 'down' : (usedPct !== null && usedPct >= 90 ? 'cooldown' : 'ok'),
      // 按模型窗口策略
      strategy_type: q.strategy_type || null,
      window_seconds: q.window_seconds || null,
      max_requests: q.max_requests ?? null,
      window_quota_remaining: q.window_quota_remaining ?? null,
      window_quota_limit: q.window_quota_limit ?? null,
      has_custom_window: !!q.has_custom_window,
      window_override: q.window_override || null,
    })
  }
  // 窗口内有调用但没有配额记录的模型
  for (const m of props.modelStats || []) {
    const key = `${m.model}::${m.account_id}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push({
      model: m.model, account_id: m.account_id, group: '—', platform: '—',
      calls: m.total, successRate: m.success_rate, usedPct: null, status: 'ok',
    })
  }
  // 仅展示有请求量的模型
  return out.filter(r => r.calls > 0).sort((a, b) => b.calls - a.calls)
})

const rateClass = (r) => {
  if (r === null || r === undefined) return 'text-ls-muted'
  return r >= 95 ? 'text-green-400' : r >= 85 ? 'text-yellow-400' : 'text-red-400'
}
const barClass = (pct) =>
  pct < 50 ? 'bg-green-400' : pct < 90 ? 'bg-yellow-400' : 'bg-red-400'

const fmtWindow = (r) => {
  const st = r.strategy_type
  if (!st || st === 'header_based') return { label: '无限制', sub: '', badge: 'muted', custom: false }
  const secs = r.window_seconds || 0
  const val = secs >= 3600 ? (secs / 3600) : (secs / 60)
  const unit = secs >= 3600 ? 'h' : 'm'
  const max = r.max_requests ?? r.window_quota_limit ?? null
  const rem = r.window_quota_remaining
  // 展示”已用/上限”（使用数），而不是”剩余/上限”，避免把剩余数误认为已用数。
  const used = max != null && rem != null ? Math.max(0, max - rem) : null
  const sub =
    used != null ? `已用 ${used}/${max} 滑窗`
    : max != null ? `${max} 滑窗`
    : ''
  if (st === 'fixed_window_per_model')
    return { label: `按模型 ${val}${unit}`, sub, badge: 'accent', custom: !!r.has_custom_window }
  if (st === 'fixed_window' || st === 'sensetime')
    return { label: `滑动窗口 ${val}${unit}`, sub, badge: 'accent', custom: false }
  return { label: '被动', sub: '', badge: 'muted', custom: false }
}
const WINDOW_BADGE = {
  accent: 'bg-ls-accent/10 text-ls-accent border-ls-accent/20',
  muted: 'bg-ls-muted/10 text-ls-muted border-ls-border',
}
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
            <th class="text-center">限流</th>
            <th class="text-right hidden sm:table-cell">调用次数</th>
            <th class="text-right hidden md:table-cell">成功率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.model + '|' + (row.account_id || '')">
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
            <td class="text-center">
              <div class="flex items-center justify-center gap-1.5 mb-1">
                <span class="text-xs px-2 py-0.5 rounded-full border font-medium"
                      :class="WINDOW_BADGE[fmtWindow(row).badge]">
                  {{ fmtWindow(row).label }}
                </span>
              </div>
              <div v-if="fmtWindow(row).sub" class="text-[10px] text-ls-muted mb-1">{{ fmtWindow(row).sub }}</div>
              <div v-if="row.usedPct !== null" class="w-20 mx-auto">
                <ProgressBar :pct="row.usedPct" width="w-20" height="h-1.5" :bar-class="barClass(row.usedPct)" />
              </div>
            </td>
            <td class="text-right hidden sm:table-cell">
              <span class="text-sm font-mono text-ls-text">{{ row.calls.toLocaleString() }}</span>
            </td>
            <td class="text-right hidden md:table-cell">
              <span class="text-sm font-mono" :class="rateClass(row.successRate)">
                {{ row.successRate === null || row.successRate === undefined ? '—' : row.successRate + '%' }}
              </span>
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
