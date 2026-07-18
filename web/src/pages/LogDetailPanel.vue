<template>
  <Teleport to="body">
    <!-- Overlay -->
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50" @click.self="close"></div>

    <!-- Drawer (v-show keeps element in DOM so CSS transition always fires) -->
    <div v-show="modelValue" class="fixed top-0 right-0 bottom-0 w-[1300px] bg-ls-bg border-l border-ls-border z-50 flex flex-col shadow-2xl"
      :class="showDrawer ? 'translate-x-0' : 'translate-x-full'"
      :style="{ transition: 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)' }">

      <template v-if="modelValue">
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3 border-b border-ls-border bg-ls-card flex-shrink-0">
        <div>
          <h2 class="text-base font-semibold text-white">请求日志</h2>
          <p class="text-xs text-gray-500 mt-0.5">{{ modelValue.request_id }} · {{ formatMsTime(modelValue.timestamp) }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs"
            :class="modelValue.status_code >= 400 ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'">
            {{ modelValue.status_code }}
          </span>
          <button @click="close" class="text-gray-500 hover:text-white p-1">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Body -->
      <div class="flex-1 flex overflow-hidden">

        <!-- Left: Conversation Flow -->
        <div class="flex-1 overflow-y-auto p-5">
          <div class="space-y-2">

            <!-- Request header -->
            <div class="bg-ls-card rounded-lg border border-ls-border p-3">
              <div class="flex items-center gap-3">
                <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Request</span>
                <span class="text-xs text-gray-600">→ {{ modelValue.account_name || modelValue.account_id }}</span>
                <span class="text-xs text-gray-600">· {{ modelValue.model }}</span>
                <span v-if="modelValue.is_stream" class="text-xs text-ls-accent">stream</span>
              </div>
            </div>

            <!-- Request messages -->
            <div v-for="(msg, i) in conversationMessages" :key="'req-' + i"
              class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
              <button @click="toggleExpanded(i)"
                class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                <span v-if="msg.role === 'system'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-ls-accent/10 text-ls-accent">System</span>
                <span v-else-if="msg.role === 'user'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-green-500/10 text-green-400">User</span>
                <span v-else-if="msg.role === 'assistant'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                <span v-else-if="msg.role === 'tool'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">Tool</span>
                <span v-else-if="msg.role === 'tool_call'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-blue-500/10 text-blue-400">
                  <span v-if="msg.toolCalls && msg.toolCalls[0]" :class="toolTypeColor(msg.toolCalls[0].name)">
                    {{ toolTypeLabel(msg.toolCalls[0].name) }}
                  </span>
                  <span class="ml-1 text-xs text-gray-400">{{ msg.toolCalls && msg.toolCalls[0] ? msg.toolCalls[0].name : 'Tool' }}</span>
                  <span v-if="msg.toolCalls && msg.toolCalls[0]?.id" class="ml-1 text-xs text-gray-500 font-mono">{{ msg.toolCalls[0].id }}</span>
                </span>
                <!-- Markdown / Raw toggle -->
                <button v-if="msg.content" @click.stop="toggleRender(i)"
                  class="text-xs text-gray-500 hover:text-white px-1.5 py-0.5 rounded transition-colors"
                  :class="renderModes[i] === 'raw' ? 'bg-ls-elevated text-gray-300' : ''">
                  {{ renderModes[i] === 'raw' ? 'RAW' : 'MD' }}
                </button>
                <span class="ml-auto text-gray-500 text-xs transition-transform" :class="expandedMap.get(i) ? 'rotate-90' : ''">▶</span>
              </button>
              <!-- Expanded content: Markdown or Raw -->
              <div v-if="expandedMap.get(i)" class="px-4 py-3 text-xs text-gray-300">
                <!-- Normal messages: show content -->
                <template v-if="msg.role !== 'tool_call'">
                  <MarkdownRender v-if="msg.content && renderModes[i] !== 'raw'" :source="msg.content" />
                  <pre v-if="msg.content && renderModes[i] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
                  <span v-if="!msg.content && !msg.toolCalls" class="text-gray-600 text-xs italic">—</span>
                </template>
                <!-- Tool call: header already shows tool name, just show args/result -->
                <template v-else-if="msg.toolCalls && msg.toolCalls.length > 0">
                  <div v-for="(tc, ti) in msg.toolCalls" :key="ti">
                    <div v-if="ti > 0" class="pt-2 mt-2 border-t border-ls-border"></div>
                    <div class="text-xs text-gray-300 mb-2">
                      <span class="text-gray-500">Args:</span>
                      <MarkdownRender :source="tc.arguments" />
                    </div>
                    <div v-if="tc.result" class="mt-2 pt-2 border-t border-ls-border">
                      <div class="flex items-center gap-2 mb-1">
                        <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">Result</span>
                      </div>
                      <MarkdownRender :source="tc.result" />
                    </div>
                  </div>
                </template>
              </div>
              <!-- Tool calls nested in assistant messages (not tool_call role) -->
              <div v-if="expandedMap.get(i) && msg.toolCalls && msg.role !== 'tool_call'" class="px-4 py-3 space-y-2">
                <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="bg-ls-bg rounded-lg border border-ls-border p-3">
                  <div class="flex items-center gap-2 mb-2">
                    <span :class="toolTypeColor(tc.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                      {{ toolTypeLabel(tc.name) }}
                    </span>
                    <span class="text-xs text-gray-400 font-medium">{{ tc.name }}</span>
                    <span v-if="tc.id" class="text-xs text-gray-500 font-mono">{{ tc.id }}</span>
                  </div>
                  <div class="text-xs text-gray-300 mb-2">
                    <span class="text-gray-500">Args:</span>
                    <MarkdownRender :source="tc.arguments" />
                  </div>
                  <div v-if="tc.result" class="mt-2 pt-2 border-t border-ls-border">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">Result</span>
                    </div>
                    <MarkdownRender :source="tc.result" />
                  </div>
                </div>
              </div>
            </div>

            <!-- Tool call cards (from tool_calls_info field) -->
            <div v-if="toolCallCards.length > 0" class="space-y-2">
              <div class="flex items-center gap-2 px-1 pt-2">
                <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">工具调用</span>
                <span class="text-xs text-gray-600">{{ toolCallCards.length }} calls</span>
              </div>
              <div v-for="(tc, i) in toolCallCards" :key="'tool-' + i"
                class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
                <button @click="tc.expanded = !tc.expanded"
                  class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                  <span :class="toolTypeColor(tc.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                    {{ toolTypeLabel(tc.name) }}
                  </span>
                  <span class="text-xs text-gray-400 font-medium">{{ tc.name }}</span>
                  <span v-if="tc.id" class="text-xs text-gray-500 font-mono">{{ tc.id }}</span>
                  <span class="ml-auto text-gray-500 text-xs transition-transform" :class="tc.expanded ? 'rotate-90' : ''">▶</span>
                </button>
                <div v-if="tc.expanded" class="px-4 pb-3 text-xs text-gray-300">
                  <pre class="bg-ls-bg rounded-lg border border-ls-border p-3 font-mono whitespace-pre-wrap overflow-x-auto">{{ JSON.stringify(tc, null, 2) }}</pre>
                </div>
              </div>
            </div>

            <!-- Assistant response (concatenated) -->
            <div v-if="responseContentText" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
              <button @click="toggleResponseExpanded"
                class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                <span v-if="responseChunks.length > 1" class="text-xs text-gray-600">{{ responseChunks.length }} chunks</span>
                <!-- Markdown / Raw toggle -->
                <button @click.stop="toggleResponseRender"
                  class="text-xs text-gray-500 hover:text-white px-1.5 py-0.5 rounded transition-colors"
                  :class="responseRenderMode === 'raw' ? 'bg-ls-elevated text-gray-300' : ''">
                  {{ responseRenderMode === 'raw' ? 'RAW' : 'MD' }}
                </button>
                <span class="ml-auto text-gray-500 text-xs transition-transform" :class="responseExpanded ? 'rotate-90' : ''">▶</span>
              </button>
              <div v-if="responseExpanded" class="px-4 pb-3 text-xs text-gray-300">
                <MarkdownRender v-if="responseRenderMode !== 'raw'" :source="responseContentText" />
                <pre v-if="responseRenderMode === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 font-mono whitespace-pre-wrap overflow-x-auto">{{ responseContentText }}</pre>
              </div>
            </div>

          </div>
        </div>

        <!-- Right: Stats Panel -->
        <div class="w-80 flex-shrink-0 border-l border-ls-border overflow-y-auto bg-ls-card">

          <!-- 模型信息 -->
          <div class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">模型信息</h3>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-gray-400">模型</span><span class="text-white font-mono">{{ modelValue.model }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">实际模型</span><span class="text-white font-mono">{{ modelValue.actual_model_id || modelValue.model }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">供应商</span><span class="text-white">{{ modelValue.account_name || modelValue.account_id }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">API Key</span><span class="text-white font-mono">{{ modelValue.client_key_name || '—' }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">流式</span><span class="text-white">{{ modelValue.is_stream ? '是' : '否' }}</span></div>
            </div>
          </div>

          <!-- Token 统计 -->
          <div class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Token 统计</h3>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-gray-400">输入 Token</span><span class="text-white font-mono">{{ (modelValue.input_tokens || 0).toLocaleString() }}</span></div>
              <div v-if="modelValue.cached_tokens || modelValue.prompt_partial_cached">
                <div class="flex justify-between text-xs">
                  <span class="text-gray-500 flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500"></span>缓存命中</span>
                  <span class="text-green-400 font-mono">{{ (modelValue.cached_tokens || 0).toLocaleString() }}</span>
                </div>
                <div v-if="modelValue.prompt_partial_cached" class="flex justify-between text-xs mt-1">
                  <span class="text-gray-500 flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-yellow-500"></span>部分缓存</span>
                  <span class="text-yellow-400 font-mono">{{ (modelValue.prompt_partial_cached || 0).toLocaleString() }}</span>
                </div>
              </div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">输出 Token</span><span class="text-white font-mono">{{ (modelValue.output_tokens || 0).toLocaleString() }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">总 Token</span><span class="text-white font-mono">{{ ((modelValue.input_tokens || 0) + (modelValue.output_tokens || 0)).toLocaleString() }}</span></div>
            </div>
          </div>

          <!-- 请求时序 -->
          <div class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">请求时序</h3>
            <div class="space-y-1.5">
              <div v-if="modelValue.request_start">
                <div class="text-xs text-gray-500">请求开始</div>
                <div class="text-xs text-white font-mono">{{ formatMsTime(modelValue.request_start) }}</div>
              </div>
              <div v-if="modelValue.first_response">
                <div class="text-xs text-gray-500">首次响应 (TTFR)</div>
                <div class="text-xs text-ls-accent font-mono">{{ formatMsTime(modelValue.first_response) }}</div>
                <div v-if="modelValue.request_start && ttfr" class="text-xs text-gray-500 ml-4">{{ ttfr }}</div>
              </div>
              <div v-if="modelValue.end_time">
                <div class="text-xs text-gray-500">响应结束</div>
                <div class="text-xs text-white font-mono">{{ formatMsTime(modelValue.end_time) }}</div>
              </div>
              <div v-if="totalDuration">
                <div class="text-xs text-gray-500">总耗时</div>
                <div class="text-xs text-white font-mono">{{ totalDuration }} ms</div>
              </div>
              <div v-if="!modelValue.request_start && !modelValue.end_time" class="text-xs text-gray-600">—</div>
            </div>
          </div>

          <!-- 工具统计 -->
          <div v-if="toolStats.length > 0" class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">工具统计</h3>
            <div class="space-y-1.5">
              <div v-for="(stat, i) in toolStats" :key="i"
                class="flex items-center justify-between">
                <span class="text-xs text-gray-400 flex items-center gap-1.5">
                  <span :class="toolTypeColor(stat.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px]">
                    {{ toolTypeLabel(stat.name) }}
                  </span>
                  <span>{{ stat.name }}</span>
                </span>
                <span class="text-xs text-white font-mono">{{ stat.count }}</span>
              </div>
              <div class="flex justify-between text-xs mt-1 pt-1.5 border-t border-ls-border">
                <span class="text-gray-500">合计</span>
                <span class="text-white font-mono">{{ totalToolCalls }}</span>
              </div>
            </div>
          </div>

          <!-- 性能指标 -->
          <div class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">性能指标</h3>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-gray-400">延迟</span><span class="text-white font-mono">{{ modelValue.latency_ms ? modelValue.latency_ms + ' ms' : '-' }}</span></div>
              <div class="flex justify-between text-sm"><span class="text-gray-400">状态码</span>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs"
                  :class="modelValue.status_code >= 400 ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'">
                  {{ modelValue.status_code }}
                </span>
              </div>
              <div v-if="modelValue.error_message" class="mt-2">
                <p class="text-xs text-red-400">{{ modelValue.error_message }}</p>
              </div>
            </div>
          </div>

          <!-- 响应头 -->
          <div v-if="responseHeaders" class="p-4 border-b border-ls-border">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide">响应头</h3>
              <button @click="copyText(JSON.stringify(responseHeaders, null, 2))" class="text-gray-500 hover:text-white">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
            </div>
            <div class="space-y-1">
              <div v-for="(val, key) in responseHeaders" :key="key" class="flex justify-between text-xs">
                <span class="text-gray-500 font-mono">{{ key }}</span>
                <span class="text-white font-mono truncate ml-2" :title="val">{{ val }}</span>
              </div>
            </div>
          </div>

          <!-- 请求数据 -->
          <div v-if="modelValue.raw_request" class="p-4">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">请求数据</h3>
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs text-gray-400">JSON</span>
              <button @click="copyText(modelValue.raw_request)" class="text-gray-500 hover:text-white">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </button>
            </div>
            <pre class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">{{ formatJson(modelValue.raw_request) }}</pre>
          </div>

        </div>

      </div>
      </template>

    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Teleport } from 'vue'
import MarkdownRender from '@/components/MarkdownRender.vue'

const props = defineProps({
  modelValue: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])
const showDrawer = ref(false)

// Expand state
const collapsedMsgs = ref({})
const responseExpanded = ref(true)
const responseRenderMode = ref('md')  // 'md' | 'raw'
const renderModes = ref({})  // index -> 'md' | 'raw'

const close = () => {
  showDrawer.value = false
  setTimeout(() => {
    emit('update:modelValue', null)
  }, 350)
}

// ESC to close
const handleKeydown = (e) => {
  if (e.key === 'Escape') close()
}
onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

// When modelValue changes, show drawer after next tick
watch(() => props.modelValue, (val) => {
  if (val) {
    nextTick(() => {
      showDrawer.value = true
      collapsedMsgs.value = {}
      renderModes.value = {}
      responseExpanded.value = true
      responseRenderMode.value = 'md'
    })
  } else {
    showDrawer.value = false
  }
}, { immediate: true })

function toggleRender(i) {
  const key = String(i)
  renderModes.value[key] = renderModes.value[key] === 'raw' ? 'md' : 'raw'
}

function toggleResponseRender() {
  responseRenderMode.value = responseRenderMode.value === 'raw' ? 'md' : 'raw'
}

// ── Parse raw_request to extract conversation messages ──
const conversationMessages = computed(() => {
  if (!props.modelValue?.raw_request) return []
  try {
    const parsed = JSON.parse(props.modelValue.raw_request)
    const messages = parsed.messages || []
    const out = []
    for (const msg of messages) {
      const content = typeof msg.content === 'string' ? msg.content : ''
      const calls = msg.tool_calls || msg.toolCalls

      // Assistant with tool calls: split into content + separate tool call entries
      if (msg.role === 'assistant' && calls && Array.isArray(calls)) {
        if (content) {
          out.push({ role: 'assistant', content, toolCalls: null })
        }
        for (const tc of calls) {
          let args = tc.function?.arguments || '{}'
          try { args = JSON.parse(args) } catch {}
          out.push({
            role: 'tool_call',
            content: '',
            toolCalls: [{
              id: tc.id || '',
              name: tc.function?.name || 'unknown',
              arguments: typeof args === 'string' ? args : JSON.stringify(args, null, 2),
              result: '',
            }],
          })
        }
      } else {
        // Plain message
        const toolCalls = calls && Array.isArray(calls)
          ? calls.map(tc => ({
              id: tc.id || '',
              name: tc.function?.name || 'unknown',
              arguments: typeof tc.function?.arguments === 'string' ? tc.function.arguments : JSON.stringify(tc.function?.arguments || {}, null, 2),
              result: '',
            }))
          : null
        out.push({ role: msg.role, content, toolCalls })
      }
    }
    return out
  } catch (e) {
    return []
  }
})

const expandedMap = computed(() => {
  const map = new Map()
  const msgs = conversationMessages.value
  for (let i = 0; i < msgs.length; i++) {
    map.set(i, !collapsedMsgs.value[String(i)])
  }
  return map
})

function toggleExpanded(i) {
  const key = String(i)
  if (collapsedMsgs.value[key]) {
    delete collapsedMsgs.value[key]
  } else {
    collapsedMsgs.value[key] = true
  }
}

// ── Parse raw_response into chunks ──
const responseChunks = computed(() => {
  const raw = props.modelValue?.raw_response
  if (!raw) return []

  const chunks = []

  try {
    const parsed = JSON.parse(raw)
    const choices = parsed.choices || []
    if (choices.length > 0) {
      for (const choice of choices) {
        const message = choice.message || {}
        const delta = choice.delta || {}
        const c = message.content || delta.content || ''
        if (c) chunks.push(c)
      }
    }
    return chunks
  } catch (e) {}

  if (raw.startsWith('data:')) {
    const lines = raw.split('\n')
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const dataStr = line.slice(5).trim()
      if (dataStr === '[DONE]' || !dataStr) continue
      try {
        const obj = JSON.parse(dataStr)
        const choices = obj.choices || []
        for (const choice of choices) {
          const msg = choice.message || {}
          const delta = choice.delta || {}
          const c = msg.content || delta.content || ''
          if (c) chunks.push(c)
        }
      } catch {}
    }
    return chunks
  }

  try {
    let pos = 0
    while (pos < raw.length) {
      let start = pos
      let depth = 0, inString = false, escape = false, end = start
      for (let i = start; i < raw.length; i++) {
        const ch = raw[i]
        if (inString) {
          if (escape) { escape = false }
          else if (ch === '\\') { escape = true }
          else if (ch === '"') { inString = false }
        } else {
          if (ch === '"') { inString = true }
          else if (ch === '{') { depth++ }
          else if (ch === '}') { depth--; if (depth === 0) { end = i + 1; break } }
        }
      }
      if (end <= start) break
      const obj = JSON.parse(raw.slice(start, end))
      const choices = obj.choices || []
      if (choices.length > 0) {
        for (const choice of choices) {
          const msg = choice.message || {}
          const delta = choice.delta || {}
          const c = msg.content || delta.content || ''
          if (c) chunks.push(c)
        }
      }
      pos = end
    }
    return chunks
  } catch (e) {}

  return [raw]
})

const responseContentText = computed(() => {
  return responseChunks.value.join('')
})

// ── Tool calls from tool_calls_info field ──
const toolCallCards = computed(() => {
  const raw = props.modelValue?.tool_calls_info
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return parsed.map(t => ({ ...t, expanded: false }))
    }
    return []
  } catch {
    return []
  }
})

