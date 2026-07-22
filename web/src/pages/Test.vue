<template>
  <div>
    <PageHeader title="在线测试" subtitle="直接发送请求测试 API 代理"></PageHeader>

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
          <button @click="sendRequest" :disabled="loading"
            class="btn btn-primary disabled:opacity-50">
            {{ loading ? '发送中...' : '发送请求' }}
          </button>
        </div>
      </CCard>

      <!-- Response Panel -->
      <CCard>
        <template #header>
          <div class="px-5 py-3.5 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span v-if="response.status" class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs font-mono">{{ response.status }}</span>
              <span v-if="response.account" class="text-xs text-ls-muted">→ {{ response.account }}</span>
              <span v-if="!response.status" class="text-xs text-ls-muted">等待请求...</span>
            </div>
            <div v-if="response.latency" class="flex items-center gap-3">
              <span class="text-xs text-ls-muted">{{ response.latency }}</span>
              <span class="text-xs text-ls-muted">{{ response.tokens }} tokens</span>
              <button @click="copyText(response.raw, 'resp')"
                class="text-xs text-ls-dim hover:text-ls-text">{{ copied.resp ? '已复制' : '复制' }}</button>
            </div>
          </div>
        </template>
        <pre v-if="response.raw" class="bg-ls-bg rounded-lg p-4 text-xs text-ls-dim overflow-x-auto leading-relaxed whitespace-pre-wrap">{{ response.raw }}</pre>
        <p v-else class="text-sm text-ls-muted">点击"发送请求"后在此处查看响应...</p>
      </CCard>
    </div>

    <!-- curl example -->
    <div class="px-6 md:px-8 py-6">
      <CCard title="curl 示例" no-padding>
        <template #action>
          <button @click="copyText(curlExample, 'curl')"
            class="text-xs text-ls-dim hover:text-ls-text">{{ copied.curl ? '已复制' : '复制' }}</button>
        </template>
        <pre class="p-5 text-xs text-ls-dim font-mono overflow-x-auto"><span class="text-green-400">$</span> curl http://localhost:8000/api/v1/chat/completions \
  -H <span class="text-ls-accent">"Content-Type: application/json"</span> \
  -d <span class="text-ls-accent">'{
  "model": "hy3",
  "messages": [{"role": "user", "content": "Hello"}]
}'</span></pre>
      </CCard>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import CCard from '@/components/CCard.vue'
import FormField from '@/components/FormField.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'

const MODEL_OPTIONS = [
  { label: 'hy3', value: 'hy3' },
  { label: 'qwen2.5-7b', value: 'qwen2.5-7b' },
  { label: 'qwen2.5-14b', value: 'qwen2.5-14b' },
]

const curlExample = `curl http://localhost:8000/api/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
  "model": "hy3",
  "messages": [{"role": "user", "content": "Hello"}]
}'`

const loading = ref(false)

// 复制反馈：点击后短暂显示「已复制」
const copied = reactive({ resp: false, curl: false })
const copyText = async (text, key) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 回退：临时 textarea
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
  model: 'hy3',
  temperature: 0.7,
  maxTokens: 2048,
  stream: true,
  messages: JSON.stringify([
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Hello, what can you do?' },
  ], null, 2),
})

const response = ref({ status: null, account: null, latency: null, tokens: null, raw: null })

const sendRequest = async () => {
  loading.value = true
  try {
    const data = JSON.parse(form.value.messages)
    const body = { model: form.value.model, messages: data }
    if (form.value.temperature !== null) body.temperature = form.value.temperature
    if (form.value.maxTokens !== null) body.max_tokens = form.value.maxTokens
    if (form.value.stream) body.stream = true

    const res = await fetch('/api/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    const text = await res.text()
    // Extract tokens from OpenAI-compatible response
    let totalTokens = null
    try {
      const parsed = JSON.parse(text)
      if (parsed.usage) {
        totalTokens = parsed.usage.total_tokens || (parsed.usage.prompt_tokens + parsed.usage.completion_tokens) || null
      }
    } catch { /* not JSON, skip */ }

    response.value = {
      status: res.status === 200 ? '200 OK' : res.status + ' Error',
      account: res.headers.get('x-upstream-account') || '—',
      latency: res.headers.get('x-latency-ms') ? `${res.headers.get('x-latency-ms')}ms` : '—',
      tokens: totalTokens != null ? totalTokens.toLocaleString() : '—',
      raw: formatJson(text),
    }
  } catch (e) {
    response.value = { status: 'Error', raw: JSON.stringify({ error: e.message }, null, 2) }
  }
  loading.value = false
}

const formatJson = (text) => {
  try { return JSON.stringify(JSON.parse(text), null, 2) }
  catch { return text }
}
</script>
