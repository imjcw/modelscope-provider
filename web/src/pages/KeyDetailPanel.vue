<script setup>
/**
 * KeyDetailPanel — API Key 详情抽屉。
 * 按 section（logs / stats / docs）渲染「专属」抽屉：点击列表里哪个图标就只弹出
 * 对应内容，不再把调用日志 / 使用统计 / 对接文档聚合在同一个抽屉的 Tab 里。
 *
 * Usage:
 *   <KeyDetailPanel :api-key="selectedKeyForDetail" :section="detailSection"
 *     @close="selectedKeyForDetail = null" />
 */
import { ref, computed, watch } from 'vue'
import Drawer from '@/components/Drawer.vue'
import CIcon from '@/components/CIcon.vue'
import CTable from '@/components/CTable.vue'
import StatusCodeBadge from '@/components/StatusCodeBadge.vue'
import Pagination from '@/components/Pagination.vue'
import CopyButton from '@/components/CopyButton.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import CodeBlock from '@/components/CodeBlock.vue'
import { formatTime } from '@/utils/format'
import { getClientKeyLogs, getClientKeyStats, getClientKeyDocs } from '@/api'

const props = defineProps({
  apiKey: { type: Object, default: null },
  section: { type: String, default: 'logs' }, // 'logs' | 'stats' | 'docs'
})

const emit = defineEmits(['close'])

const SECTION_META = {
  logs: { title: '调用日志', icon: 'file' },
  stats: { title: '使用统计', icon: 'chart' },
  docs: { title: '对接文档', icon: 'book' },
}
const meta = computed(() => SECTION_META[props.section] || SECTION_META.logs)

// 关闭动画期间保留最后一次打开的 key，避免抽屉滑出时内容闪空
const renderKey = ref(null)

const detailLoading = ref(false)
const detailLogs = ref([])
const detailTotal = ref(0)
const detailPage = ref(0)
const logDays = ref(0)
const statsLoading = ref(false)
const keyStats = ref({})
const statsDays = ref(0)
const DAYS_OPTIONS = [
  { label: '今天', value: 0 },
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
]
const docsLoading = ref(false)
const keyDocsMeta = ref({}) // { key_value, base_url }

// ── 错误码表（与 Guide.vue 保持一致）──────────────────────────
const ERROR_CODES = [
  { code: 200, name: '成功', cause: '请求正常处理', suggest: '—' },
  { code: 400, name: '请求错误', cause: '参数格式不正确或必填字段缺失', suggest: '检查请求体 JSON 格式' },
  { code: 401, name: '认证失败', cause: 'API Key 无效或已禁用', suggest: '检查 Key 是否正确并在管理后台启用' },
  { code: 404, name: '未找到', cause: '模型别名不存在且无法解析', suggest: '在「模型映射」中添加该别名' },
  { code: 429, name: '配额耗尽', cause: '所有供应商的配额均已用尽', suggest: '等待每日重置或添加新供应商' },
  { code: 502, name: '上游错误', cause: 'ModelScope 返回 5xx 错误', suggest: '稍后重试，或检查供应商状态' },
  { code: 504, name: '超时', cause: '请求超过配置的超时时间', suggest: '在「系统配置」中增大超时时间' },
]

// ── 代码示例（后端只返回 key + base_url）─────────────────────
const codeTabs = ['cURL', 'Python', 'Node.js']
const activeCodeTab = ref(0)

function curlSnippet(base, key) {
  return `curl -X POST ${base}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '{"model": "alias-name", "messages": [{"role": "user", "content": "你好"}]}'`
}

function pythonSnippet(base, key) {
  return `import openai

openai.api_key = "${key}"
openai.base_url = "${base}"

response = openai.chat.completions.create(
    model="alias-name",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)`
}

function nodeSnippet(base, key) {
  return `import OpenAI from "openai";

const openai = new OpenAI({
  apiKey: "${key}",
  baseURL: "${base}"
});

const response = await openai.chat.completions.create({
  model: "alias-name",
  messages: [{"role": "user", "content": "你好"}]
});
console.log(response.choices[0].message.content);`
}

