<template>
  <div>
    <PageHeader title="系统配置" subtitle="全局参数和服务设置"></PageHeader>

    <div class="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">

      <!-- Server Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">服务设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">监听地址 <span class="text-gray-600">(读取配置文件)</span></label>
            <input v-model="config.listenHost" type="text" disabled
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-gray-400 font-mono cursor-not-allowed">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">监听端口 <span class="text-gray-600">(读取配置文件)</span></label>
            <input v-model.number="config.listenPort" type="number" disabled
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-gray-400 font-mono cursor-not-allowed">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">API 前缀 <span class="text-gray-600">(读取配置文件)</span></label>
            <input v-model="config.apiPrefix" type="text" disabled
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-gray-400 font-mono cursor-not-allowed">
          </div>
        </div>
      </div>

      <!-- Database Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">数据库设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">数据库路径 <span class="text-gray-600">(读取配置文件)</span></label>
            <input v-model="config.dbPath" type="text" disabled
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-gray-400 font-mono cursor-not-allowed">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">数据库大小</label>
            <p class="text-sm text-gray-400 font-mono">{{ info.dbSize || '—' }}</p>
          </div>
        </div>
      </div>

      <!-- Log Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">日志设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">日志级别</label>
            <CSelect v-model="config.logLevel" :options="LOG_LEVEL_OPTIONS" placeholder="日志级别" />
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">请求日志持久化 <span class="text-gray-600 text-xs">(读取配置文件)</span></p>
              <p class="text-xs text-gray-500 mt-0.5">将请求日志写入数据库</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer opacity-50">
              <input v-model="config.persistLogs" type="checkbox" disabled class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
        </div>
      </div>

      <!-- Load Balancer -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">负载均衡策略</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">策略</label>
            <CSelect v-model="config.lbStrategy" :options="LB_STRATEGY_OPTIONS" placeholder="策略" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">超时 (ms)</label>
            <input v-model.number="config.timeoutMs" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">重试次数</label>
            <input v-model.number="config.retryCount" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
        </div>
      </div>

      <!-- Quota Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">配额设置</h2></div>
        <div class="p-5 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">配额耗尽自动禁用</p>
              <p class="text-xs text-gray-500 mt-0.5">供应商配额耗尽时自动标记为不可用</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="config.autoDisable" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">每日自动重置配额</p>
              <p class="text-xs text-gray-500 mt-0.5">每日 00:00 自动刷新配额状态</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="config.autoReset" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
        </div>
      </div>

      <!-- Data Management (Import / Export) -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">数据管理</h2></div>
        <div class="p-5 space-y-5">
          <!-- Export -->
          <div class="flex items-end justify-between gap-4">
            <div class="flex-1">
              <label class="block text-xs text-gray-500 mb-1.5">导出格式</label>
              <select v-model="exportFormat"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
                <option value="json">JSON</option>
                <option value="yaml">YAML</option>
              </select>
            </div>
            <button @click="handleExport" class="btn btn-secondary whitespace-nowrap" :disabled="exporting">
              <svg v-if="!exporting" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mr-1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              <svg v-else class="animate-spin mr-1.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              {{ exporting ? '导出中…' : '导出供应商数据' }}
            </button>
          </div>

          <!-- Divider -->
          <div class="border-t border-ls-border"></div>

          <!-- Import -->
          <div class="space-y-3">
            <div class="flex items-end justify-between gap-4">
              <div class="flex-1">
                <label class="block text-xs text-gray-500 mb-1.5">导入文件 <span class="text-gray-600">(.json / .yaml)</span></label>
                <div class="flex items-center gap-2">
                  <button @click="triggerFileInput" class="btn-secondary px-3 py-2 text-sm rounded-lg border border-ls-border text-gray-300 hover:text-white transition-colors">
                    选择文件
                  </button>
                  <span class="text-sm text-gray-400 truncate">{{ selectedFileName || '未选择文件' }}</span>
                  <input ref="fileInput" type="file" accept=".json,.yaml,.yml" @change="handleFileSelect" class="hidden">
                </div>
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1.5">重复处理</label>
                <select v-model="importStrategy"
                  class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
                  <option value="skip">跳过已有</option>
                  <option value="overwrite">覆盖已有</option>
                </select>
              </div>
            </div>
            <div class="flex items-center justify-between">
              <p class="text-xs text-gray-600">导入将批量添加或更新供应商及其关联模型</p>
              <button @click="handleImport" class="btn btn-primary whitespace-nowrap" :disabled="!selectedFile || importing">
                <svg v-if="!importing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mr-1.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <svg v-else class="animate-spin mr-1.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                {{ importing ? '导入中…' : '导入供应商数据' }}
              </button>
            </div>
          </div>

          <!-- Import Result -->
          <div v-if="importResult" class="rounded-lg border border-green-800/50 bg-green-900/20 px-4 py-3">
            <div class="flex items-center gap-2 text-sm text-green-300">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <span>导入完成 — 新增 <strong>{{ importResult.created }}</strong> / 跳过 <strong>{{ importResult.skipped }}</strong> / 更新 <strong>{{ importResult.updated }}</strong> / 错误 <strong>{{ importResult.errors.length }}</strong></span>
            </div>
            <ul v-if="importResult.errors.length" class="mt-2 space-y-1">
              <li v-for="(err, i) in importResult.errors" :key="i" class="text-xs text-red-400 font-mono">• {{ err }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">关于</h2></div>
        <div class="p-5 space-y-2">
          <div class="flex justify-between text-sm"><span class="text-gray-500">版本</span><span class="text-white font-mono">{{ info.version || '—' }}</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">运行时长</span><span class="text-white font-mono">{{ info.uptime || '—' }}</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">Python</span><span class="text-white font-mono">{{ info.python || '—' }}</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">Uvicorn</span><span class="text-white font-mono">{{ info.uvicorn || '—' }}</span></div>
        </div>
      </div>
    </div>

    <!-- Save bar -->
    <div class="px-6 pb-6">
      <div class="bg-ls-card rounded-lg border border-ls-border px-5 py-3 flex items-center justify-between">
        <p class="text-xs text-gray-500">修改后请点击保存以应用配置</p>
        <div class="flex items-center gap-2.5">
          <button @click="resetConfig" class="btn btn-secondary">取消</button>
          <button @click="saveConfig" class="btn btn-primary">保存配置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import CSelect from '@/components/CSelect.vue'
import { getConfig as apiGetConfig, updateConfig as apiUpdateConfig, getAppInfo, exportSuppliers, importSuppliers } from '@/api'

const toast = inject('$toast')

// ── Select options ──
const LOG_LEVEL_OPTIONS = [
  { label: 'DEBUG', value: 'DEBUG' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' },
]
const LB_STRATEGY_OPTIONS = [
  { label: '轮询 (round_robin)', value: 'round_robin' },
  { label: '最少连接 (least_conn)', value: 'least_conn' },
  { label: '随机 (random)', value: 'random' },
]

const DEFAULTS = {
  listenHost: '0.0.0.0', listenPort: 8000, apiPrefix: '/api',
  dbPath: 'modelscope_proxy.db', logLevel: 'INFO', persistLogs: true,
  lbStrategy: 'round_robin', timeoutMs: 30000, retryCount: 0,
  autoDisable: true, autoReset: true,
}

// Snapshot of the last successfully loaded config (used by "取消")
let savedConfig = {}

const config = reactive({ ...DEFAULTS })

const info = ref({ version: '', uptime: '', python: '', uvicorn: '' })
const dbSize = ref('')
const loading = ref(true)

// Parse a backend config value from its {value, description} wrapper
const parse = (entry) => entry ? String(entry.value || '') : ''

// Flatten backend response {key: {value, description}} → frontend fields
const applyBackendConfig = (data) => {
  const m = (key) => parse(data[key])
  Object.assign(config, {
    logLevel: m('log_level') || 'INFO',
    lbStrategy: m('load_balancer_strategy') || 'round_robin',
    timeoutMs: Number(m('request_timeout_ms')) || 30000,
    retryCount: Number(m('retry_count')) || 0,
    autoDisable: (m('auto_disable_on_quota') || 'true').toLowerCase() === 'true',
    autoReset: (m('auto_reset_daily') || 'true').toLowerCase() === 'true',
  })
  // Frontend-only fields keep their defaults if backend has nothing
}

// Snapshot current config for "取消" restore
const snapshotConfig = () => {
  savedConfig = { ...config }
}

const loadConfig = async () => {
  loading.value = true
  try {
    const [cfgRes, infoRes] = await Promise.allSettled([
      apiGetConfig(),
      getAppInfo(),
    ])
    if (cfgRes.status === 'fulfilled') {
      applyBackendConfig(cfgRes.value.data || {})
      snapshotConfig()
    } else {
      toast('加载配置失败: ' + cfgRes.reason.message, 'warning')
    }
    if (infoRes.status === 'fulfilled') {
      const d = infoRes.value.data || {}
      info.value = {
        version: d.version || '—',
        uptime: d.uptime || '—',
        python: d.python || '—',
        uvicorn: d.uvicorn || '—',
        dbSize: d.db_size || '',
      }
      if (info.value.dbSize) dbSize.value = info.value.dbSize
    }
  } catch (e) {
    toast('加载失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

onMounted(loadConfig)

const saveConfig = async () => {
  const payload = {
    log_level: config.logLevel,
    load_balancer_strategy: config.lbStrategy,
    request_timeout_ms: String(config.timeoutMs),
    retry_count: String(config.retryCount),
    auto_disable_on_quota: String(config.autoDisable),
    auto_reset_daily: String(config.autoReset),
  }
  try {
    await apiUpdateConfig(payload)
    snapshotConfig()
    toast('配置已保存', 'success')
  } catch (e) {
    toast('保存失败: ' + e.message, 'error')
  }
}

const resetConfig = () => {
  if (Object.keys(savedConfig).length) {
    Object.assign(config, savedConfig)
  } else {
    Object.assign(config, DEFAULTS)
  }
}

// ── Supplier Import / Export ──

const exportFormat = ref('json')
const exporting = ref(false)

const importStrategy = ref('skip')
const selectedFile = ref(null)
const selectedFileName = ref('')
const fileInput = ref(null)
const importing = ref(false)
const importResult = ref(null)

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (e) => {
  const file = e.target.files?.[0]
  if (file) {
    selectedFile.value = file
    selectedFileName.value = file.name
    importResult.value = null
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    const res = await exportSuppliers(exportFormat.value)
    const blob = new Blob([res.data], {
      type: exportFormat.value === 'yaml' ? 'application/yaml' : 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    a.download = `suppliers_export_${date}.${exportFormat.value === 'yaml' ? 'yaml' : 'json'}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast('导出成功', 'success')
  } catch (e) {
    toast('导出失败: ' + (e?.message || '未知错误'), 'error')
  } finally {
    exporting.value = false
  }
}

const handleImport = async () => {
  if (!selectedFile.value) return
  importing.value = true
  importResult.value = null
  try {
    const res = await importSuppliers(selectedFile.value, importStrategy.value)
    importResult.value = res.data || res
    const errs = importResult.value?.errors?.length || 0
    if (errs > 0) {
      toast(`导入完成，但有 ${errs} 项失败`, 'warning')
    } else {
      toast('导入成功', 'success')
    }
    // Reset file input for potential re-import of same file
    selectedFile.value = null
    selectedFileName.value = ''
    if (fileInput.value) fileInput.value.value = ''
  } catch (e) {
    toast('导入失败: ' + (e?.message || '未知错误'), 'error')
  } finally {
    importing.value = false
  }
}
</script>
