<template>
  <Teleport to="body">
    <div v-if="visible" class="drawer-overlay" :class="{ exiting }" @click.self="close">
      <div class="drawer-panel-fixed flex flex-col" :class="{ exiting }">
        <!-- Header -->
        <div class="flex items-center justify-between gap-3 px-4 py-3 lg:px-5 border-b border-ls-border flex-shrink-0 bg-ls-card">
          <div class="min-w-0">
            <div class="flex items-center gap-2.5 flex-wrap">
              <h2 class="text-base font-semibold text-ls-text">请求日志</h2>
              <StatusCodeBadge :code="modelValue.status_code" small padded />
            </div>
            <p class="text-xs text-ls-muted mt-0.5 truncate">{{ modelValue.request_id }} · {{ fmtMsTime(modelValue.timestamp) }}</p>
          </div>
          <button @click="close" class="drawer-close btn-esc flex-shrink-0" aria-label="关闭">
            <CIcon name="x" :size="18" />
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 flex flex-col lg:flex-row overflow-hidden">

          <!-- Left: Conversation Flow -->
          <div class="flex-1 overflow-y-auto p-3 lg:p-5">
            <div class="space-y-2">

              <!-- Request header -->
              <div class="bg-ls-card rounded-lg border border-ls-border p-3">
                <div class="flex items-center gap-3">
                  <span class="text-xs font-medium text-ls-muted uppercase tracking-wide">Request</span>
                  <span class="text-xs text-ls-muted">→ {{ modelValue.account_name || modelValue.account_id }}</span>
                  <span class="text-xs text-ls-muted">· {{ modelValue.actual_model_id || modelValue.model }}</span>
                  <span v-if="modelValue.actual_model_id && modelValue.model !== modelValue.actual_model_id" class="text-xs text-ls-dim">（路由: {{ modelValue.model }}）</span>
                  <span v-if="modelValue.is_stream" class="text-xs text-ls-accent">stream</span>
                </div>
              </div>

              <!-- ── History messages (before the last user message) ── -->
              <template v-if="historyMessages.length > 0">
                <button @click="showHistory = !showHistory"
                  class="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-dashed border-ls-border text-xs text-ls-muted hover:text-ls-text hover:border-ls-dim transition-colors">
                  <CIcon name="chevron-down" :size="12" class="transition-transform" :class="showHistory ? 'rotate-180' : ''" />
                  <span>{{ showHistory ? '收起历史消息' : '加载历史消息' }}</span>
                  <span class="text-ls-muted">{{ historyMessages.length }} 条</span>
                </button>
                <div v-if="showHistory" class="space-y-2">
                  <MessageCard v-for="(msg, i) in historyMessages" :key="'hist-' + i"
                    :msg="msg"
                    :expanded="!historyCollapsed[String(i)]"
                    :render-mode="renderModes[String(i)] || 'md'"
                    @toggle-expand="toggleHistoryCollapsed(i)"
                    @toggle-render="toggleHistoryRender(i)" />
                </div>
              </template>

              <!-- ── Current conversation (from the last user message onwards) ── -->
              <MessageCard v-for="(msg, i) in currentMessages" :key="'cur-' + i"
                :msg="msg"
                :expanded="expandedMap.get(currentStartIndex + i)"
                :render-mode="renderModes[String(currentStartIndex + i)] || 'md'"
                :highlight="i === 0"
                :input-badge="i === 0 && msg.role === 'user'"
                @toggle-expand="toggleExpanded(currentStartIndex + i)"
                @toggle-render="toggleRender(currentStartIndex + i)" />

              <!-- Assistant response (concatenated) -->
              <div v-if="responseContentText || responseToolCalls.length || responseReasoning" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
                <button @click="toggleResponseExpanded"
                  class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                  <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                  <span v-if="responseChunks.length > 1" class="text-xs text-ls-muted">{{ responseChunks.length }} chunks</span>
                  <button @click.stop="toggleResponseRender"
                    class="text-xs text-ls-muted hover:text-ls-text px-1.5 py-0.5 rounded transition-colors"
                    :class="responseRenderMode === 'raw' ? 'bg-ls-elevated text-ls-dim' : ''">
                    {{ responseRenderMode === 'raw' ? 'RAW' : 'MD' }}
                  </button>
                  <span class="ml-auto text-ls-muted text-xs transition-transform" :class="responseExpanded ? 'rotate-90' : ''">▶</span>
                </button>
                <div v-if="responseExpanded" class="px-4 pt-3 pb-3 text-xs text-ls-dim">
                  <!-- Reasoning -->
                  <div v-if="responseReasoning" class="mb-3">
                    <button @click.stop="toggleResponseReasoning"
                      class="flex items-center gap-1.5 text-xs text-ls-muted hover:text-ls-text transition-colors mb-1">
                      <CIcon name="lightbulb" :size="12" class="text-ls-muted" />
                      <span>思考过程</span>
                      <CIcon :name="responseReasoningExpanded ? 'chevron-up' : 'chevron-down'" :size="11" />
                    </button>
                    <div v-if="responseReasoningExpanded" class="text-ls-dim leading-relaxed bg-ls-elevated rounded-lg px-3 py-2 mb-2">
                      {{ responseReasoning }}
                    </div>
                  </div>
                  <!-- Tool calls -->
                  <div v-if="responseToolCalls.length > 0" class="mb-3">
                    <div class="text-xs text-ls-muted mb-1.5">工具调用</div>
                    <div class="space-y-2">
                      <ToolCallCard v-for="(tc, ti) in responseToolCalls" :key="ti" :tc="tc" />
                    </div>
                  </div>
                  <!-- Content -->
                  <div v-if="responseContentText">
                    <MarkdownRender v-if="responseRenderMode !== 'raw'" :source="responseContentText" />
                    <div v-else class="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{{ responseContentText }}</div>
                  </div>
                </div>
              </div>

            </div>
          </div>

          <!-- Right: Stats Panel -->
          <div class="w-full lg:w-80 flex-shrink-0 border-t lg:border-t-0 lg:border-l border-ls-border overflow-y-auto bg-ls-card"
               :class="statsExpanded ? 'max-h-[60vh]' : 'max-h-[52px] lg:max-h-none'">
            <button @click="statsExpanded = !statsExpanded"
                    class="lg:hidden w-full flex items-center justify-between p-3 text-left">
              <div class="flex items-center gap-4 text-xs">
                <span class="text-ls-dim">延迟: <span class="text-ls-text font-mono">{{ modelValue.latency_ms ? formatDuration(modelValue.latency_ms) : '-' }}</span></span>
                <span class="text-ls-dim">Token: <span class="text-ls-text font-mono">{{ ((modelValue.input_tokens || 0) + (modelValue.output_tokens || 0)).toLocaleString() }}</span></span>
              </div>
              <CIcon name="chevron-down" :size="16" class="text-ls-dim transition-transform" :class="statsExpanded ? 'rotate-180' : ''" />
            </button>
            <div :class="statsExpanded ? 'block' : 'hidden lg:block'">

            <!-- 模型信息 -->
            <StatsSection title="模型信息">
              <div class="space-y-2">
                <div class="flex justify-between text-sm"><span class="text-ls-dim">模型</span><span class="text-ls-text font-mono">{{ modelValue.model }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-ls-dim">实际模型</span><span class="text-ls-text font-mono">{{ modelValue.actual_model_id || modelValue.model }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-ls-dim">供应商</span><span class="text-ls-text">{{ modelValue.account_name || modelValue.account_id }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-ls-dim">API Key</span><span class="text-ls-text font-mono">{{ modelValue.client_key_name || '—' }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-ls-dim">流式</span><span class="text-ls-text">{{ modelValue.is_stream ? '是' : '否' }}</span></div>
              </div>
            </StatsSection>

            <!-- Token -->
            <StatsSection title="Token">
              <TokenStack
                :input="modelValue.input_tokens || 0"
                :output="modelValue.output_tokens || 0"
                :cache="(modelValue.cached_tokens || 0) + (modelValue.prompt_partial_cached || 0)"
                plain
              />
            </StatsSection>

            <!-- 请求时序 -->
            <StatsSection title="请求时序">
              <div class="space-y-1.5">
                <div v-if="modelValue.request_start">
                  <div class="text-xs text-ls-muted">请求开始</div>
                  <div class="text-xs text-ls-text font-mono">{{ fmtMsTime(modelValue.request_start) }}</div>
                </div>
                <div v-if="modelValue.first_response">
                  <div class="text-xs text-ls-muted">首次响应</div>
                  <div class="text-xs text-ls-accent font-mono">{{ fmtMsTime(modelValue.first_response) }}</div>
                </div>
                <div v-if="modelValue.request_start && ttfr">
                  <div class="text-xs text-ls-muted">首次响应耗时</div>
                  <div class="text-xs text-ls-text font-mono">{{ ttfr }}</div>
                </div>
                <div v-if="modelValue.end_time">
                  <div class="text-xs text-ls-muted">响应结束</div>
                  <div class="text-xs text-ls-text font-mono">{{ fmtMsTime(modelValue.end_time) }}</div>
                </div>
                <div v-if="totalDuration">
                  <div class="text-xs text-ls-muted">总耗时</div>
                  <div class="text-xs text-ls-text font-mono">{{ totalDuration }}</div>
                </div>
                <div v-if="!modelValue.request_start && !modelValue.end_time" class="text-xs text-ls-muted">—</div>
              </div>
            </StatsSection>

            <!-- 性能指标 -->
            <StatsSection title="性能指标">
              <div class="space-y-2">
                <div class="flex justify-between text-sm"><span class="text-ls-dim">延迟</span><span class="text-ls-text font-mono">{{ modelValue.latency_ms ? formatDuration(modelValue.latency_ms) : '-' }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-ls-dim">状态码</span>
                  <StatusCodeBadge :code="modelValue.status_code" small />
                </div>
                <div v-if="modelValue.error_message" class="mt-2">
                  <p class="text-xs text-red-400">{{ modelValue.error_message }}</p>
                </div>
              </div>
            </StatsSection>

            <!-- 响应头 -->
            <StatsSection v-if="responseHeaders" title="响应头">
              <template #action>
                <CopyButton :text="JSON.stringify(responseHeaders, null, 2)" />
              </template>
              <div class="space-y-1.5">
                <div v-for="(val, key) in responseHeaders" :key="key">
                  <div class="text-xs text-ls-muted font-mono">{{ key }}</div>
                  <div class="text-xs text-ls-text font-mono" :title="val">{{ val }}</div>
                </div>
              </div>
            </StatsSection>

            </div>
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import TokenStack from '@/components/TokenStack.vue'
import CIcon from '@/components/CIcon.vue'
import StatusCodeBadge from '@/components/StatusCodeBadge.vue'
import CopyButton from '@/components/CopyButton.vue'
import MessageCard from '@/components/log/MessageCard.vue'
import ToolCallCard from '@/components/log/ToolCallCard.vue'
import StatsSection from '@/components/log/StatsSection.vue'
import { formatTime, formatDuration } from '@/utils/format'

const props = defineProps({
  modelValue: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])
const showHistory = ref(false)

const statsExpanded = ref(false)

// ── 退出动画：先播 250ms 滑出/淡出，再销毁 DOM（与共享 Drawer 同构）──
const visible = ref(false)
const exiting = ref(false)
let exitingTimer = null

// ── Close on ESC (mirrors Drawer behavior) ──
const handleEsc = (e) => {
  if (e.key === 'Escape' && props.modelValue) {
    close()
    e.stopImmediatePropagation()
  }
}
onMounted(() => document.addEventListener('keydown', handleEsc))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEsc)
  if (exitingTimer) clearTimeout(exitingTimer)
})

