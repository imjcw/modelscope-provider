<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="临时会话 // Chat" subtitle="// 与 API 代理对话测试">
      <template #action>
        <button @click="sidebarCollapsed = !sidebarCollapsed"
          class="h-8 w-8 flex items-center justify-center rounded-md text-ls-dim hover:text-ls-text hover:bg-ls-elevated transition-colors"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          aria-label="切换侧边栏">
          <!-- 展开状态：panel-right-close 图标 -->
          <svg v-if="!sidebarCollapsed" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect width="18" height="18" x="3" y="3" rx="2"/>
            <path d="M15 3v18"/>
            <path d="m8 9 3 3-3 3"/>
          </svg>
          <!-- 折叠状态：panel-right-open 图标 -->
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect width="18" height="18" x="3" y="3" rx="2"/>
            <path d="M15 3v18"/>
            <path d="m10 15-3-3 3-3"/>
          </svg>
        </button>
      </template>
    </PageHeader>

    <div class="flex-1 flex min-h-0">
      <!-- 聊天区域 -->
      <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div class="relative flex-1 flex flex-col min-w-0 overflow-hidden">
          <div ref="chatScrollEl" class="h-full overflow-y-auto" @scroll.passive="onChatScroll">
            <div v-if="messages.length === 0"
              class="h-full flex flex-col items-center justify-center text-ls-muted px-8">
              <div class="w-12 h-12 rounded-full bg-ls-elevated flex items-center justify-center mb-4">
                <CIcon name="message" :size="22" :stroke-width="1.5" class="text-ls-muted opacity-60" />
              </div>
              <p class="text-sm">有什么我能帮您的吗？</p>
            </div>

            <div v-else ref="chatContentEl" class="max-w-none mx-auto px-3 md:px-6 py-6 space-y-6">
              <div v-for="(msg, idx) in messages" :key="idx">
                <!-- 助手消息：带边框的卡片，左侧小头像，右侧内容 -->
                <div v-if="msg.role === 'assistant'" class="flex flex-col gap-1">
                  <div class="flex gap-3">
                    <div class="w-7 h-7 rounded-full bg-ls-card border border-ls-border flex items-center justify-center flex-shrink-0 mt-1">
                      <CIcon name="terminal" :size="12" class="text-blue-400" />
                    </div>
                    <div class="flex-1 min-w-0 rounded-2xl bg-ls-card border border-ls-border px-4 py-3 text-ls-text">
                      <!-- 思考过程（可折叠） -->
                      <div v-if="msg.reasoning">
                        <button @click="msg.showReasoning = !msg.showReasoning"
                          class="flex items-center gap-1.5 text-xs text-ls-muted hover:text-ls-text transition-colors mb-2">
                          <CIcon name="lightbulb" :size="12" class="text-ls-muted" />
                          <span>已完成思考</span>
                          <CIcon :name="msg.showReasoning ? 'chevron-up' : 'chevron-down'" :size="11" />
                        </button>
                        <div v-if="msg.showReasoning"
                          class="text-xs text-ls-dim leading-relaxed bg-ls-elevated rounded-lg px-3 py-2 mb-3">
                          {{ msg.reasoning }}
                        </div>
                      </div>

                      <!-- 回复内容 -->
                      <div v-if="msg.content">
                        <MarkdownRender v-if="msg.renderMode !== 'raw'" :source="msg.content" />
                        <div v-else class="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
                          {{ msg.content }}
                        </div>
                      </div>

                      <p v-else-if="msg.status === 'loading'"
                        class="text-sm flex items-center py-2">
                        <span class="text-xs breathing-text">思考中</span>
                      </p>
                    </div>
                  </div>

                  <!-- 模型信息和操作栏：气泡外部，气泡下方 -->
                  <div v-if="msg.status !== 'loading'" class="flex items-center gap-3 ml-10">
                    <button @click="copyText(msg.content || msg.raw || '', msg._copyKey)"
                      class="flex items-center justify-center h-6 w-6 rounded hover:bg-ls-elevated text-ls-dim hover:text-ls-text transition-colors"
                      title="复制">
                      <CIcon name="copy" :size="12" />
                    </button>
                    <span class="text-[11px] text-ls-muted font-mono">
                      {{ msg.model || 'AI' }}
                    </span>
                  </div>
                </div>
                <div v-else class="flex justify-end flex-col items-end gap-2">
                  <div class="max-w-[75%] bg-blue-600 rounded-2xl rounded-br-sm px-4 py-2.5 text-sm font-mono leading-relaxed"
                    style="color: #fff;">
                    {{ msg.content }}
                  </div>
                  <button @click="replayMessage(idx)"
                    class="h-6 w-6 flex items-center justify-center rounded hover:bg-ls-elevated text-ls-dim hover:text-ls-text transition-colors"
                    title="重发">
                    <CIcon name="refresh" :size="11" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 回到底部：用户上滚阅读时出现，流式输出中带呼吸点提示有新内容 -->
          <Transition name="back-to-bottom">
            <button v-if="!stickToBottom && messages.length > 0" @click="goToBottom"
              aria-label="回到底部" title="回到底部"
              class="absolute bottom-4 left-0 right-0 mx-auto h-9 w-9 flex items-center justify-center rounded-full border border-ls-border bg-ls-card text-ls-muted shadow-lg shadow-black/20 hover:text-ls-text hover:border-blue-500/50 hover:-translate-y-0.5 transition-all duration-200">
              <!-- 流式输出中：右上角呼吸点，提示有新内容 -->
              <span v-if="sending"
                class="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-cyan-400 animate-pulse ring-2 ring-ls-card"></span>
              <svg width="16" height="16" stroke="currentColor" aria-hidden="true" focusable="false"><use xlink:href="#icon-line-arrow-down"></use></svg>
            </button>
          </Transition>
        </div>

        <!-- 输入栏 -->
        <div class="px-3 md:px-6 pb-3">
          <div class="max-w-none mx-auto">
            <div class="chat-input-box rounded-2xl overflow-hidden p-[10px]" @click="focusInput">
              <textarea ref="inputEl" v-model="inputText" rows="1"
                @keydown.enter.exact.prevent="sendMessage"
                @input="autoResize"
                class="chat-textarea w-full px-2 py-2 text-sm text-ls-text font-mono leading-6 focus:outline-none resize-none placeholder:text-ls-muted bg-transparent overflow-y-hidden"
                placeholder="输入消息..."></textarea>
              <div class="flex items-center justify-end">
                <button @click="sendMessage"
                  :disabled="sending || !inputText.trim() || !form.model"
                  class="h-9 w-9 flex items-center justify-center rounded-full bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200"
                  style="color: #fff;">
                  <CIcon name="send" :size="14" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧侧边栏 -->
      <div ref="sidebarPanel" class="relative flex flex-col flex-shrink-0 bg-ls-bg overflow-hidden sidebar-panel"
        :style="{
          width: sidebarWidth + 'px',
          'border-left': sidebarCollapsed ? '0' : '1px solid var(--border)',
          transform: sidebarTransform,
        }">
        <div class="h-full overflow-y-auto px-4 py-4 space-y-4"
          :class="{ 'invisible': sidebarCollapsed }"
          :style="sidebarCollapsed ? { 'pointer-events': 'none' } : {}">
          <FormField label="供应商">
            <CSelect v-model="form.supplierId" :options="SUPPLIER_OPTIONS" placeholder="选择供应商" />
          </FormField>
          <FormField label="模型">
            <CSelect v-model="form.model" :options="MODEL_OPTIONS" placeholder="选择模型" />
          </FormField>
          <FormField label="API Key">
            <CSelect v-model="form.apiKey" :options="KEY_OPTIONS" placeholder="选择 API Key（可选）" />
          </FormField>

          <div class="pt-3 border-t border-ls-border space-y-4">
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-xs text-gray-500 mb-1">Temperature</label>
                <input v-model.number="form.temperature" type="number" step="0.1"
                  class="w-full bg-ls-bg rounded-lg border border-ls-border px-2 py-1.5 text-sm text-ls-text font-mono focus:outline-none focus:border-ls-accent">
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1">Max Tokens</label>
                <input v-model.number="form.maxTokens" type="number"
                  class="w-full bg-ls-bg rounded-lg border border-ls-border px-2 py-1.5 text-sm text-ls-text font-mono focus:outline-none focus:border-ls-accent">
              </div>
            </div>

            <div class="flex items-center justify-between">
              <label class="text-xs text-ls-muted">Stream</label>
              <CCheckbox v-model="form.stream" />
            </div>
          </div>

          <div class="pt-3 border-t border-ls-border">
            <FormField label="系统提示词">
              <textarea v-model="form.systemPrompt" rows="4"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-2 py-1.5 text-xs text-ls-text font-mono focus:outline-none focus:border-ls-accent resize-y min-h-[80px]"></textarea>
            </FormField>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, inject, watch, nextTick } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import FormField from '@/components/FormField.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import CIcon from '@/components/CIcon.vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import { getMappings, getSuppliers, getSupplierModels,getClientKeys } from '@/api'