function currentCodeSnippet() {
  const { base_url, key_value } = keyDocsMeta.value
  if (!base_url) return ''
  const idx = activeCodeTab.value
  if (idx === 0) return curlSnippet(base_url, key_value)
  if (idx === 1) return pythonSnippet(base_url, key_value)
  return nodeSnippet(base_url, key_value)
}

function snippetLang() {
  return ['bash', 'python', 'javascript'][activeCodeTab.value]
}


const fmtTime = (ts) => formatTime(ts)

const onClose = () => emit('close')

// 每个抽屉只加载自己那一块数据
function loadActiveSection() {
  if (props.section === 'logs') loadDetailLogs()
  else if (props.section === 'stats') loadKeyStats()
  else if (props.section === 'docs') loadKeyDocs()
}

watch(() => props.apiKey, (val) => {
  if (!val) return
  renderKey.value = val
  detailPage.value = 0
  loadActiveSection()
})

const loadDetailLogs = async () => {
  if (!props.apiKey) return
  detailLoading.value = true
  try {
    const res = await getClientKeyLogs(props.apiKey.id, {
      page: detailPage.value,
      page_size: 20,
      days: logDays.value,
    })
    detailLogs.value = res.data.records || []
    detailTotal.value = res.data.total || 0
  } catch {
    detailLogs.value = []
    detailTotal.value = 0
  }
  detailLoading.value = false
}

const loadKeyStats = async () => {
  if (!props.apiKey) return
  statsLoading.value = true
  try {
    const res = await getClientKeyStats(props.apiKey.id, { days: statsDays.value })
    keyStats.value = res.data || {}
  } catch {
    keyStats.value = {}
  }
  statsLoading.value = false
}

// 时间范围变化时重新加载统计
watch(statsDays, () => { if (props.section === 'stats' && props.apiKey) loadKeyStats() })

// 时间范围变化时重新加载日志
watch(logDays, () => {
  if (props.section === 'logs' && props.apiKey) {
    detailPage.value = 0
    loadDetailLogs()
  }
})

const loadKeyDocs = async () => {
  if (!props.apiKey) return
  docsLoading.value = true
  try {
    const res = await getClientKeyDocs(props.apiKey.id)
    keyDocsMeta.value = res.data || {}
  } catch {
    keyDocsMeta.value = {}
  }
  docsLoading.value = false
}

// 翻页时重新加载日志
watch(detailPage, () => { if (props.section === 'logs') loadDetailLogs() })

</script>