// ── Find the index of the last user message (the one that triggered this request) ──
const lastUserIndex = computed(() => {
  const msgs = conversationMessages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') return i
  }
  return -1
})

// Messages before the last user message = history
const historyMessages = computed(() => {
  return lastUserIndex.value >= 0
    ? conversationMessages.value.slice(0, lastUserIndex.value)
    : []
})

// Messages from the last user message onwards = current conversation
const currentMessages = computed(() => {
  if (lastUserIndex.value >= 0) {
    return conversationMessages.value.slice(lastUserIndex.value)
  }
  return conversationMessages.value
})
const currentStartIndex = computed(() => lastUserIndex.value >= 0 ? lastUserIndex.value : 0)

// ── Expand / collapse state ──
const collapsedMsgs = ref({})
const historyCollapsed = ref({})
const responseExpanded = ref(true)
const responseRenderMode = ref('md')
const responseReasoningExpanded = ref(false)
const renderModes = ref({})

const close = () => {
  if (exiting.value) return
  exiting.value = true
  exitingTimer = setTimeout(() => {
    visible.value = false
    exiting.value = false
    emit('update:modelValue', null)
  }, 250)
}

watch(() => props.modelValue, (val) => {
  renderModes.value = {}
  responseExpanded.value = true
  responseRenderMode.value = 'md'
  responseReasoningExpanded.value = false
  showHistory.value = false

  if (val) {
    visible.value = true
    exiting.value = false

    // History messages: all collapsed
    const hist = {}
    for (let i = 0; i < historyMessages.value.length; i++) {
      hist[String(i)] = true
    }
    historyCollapsed.value = hist

    // Current messages: collapse system/tool/tool_call, leave user/assistant expanded
    const curr = {}
    for (let i = currentStartIndex.value; i < conversationMessages.value.length; i++) {
      const msg = conversationMessages.value[i]
      if (msg.role === 'system' || msg.role === 'tool' || msg.role === 'tool_call') {
        curr[String(i)] = true
      }
    }
    collapsedMsgs.value = curr
  } else {
    collapsedMsgs.value = {}
    historyCollapsed.value = {}
    if (visible.value) close()
  }
}, { immediate: true })

