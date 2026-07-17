<template>
  <div>
    <PageHeader title="Dashboard" :subtitle="today">
      <template #action>
        <span class="inline-flex items-center rounded-md px-2 py-0.5 bg-green-500/10 text-green-400 text-xs">● Healthy</span>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>
      <!-- Stat Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-6">
        <div v-for="card in statCards" :key="card.label" class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">{{ card.label }}</p>
          <p class="text-2xl font-semibold tracking-tight text-white">{{ card.value }}</p>
          <p :class="['text-xs mt-1', card.trendColor || 'text-gray-500']">{{ card.sub }}</p>
        </div>
      </div>

      <!-- Quota bars + Trend -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5 mb-6">
        <!-- Quota usage -->
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-3 font-medium">Quota Usage</p>
          <div class="space-y-3">
            <div v-for="acc in suppliers" :key="acc.id">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-300">{{ acc.name }}</span>
                <span class="text-gray-500">{{ acc.usage }}%</span>
              </div>
              <div class="w-full bg-ls-bg rounded-full h-1.5">
                <div
                  class="h-1.5 rounded-full"
                  :class="acc.usage > 90 ? 'bg-red-500' : 'bg-ls-accent'"
                  :style="{ width: acc.usage + '%' }"
               ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Today trend (mini bar chart) -->
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-3 font-medium">Today's Requests</p>
          <div class="flex items-end gap-1 h-20">
            <div v-for="(bar, i) in trendBars" :key="i"
              class="flex-1 bg-ls-accent rounded-sm transition-all"
              :class="{ 'opacity-40': i !== trendBars.length - 1 }"
              :style="{ height: bar + '%' }"></div>
          </div>
          <div class="flex justify-between text-[10px] text-gray-600 mt-2">
            <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span>
          </div>
        </div>
      </div>

      <!-- Accounts Table -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center justify-between">
          <h2 class="font-semibold tracking-tight text-sm">Suppliers</h2>
          <router-link to="/suppliers" class="text-xs text-gray-500 hover:text-white">View all →</router-link>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border text-xs">
              <th class="text-left px-5 py-2.5 font-medium">Supplier</th>
              <th class="text-left px-5 py-2.5 font-medium">Status</th>
              <th class="text-left px-5 py-2.5 font-medium">Quota</th>
              <th class="text-left px-5 py-2.5 font-medium">Today</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in suppliers" :key="acc.id" class="border-b border-ls-border/50">
              <td class="px-5 py-3 font-medium text-white">{{ acc.name }}</td>
              <td class="px-5 py-3">
                <span class="inline-flex items-center rounded-md px-2 py-0.5"
                  :class="acc.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-ls-elevated text-gray-400'">
                  <span class="w-1.5 h-1.5 rounded-full mr-1.5"
                    :class="acc.status === 'active' ? 'bg-green-400' : 'bg-gray-500'"></span>
                  {{ acc.status === 'active' ? 'Active' : 'Disabled' }}
                </span>
              </td>
              <td class="px-5 py-3 text-xs text-gray-400">{{ acc.quota }}</td>
              <td class="px-5 py-3 text-xs text-gray-500">{{ acc.today }}</td>
            </tr>
            <tr v-if="suppliers.length === 0">
              <td colspan="4" class="px-5 py-8 text-center text-gray-500">No suppliers configured. Go to Suppliers page to add one.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getSuppliers, getLogs, getStats, getAlerts } from '@/api'

const today = computed(() => {
  return new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
})

const loading = ref(true)
const error = ref(null)

const statCards = ref([
  { label: 'Today Requests', value: '...', sub: 'loading...', trendColor: 'text-gray-500' },
  { label: 'Active Suppliers', value: '...', sub: '', trendColor: 'text-gray-500' },
  { label: 'Remaining Quota', value: '...', sub: '', trendColor: 'text-gray-500' },
  { label: 'Avg Latency', value: '...', sub: '', trendColor: 'text-gray-500' },
])

const suppliers = ref([])
const trendBars = ref([20, 35, 50, 75, 90, 100, 88, 72, 55, 30])

const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const [suppliersRes, logsRes, statsRes] = await Promise.allSettled([
      getSuppliers(),
      getLogs({ page: 0, page_size: 20 }),
      getStats(7),
    ])

    // Suppliers
    if (suppliersRes.status === 'fulfilled') {
      const sups = suppliersRes.value.data || []
      suppliers.value = sups.map(a => ({
        id: a.id,
        name: a.name || a.account_id,
        status: a.status,
        usage: a.quota_remaining && a.quota_limit
          ? Math.round((a.quota_limit - a.quota_remaining) / a.quota_limit * 100)
          : 0,
        quota: `${a.quota_remaining || 0} / ${a.quota_limit || '—'}`,
        today: '—',
      }))
    }

    // Logs / stats for summary cards
    if (logsRes.status === 'fulfilled') {
      const total = logsRes.value.data?.total || 0
      statCards.value[0].value = total.toLocaleString()
      statCards.value[0].sub = 'today'
    }
    if (suppliersRes.status === 'fulfilled') {
      const sups = suppliersRes.value.data || []
      const active = sups.filter(a => a.status === 'active').length
      statCards.value[1].value = `${active} / ${sups.length}`
    }
    if (statsRes.status === 'fulfilled') {
      const s = statsRes.value.data || {}
      if (s.avg_latency != null) {
        statCards.value[3].value = `${s.avg_latency}ms`
        statCards.value[3].sub = 'avg'
      } else if (s.avg_latency_ms != null) {
        statCards.value[3].value = `${s.avg_latency_ms}ms`
        statCards.value[3].sub = 'avg'
      } else {
        statCards.value[3].value = '—'
        statCards.value[3].sub = 'no data'
      }
    }
  } catch (e) {
    error.value = e.message || 'Failed to load data'
  }
  loading.value = false
}

onMounted(() => loadData())
</script>
