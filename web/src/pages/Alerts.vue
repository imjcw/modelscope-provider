<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">告警历史</h1>
        <p class="text-xs text-gray-500 mt-0.5">配额耗尽、请求失败等告警记录</p>
      </div>
      <select v-model="alertFilter" class="bg-ls-card border border-ls-border rounded-md px-2.5 py-1 text-sm text-white focus:outline-none focus:border-ls-accent">
        <option value="all">全部类型</option>
        <option value="quota_exhausted">配额耗尽</option>
        <option value="api_error">请求失败</option>
        <option value="account_disabled">账户禁用</option>
      </select>
    </header>

    <div class="p-6">
      <!-- Summary cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mb-6">
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">今日告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">7</p>
          <p class="text-xs text-gray-500 mt-1">较昨日 +2</p>
        </div>
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">本周告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">23</p>
          <p class="text-xs text-gray-500 mt-1">配额耗尽 18 · 请求失败 5</p>
        </div>
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">最近严重告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">—</p>
          <p class="text-xs text-green-400 mt-1">系统运行正常</p>
        </div>
      </div>

      <!-- Alert List -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center justify-between">
          <h2 class="font-semibold tracking-tight text-sm">告警记录</h2>
          <span class="text-xs text-gray-500">共 {{ filteredAlerts.length }} 条</span>
        </div>
        <div>
          <div v-for="alert in filteredAlerts" :key="alert.id"
            class="px-5 py-3.5 border-b border-ls-border/50 flex items-start gap-3 hover:bg-ls-elevated transition-colors last:border-b-0">
            <span class="flex-shrink-0 mt-1">
              <svg v-if="alert.level === 'warning'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-yellow-400">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <svg v-else-if="alert.level === 'error'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-red-400">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <svg v-else-if="alert.level === 'info'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ls-accent">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
              <svg v-else-if="alert.level === 'critical'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-red-400">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-green-400">
                <circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>
              </svg>
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm text-white">{{ alert.title }}</span>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs" :class="levelClass(alert.level)">{{ levelLabel(alert.level) }}</span>
                <span class="text-xs text-gray-500 ml-auto">{{ alert.timestamp }}</span>
              </div>
              <p class="text-xs text-gray-400 mt-1">{{ alert.message }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const alertFilter = ref('all')

const alerts = ref([
  { id: 1, timestamp: '09:28:14', type: 'quota_exhausted', level: 'warning', title: '账户配额耗尽', message: 'account-1 的 hy3 模型今日配额已耗尽（20,000/20,000），该模型已标记为不可用' },
  { id: 2, timestamp: '09:31:42', type: 'api_error', level: 'error', title: 'API 请求失败', message: 'account-3 调用 qwen2.5-7b 返回 500 错误（Internal Server Error），请求 ID: req_q7r8s9t0' },
  { id: 3, timestamp: '09:15:03', type: 'info', level: 'info', title: '模型不可用通知', message: 'account-2 的 qwen2.5-14b 因上游服务维护暂时不可用，预计 30 分钟后恢复' },
  { id: 4, timestamp: '08:42:11', type: 'quota_exhausted', level: 'warning', title: '配额即将耗尽', message: 'account-3 剩余配额仅 12,200/20,000（61%），按当前使用速度预计今晚耗尽' },
  { id: 5, timestamp: '07:10:00', type: 'account_disabled', level: 'critical', title: '账户被禁用', message: 'account-4 因连续多次配额耗尽，已被系统自动禁用。请补充配额后手动启用' },
  { id: 6, timestamp: '00:00:01', type: 'recovered', level: 'recovered', title: '配额已恢复', message: '新日期配额重置完成：account-1、account-2、account-3 配额已恢复至每日上限' },
])

const filteredAlerts = computed(() => {
  if (alertFilter.value === 'all') return alerts.value
  return alerts.value.filter(a => a.level === alertFilter.value)
})

const levelClass = (level) => ({
  warning: 'bg-yellow-500/10 text-yellow-400',
  error: 'bg-red-500/10 text-red-400',
  info: 'bg-ls-accent/10 text-ls-accent',
  critical: 'bg-red-500/10 text-red-400',
  recovered: 'bg-green-500/10 text-green-400',
}[level] || 'bg-ls-elevated text-gray-400')

const levelLabel = (level) => ({
  warning: '警告', error: '错误', info: '信息', critical: '严重', recovered: '恢复',
}[level] || level)
</script>
