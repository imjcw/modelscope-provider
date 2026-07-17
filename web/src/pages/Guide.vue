<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">使用指南</h1>
        <p class="text-xs text-gray-500 mt-0.5">将代理服务接入你的工具和项目</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-500">API 基础地址</span>
        <div class="flex items-center gap-1 bg-ls-card rounded-md border border-ls-border px-2.5 py-1">
          <code class="text-xs font-mono text-ls-accent">{{ apiBaseUrl }}</code>
          <button @click="copyBaseUrl" class="text-gray-400 hover:text-white ml-1" title="复制">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <div class="p-6 space-y-6">
      <!-- 步骤导航 -->
      <div class="bg-ls-card rounded-lg border border-ls-border p-5">
        <h2 class="font-semibold text-white mb-4">三步开始使用</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div v-for="(step, i) in steps" :key="i" class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-full bg-ls-accent/20 text-ls-accent flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5">{{ i + 1 }}</div>
            <div>
              <p class="text-sm text-white font-medium">{{ step.title }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 接入方式标签页 -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3 border-b border-ls-border flex items-center gap-1 overflow-x-auto">
          <button v-for="(tab, i) in tabs" :key="i" @click="activeTab = i"
            :class="activeTab === i ? 'bg-ls-accent text-white' : 'text-gray-400 hover:text-white'"
            class="px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap">{{ tab }}</button>
        </div>

        <!-- Tab: OpenAI SDK -->
        <div v-show="activeTab === 0" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">Python · OpenAI SDK</h3>
            <p class="text-xs text-gray-500 mt-0.5">只需修改 base_url，其余代码不变</p>
          </div>
          <pre class="code-block"><code>{{ pythonSdkCode }}</code></pre>
          <div class="bg-ls-bg rounded-md border border-ls-border p-3">
            <div class="flex items-center gap-2 mb-1">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>
              <span class="text-xs text-green-400">注意</span>
            </div>
            <p class="text-xs text-gray-400">api_key 可以填任意字符串，代理服务不会校验。base_url 指向本服务的 `/api/v1` 路径即可。</p>
          </div>
        </div>

        <!-- Tab: JavaScript SDK -->
        <div v-show="activeTab === 1" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">JavaScript / TypeScript · OpenAI SDK</h3>
            <p class="text-xs text-gray-500 mt-0.5">npm 包 <code class="text-ls-accent">@openai/openai</code> 同样兼容</p>
          </div>
          <pre class="code-block"><code>{{ jsSdkCode }}</code></pre>
        </div>

        <!-- Tab: curl -->
        <div v-show="activeTab === 2" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">curl · 直接 HTTP 调用</h3>
            <p class="text-xs text-gray-500 mt-0.5">适合快速验证或无 SDK 环境</p>
          </div>
          <pre class="code-block"><code>{{ curlCode }}</code></pre>
          <div>
            <h3 class="text-sm font-medium text-white mt-3">流式响应（SSE）</h3>
            <p class="text-xs text-gray-500 mt-0.5">添加 <code class="text-ls-accent">"stream": true</code> 即可</p>
          </div>
          <pre class="code-block"><code>{{ curlStreamCode }}</code></pre>
        </div>

        <!-- Tab: 第三方工具 -->
        <div v-show="activeTab === 3" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">第三方工具对接</h3>
            <p class="text-xs text-gray-500 mt-0.5">兼容 OpenAI API 的工具均可直接接入</p>
          </div>

          <!-- 通用配置说明 -->
          <div class="bg-ls-bg rounded-md border border-ls-border p-4">
            <h4 class="text-xs font-medium text-white mb-2">通用配置</h4>
            <div class="space-y-1.5">
              <div v-for="row in commonConfig" :key="row.label" class="flex items-center gap-3 text-xs">
                <span class="text-gray-500 w-32 flex-shrink-0">{{ row.label }}</span>
                <code class="text-ls-accent font-mono bg-ls-card px-1.5 py-0.5 rounded">{{ row.value }}</code>
              </div>
            </div>
          </div>

          <!-- 工具卡片 -->
          <div class="space-y-3">
            <div v-for="tool in tools" :key="tool.name" class="bg-ls-bg rounded-md border border-ls-border p-4">
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-xs font-medium text-white">{{ tool.name }}</h4>
                <span class="text-xs text-ls-accent px-1.5 py-0.5 rounded bg-ls-accent/10">已兼容</span>
              </div>
              <div class="space-y-1 text-xs">
                <div class="flex items-center gap-2"><span class="text-gray-500 w-20">API Host</span><code class="font-mono text-gray-300">{{ tool.host }}</code></div>
                <div class="flex items-center gap-2"><span class="text-gray-500 w-20">API Path</span><code class="font-mono text-gray-300">{{ tool.path }}</code></div>
                <p class="text-gray-500 mt-1">{{ tool.desc }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab: 请求格式 -->
        <div v-show="activeTab === 4" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">请求 / 响应格式</h3>
            <p class="text-xs text-gray-500 mt-0.5">完全兼容 OpenAI API 格式</p>
          </div>
          <div>
            <p class="text-xs text-gray-400 mb-1.5">请求体</p>
            <pre class="code-block"><code>{{ requestFormat }}</code></pre>
          </div>
          <div>
            <p class="text-xs text-gray-400 mb-1.5">响应体</p>
            <pre class="code-block"><code>{{ responseFormat }}</code></pre>
          </div>
        </div>

        <!-- Tab: 错误处理 -->
        <div v-show="activeTab === 5" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-white">错误码与处理建议</h3>
            <p class="text-xs text-gray-500 mt-0.5">调用失败时请参考以下状态码排查</p>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="text-gray-500 border-b border-ls-border">
                  <th class="text-left py-2 px-2">状态码</th>
                  <th class="text-left py-2 px-2">含义</th>
                  <th class="text-left py-2 px-2">原因</th>
                  <th class="text-left py-2 px-2">建议</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-ls-border">
                <tr v-for="err in errors" :key="err.code">
                  <td class="py-2 px-2"><code class="font-mono text-ls-accent">{{ err.code }}</code></td>
                  <td class="py-2 px-2 text-gray-300">{{ err.name }}</td>
                  <td class="py-2 px-2 text-gray-400">{{ err.cause }}</td>
                  <td class="py-2 px-2 text-gray-400">{{ err.suggest }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'

const toast = inject('$toast')

// ── 页面级数据 ──
const apiBaseUrl = computed(() => window.location.origin + '/api/v1')

const copyBaseUrl = () => {
  navigator.clipboard.writeText(apiBaseUrl.value)
  toast('已复制: ' + apiBaseUrl.value, 'success')
}

// ── 三步开始使用 ──
const steps = [
  { title: '添加供应商', desc: '在「供应商管理」中添加 ModelScope 账户' },
  { title: '配置别名映射', desc: '在「模型映射」中设置别名到真实模型 ID' },
  { title: '接入工具', desc: '将工具 API 地址指向本服务的 /api/v1' },
]

// ── 标签页 ──
const tabs = ['Python SDK', 'JavaScript SDK', 'curl', '第三方工具', '请求格式', '错误处理']
const activeTab = ref(3)

// ── 代码示例 ──
const pythonSdkCode = `from openai import OpenAI

client = OpenAI(
    api_key="任意值",
    base_url="${window.location.origin}/api/v1",
)

# 普通调用
response = client.chat.completions.create(
    model="hy3",
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"},
    ],
    temperature=0.7,
)
print(response.choices[0].message.content)

# 流式调用
for chunk in client.chat.completions.create(
    model="hy3",
    messages=[{"role": "user", "content": "写一首诗"}],
    stream=True,
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")`

const jsSdkCode = `import { OpenAI } from "openai"

const client = new OpenAI({
  apiKey: "任意值",
  baseURL: "${window.location.origin}/api/v1",
})

// 普通调用
const response = await client.chat.completions.create({
  model: "hy3",
  messages: [
    { role: "system", content: "你是一个助手" },
    { role: "user", content: "你好" },
  ],
  temperature: 0.7,
})
console.log(response.choices[0].message.content)

// 流式调用
const stream = await client.chat.completions.create({
  model: "hy3",
  messages: [{ role: "user", content: "写一首诗" }],
  stream: true,
})
for await (const chunk of stream) {
  if (chunk.choices[0]?.delta?.content) {
    process.stdout.write(chunk.choices[0].delta.content)
  }
}`

const curlCode = `curl ${window.location.origin}/api/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "hy3",
    "messages": [
      {"role": "system", "content": "你是一个助手"},
      {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "max_tokens": 512
  }'`

const curlStreamCode = `curl ${window.location.origin}/api/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "hy3",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'`

const commonConfig = [
  { label: 'API 地址', value: apiBaseUrl.value },
  { label: 'API Key', value: '任意字符串' },
  { label: '模型名', value: '别名（如 hy3）' },
]

const tools = [
  {
    name: 'Cursor / Windsurf',
    host: new URL(apiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '在设置中选择 "Custom OpenAI"，填入本服务的完整 URL 作为 API Base，API Key 任意填写即可。',
  },
  {
    name: 'Next.js / Vercel AI SDK',
    host: new URL(apiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '使用 createOpenAI 时传入 baseURL 指向本服务，即可像调用 OpenAI 一样使用 ModelScope。',
  },
  {
    name: 'LangChain',
    host: new URL(apiBaseUrl.value).host,
    path: '/chat/completions',
    desc: 'ChatOpenAI(base_url=本服务地址, api_key="任意值") 即可初始化，支持所有 LangChain 链和工具。',
  },
  {
    name: 'Dify / Coze / FastGPT',
    host: new URL(apiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '在自定义模型/数据源设置中选择 OpenAI 兼容，填入本服务地址，模型名称填写已配置的别名。',
  },
  {
    name: 'Claude Code / Aider',
    host: new URL(apiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '设置自定义 API provider，base_url 指向本服务，即可通过代理调用 ModelScope 模型。',
  },
]

const requestFormat = `{
  "model": "hy3",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 0.9,
  "stream": false
}`

const responseFormat = `{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1721000000,
  "model": "hy3",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "你好！有什么可以帮你的？"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 15,
    "total_tokens": 35
  }
}`

const errors = [
  { code: 200, name: '成功', cause: '请求正常处理', suggest: '—' },
  { code: 400, name: '请求错误', cause: '参数格式不正确或必填字段缺失', suggest: '检查请求体 JSON 格式' },
  { code: 404, name: '未找到', cause: '模型别名不存在且无法解析', suggest: '在「模型映射」中添加该别名' },
  { code: 429, name: '配额耗尽', cause: '所有供应商的配额均已用尽', suggest: '等待每日重置或添加新供应商' },
  { code: 502, name: '上游错误', cause: 'ModelScope 返回 5xx 错误', suggest: '稍后重试，或检查供应商状态' },
  { code: 504, name: '超时', cause: '请求超过配置的超时时间', suggest: '在「系统配置」中增大超时时间' },
]
</script>

<style scoped>
code {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
}

.code-block {
  @apply bg-ls-bg rounded-md border border-ls-border p-4 text-xs text-gray-300
    font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed;
}
.code-block code {
  @apply text-gray-300;
}
</style>