function toggleRender(i) {
  const key = String(i)
  renderModes.value[key] = renderModes.value[key] === 'raw' ? 'md' : 'raw'
}

function toggleHistoryRender(i) {
  const key = String(i)
  renderModes.value[key] = renderModes.value[key] === 'raw' ? 'md' : 'raw'
}

function toggleResponseRender() {
  responseRenderMode.value = responseRenderMode.value === 'raw' ? 'md' : 'raw'
}

function toggleResponseReasoning() {
  responseReasoningExpanded.value = !responseReasoningExpanded.value
}

// ── Parse raw_request to extract conversation messages ──
// Strategy:
//   1. assistant with tool_calls → split into individual "tool_call" cards
//      (each shows: tool type, name, id, 入参)
//   2. tool role messages → merge into the matching tool_call card by tool_call_id,
//      becoming the 出参.
const conversationMessages = computed(() => {
  if (!props.modelValue?.raw_request) return []
  try {
    const parsed = JSON.parse(props.modelValue.raw_request)
    const messages = parsed.messages || []
    const out = []

    // Pass 1: flatten all messages, split assistant tool_calls into individual entries
    for (const msg of messages) {
      // Keep original content (string or array for multimodal) as-is
      const content = msg.content
      const reasoning = msg.reasoning_content || msg.reasoning || msg.thinking || ''
      const calls = msg.tool_calls || msg.toolCalls

      if (msg.role === 'assistant' && calls && Array.isArray(calls)) {
        // Check if there's anything to display (text content, reasoning, or images)
        const hasContent = typeof content === 'string' ? !!content
          : Array.isArray(content) && content.some(c => c.type === 'text' && c.text)
        const hasImages = Array.isArray(content) && content.some(c => c.type === 'image_url' && c.image_url?.url)
        if (hasContent || reasoning || hasImages) {
          out.push({ role: 'assistant', content, reasoning, toolCalls: null })
        }
        for (const tc of calls) {
          let args = tc.function?.arguments || '{}'
          try { args = JSON.parse(args) } catch {}
          out.push({
            role: 'tool_call',
            content: '',
            reasoning: '',
            toolName: tc.function?.name || 'unknown',
            toolId: tc.id || '',
            toolArguments: typeof args === 'string' ? args : JSON.stringify(args, null, 2),
            toolResult: '',
          })
        }
      } else {
        out.push({
          role: msg.role,
          content,
          reasoning,
          toolCalls: null,
          toolResult: '',
          // Preserve tool_call_id on tool role messages so Pass 2 can match
          tool_call_id: msg.tool_call_id || msg.toolCallId || '',
        })
      }
    }

    // Filter out empty assistant messages from the request history — their
    // actual content already appears in the raw_response Assistant card below.
    out = out.filter((m) => {
      if (m.role !== 'assistant') return true
      const hasContent = typeof m.content === 'string'
        ? m.content.length > 0
        : Array.isArray(m.content) && m.content.some((c) => c.type === 'text' && c.text)
      return hasContent || !!m.reasoning || m.toolCalls?.length > 0
    })

    // Pass 2: merge tool results into matching tool_call entries by tool_call_id.
    // assistant 单轮可能并发多个 tool_calls，展平后顺序为
    // [call A, call B, result A, result B]，结果与调用并不相邻，
    // 因此需跨整个列表按 id 匹配，而不是只看紧邻消息。
    const consumed = new Set()
    for (const msg of out) {
      if (msg.role !== 'tool_call' || !msg.toolId) continue
      for (let j = 0; j < out.length; j++) {
        if (consumed.has(j)) continue
        const toolMsg = out[j]
        if (toolMsg.role === 'tool' && toolMsg.tool_call_id === msg.toolId) {
          msg.toolResult = toolMsg.content
          consumed.add(j) // consume the tool message (don't render standalone)
        }
      }
    }

    return out.filter((_, idx) => !consumed.has(idx))
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

function toggleHistoryCollapsed(i) {
  const key = String(i)
  if (historyCollapsed.value[key]) {
    delete historyCollapsed.value[key]
  } else {
    historyCollapsed.value[key] = true
  }
}

// ── Shared response-stream parser ──
import { parseResponseStreams } from '@/composables/useResponseParser'

// ── Parse raw_response into chunks ──
const responseChunks = computed(() => {
  const raw = props.modelValue?.raw_response
  if (!raw) return []
  const parsed = parseResponseStreams(raw)
  if (!parsed) return [raw]
  const chunks = []
  for (const c of parsed.choices) {
    const content = c.message?.content || c.delta?.content || ''
    if (content) chunks.push(content)
  }
  return chunks
})

const responseContentText = computed(() => responseChunks.value.join(''))

// ── Extract tool_calls from raw_response (response-side, not history) ──
const responseToolCalls = computed(() => {
  const raw = props.modelValue?.raw_response
  if (!raw) return []
  const parsed = parseResponseStreams(raw)
  if (!parsed) return []
  const out = []
  for (const c of parsed.choices) {
    // Streamed: use merged tool_calls
    if (c._mergedToolCalls) {
      for (const t of c._mergedToolCalls) {
        out.push({
          id: t.id || '',
          type: t.type || 'function',
          name: t.name || 'unknown',
          arguments: t.arguments || '{}',
        })
      }
      continue
    }
    // Non-streamed: use message.tool_calls
    const tc = c.message?.tool_calls || []
    if (!Array.isArray(tc)) continue
    for (const t of tc) {
      out.push({
        id: t.id || '',
        type: t.type || 'function',
        name: t.function?.name || 'unknown',
        arguments: t.function?.arguments || '{}',
      })
    }
  }
  return out
})

// ── Extract reasoning_content from raw_response ──
const responseReasoning = computed(() => {
  const raw = props.modelValue?.raw_response
  if (!raw) return ''
  const parsed = parseResponseStreams(raw)
  if (!parsed) return ''
  const parts = []
  for (const c of parsed.choices) {
    const r = c.message?.reasoning_content || c.delta?.reasoning_content || ''
    if (r) parts.push(r)
  }
  return parts.join('')
})

const fmtMsTime = (ts) => formatTime(ts, { ms: true })

const ttfr = computed(() => {
  const start = props.modelValue?.request_start
  const first = props.modelValue?.first_response
  if (!start || !first) return null
  try { return formatDuration(Math.round((new Date(first) - new Date(start)) / 1)) } catch { return null }
})

const totalDuration = computed(() => {
  const start = props.modelValue?.request_start
  const end = props.modelValue?.end_time
  if (!start || !end) return null
  try { return formatDuration(Math.round((new Date(end) - new Date(start)) / 1)) } catch { return null }
})

const responseHeaders = computed(() => {
  const raw = props.modelValue?.response_headers
  if (!raw) return null
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return null }
})
</script>

<style scoped>
/* Responsive drawer panel: full-screen below lg, 1300px on desktop.
   Reuses the shared .drawer-overlay backdrop from main.css. */
.drawer-panel-fixed {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: var(--ls-card);
  border-left: 1px solid var(--border);
  animation: slideInRight .25s cubic-bezier(.4,0,.2,1);
}
.drawer-panel-fixed.exiting {
  animation: slideOutRight .25s cubic-bezier(.4,0,.2,1) forwards;
}
@media (min-width: 1024px) {
  .drawer-panel-fixed {
    inset: 0 0 0 auto;
    width: 1300px;
    max-width: 92vw;
  }
}
</style>