const toast = inject('$toast')
const sending = ref(false)
const inputText = ref('')
const inputEl = ref(null)
const sidebarCollapsed = ref(false)
const SIDEBAR_W = 288
// 折叠时 width → 0 + translateX(288px) 同步动画：视觉上向右滑出，布局空间同时释放
const sidebarTransform = computed(() => sidebarCollapsed.value ? `translateX(${SIDEBAR_W}px)` : 'translateX(0)')
const sidebarWidth = computed(() => sidebarCollapsed.value ? 0 : SIDEBAR_W)

// 输入框行数：默认 MIN_ROWS 行，随内容自动扩展，最高 MAX_ROWS 行
const MIN_ROWS = 1
const MAX_ROWS = 5

const autoResize = () => {
  nextTick(() => {
    const el = inputEl.value
    if (!el) return
    const cs = getComputedStyle(el)
    const lineH = parseFloat(cs.lineHeight)
    const padV = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
    const minH = lineH * MIN_ROWS + padV
    const maxH = lineH * MAX_ROWS + padV
    el.style.height = 'auto'
    const target = Math.min(Math.max(el.scrollHeight, minH), maxH)
    el.style.height = target + 'px'
    el.style.overflowY = el.scrollHeight > maxH ? 'auto' : 'hidden'
  })
}

