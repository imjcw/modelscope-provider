<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">Dashboard</h1>
        <p class="text-xs text-gray-500 mt-0.5">{{ today }}</p>
      </div>
      <div class="flex items-center gap-2.5">
        <span class="inline-flex items-center rounded-md px-2 py-0.5 bg-green-500/10 text-green-400 text-xs">● Healthy</span>
      </div>
    </header>

    <div class="p-6">
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
            <div v-for="acc in accounts" :key="acc.account_id">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-300">{{ acc.account_id }}</span>
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
          <h2 class="font-semibold tracking-tight text-sm">Accounts</h2>
          <router-link to="/accounts" class="text-xs text-gray-500 hover:text-white">View all →</router-link>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border text-xs">
              <th class="text-left px-5 py-2.5 font-medium">Account</th>
              <th class="text-left px-5 py-2.5 font-medium">Region</th>
              <th class="text-left px-5 py-2.5 font-medium">Status</th>
              <th class="text-left px-5 py-2.5 font-medium">Quota</th>
              <th class="text-left px-5 py-2.5 font-medium">Today</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in accounts" :key="acc.account_id" class="border-b border-ls-border/50">
              <td class="px-5 py-3 font-medium text-white">{{ acc.account_id }}</td>
              <td class="px-5 py-3 text-gray-500 text-xs">
                <span class="inline-flex items-center rounded-md px-2 py-0.5 bg-ls-elevated text-gray-300">{{ acc.region }}</span>
              </td>
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
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const today = computed(() => {
  return new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
})

const statCards = ref([
  { label: 'Today Requests', value: '12,847', sub: '↑ 8.3% vs yesterday', trendColor: 'text-green-400' },
  { label: 'Active Accounts', value: '3 / 4', sub: '1 disabled', trendColor: 'text-gray-500' },
  { label: 'Remaining Quota', value: '56.2k', sub: 'of 80,000 total', trendColor: 'text-gray-500' },
  { label: 'Avg Latency', value: '342 ms', sub: 'last 1 hour', trendColor: 'text-gray-500' },
])

const accounts = ref([
  { account_id: 'account-1', region: 'CN', status: 'active', usage: 92, quota: '18,400 / 20,000', today: '1,600' },
  { account_id: 'account-2', region: 'US', status: 'active', usage: 0, quota: '20,000 / 20,000', today: '0' },
  { account_id: 'account-3', region: 'CN', status: 'active', usage: 61, quota: '12,200 / 20,000', today: '7,800' },
  { account_id: 'account-4', region: 'US', status: 'disabled', usage: 100, quota: '0 / 20,000', today: '—' },
])

const trendBars = ref([20, 35, 50, 75, 90, 100, 88, 72, 55, 30])
</script>