<template>
  <Drawer :model-value="!!apiKey" no-header width="1100px" @update:model-value="onClose">
    <div v-if="renderKey" class="flex flex-col h-full">
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3 border-b border-ls-border bg-ls-card flex-shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <span class="w-8 h-8 rounded-lg bg-ls-accent/10 text-ls-accent flex items-center justify-center flex-shrink-0">
            <CIcon :name="meta.icon" :size="16" />
          </span>
          <div class="min-w-0">
            <h2 class="text-base font-semibold text-ls-text flex items-center gap-2">
              {{ meta.title }}
              <span class="text-sm font-normal text-ls-muted">· {{ renderKey.name }}</span>
            </h2>
            <p class="text-xs text-ls-muted mt-0.5 font-mono truncate">{{ renderKey.key_value_masked }}</p>
          </div>
        </div>
        <button @click="onClose" class="drawer-close btn-esc">
          <CIcon name="x" :size="20" />
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto">
        <!-- Logs -->
        <div v-if="section === 'logs'" class="p-4">
          <!-- 时间范围 -->
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-xs font-medium text-ls-muted uppercase tracking-wide">调用日志</h3>
            <SegmentedControl v-model="logDays" :options="DAYS_OPTIONS" size="sm" />
          </div>
          <div v-if="detailLoading" class="flex items-center justify-center h-48">
            <div class="text-ls-muted"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" class="text-ls-muted animate-spin">
          <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg></div>
          </div>
          <div v-else-if="detailLogs.length === 0" class="flex items-center justify-center h-48 text-ls-muted text-sm">
            暂无调用记录
          </div>
          <CTable v-else size="sm" head-bg hover="full">
            <thead>
              <tr>
                <th class="text-left">时间戳</th>
                <th class="text-left">请求 ID</th>
                <th class="text-left">模型</th>
                <th class="text-left">状态</th>
                <th class="text-left">Token</th>
                <th class="text-left">延迟</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in detailLogs" :key="log.id">
                <td class="text-ls-dim">{{ fmtTime(log.timestamp) }}</td>
                <td class="text-ls-dim font-mono">{{ log.request_id }}</td>
                <td class="text-ls-text font-mono">{{ log.model }}</td>
                <td>
                  <StatusCodeBadge :code="log.status_code" />
                </td>
                <td>
                  <TokenStack :input="log.input_tokens || 0" :output="log.output_tokens || 0" compact />
                </td>
                <td class="font-mono text-ls-dim">{{ log.latency_ms ? log.latency_ms + ' ms' : '-' }}</td>
              </tr>
            </tbody>
          </CTable>
          <Pagination v-model:page="detailPage" :total="detailTotal" simple />
        </div>

        <!-- Stats -->
        <div v-else-if="section === 'stats'" class="p-4">
          <!-- 时间范围 -->
          <div class="flex items-center justify-between mb-5">
            <h3 class="text-xs font-medium text-ls-muted uppercase tracking-wide">时间范围</h3>
            <SegmentedControl v-model="statsDays" :options="DAYS_OPTIONS" size="sm" />
          </div>

          <div v-if="statsLoading" class="flex items-center justify-center h-48">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round" class="text-ls-muted animate-spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          </div>
          <div v-else class="space-y-4">
            <!-- 关键指标：总请求数 / 成功请求 / 失败请求 各一块 -->
            <div class="grid grid-cols-3 gap-4">
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">总请求数</span>
                <p class="text-base font-mono text-ls-text mt-1">{{ (keyStats.total_requests || 0).toLocaleString() }}</p>
              </div>
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">成功请求</span>
                <p class="text-base font-mono text-green-400 mt-1">{{ (keyStats.success_count || 0).toLocaleString() }}</p>
              </div>
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">失败请求</span>
                <p class="text-base font-mono text-red-400 mt-1">{{ (keyStats.error_count || 0).toLocaleString() }}</p>
              </div>
            </div>

            <!-- Token：输入 / 缓存命中 / 输出 各一块 -->
            <div class="grid grid-cols-3 gap-4">
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">输入</span>
                <p class="text-base font-mono text-ls-text mt-1">{{ (keyStats.total_input_tokens || 0).toLocaleString() }}</p>
              </div>
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">缓存命中</span>
                <p class="text-base font-mono mt-1" :class="(keyStats.total_cache_tokens || 0) > 0 ? 'text-green-400' : 'text-ls-muted'">{{ (keyStats.total_cache_tokens || 0).toLocaleString() }}</p>
              </div>
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">输出</span>
                <p class="text-base font-mono text-ls-text mt-1">{{ (keyStats.total_output_tokens || 0).toLocaleString() }}</p>
              </div>
            </div>

            <!-- 性能：平均延迟 / 成功率 各一块 -->
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">平均延迟</span>
                <p class="text-base font-bold text-ls-text mt-1">{{ keyStats.avg_latency_ms || 0 }} ms</p>
              </div>
              <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 neon-glow">
                <span class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]">成功率</span>
                <p class="text-base font-bold mt-1"
                  :class="(keyStats.success_count || 0) / Math.max(keyStats.total_requests || 1, 1) >= 0.9 ? 'text-green-400' : 'text-yellow-400'">
                  {{ keyStats.total_requests > 0 ? Math.round((keyStats.success_count || 0) / (keyStats.total_requests || 1) * 100) : 0 }}%
                </p>
              </div>
            </div>

          <!-- 按模型分布 -->
          <CTable v-if="keyStats.per_model && keyStats.per_model.length > 0" size="sm" head-bg dense>
            <thead>
              <tr>
                <th class="text-left">模型</th>
                <th class="text-right">请求</th>
                <th class="text-right">输入</th>
                <th class="text-right">缓存命中</th>
                <th class="text-right">输出</th>
                <th class="text-right">错误</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in keyStats.per_model" :key="m.model">
                <td class="font-mono text-ls-text">{{ m.model }}</td>
                <td class="font-mono text-right text-ls-dim">{{ (m.requests || 0).toLocaleString() }}</td>
                <td class="font-mono text-right text-ls-dim">{{ (m.input_tokens || 0).toLocaleString() }}</td>
                <td class="font-mono text-right text-ls-dim">{{ (m.cache_tokens || 0).toLocaleString() }}</td>
                <td class="font-mono text-right text-ls-dim">{{ (m.output_tokens || 0).toLocaleString() }}</td>
                <td class="font-mono text-right" :class="m.error_count > 0 ? 'text-red-400' : 'text-ls-muted'">{{ m.error_count || 0 }}</td>
              </tr>
            </tbody>
          </CTable>
          <div v-else-if="keyStats.per_model && keyStats.per_model.length === 0"
            class="text-center text-ls-muted text-xs py-6">暂无记录</div>
          </div>
        </div>

        <!-- Docs -->
        <div v-else-if="section === 'docs'" class="p-4 space-y-5">
          <div v-if="docsLoading" class="flex items-center justify-center h-48">
            <div class="text-ls-muted"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round" class="text-ls-muted animate-spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg></div>
          </div>

          <div v-else class="space-y-5">
            <!-- 基础信息 -->
            <div>
              <h3 class="text-sm font-medium text-ls-text">基础信息</h3>
              <div class="space-y-2 mt-3">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-ls-dim w-24">API 地址</span>
                  <span class="text-xs font-mono text-ls-accent">{{ keyDocsMeta.base_url }}</span>
                  <CopyButton :text="keyDocsMeta.base_url" :size="12"
                    color-class="text-ls-dim hover:text-ls-text" :toast-text="'已复制: ' + keyDocsMeta.base_url" />
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-ls-dim w-24">API Key</span>
                  <span class="text-xs font-mono text-ls-accent">{{ renderKey.key_value }}</span>
                  <CopyButton :text="renderKey.key_value" :size="12"
                    color-class="text-ls-dim hover:text-ls-text" :toast-text="'已复制: ' + renderKey.key_value" />
                </div>
              </div>
            </div>

            <!-- 快速开始 tab -->
            <div>
              <h3 class="text-sm font-medium text-ls-text">快速开始</h3>
              <div class="flex gap-1 mt-3">
                <button v-for="(tab, i) in codeTabs" :key="tab" @click="activeCodeTab = i"
                  :class="activeCodeTab === i ? 'bg-ls-accent text-ls-bg' : 'text-ls-dim hover:text-ls-text'"
                  class="px-3 py-1.5 text-xs rounded-md transition-colors">{{ tab }}</button>
              </div>

                <!-- 代码块 -->
                <CodeBlock v-if="keyDocsMeta.base_url" class="mt-3" :lang="snippetLang()" :code="currentCodeSnippet()" />

              <div v-else class="text-center text-ls-muted text-xs py-8">加载失败，请刷新重试</div>
            </div>

            <!-- 错误码 -->
            <div>
              <h3 class="text-sm font-medium text-white">错误码</h3>
              <p class="text-xs text-gray-500 mt-0.5">调用失败时请参考以下状态码排查</p>
              <div class="overflow-x-auto mt-3">
                <table class="w-full text-xs">
                  <thead>
                    <tr class="text-gray-500 border-b border-ls-border">
                      <th class="text-left py-2 px-2">状态码</th>
                      <th class="text-left py-2 px-2">含义</th>
                      <th class="text-left py-2 px-2">原因</th>
                      <th class="text-left py-2 px-2">建议</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-ls-border">
                    <tr v-for="err in ERROR_CODES" :key="err.code">
                      <td class="py-2 px-2"><code class="font-mono" style="color:var(--ls-accent)">{{ err.code }}</code></td>
                      <td class="py-2 px-2" style="color:var(--text-dim)">{{ err.name }}</td>
                      <td class="py-2 px-2" style="color:var(--text-muted)">{{ err.cause }}</td>
                      <td class="py-2 px-2" style="color:var(--text-muted)">{{ err.suggest }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Drawer>
</template>

<style scoped>
code {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
}
</style>
