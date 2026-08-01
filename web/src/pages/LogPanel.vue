<script setup>
/**
 * LogPanel — 智能路由「日志」列点开后的抽屉：使用情况统计。
 * 复用 <Drawer> 组件（与 Accounts/添加/编辑/用量抽屉同构），自带滑入/滑出过渡。
 * 纯展示型：GET /mappings/{alias}/logs，按时间范围聚合。
 * 赛博朋克霓虹主题。
 */
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import Drawer from '@/components/Drawer.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import CTable from '@/components/CTable.vue'
import { getMappingUsage } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  alias: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const DAYS_OPTIONS = [
  { label: '今天', value: 0 },
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
]

const loading = ref(false)
const error = ref(null)
const data = ref(null)
const days = ref(0)

const usage = computed(() => data.value?.usage || null)

const fmt = (n) => (n || 0).toLocaleString()

const load = async () => {
  if (!props.alias) return
  loading.value = true
  error.value = null
  try {
    const res = await getMappingUsage(props.alias, { days: days.value })
    data.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

watch([days], () => { if (props.modelValue) load() })

const close = () => emit('update:modelValue', false)

// ── Auto-refresh every 30s while drawer is open ──
let refreshTimer = null
watch(() => props.modelValue, (v) => {
  if (v) {
    data.value = null
    load()
    refreshTimer = setInterval(load, 30000)
  } else {
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = null
  }
})
onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <Drawer :model-value="modelValue" @update:model-value="close"
    :title="`${alias} · 使用统计`" width="880px">

    <!-- 时间范围 -->
    <div class="flex items-center justify-between mb-5">
      <h3 class="text-xs font-medium text-ls-muted uppercase tracking-wide">时间范围</h3>
      <SegmentedControl v-model="days" :options="DAYS_OPTIONS" size="sm" />
    </div>

    <div v-if="loading" class="flex items-center justify-center h-24 text-xs text-ls-muted">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-xs text-center py-6">{{ error }}</div>

    <div v-else-if="usage" class="space-y-5">
      <!-- 关键指标卡片（朴素 key/value） -->
      <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 grid grid-cols-4 gap-4 text-xs neon-glow">
        <div><span class="text-ls-muted">请求数</span><span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(usage.requests) }}</span></div>
        <div><span class="text-ls-muted">输入 Token</span><span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(usage.input_tokens) }}</span></div>
        <div><span class="text-ls-muted">输出 Token</span><span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(usage.output_tokens) }}</span></div>
        <div>
          <span class="text-ls-muted">缓存命中</span>
          <span class="block mt-1 text-base font-mono text-ls-text">
            {{ fmt(usage.cache_tokens) }} <span class="text-[10px] text-ls-muted">({{ usage.cache_hit_rate }}%)</span>
          </span>
        </div>
      </div>

      <!-- 按实际模型分布（供应商在前；所有模型都显示，含 0） -->
      <CTable v-if="usage.per_model && usage.per_model.length > 0" size="sm" head-bg dense>
        <thead>
          <tr>
            <th class="text-left">供应商</th>
            <th class="text-left">实际模型</th>
            <th class="text-right">请求</th>
            <th class="text-right">输入</th>
            <th class="text-right">缓存命中</th>
            <th class="text-right">输出</th>
            <th class="text-right">错误</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in usage.per_model" :key="m.model">
            <td class="text-ls-dim">{{ m.supplier || '—' }}</td>
            <td class="font-mono text-ls-accent">{{ m.model }}</td>
            <td class="font-mono text-right text-ls-dim">{{ fmt(m.requests) }}</td>
            <td class="font-mono text-right text-ls-dim">{{ fmt(m.input_tokens) }}</td>
            <td class="font-mono text-right text-ls-dim">{{ fmt(m.cache_tokens || 0) }}</td>
            <td class="font-mono text-right text-ls-dim">{{ fmt(m.output_tokens) }}</td>
            <td class="font-mono text-right" :class="m.error_count > 0 ? 'text-red-400' : 'text-ls-muted'">{{ m.error_count }}</td>
          </tr>
        </tbody>
      </CTable>

      <div v-else class="text-center text-ls-muted text-xs py-8">该时间段暂无请求记录</div>
    </div>
  </Drawer>
</template>