// Tool stats: count by name
const toolStats = computed(() => {
  const cards = toolCallCards.value
  const counts = {}
  for (const t of cards) {
    counts[t.name] = (counts[t.name] || 0) + 1
  }
  return Object.entries(counts).map(([name, count]) => ({ name, count }))
})

const totalToolCalls = computed(() => {
  return toolCallCards.value.length
})

// ── Timing helpers ──
const ttfr = computed(() => {
  const start = props.modelValue?.request_start
  const first = props.modelValue?.first_response
  if (!start || !first) return null
  try {
    return Math.round((new Date(first) - new Date(start)) / 1) + ' ms'
  } catch { return null }
})

const totalDuration = computed(() => {
  const start = props.modelValue?.request_start
  const end = props.modelValue?.end_time
  if (!start || !end) return null
  try {
    return Math.round((new Date(end) - new Date(start)) / 1) + ' ms'
  } catch { return null }
})

// ── Tool type helpers ──
function toolTypeColor(name) {
  const n = (name || '').toLowerCase()
  if (n.startsWith('mcp_')) return 'bg-blue-500/10 text-blue-400'
  if (n.startsWith('skill:')) return 'bg-orange-500/10 text-orange-400'
  return 'bg-ls-accent/10 text-ls-accent'
}

function toolTypeLabel(name) {
  const n = (name || '').toLowerCase()
  if (n.startsWith('mcp_')) return 'MCP'
  if (n.startsWith('skill:')) return 'Skill'
  return 'Tool'
}

// ── Formatting ──
function formatMsTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    const pad = (n, l = 2) => String(n).padStart(l, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`
  } catch {
    return ts
  }
}

const formatTime = formatMsTime  // alias for backward compat

const formatJson = (str) => {
  if (!str) return '(empty)'
  try { return JSON.stringify(JSON.parse(str), null, 2) } catch { return str }
}

// ── Response headers parser ──
const responseHeaders = computed(() => {
  const raw = props.modelValue?.response_headers
  if (!raw) return null
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return null
  }
})

const copyText = (text) => navigator.clipboard.writeText(text).catch(() => {})

</script>
