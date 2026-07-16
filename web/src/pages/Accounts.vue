<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">账户管理</h1>
        <p class="text-xs text-gray-500 mt-0.5">添加、编辑和删除 ModelScope 账户</p>
      </div>
      <button @click="showAddDialog = true"
        class="bg-ls-accent text-white font-medium rounded-lg h-9 px-4 text-sm hover:bg-ls-accentHover transition-all inline-flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        添加账户
      </button>
    </header>

    <div class="p-6">
      <div class="space-y-3">
        <div v-for="acc in accounts" :key="acc.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all"
          :class="{ 'opacity-50': acc.status !== 'active' }">
          <div class="flex items-center gap-4 flex-1">
            <div class="w-10 h-10 rounded-md bg-ls-elevated flex items-center justify-center">
              <span class="font-semibold text-sm text-gray-300">{{ acc.account_id.slice(0, 2).toUpperCase() }}</span>
            </div>
            <div>
              <p class="font-medium text-sm text-white">{{ acc.account_id }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ maskKey(acc.api_key) }}</p>
            </div>
          </div>
          <div class="flex items-center gap-6">
            <span class="inline-flex items-center rounded-md px-2 py-0.5 bg-ls-elevated text-gray-300 text-xs">{{ acc.region === 'china' ? '中国大陆' : '海外' }}</span>
            <div class="text-xs text-gray-500 w-28">
              <span class="text-white font-medium">{{ acc.quota_remaining }}</span> / {{ acc.quota_limit }}
              <div class="w-20 bg-ls-bg rounded-full h-1 mt-1">
                <div class="bg-ls-accent h-1 rounded-full" :style="{ width: acc.usagePct + '%' }"></div>
              </div>
            </div>
            <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs"
              :class="acc.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-ls-elevated text-gray-400'">
              <span class="w-1.5 h-1.5 rounded-full mr-1.5"
                :class="acc.status === 'active' ? 'bg-green-400' : 'bg-gray-500'"></span>
              {{ acc.status === 'active' ? '活跃' : '已禁用' }}
            </span>
            <button @click="toggleAccount(acc)" class="text-gray-500 hover:text-white transition-colors" title="切换状态">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
              </svg>
            </button>
            <button @click="deleteAccount(acc.id)" class="text-gray-500 hover:text-red-400 transition-colors" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ accounts.length }} 个账户 · {{ activeCount }} 个活跃
      </div>

      <!-- Add Account Dialog -->
      <div v-if="showAddDialog" class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showAddDialog = false">
        <div class="bg-ls-card border border-ls-border rounded-lg w-full max-w-md p-6">
          <h2 class="text-lg font-semibold text-white mb-4">添加账户</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">账户 ID</label>
              <input v-model="newAccount.account_id" type="text" placeholder="account-5"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">API Key</label>
              <input v-model="newAccount.api_key" type="password" placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">Base URL</label>
              <input v-model="newAccount.base_url" type="text" placeholder="https://api-inference.modelscope.cn/v1"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">区域</label>
              <select v-model="newAccount.region"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white focus:outline-none focus:border-ls-accent">
                <option value="china">中国大陆</option>
                <option value="overseas">海外</option>
              </select>
            </div>
          </div>
          <div class="flex items-center justify-end gap-2.5 mt-6">
            <button @click="showAddDialog = false" class="text-sm text-gray-400 hover:text-white px-4 py-1.5 rounded-md">取消</button>
            <button @click="addAccount" class="bg-ls-accent text-white font-medium rounded-lg h-9 px-6 text-sm hover:bg-ls-accentHover transition-all">添加</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const showAddDialog = ref(false)
const newAccount = ref({ account_id: '', api_key: '', base_url: '', region: 'china' })

const accounts = ref([
  { id: 1, account_id: 'account-1', api_key: 'ms-ef15676c-****-****-****-2c2ae7101b8c', region: 'china', status: 'active', quota_remaining: 18400, quota_limit: 20000, usagePct: 92 },
  { id: 2, account_id: 'account-2', api_key: 'ms-ff949c01-****-****-****-9c43b0c02c53', region: 'overseas', status: 'active', quota_remaining: 20000, quota_limit: 20000, usagePct: 0 },
  { id: 3, account_id: 'account-3', api_key: 'ms-a1b2c3d4-****-****-****-12345678', region: 'china', status: 'active', quota_remaining: 12200, quota_limit: 20000, usagePct: 61 },
  { id: 4, account_id: 'account-4', api_key: 'ms-****-****-****-****-************', region: 'overseas', status: 'disabled', quota_remaining: 0, quota_limit: 20000, usagePct: 100 },
])

const activeCount = computed(() => accounts.value.filter(a => a.status === 'active').length)

const maskKey = (key) => {
  if (!key || key.length < 20) return '********'
  return key.slice(0, 10) + '****' + key.slice(-10)
}

const toggleAccount = (acc) => {
  acc.status = acc.status === 'active' ? 'disabled' : 'active'
}

const deleteAccount = (id) => {
  if (confirm('确定要删除这个账户吗？')) {
    accounts.value = accounts.value.filter(a => a.id !== id)
  }
}

const addAccount = () => {
  accounts.value.push({
    id: Date.now(),
    account_id: newAccount.value.account_id || 'new-account',
    api_key: (newAccount.value.api_key || '****').slice(0, 10) + '****' + (newAccount.value.api_key || '****').slice(-10),
    region: newAccount.value.region,
    status: 'active',
    quota_remaining: 20000,
    quota_limit: 20000,
    usagePct: 0,
  })
  showAddDialog.value = false
  newAccount.value = { account_id: '', api_key: '', base_url: '', region: 'china' }
}
</script>