const inputLinesClass = computed(() => {
  return 'py-3'
})

const messages = ref([])

const form = ref({
  supplierId: '',
  model: '',
  apiKey: '',
  systemPrompt: 'You are a helpful assistant.',
  temperature: 0.7,
  maxTokens: 2048,
  stream: true,
})

const SUPPLIER_OPTIONS = ref([{ label: '加载中...', value: '' }])
const MODEL_OPTIONS = ref([{ label: '加载中...', value: '' }])
const supplierModelsMap = ref({})
const KEY_OPTIONS = ref([{ label: '不使用 API Key', value: '' }])

const loadSuppliers = async () => {
  const opts = [{ label: '智能路由', value: '' }]
  try {
    const res = await getSuppliers()
    for (const s of (res.data || [])) {
      opts.push({ label: s.name, value: s.id })
    }
  } catch { /* ignore */ }
  SUPPLIER_OPTIONS.value = opts
  if (!form.value.supplierId && opts.length) form.value.supplierId = opts[0].value
}

const loadModels = async () => {
  const smartRoutingModels = []
  const seen = new Set()
  supplierModelsMap.value = {}

  try {
    const res = await getMappings()
    for (const m of (res.data || [])) {
      if (m.alias_name && !seen.has(m.alias_name)) {
        seen.add(m.alias_name)
        smartRoutingModels.push({ label: `${m.alias_name}（智能路由）`, value: m.alias_name })
      }
    }
  } catch { /* ignore */ }
  supplierModelsMap.value[''] = smartRoutingModels

  let suppliers = []
  try {
    const sres = await getSuppliers()
    suppliers = sres.data || []
  } catch { /* ignore */ }

  for (const s of suppliers) {
    const supplierOpts = []
    try {
      const mres = await getSupplierModels(s.id)
      for (const mm of (mres.data || [])) {
        if (mm.model_name && !seen.has(mm.model_name)) {
          seen.add(mm.model_name)
          supplierOpts.push({ label: mm.model_name, value: mm.model_name })
        }
      }
    } catch { /* skip */ }
    supplierModelsMap.value[s.id] = supplierOpts
  }

  updateModelOptions()
}

