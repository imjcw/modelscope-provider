<script setup>
/**
 * LogPanel — 虚拟模型「日志」列点开后的抽屉：使用情况统计。
 * 复用 <Drawer> 组件（与 Accounts/添加/编辑/用量抽屉同构），自带滑入/滑出过渡。
 * 纯展示型：GET /mappings/{alias}/logs，按时间范围聚合。
 * 主题朴素 — key/value 文字，无花哨配色。
 */
import { ref, computed, watch } from 'vue'
import Drawer from '@/components/Drawer.vue'
import { getMappingUsage } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  alias: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const DAYS_OPTIONS = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]

const loading = ref(false)
const error = ref(null)
const data = ref(null)
const days = ref(7)

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

watch(() => props.modelValue, (v) => {
  if (v) {
    data.value = null
    load()
  }
})

watch([days], () => { if (props.modelValue) load() })

const close = () => emit('update:modelValue', false)
</script>

<template>
  <Drawer :model-value="modelValue" @update:model-value="close"
    :title="`${alias} · 使用统计`" width="880px">

    <!-- 时间范围 -->
    <div class="flex items-center justify-between mb-5">
      <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide">时间范围</h3>
      <div class="flex bg-ls-card rounded-lg border border-ls-border p-0.5">
        <button v-for="opt in DAYS_OPTIONS" :key="opt.value" type="button"
          @click="days = opt.value"
          class="px-2.5 h-7 rounded-md text-xs font-medium transition-colors"
          :class="days === opt.value ? 'bg-ls-elevated text-white' : 'text-gray-500 hover:text-white'">
          {{ opt.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center h-24 text-xs text-gray-500">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-xs text-center py-6">{{ error }}</div>

    <div v-else-if="usage" class="space-y-5">
      <!-- 关键指标卡片（朴素 key/value） -->
      <div class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 grid grid-cols-4 gap-4 text-xs">
        <div><span class="text-gray-500">请求数</span><span class="block mt-1 text-base font-mono text-white">{{ fmt(usage.requests) }}</span></div>
        <div><span class="text-gray-500">输入 Token</span><span class="block mt-1 text-base font-mono text-white">{{ fmt(usage.input_tokens) }}</span></div>
        <div><span class="text-gray-500">输出 Token</span><span class="block mt-1 text-base font-mono text-white">{{ fmt(usage.output_tokens) }}</span></div>
        <div>
          <span class="text-gray-500">Cache 命中</span>
          <span class="block mt-1 text-base font-mono text-white">
            {{ fmt(usage.cache_tokens) }} <span class="text-[10px] text-gray-500">({{ usage.cache_hit_rate }}%)</span>
          </span>
        </div>
      </div>

      <!-- 按实际模型分布（供应商在前；所有模型都显示，含 0） -->
      <div v-if="usage.per_model && usage.per_model.length > 0" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border bg-ls-bg">
              <th class="text-left px-4 py-2.5 font-medium">供应商</th>
              <th class="text-left px-4 py-2.5 font-medium">实际模型</th>
              <th class="text-right px-4 py-2.5 font-medium">请求</th>
              <th class="text-right px-4 py-2.5 font-medium">输入</th>
              <th class="text-right px-4 py-2.5 font-medium">Cache 命中</th>
              <th class="text-right px-4 py-2.5 font-medium">输出</th>
              <th class="text-right px-4 py-2.5 font-medium">错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in usage.per_model" :key="m.model"
              class="border-b border-ls-border/50 hover:bg-ls-elevated/30 transition-colors">
              <td class="px-4 py-2.5 text-gray-400">{{ m.supplier || '—' }}</td>
              <td class="px-4 py-2.5 font-mono text-ls-accent">{{ m.model }}</td>
              <td class="px-4 py-2.5 font-mono text-right text-gray-300">{{ fmt(m.requests) }}</td>
              <td class="px-4 py-2.5 font-mono text-right text-gray-400">{{ fmt(m.input_tokens) }}</td>
              <td class="px-4 py-2.5 font-mono text-right text-gray-400">{{ fmt(m.cache_tokens || 0) }}</td>
              <td class="px-4 py-2.5 font-mono text-right text-gray-400">{{ fmt(m.output_tokens) }}</td>
              <td class="px-4 py-2.5 font-mono text-right" :class="m.error_count > 0 ? 'text-red-400' : 'text-gray-600'">{{ m.error_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="text-center text-gray-600 text-xs py-8">该时间段暂无请求记录</div>
    </div>
  </Drawer>
</template>
