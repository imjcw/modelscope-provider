<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">在线测试</h1>
        <p class="text-xs text-gray-500 mt-0.5">直接发送请求测试 API 代理</p>
      </div>
    </header>

    <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Request Panel -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center gap-2">
          <span class="text-xs font-mono text-ls-accent">POST</span>
          <span class="text-xs font-mono text-gray-400">/api/v1/chat/completions</span>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">模型</label>
            <select v-model="form.model" class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
              <option>hy3</option>
              <option>qwen2.5-7b</option>
              <option>qwen2.5-14b</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">Temperature</label>
              <input v-model.number="form.temperature" type="number" step="0.1"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">Max Tokens</label>
              <input v-model.number="form.maxTokens" type="number"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
            </div>
          </div>
          <div class="flex items-center justify-between">
            <label class="text-xs text-gray-500">Stream</label>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="form.stream" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">Messages (JSON)</label>
            <textarea v-model="form.messages"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent resize-none"
              rows="8"></textarea>
          </div>
          <div class="flex items-center justify-between">
            <p class="text-xs text-gray-600">发送请求将消耗配额</p>
            <button @click="sendRequest" :disabled="loading"
              class="bg-ls-accent text-white font-medium rounded-lg h-9 px-6 text-sm hover:bg-ls-accentHover transition-all disabled:opacity-50">
              {{ loading ? '发送中...' : '发送请求' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Response Panel -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span v-if="response.status" class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs font-mono">{{ response.status }}</span>
            <span v-if="response.account" class="text-xs text-gray-500">→ {{ response.account }}</span>
            <span v-if="!response.status" class="text-xs text-gray-500">等待请求...</span>
          </div>
          <div v-if="response.latency" class="flex items-center gap-3">
            <span class="text-xs text-gray-500">{{ response.latency }}ms</span>
            <span class="text-xs text-gray-500">{{ response.tokens }} tokens</span>
            <button class="text-xs text-gray-400 hover:text-white">复制</button>
          </div>
        </div>
        <div class="p-5">
          <pre v-if="response.raw" class="bg-ls-bg rounded-lg p-4 text-xs text-gray-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">{{ response.raw }}</pre>
          <p v-else class="text-sm text-gray-500">点击"发送请求"后在此处查看响应...</p>
        </div>
      </div>
    </div>

    <!-- curl example -->
    <div class="p-6 pt-0">
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3 border-b border-ls-border flex items-center justify-between">
          <h2 class="font-semibold tracking-tight text-sm">curl 示例</h2>
          <button class="text-xs text-gray-400 hover:text-white">复制</button>
        </div>
        <pre class="p-5 text-xs text-gray-300 font-mono overflow-x-auto"><span class="text-green-400">$</span> curl http://localhost:8000/api/v1/chat/completions \
  -H <span class="text-ls-accent">"Content-Type: application/json"</span> \
  -d <span class="text-ls-accent">'{
  "model": "hy3",
  "messages": [{"role": "user", "content": "Hello"}]
}'</span></pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const loading = ref(false)

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
    response.value = {
      status: res.status === 200 ? '200 OK' : res.status + ' Error',
      account: 'account-1',
      latency: Math.floor(Math.random() * 500 + 100) + 'ms',
      tokens: '1,240',
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