const updateModelOptions = () => {
  const opts = supplierModelsMap.value[form.value.supplierId] || []
  MODEL_OPTIONS.value = opts.length ? opts : [{ label: '暂无可用模型', value: '' }]
  if (opts.length) form.value.model = opts[0].value
}

watch(() => form.value.supplierId, () => {
  updateModelOptions()
})

const loadKeys = async () => {
  try {
    const res = await getClientKeys()
    const active = (res.data || []).filter(k => k.status === 'active')
    KEY_OPTIONS.value = [
      { label: '不使用 API Key', value: '' },
      ...active.map(k => ({ label: k.name, value: k.key_value })),
    ]
  } catch { /* ignore */ }
}

// ---------- 聊天区跟随滚动 ----------
const chatScrollEl = ref(null)
const chatContentEl = ref(null)
// 是否吸附底部：用户主动上滚阅读时暂停跟随，滚回底部后自动恢复
const stickToBottom = ref(true)
const NEAR_BOTTOM_PX = 64
let autoScrolling = false
let contentRO = null

const isNearBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX

const onChatScroll = () => {
  const el = chatScrollEl.value
  if (!el) return
  if (autoScrolling) {
    // 程序触发的平滑滚动：到达底部前不更新吸附状态，滚到底后恢复追踪
    if (isNearBottom(el)) autoScrolling = false
    return
  }
  stickToBottom.value = isNearBottom(el)
}

const scrollToBottom = (smooth = false) => {
  const el = chatScrollEl.value
  if (!el) return
  if (smooth) autoScrolling = true
  el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

// 点击"回到底部"：恢复吸附并平滑滚到底
const goToBottom = () => {
  stickToBottom.value = true
  scrollToBottom(true)
}

// 用户滚轮 / 触摸打断平滑滚动时，立即恢复吸附状态追踪
const cancelAutoScroll = () => { autoScrolling = false }

// 消息变化（发送 / 流式输出 / 状态切换）时，吸附状态下跟随滚动
watch(
  () => {
    const list = messages.value
    const last = list[list.length - 1]
    return [
      list.length,
      last ? last.content.length : 0,
      last ? (last.reasoning || '').length : 0,
      last ? last.status : '',
    ].join('|')
  },
  () => {
    if (!stickToBottom.value) return
    nextTick(() => scrollToBottom())
  }
)

// 点击聊天区域时聚焦输入框
const focusInput = () => {
  if (!sending.value && inputEl.value) inputEl.value.focus()
}

// 内容高度变化（图片加载、展开思考过程等）时保持吸附
watch(chatContentEl, (el) => {
  contentRO?.disconnect()
  if (!el) return
  contentRO = new ResizeObserver(() => {
    if (stickToBottom.value && !autoScrolling) scrollToBottom()
  })
  contentRO.observe(el)
})

const msgTokens = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'assistant' && m.status === 'done' && m.tokens) return m.tokens
  }
  return ''
})

