<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="系统配置 // Config" subtitle="// 全局参数和服务设置"></PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6 grid grid-cols-1 md:grid-cols-2 gap-6">

      <!-- Server Settings -->
      <CCard title="服务设置" body-class="p-5 space-y-4">
        <FormField label="监听地址" plain hint="(读取配置文件)">
          <input v-model="config.listenHost" type="text" disabled class="form-input font-mono cursor-not-allowed">
        </FormField>
        <FormField label="监听端口" plain hint="(读取配置文件)">
          <input v-model.number="config.listenPort" type="number" disabled class="form-input font-mono cursor-not-allowed">
        </FormField>
        <FormField label="API 前缀" plain hint="(读取配置文件)">
          <input v-model="config.apiPrefix" type="text" disabled class="form-input font-mono cursor-not-allowed">
        </FormField>
      </CCard>

      <!-- Database Settings -->
      <CCard title="数据库设置" body-class="p-5 space-y-4">
        <FormField label="数据库路径" plain hint="(读取配置文件)">
          <input v-model="config.dbPath" type="text" disabled class="form-input font-mono cursor-not-allowed">
        </FormField>
        <FormField label="数据库大小" plain>
          <p class="text-sm text-ls-dim font-mono">{{ info.dbSize || '—' }}</p>
        </FormField>
      </CCard>

      <!-- Log Settings -->
      <CCard title="日志设置" body-class="p-5 space-y-4">
        <FormField label="日志级别" plain>
          <CSelect v-model="config.logLevel" :options="LOG_LEVEL_OPTIONS" placeholder="日志级别" />
        </FormField>
        <FormField label="请求日志保留时长 (小时)" hint="超过此时长的请求日志将由定时任务自动清空，最小 1 小时">
          <input v-model.number="config.logRetentionHours" type="number" min="1" class="form-input font-mono">
        </FormField>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-ls-text">请求日志持久化 <span class="text-ls-muted text-xs">(读取配置文件)</span></p>
            <p class="text-xs text-ls-muted mt-0.5">将请求日志写入数据库</p>
          </div>
          <CCheckbox v-model="config.persistLogs" disabled />
        </div>
      </CCard>

      <!-- Desktop Widget -->
      <CCard title="桌面卡片" body-class="p-5 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-ls-text">桌面显示今日 Token 卡片</p>
            <p class="text-xs text-ls-muted mt-0.5">应用启动后自动在桌面显示今日 Token 消耗小卡片，关闭后不再显示</p>
          </div>
          <CCheckbox v-model="config.desktopWidget" />
        </div>
      </CCard>

      <!-- Load Balancer -->
      <CCard title="负载均衡策略" body-class="p-5 space-y-4">
        <FormField label="策略" plain>
          <CSelect v-model="config.lbStrategy" :options="LB_STRATEGY_OPTIONS" placeholder="策略" />
        </FormField>
        <FormField label="超时 (ms)" plain>
          <input v-model.number="config.timeoutMs" type="number" class="form-input font-mono">
        </FormField>
      </CCard>

      <!-- Quota Settings -->
      <CCard title="配额设置" body-class="p-5 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-ls-text">配额耗尽自动禁用</p>
            <p class="text-xs text-ls-muted mt-0.5">供应商配额耗尽时自动标记为不可用</p>
          </div>
          <CCheckbox v-model="config.autoDisable" />
        </div>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-ls-text">每日自动重置配额</p>
            <p class="text-xs text-ls-muted mt-0.5">每日 00:00 自动刷新配额状态</p>
          </div>
          <CCheckbox v-model="config.autoReset" />
        </div>
      </CCard>

      <!-- Data Management (Import / Export) -->
      <CCard title="数据管理" body-class="p-5 space-y-5">
          <!-- Export -->
          <div class="flex items-end justify-between gap-4">
            <FormField label="导出格式" plain class="flex-1">
              <CSelect v-model="exportFormat" :options="[{label:'JSON',value:'json'},{label:'YAML',value:'yaml'}]" placeholder="导出格式" />
            </FormField>
            <button @click="handleExport" class="btn btn-secondary whitespace-nowrap" :disabled="exporting">
              <svg v-if="!exporting" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mr-1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              <svg v-else class="animate-spin mr-1.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              {{ exporting ? '导出中…' : '导出配置' }}
            </button>
          </div>

          <!-- Divider -->
          <div class="border-t border-ls-border"></div>

          <!-- Import -->
          <div class="space-y-3">
            <div class="flex items-end justify-between gap-4">
              <FormField label="导入文件" plain hint="(.json / .yaml)" class="flex-1">
                <div class="flex items-center gap-2">
                  <button @click="triggerFileInput" class="btn btn-secondary">选择文件</button>
                  <span class="text-sm text-ls-dim truncate">{{ selectedFileName || '未选择文件' }}</span>
                  <input ref="fileInput" type="file" accept=".json,.yaml,.yml" @change="handleFileSelect" class="hidden">
                </div>
              </FormField>
              <FormField label="重复处理" plain>
                <CSelect v-model="importStrategy" :options="[{label:'跳过已有',value:'skip'},{label:'覆盖已有',value:'overwrite'}]" placeholder="重复处理" />
              </FormField>
            </div>
            <div class="flex items-center justify-between">
              <p class="text-xs text-ls-dim">导入将批量添加或更新供应商、供应商类型及映射配置</p>
              <button @click="handleImport" class="btn btn-primary whitespace-nowrap" :disabled="!selectedFile || importing">
                <svg v-if="!importing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="mr-1.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <svg v-else class="animate-spin mr-1.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                {{ importing ? '导入中…' : '导入配置' }}
              </button>
            </div>
          </div>

          <!-- Import Result -->
          <div v-if="importResult" class="rounded-lg border border-ls-border bg-ls-card px-4 py-3">
            <div class="flex items-center gap-2 text-sm text-ls-text">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <span>导入完成</span>
            </div>
            <div class="mt-2 grid grid-cols-3 gap-3 text-xs">
              <div class="text-ls-dim">供应商类型</div>
              <div class="text-ls-text">新增 {{ importResult.provider_types?.created ?? 0 }} / 跳过 {{ importResult.provider_types?.skipped ?? 0 }} / 更新 {{ importResult.provider_types?.updated ?? 0 }}</div>
              <div></div>
              <div class="text-ls-dim">供应商</div>
              <div class="text-ls-text">新增 {{ importResult.suppliers?.created ?? 0 }} / 跳过 {{ importResult.suppliers?.skipped ?? 0 }} / 更新 {{ importResult.suppliers?.updated ?? 0 }}</div>
              <div></div>
              <div class="text-ls-dim">映射</div>
              <div class="text-ls-text">新增 {{ importResult.mappings?.created ?? 0 }} / 跳过 {{ importResult.mappings?.skipped ?? 0 }} / 更新 {{ importResult.mappings?.updated ?? 0 }}</div>
              <div></div>
            </div>
            <ul v-if="importResult.errors?.length" class="mt-2 space-y-1">
              <li v-for="(err, i) in importResult.errors" :key="i" class="text-xs text-ls-danger font-mono">• {{ err }}</li>
            </ul>
          </div>
      </CCard>

      <!-- About -->
      <CCard title="关于" body-class="p-5 space-y-2">
        <div class="flex justify-between text-sm"><span class="text-ls-dim">版本</span><span class="text-ls-text font-mono">{{ info.version || '—' }}</span></div>
        <div class="flex justify-between text-sm"><span class="text-ls-dim">运行时长</span><span class="text-ls-text font-mono">{{ info.uptime || '—' }}</span></div>
        <div class="flex justify-between text-sm"><span class="text-ls-dim">Python</span><span class="text-ls-text font-mono">{{ info.python || '—' }}</span></div>
        <div class="flex justify-between text-sm"><span class="text-ls-dim">Uvicorn</span><span class="text-ls-text font-mono">{{ info.uvicorn || '—' }}</span></div>
      </CCard>
    </div>

    <!-- Save bar -->
    <div class="flex-shrink-0 px-6 pb-6">
      <div class="bg-ls-card rounded-lg border border-ls-border px-5 py-3 flex items-center justify-between">
        <p class="text-xs text-ls-dim">修改后请点击保存以应用配置</p>
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
import CCard from '@/components/CCard.vue'
import FormField from '@/components/FormField.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import { getConfig as apiGetConfig, updateConfig as apiUpdateConfig, getAppInfo, exportConfig, importConfig } from '@/api'

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
  logRetentionHours: 1,
  lbStrategy: 'round_robin', timeoutMs: 30000,
  autoDisable: true, autoReset: true,
  desktopWidget: true,
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
    autoDisable: (m('auto_disable_on_quota') || 'true').toLowerCase() === 'true',
    autoReset: (m('auto_reset_daily') || 'true').toLowerCase() === 'true',
    logRetentionHours: Number(m('log_retention_hours')) || 1,
    desktopWidget: (m('desktop_widget_enabled') || 'true').toLowerCase() === 'true',
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
    auto_disable_on_quota: String(config.autoDisable),
    auto_reset_daily: String(config.autoReset),
    log_retention_hours: String(config.logRetentionHours),
    desktop_widget_enabled: String(config.desktopWidget),
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
    const res = await exportConfig(exportFormat.value)
    const blob = new Blob([res.data], {
      type: exportFormat.value === 'yaml' ? 'application/yaml' : 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    a.download = `config_export_${date}.${exportFormat.value === 'yaml' ? 'yaml' : 'json'}`
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
    const res = await importConfig(selectedFile.value, importStrategy.value)
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
