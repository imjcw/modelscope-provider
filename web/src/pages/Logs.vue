<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div class="flex items-center gap-2">
        <h1 class="text-lg font-semibold tracking-tight text-white">日志</h1>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-gray-600">
          <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
        </svg>
      </div>
      <button class="bg-ls-accent text-white font-medium rounded-lg h-8 px-4 text-sm hover:bg-ls-accentHover transition-all">↻ 刷新</button>
    </header>

    <div class="p-6">
      <!-- Filters (2 rows) -->
      <div class="flex flex-wrap gap-3 mb-5">
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">时间</label>
          <input type="text" v-model="filters.startTime" placeholder="开始"
            class="bg-transparent text-sm text-white border-0 focus:outline-none w-24 placeholder:text-gray-600">
          <span class="text-gray-600 text-xs">~</span>
          <input type="text" v-model="filters.endTime" placeholder="结束"
            class="bg-transparent text-sm text-white border-0 focus:outline-none w-24 placeholder:text-gray-600">
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">账户</label>
          <select v-model="filters.accountId" class="bg-transparent text-sm text-white border-0 focus:outline-none min-w-[120px]">
            <option value="">选择账户</option>
            <option>account-1</option><option>account-2</option><option>account-3</option>
          </select>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2 flex-1 min-w-[200px]">
          <label class="text-xs text-gray-500 flex-shrink-0">请求 ID</label>
          <input v-model="filters.requestId" type="text" placeholder="输入请求 ID"
            class="bg-transparent text-sm text-white placeholder:text-gray-600 border-0 focus:outline-none flex-1">
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">状态</label>
          <select v-model="filters.statusCode" class="bg-transparent text-sm text-white border-0 focus:outline-none min-w-[80px]">
            <option value="">全部</option><option value="200">200</option><option value="429">429</option><option value="500">500</option>
          </select>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">模型</label>
          <select v-model="filters.model" class="bg-transparent text-sm text-white border-0 focus:outline-none min-w-[120px]">
            <option value="">选择模型</option><option>hy3</option><option>qwen2.5-7b</option><option>qwen2.5-14b</option>
          </select>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">流式</label>
          <select v-model="filters.isStream" class="bg-transparent text-sm text-white border-0 focus:outline-none min-w-[80px]">
            <option value="">全部</option><option :value="true">是</option><option :value="false">否</option>
          </select>
        </div>
      </div>

      <!-- Table -->
      <div class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border bg-ls-bg">
              <th class="text-left px-4 py-2.5 font-medium">时间戳</th>
              <th class="text-left px-4 py-2.5 font-medium">请求 ID</th>
              <th class="text-left px-4 py-2.5 font-medium">模型</th>
              <th class="text-left px-4 py-2.5 font-medium">账户</th>
              <th class="text-left px-4 py-2.5 font-medium">状态</th>
              <th class="text-left px-4 py-2.5 font-medium">输入 Token</th>
              <th class="text-left px-4 py-2.5 font-medium">输出 Token</th>
              <th class="text-left px-4 py-2.5 font-medium">延迟</th>
              <th class="text-left px-4 py-2.5 font-medium">流式</th>
              <th class="text-right px-4 py-2.5 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in filteredLogs" :key="log.request_id"
              class="border-b border-ls-border/50 hover:bg-ls-elevated transition-colors cursor-pointer"
              @click="showDetail(log)">
              <td class="px-4 py-3 text-gray-400">{{ formatTime(log.timestamp) }}</td>
              <td class="px-4 py-3 text-gray-300 font-mono">{{ log.request_id }}</td>
              <td class="px-4 py-3">
                <span class="text-white hover:underline inline-flex items-center gap-1.5">
                  <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ log.model[0].toUpperCase() }}</span>
                  <span class="font-mono">{{ log.model }}</span>
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center gap-1.5 text-gray-400">
                  <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ log.account_id[0].toUpperCase() }}</span>
                  {{ log.account_id }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                  :class="log.status_code >= 500 ? 'bg-red-500/10 text-red-400' : log.status_code >= 400 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-green-500/10 text-green-400'">
                  {{ log.status_code }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-white">{{ log.input_tokens.toLocaleString() }}</td>
              <td class="px-4 py-3 font-mono text-white">{{ log.output_tokens.toLocaleString() }}</td>
              <td class="px-4 py-3 font-mono text-white">{{ log.latency_ms }}ms</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                  :class="log.is_stream ? 'bg-ls-accent/10 text-ls-accent' : 'bg-ls-elevated text-gray-400'">
                  {{ log.is_stream ? 'P' : 'N' }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <button @click.stop="showDetail(log)" class="bg-ls-elevated text-gray-300 hover:text-white rounded-md px-3 py-1 text-xs transition-colors">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between mt-4">
        <p class="text-xs text-gray-500">共 {{ total }} 条记录</p>
        <div class="flex items-center gap-2">
          <button @click="page--" :disabled="page <= 0"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">← 上页</button>
          <span class="text-xs text-gray-500">{{ page + 1 }} / {{ totalPages }}</span>
          <button @click="page++" :disabled="page >= totalPages - 1"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">下页 →</button>
        </div>
      </div>

      <!-- Detail Drawer -->
      <div v-if="selectedLog" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end" @click.self="selectedLog = null">
        <div class="w-[640px] h-full bg-ls-bg border-l border-ls-border overflow-y-auto p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-lg font-semibold text-white">日志详情</h2>
              <p class="text-xs text-gray-500 mt-0.5">{{ selectedLog.request_id }} · {{ selectedLog.timestamp }}</p>
            </div>
            <button @click="selectedLog = null" class="text-gray-500 hover:text-white">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- Meta -->
          <div class="bg-ls-card rounded-lg border border-ls-border p-5 mb-4">
            <h3 class="text-xs text-gray-500 font-medium mb-3">请求信息</h3>
            <div class="grid grid-cols-2 gap-x-8 gap-y-2.5">
              <div v-for="(v, k) in logMeta" :key="k">
                <p class="text-xs text-gray-500">{{ k }}</p>
                <p class="text-sm text-white">{{ v }}</p>
              </div>
            </div>
          </div>

          <!-- Status & Response -->
          <div class="bg-ls-card rounded-lg border border-ls-border p-5 mb-4">
            <h3 class="text-xs text-gray-500 font-medium mb-3">响应</h3>
            <div class="flex items-center gap-3 mb-3">
              <span class="inline-flex items-center rounded-md px-2 py-0.5 text-sm"
                :class="selectedLog.status_code >= 400 ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'">
                {{ selectedLog.status_code }} {{ selectedLog.status_code >= 400 ? 'Error' : 'OK' }}
              </span>
              <span class="text-xs text-gray-500">{{ selectedLog.latency_ms }}ms</span>
            </div>
            <pre class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono overflow-x-auto leading-relaxed whitespace-pre-wrap">{{ selectedLog.raw_response || '{}' }}</pre>
          </div>

          <!-- Messages -->
          <div class="bg-ls-card rounded-lg border border-ls-border p-5 mb-4">
            <h3 class="text-xs text-gray-500 font-medium mb-3">Messages</h3>
            <div class="space-y-2">
              <details v-for="(msg, i) in sampleMessages" :key="i" class="group bg-ls-bg rounded-lg border border-ls-border">
                <summary class="flex items-center gap-2 px-3 py-2 cursor-pointer list-none hover:bg-ls-elevated transition-colors">
                  <span class="w-1.5 h-1.5 rounded-full bg-gray-500"></span>
                  <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs"
                    :class="msg.role === 'system' ? 'bg-ls-accent/10 text-ls-accent' : msg.role === 'user' ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'">
                    {{ msg.role }}
                  </span>
                  <span class="text-xs text-gray-400 truncate">{{ msg.content.slice(0, 60) }}{{ msg.content.length > 60 ? '...' : '' }}</span>
                </summary>
                <pre class="px-3 pb-3 text-xs text-gray-300 font-mono whitespace-pre-wrap">{{ msg.content }}</pre>
              </details>
            </div>
          </div>

          <!-- Token usage -->
          <div class="bg-ls-card rounded-lg border border-ls-border p-5">
            <h3 class="text-xs text-gray-500 font-medium mb-3">Token 用量</h3>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-gray-400">输入 Token</span><span class="text-white font-mono">{{ selectedLog.input_tokens.toLocaleString() }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">输出 Token</span><span class="text-white font-mono">{{ selectedLog.output_tokens.toLocaleString() }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">总 Token</span><span class="text-white font-mono">{{ (selectedLog.input_tokens + selectedLog.output_tokens).toLocaleString() }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const page = ref(0)
const pageSize = 50
const total = ref(12847)
const totalPages = computed(() => Math.ceil(total.value / pageSize))

const filters = ref({ startTime: '', endTime: '', accountId: '', requestId: '', statusCode: '', model: '', isStream: '' })

const sampleLogs = [
  { request_id: 'req_a1b2c3d4', timestamp: '2026-07-16 09:49:14', model: 'hy3', account_id: 'account-1', status_code: 200, input_tokens: 30766, output_tokens: 688, latency_ms: 342, is_stream: true, raw_response: '{"id": "chatcmpl-abc123", "model": "hy3", "choices": [{"message": {"role": "assistant", "content": "Hi! I can help..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 31454}}' },
  { request_id: 'req_e5f6g7h8', timestamp: '2026-07-16 09:47:11', model: 'hy3', account_id: 'account-1', status_code: 200, input_tokens: 30194, output_tokens: 625, latency_ms: 298, is_stream: true, raw_response: '{"id": "chatcmpl-def456", "model": "hy3", "choices": [{"message": {"role": "assistant", "content": "Sure, here is the answer..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 30819}}' },
  { request_id: 'req_i9j0k1l2', timestamp: '2026-07-16 09:46:08', model: 'qwen2.5-7b', account_id: 'account-3', status_code: 200, input_tokens: 29650, output_tokens: 804, latency_ms: 1200, is_stream: true, raw_response: '{"id": "chatcmpl-ghi789", "model": "qwen2.5-7b-instruct", "choices": [{"message": {"role": "assistant", "content": "Based on your query..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 30454}}' },
  { request_id: 'req_m3n4o5p6', timestamp: '2026-07-15 17:32:00', model: 'hy3', account_id: 'account-2', status_code: 200, input_tokens: 28590, output_tokens: 916, latency_ms: 187, is_stream: true, raw_response: '{"id": "chatcmpl-jkl012", "model": "hy3", "choices": [{"message": {"role": "assistant", "content": "That is interesting..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 29506}}' },
  { request_id: 'req_q7r8s9t0', timestamp: '2026-07-15 10:00:00', model: 'qwen2.5-7b', account_id: 'account-3', status_code: 500, input_tokens: 0, output_tokens: 0, latency_ms: 0, is_stream: false, raw_response: '{"error": {"message": "Internal Server Error", "type": "server_error"}}' },
  { request_id: 'req_u1v2w3x4', timestamp: '2026-07-15 09:51:00', model: 'hy3', account_id: 'account-1', status_code: 429, input_tokens: 0, output_tokens: 0, latency_ms: 0, is_stream: false, raw_response: '{"error": {"message": "Rate limit exceeded", "type": "rate_limit"}}' },
  { request_id: 'req_y5z6a7b8', timestamp: '2026-07-15 09:45:30', model: 'hy3', account_id: 'account-1', status_code: 200, input_tokens: 15420, output_tokens: 1200, latency_ms: 256, is_stream: false, raw_response: '{"id": "chatcmpl-mno345", "model": "hy3", "choices": [{"message": {"role": "assistant", "content": "Here is the summary..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 16620}}' },
  { request_id: 'req_c9d0e1f2', timestamp: '2026-07-15 08:22:15', model: 'qwen2.5-14b', account_id: 'account-2', status_code: 200, input_tokens: 42000, output_tokens: 3500, latency_ms: 890, is_stream: true, raw_response: '{"id": "chatcmpl-pqr678", "model": "qwen2.5-14b", "choices": [{"message": {"role": "assistant", "content": "Analysis complete..."}, "finish_reason": "stop"}], "usage": {"total_tokens": 45500}}' },
]

const filteredLogs = computed(() => {
  let logs = [...sampleLogs]
  if (filters.value.model) logs = logs.filter(l => l.model === filters.value.model)
  if (filters.value.accountId) logs = logs.filter(l => l.account_id === filters.value.accountId)
  if (filters.value.statusCode) logs = logs.filter(l => l.status_code === Number(filters.value.statusCode))
  if (filters.value.isStream !== '' && filters.value.isStream !== undefined) logs = logs.filter(l => l.is_stream === filters.value.isStream)
  return logs
})

const selectedLog = ref(null)
const sampleMessages = ref([
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'Hello, what can you do? Please tell me in a friendly way.' },
  { role: 'assistant', content: 'Hi! I can help with writing, analysis, coding, and more. What would you like to explore? I am here to assist you with any task you have in mind.' },
])

const formatTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts.replace(' ', 'T'))
  return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' }) + ', ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
}

const logMeta = computed(() => {
  if (!selectedLog.value) return {}
  const l = selectedLog.value
  return {
    '请求 ID': l.request_id,
    '时间': l.timestamp,
    '模型': l.model,
    '实际模型': l.actual_model_id || l.model,
    '账户': l.account_id,
    '状态': l.status_code >= 400 ? l.status_code + ' Error' : '200 OK',
    '流式': l.is_stream ? '是' : '否',
    '延迟': l.latency_ms + 'ms',
  }
})

const showDetail = (log) => {
  selectedLog.value = log
}
</script>