const readStream = async (res, msg) => {
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let tokens = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const data = trimmed.slice(5).trim()
      if (data === '[DONE]') continue
      try {
        const obj = JSON.parse(data)
        const choice = (obj.choices || [])[0] || {}
        const delta = choice.delta || choice.message || {}
        if (delta.reasoning_content) msg.reasoning += delta.reasoning_content
        if (delta.content) msg.content += delta.content
        if (obj.usage) {
          tokens = obj.usage.total_tokens || ((obj.usage.prompt_tokens || 0) + (obj.usage.completion_tokens || 0))
        }
        await nextTick()
      } catch { /* ignore */ }
    }
  }
  msg.tokens = tokens != null ? tokens.toLocaleString() : '—'
  msg.status = 'done'
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || !form.value.model || sending.value) return

  inputText.value = ''
  autoResize()

  // 发送自己的消息：强制回到底部并恢复跟随
  stickToBottom.value = true

  messages.value.push({
    role: 'user',
    content: text,
  })

  messages.value.push({
    role: 'assistant',
    content: '',
    reasoning: '',
    status: 'loading',
    showReasoning: false,
    renderMode: 'md',
    _copied: false,
    _copyKey: 'msg-' + Date.now(),
  })
  // 通过响应式代理读取，保证流式更新 content 时能触发视图刷新与跟随滚动
  const assistantMsg = messages.value[messages.value.length - 1]

  const headers = { 'Content-Type': 'application/json' }
  if (form.value.apiKey) headers['Authorization'] = 'Bearer ' + form.value.apiKey

  const body = {
    model: form.value.model,
    messages: [
      ...(form.value.systemPrompt ? [{ role: 'system', content: form.value.systemPrompt }] : []),
      ...messages.value.map(m => ({ role: m.role, content: m.content })),
    ],
  }
  if (form.value.stream) body.stream = true
  if (form.value.temperature !== null) body.temperature = form.value.temperature
  if (form.value.maxTokens !== null) body.max_tokens = form.value.maxTokens

  sending.value = true

  try {
    const res = await fetch('/api/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })

    assistantMsg.account = res.headers.get('x-upstream-account') || '—'
    assistantMsg.model = res.headers.get('x-upstream-model') || ''

    const ctype = res.headers.get('content-type') || ''
    if (res.ok && form.value.stream && ctype.includes('text/event-stream')) {
      await readStream(res, assistantMsg)
    } else {
      const text = await res.text()
      try {
        const p = JSON.parse(text)
        if (p.usage) assistantMsg.tokens = p.usage.total_tokens
        const msg = (p.choices && p.choices[0] && p.choices[0].message) || {}
        assistantMsg.content = msg.content || ''
        assistantMsg.reasoning = msg.reasoning_content || msg.reasoning || ''
      } catch {
        assistantMsg.raw = text
      }
      assistantMsg.status = res.ok ? 'done' : 'error'
    }
  } catch (e) {
    assistantMsg.content = '请求失败: ' + e.message
    assistantMsg.status = 'error'
  }

  sending.value = false
}

