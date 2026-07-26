<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="在线测试 // Playground" subtitle="// 直接发送请求测试 API 代理"></PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0">
    <div class="px-6 md:px-8 py-6 grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Request Panel -->
      <CCard body-class="p-5 space-y-4">
        <template #header>
          <div class="px-5 py-3.5 flex items-center gap-2">
            <span class="text-xs font-mono text-ls-accent">POST</span>
            <span class="text-xs font-mono text-ls-dim">/api/v1/chat/completions</span>
          </div>
        </template>
        <FormField label="模型" plain>
          <CSelect v-model="form.model" :options="MODEL_OPTIONS" placeholder="选择模型" />
        </FormField>
        <FormField label="API Key" plain>
          <CSelect v-model="form.apiKey" :options="KEY_OPTIONS" placeholder="选择 API Key（可选）" />
        </FormField>
        <div class="grid grid-cols-2 gap-3">
          <FormField label="Temperature" plain>
            <input v-model.number="form.temperature" type="number" step="0.1"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-ls-text font-mono focus:outline-none focus:border-ls-accent">
          </FormField>
          <FormField label="Max Tokens" plain>
            <input v-model.number="form.maxTokens" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-ls-text font-mono focus:outline-none focus:border-ls-accent">
          </FormField>
        </div>
        <div class="flex items-center justify-between">
          <label class="text-xs text-ls-muted">Stream</label>
          <CCheckbox v-model="form.stream" />
        </div>
        <FormField label="Messages (JSON)" plain>
          <textarea v-model="form.messages"
            class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-ls-text font-mono focus:outline-none focus:border-ls-accent resize-none"
            rows="8"></textarea>
        </FormField>
        <div class="flex items-center justify-between">
          <p class="text-xs text-ls-muted">发送请求将消耗配额</p>
          <button @click="sendRequest" :disabled="loading || !form.model"
            class="btn btn-primary disabled:opacity-50">
            {{ loading ? '发送中...' : '发送请求' }}
          </button>
        </div>
      </CCard>

      <!-- Response Panel -->
      <CCard>
        <template #header>
          <div class="px-5 py-3.5 flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2 min-w-0">
              <span v-if="response.status" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-mono"
                :class="response.ok ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'">{{ response.status }}</span>
              <span v-if="response.account" class="text-xs text-ls-muted truncate">→ {{ response.account }}</span>
              <span v-if="response.model" class="text-xs text-ls-dim font-mono truncate">({{ response.model }})</span>
              <span v-if="!response.status" class="text-xs text-ls-muted">等待请求...</span>
            </div>
            <div v-if="response.status" class="flex items-center gap-3">
              <span class="text-xs text-ls-muted">{{ response.latency || '—' }}</span>
              <span class="text-xs text-ls-muted">{{ response.tokens || '—' }} tokens</span>
              <button v-if="!response.streaming" @click="renderMode = renderMode === 'raw' ? 'md' : 'raw'"
                class="text-xs px-1.5 py-0.5 rounded transition-colors"
                :class="renderMode === 'raw' ? 'bg-ls-elevated text-ls-dim' : 'text-ls-muted hover:text-ls-text'">
                {{ renderMode === 'raw' ? 'RAW' : 'MD' }}
              </button>
              <button @click="copyText(copyPayload, 'resp')"
                class="text-xs text-ls-dim hover:text-ls-text">{{ copied.resp ? '已复制' : '复制' }}</button>
            </div>
          </div>
        </template>

        <div v-if="response.status" class="p-4 space-y-4">
          <!-- 思考过程 -->
          <div v-if="response.reasoning">
            <div class="text-xs text-purple-400 mb-1.5 flex items-center gap-1.5">
              <span class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-purple-500/10 text-purple-400">Thinking</span>
              思考过程
            </div>
            <CodeBlock lang="thinking" :code="response.reasoning" />
          </div>
          <!-- 正文 -->
          <div v-if="response.content">
            <MarkdownRender v-if="renderMode !== 'raw'" :source="response.content" />
            <div v-else class="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{{ response.content }}</div>
          </div>
          <!-- 非流式原始响应（RAW 模式或错误时） -->
          <div v-if="response.raw && (renderMode === 'raw' || !response.ok || (!response.content && !response.reasoning))" class="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{{ response.raw }}</div>
          <p v-if="!response.content && !response.reasoning && !response.raw && response.ok" class="text-sm text-ls-muted">
            {{ response.streaming ? '等待上游返回...' : '无内容' }}
          </p>
        </div>
        <p v-else class="text-sm text-ls-muted p-4">点击"发送请求"后在此处查看响应...</p>
      </CCard>
    </div>

    <!-- curl example -->
    <div class="px-6 md:px-8 py-6">
      <CCard title="curl 示例" no-padding>
        <template #action>
          <button @click="copyText(curlExample, 'curl')"
            class="text-xs text-ls-dim hover:text-ls-text">{{ copied.curl ? '已复制' : '复制' }}</button>
        </template>
        <CodeBlock lang="bash" :code="'$ ' + curlExample" />
      </CCard>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import CCard from '@/components/CCard.vue'
import FormField from '@/components/FormField.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import CodeBlock from '@/components/CodeBlock.vue'
import { getMappings, getSuppliers, getSupplierModels, getClientKeys } from '@/api'

const toast = inject('$toast')

const MODEL_OPTIONS = ref([{ label: '加载中...', value: '' }])
const KEY_OPTIONS = ref([{ label: '不使用 API Key', value: '' }])

const loading = ref(false)
const renderMode = ref('md')

// 复制反馈：点击后短暂显示「已复制」
const copied = reactive({ resp: false, curl: false })
const copyText = async (text, key) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch { /* ignore */ }
    document.body.removeChild(ta)
  }
  copied[key] = true
  setTimeout(() => { copied[key] = false }, 1500)
}

