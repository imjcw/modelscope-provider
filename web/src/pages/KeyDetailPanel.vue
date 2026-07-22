<script setup>
/**
 * KeyDetailPanel — API Key 详情面板（调用日志 / 使用统计 / 对接文档）。
 * 从 ApiKeys.vue 的手写 fixed 面板抽出，复用 Drawer（no-header + 1100px）。
 *
 * Usage:
 *   <KeyDetailPanel :api-key="selectedKeyForDetail" :initial-tab="detailInitialTab"
 *     @close="selectedKeyForDetail = null" />
 */
import { ref, watch } from 'vue'
import Drawer from '@/components/Drawer.vue'
import CIcon from '@/components/CIcon.vue'
import CTable from '@/components/CTable.vue'
import StatusCodeBadge from '@/components/StatusCodeBadge.vue'
import StatCard from '@/components/StatCard.vue'
import Pagination from '@/components/Pagination.vue'
import CopyButton from '@/components/CopyButton.vue'
import TokenStack from '@/components/TokenStack.vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import { formatTime } from '@/utils/format'
import { getClientKeyLogs, getClientKeyStats, getClientKeyDocs } from '@/api'

const props = defineProps({
  apiKey: { type: Object, default: null },
  initialTab: { type: String, default: 'logs' },
})

const emit = defineEmits(['close'])

// 关闭动画期间保留最后一次打开的 key，避免抽屉滑出时内容闪空
const renderKey = ref(null)

const detailTab = ref('logs')
const detailLoading = ref(false)
const detailLogs = ref([])
const detailTotal = ref(0)
const detailPage = ref(0)
const statsLoading = ref(false)
const keyStats = ref({})
const docsLoading = ref(false)
const keyDocs = ref('')

const fmtTime = (ts) => formatTime(ts)

const onClose = () => emit('close')

watch(() => props.apiKey, (val) => {
  if (!val) return
  renderKey.value = val
  detailTab.value = props.initialTab
  detailPage.value = 0
  loadDetailLogs()
  loadKeyStats()
  loadKeyDocs()
})

const loadDetailLogs = async () => {
  if (!props.apiKey) return
  detailLoading.value = true
  try {
    const res = await getClientKeyLogs(props.apiKey.id, {
      page: detailPage.value,
      page_size: 20,
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
    const res = await getClientKeyStats(props.apiKey.id)
    keyStats.value = res.data || {}
  } catch {
    keyStats.value = {}
  }
  statsLoading.value = false
}

const loadKeyDocs = async () => {
  if (!props.apiKey) return
  docsLoading.value = true
  try {
    const res = await getClientKeyDocs(props.apiKey.id)
    keyDocs.value = res.data.markdown || ''
  } catch {
    keyDocs.value = ''
  }
  docsLoading.value = false
}

// 翻页时重新加载日志
watch(detailPage, () => loadDetailLogs())
</script>

<template>
  <Drawer :model-value="!!apiKey" no-header width="1100px" @update:model-value="onClose">
    <div v-if="renderKey" class="flex flex-col h-full">
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3 border-b border-ls-border bg-ls-card flex-shrink-0">
        <div>
          <h2 class="text-base font-semibold text-ls-text">{{ renderKey.name }}</h2>
          <p class="text-xs text-ls-muted mt-0.5 font-mono">{{ renderKey.key_value_masked }}</p>
        </div>
        <div class="flex items-center gap-2">
          <button @click="detailTab = 'docs'" class="text-xs text-ls-accent hover:text-ls-accentHover px-2 py-1">
            对接文档
          </button>
          <button @click="onClose" class="text-ls-muted hover:text-ls-text p-1">
            <CIcon name="x" :size="20" />
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-ls-border bg-ls-card flex-shrink-0">
        <button @click="detailTab = 'logs'"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
          :class="detailTab === 'logs' ? 'text-ls-text border-ls-accent' : 'text-ls-muted hover:text-ls-text border-transparent'">
          调用日志
        </button>
        <button @click="detailTab = 'stats'"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
          :class="detailTab === 'stats' ? 'text-ls-text border-ls-accent' : 'text-ls-muted hover:text-ls-text border-transparent'">
          使用统计
        </button>
        <button @click="detailTab = 'docs'"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
          :class="detailTab === 'docs' ? 'text-ls-text border-ls-accent' : 'text-ls-muted hover:text-ls-text border-transparent'">
          对接文档
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto">
        <!-- Logs Tab -->
        <div v-if="detailTab === 'logs'" class="p-4">
          <div v-if="detailLoading" class="flex items-center justify-center h-48">
            <div class="text-ls-muted">Loading...</div>
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

        <!-- Stats Tab -->
        <div v-else-if="detailTab === 'stats'" class="p-4">
          <div v-if="statsLoading" class="flex items-center justify-center h-48">
            <div class="text-ls-muted">Loading...</div>
          </div>
          <div v-else class="space-y-4">
            <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
              <StatCard label="总请求数" size="sm" :value="keyStats.total_requests || 0" />
              <StatCard label="成功请求" size="sm">
                <p class="text-2xl font-bold text-green-400 mt-1">{{ keyStats.success_count || 0 }}</p>
              </StatCard>
              <StatCard label="失败请求" size="sm">
                <p class="text-2xl font-bold text-red-400 mt-1">{{ keyStats.error_count || 0 }}</p>
              </StatCard>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Token" size="sm" label-class="mb-2">
                <TokenStack :input="keyStats.total_input_tokens || 0" :output="keyStats.total_output_tokens || 0" />
              </StatCard>
              <StatCard label="平均延迟" size="sm">
                <p class="text-xl font-bold text-ls-text mt-1">{{ keyStats.avg_latency_ms || 0 }} ms</p>
              </StatCard>
              <StatCard label="成功率" size="sm">
                <p class="text-xl font-bold mt-1"
                  :class="keyStats.success_count / Math.max(keyStats.total_requests, 1) >= 0.9 ? 'text-green-400' : 'text-yellow-400'">
                  {{ keyStats.total_requests > 0 ? Math.round(keyStats.success_count / keyStats.total_requests * 100) : 0 }}%
                </p>
              </StatCard>
            </div>
          </div>
        </div>

        <!-- Docs Tab -->
        <div v-else-if="detailTab === 'docs'" class="p-4">
          <div v-if="docsLoading" class="flex items-center justify-center h-48">
            <div class="text-ls-muted">Loading...</div>
          </div>
          <div v-else>
            <div class="flex items-center gap-2 mb-4">
              <span class="text-sm text-ls-dim">API Key:</span>
              <span class="font-mono text-ls-accent text-sm">{{ renderKey.key_value }}</span>
              <CopyButton :text="renderKey.key_value" class="ml-auto" />
            </div>
            <MarkdownRender :source="keyDocs" />
          </div>
        </div>
      </div>
    </div>
  </Drawer>
</template>