const replayMessage = async (idx) => {
  const userMsg = messages.value[idx]
  if (userMsg.role !== 'user') return

  // 删除该用户消息之后的所有助手回复
  let next = idx + 1
  while (next < messages.value.length && messages.value[next].role === 'assistant') {
    next++
  }
  if (next > idx + 1) messages.value.splice(idx + 1, next - idx - 1)

  // 重发：强制回到底部并恢复跟随
  stickToBottom.value = true

  messages.value.push({
    role: 'assistant',
    content: '',
    reasoning: '',
    status: 'loading',
    showReasoning: false,
    renderMode: 'md',
    _copied: false,
    _copyKey: 'msg-' + Date.now(),
  })

  const headers = { 'Content-Type': 'application/json' }
  if (form.value.apiKey) headers['Authorization'] = 'Bearer ' + form.value.apiKey

  const body = {
    model: form.value.model,
    messages: [
      ...(form.value.systemPrompt ? [{ role: 'system', content: form.value.systemPrompt }] : []),
      ...messages.value.map(m => ({ role: m.role, content: m.content })),
    ],
  }
  if (form.value.stream) body.stream = true
  if (form.value.temperature !== null) body.temperature = form.value.temperature
  if (form.value.maxTokens !== null) body.max_tokens = form.value.maxTokens

  sending.value = true

  try {
    const res = await fetch('/api/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })

    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.account = res.headers.get('x-upstream-account') || '—'
    lastMsg.model = res.headers.get('x-upstream-model') || ''

    const ctype = res.headers.get('content-type') || ''
    if (res.ok && form.value.stream && ctype.includes('text/event-stream')) {
      await readStream(res, lastMsg)
    } else {
      const text = await res.text()
      try {
        const p = JSON.parse(text)
        if (p.usage) lastMsg.tokens = p.usage.total_tokens
        const msg = (p.choices && p.choices[0] && p.choices[0].message) || {}
        lastMsg.content = msg.content || ''
        lastMsg.reasoning = msg.reasoning_content || msg.reasoning || ''
      } catch {
        lastMsg.raw = text
      }
      lastMsg.status = res.ok ? 'done' : 'error'
    }
  } catch (e) {
    const lastMsg = messages.value[messages.value.length - 1]
    lastMsg.content = '请求失败: ' + e.message
    lastMsg.status = 'error'
  }

  sending.value = false
}

const copyText = async (text, key) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast?.('已复制到剪贴板', 'success')
  } catch {
    toast?.('复制失败', 'error')
  }
}

onMounted(() => {
  loadSuppliers()
  loadModels()
  loadKeys()
  autoResize()
  nextTick(() => inputEl.value?.focus())
  const el = chatScrollEl.value
  if (el) {
    el.addEventListener('wheel', cancelAutoScroll, { passive: true })
    el.addEventListener('touchstart', cancelAutoScroll, { passive: true })
  }
})

onBeforeUnmount(() => {
  contentRO?.disconnect()
  const el = chatScrollEl.value
  if (el) {
    el.removeEventListener('wheel', cancelAutoScroll)
    el.removeEventListener('touchstart', cancelAutoScroll)
  }
})
</script>

<style scoped>
/* "回到底部"按钮进出场：轻微上浮 + 淡入 */
.back-to-bottom-enter-active,
.back-to-bottom-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.back-to-bottom-enter-from,
.back-to-bottom-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* 思考中：黑色 ↔ 靛色呼吸 */
.breathing-text {
  color: #1a1a2e;
  animation: breathing-text 1.6s ease-in-out infinite;
}
@keyframes breathing-text {
  0%, 100% { color: #1a1a2e; }
  50% { color: #6366f1; }
}

/* 浅色主题：深灰 ↔ 靛蓝，保证对比 */
[data-theme="light"] .breathing-text {
  color: #1a1a2e;
  animation: breathing-text-light 1.6s ease-in-out infinite;
}
@keyframes breathing-text-light {
  0%, 100% { color: #1a1a2e; }
  50% { color: #4338ca; }
}

/* 暗色卡片：用暗灰代替纯黑，避免纯黑糊在深色卡片上 */
[data-theme="dark"] .breathing-text {
  color: #2a2d3e;
  animation: breathing-text-dark 1.6s ease-in-out infinite;
}
@keyframes breathing-text-dark {
  0%, 100% { color: #2a2d3e; }
  50% { color: #818cf8; }
}

/* 侧边栏：折叠时 translateX + width 同步动画，视觉上向右滑出同时布局空间释放 */
.sidebar-panel {
  transition: transform 0.25s ease-in-out, width 0.25s ease-in-out, border-left-width 0.25s ease-in-out;
  transition-property: transform, width, border-left-width;
}
</style>