const form = ref({
  model: '',
  apiKey: '',
  temperature: 0.7,
  maxTokens: 2048,
  stream: true,
  messages: JSON.stringify([
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Hello, what can you do?' },
  ], null, 2),
})

const response = ref({
  status: null, ok: false, account: null, model: null, latency: null,
  tokens: null, content: '', reasoning: '', raw: '', streaming: false,
})

// 复制内容：有正文复制正文，否则复制原始响应
const copyPayload = computed(() => response.value.content || response.value.raw || '')

const origin = computed(() => window.location.origin)
const curlExample = computed(() => {
  const body = {
    model: form.value.model || 'my-virtual-model',
    messages: [{ role: 'user', content: 'Hello' }],
  }
  if (form.value.stream) body.stream = true
  const keyHeader = form.value.apiKey
    ? `\n  -H "Authorization: Bearer ${form.value.apiKey}" \\`
    : ''
  return `curl ${origin.value}/api/v1/chat/completions \\
  -H "Content-Type: application/json" \\${keyHeader}
  -d '${JSON.stringify(body, null, 2)}'`
})

// ── 加载真实模型列表（虚拟模型优先，回退到供应商模型） ──
const loadModels = async () => {
  const opts = []
  const seen = new Set()
  try {
    const res = await getMappings()
    for (const m of (res.data || [])) {
      if (m.alias_name && !seen.has(m.alias_name)) {
        seen.add(m.alias_name)
        opts.push({ label: `${m.alias_name}（虚拟模型）`, value: m.alias_name })
      }
    }
  } catch { /* ignore */ }
  try {
    const sres = await getSuppliers()
    for (const s of (sres.data || [])) {
      try {
        const mres = await getSupplierModels(s.id)
        for (const mm of (mres.data || [])) {
          if (mm.model_name && !seen.has(mm.model_name)) {
            seen.add(mm.model_name)
            opts.push({ label: mm.model_name, value: mm.model_name })
          }
        }
      } catch { /* skip supplier */ }
    }
  } catch { /* ignore */ }
  MODEL_OPTIONS.value = opts.length ? opts : [{ label: '暂无可用模型', value: '' }]
  if (opts.length && !form.value.model) form.value.model = opts[0].value
}

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

// ── 逐块读取 SSE 流，增量渲染正文与思考内容 ──
const readStream = async (res) => {
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let tokens = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() // 保留最后一段不完整行
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const data = trimmed.slice(5).trim()
      if (data === '[DONE]') continue
      try {
        const obj = JSON.parse(data)
        const choice = (obj.choices || [])[0] || {}
        const delta = choice.delta || choice.message || {}
        if (delta.reasoning_content) response.value.reasoning += delta.reasoning_content
        if (delta.content) response.value.content += delta.content
        if (obj.usage) {
          tokens = obj.usage.total_tokens || ((obj.usage.prompt_tokens || 0) + (obj.usage.completion_tokens || 0))
        }
      } catch { /* 忽略非 JSON 行 */ }
    }
  }
  response.value.tokens = tokens != null ? tokens.toLocaleString() : '—'
}

const sendRequest = async () => {
  let msgs
  try {
    msgs = JSON.parse(form.value.messages)
  } catch {
    toast('Messages 不是合法 JSON', 'error')
    return
  }
  const body = { model: form.value.model, messages: msgs }
  if (form.value.temperature !== null && form.value.temperature !== '') body.temperature = form.value.temperature
  if (form.value.maxTokens !== null && form.value.maxTokens !== '') body.max_tokens = form.value.maxTokens
  if (form.value.stream) body.stream = true

  const headers = { 'Content-Type': 'application/json' }
  if (form.value.apiKey) headers['Authorization'] = 'Bearer ' + form.value.apiKey

  loading.value = true
  renderMode.value = 'md'
  response.value = {
    status: null, ok: false, account: null, model: null, latency: null,
    tokens: null, content: '', reasoning: '', raw: '', streaming: form.value.stream,
  }
  const t0 = performance.now()
  try {
    const res = await fetch('/api/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
    response.value.ok = res.ok
    response.value.status = res.ok ? `${res.status} OK` : `${res.status} Error`
    response.value.account = res.headers.get('x-upstream-account') || '—'
    response.value.model = res.headers.get('x-upstream-model') || ''

    const ctype = res.headers.get('content-type') || ''
    if (form.value.stream && res.ok && ctype.includes('text/event-stream')) {
      await readStream(res)
      const serverLatency = res.headers.get('x-latency-ms')
      response.value.latency = `${serverLatency || Math.round(performance.now() - t0)}ms`
    } else {
      const text = await res.text()
      let totalTokens = null
      try {
        const p = JSON.parse(text)
        if (p.usage) totalTokens = p.usage.total_tokens || ((p.usage.prompt_tokens || 0) + (p.usage.completion_tokens || 0))
        const msg = (p.choices && p.choices[0] && p.choices[0].message) || {}
        response.value.content = msg.content || ''
        response.value.reasoning = msg.reasoning_content || msg.reasoning || ''
      } catch { /* 非 JSON */ }
      response.value.tokens = totalTokens != null ? totalTokens.toLocaleString() : '—'
      const serverLatency = res.headers.get('x-latency-ms')
      response.value.latency = `${serverLatency || Math.round(performance.now() - t0)}ms`
      try { response.value.raw = JSON.stringify(JSON.parse(text), null, 2) } catch { response.value.raw = text }
    }
  } catch (e) {
    response.value.ok = false
    response.value.status = 'Error'
    response.value.raw = JSON.stringify({ error: e.message }, null, 2)
  }
  loading.value = false
}

onMounted(() => {
  loadModels()
  loadKeys()
})
</script>
