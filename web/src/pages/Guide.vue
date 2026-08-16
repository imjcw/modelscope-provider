<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="使用指南 // Guide" subtitle="// 将代理服务接入你的工具和项目">
      <template #action>
        <div class="flex items-center gap-3">
          <div>
            <span class="text-xs text-ls-muted">OpenAI 端</span>
            <div class="flex items-center gap-1 bg-ls-card rounded-md border border-ls-border px-2.5 py-1">
              <code class="text-xs font-mono text-ls-accent">{{ openaiBaseUrl }}</code>
              <CopyButton :text="openaiBaseUrl" :size="12" class="ml-1"
                color-class="text-ls-dim hover:text-ls-text"
                :toast-text="'已复制: ' + openaiBaseUrl" />
            </div>
          </div>
          <div>
            <span class="text-xs text-ls-muted">Anthropic 端</span>
            <div class="flex items-center gap-1 bg-ls-card rounded-md border border-ls-border px-2.5 py-1">
              <code class="text-xs font-mono text-ls-accent">{{ anthropicBaseUrl }}</code>
              <CopyButton :text="anthropicBaseUrl" :size="12" class="ml-1"
                color-class="text-ls-dim hover:text-ls-text"
                :toast-text="'已复制: ' + anthropicBaseUrl" />
            </div>
          </div>
        </div>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6 space-y-6">
      <!-- 协议说明 -->
      <CCard no-padding>
        <div class="p-4">
          <div class="flex items-center gap-2 mb-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--chart-yellow)" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
            <span class="text-xs text-ls-text font-medium">协议由客户端入口决定</span>
          </div>
          <p class="text-xs text-ls-dim">一个供应商可同时支持 OpenAI 兼容接口和 Anthropic 原生接口、两个入口对应两个地址。</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
            <div class="bg-ls-bg rounded-md border border-ls-border p-3">
              <p class="text-xs font-mono text-ls-accent">/openai/v1/chat/completions</p>
              <p class="text-[11px] text-ls-muted mt-1">OpenAI 协议 · 鉴权 <span class="font-mono">Authorization: Bearer</span> · 指向 <span class="font-mono">base_url</span></p>
            </div>
            <div class="bg-ls-bg rounded-md border border-ls-border p-3">
              <p class="text-xs font-mono text-ls-accent">/anthropic/v1/messages</p>
              <p class="text-[11px] text-ls-muted mt-1">Anthropic 协议 · 鉴权 <span class="font-mono">x-api-key</span> · 指向 <span class="font-mono">anthropic_base_url</span>（回落 base_url）</p>
            </div>
          </div>
        </div>
      </CCard>
      <!-- 步骤导航 -->
      <CCard>
        <h2 class="font-semibold text-ls-text mb-4">三步开始使用</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div v-for="(step, i) in steps" :key="i" class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-full bg-ls-accent/20 text-ls-accent flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5">{{ i + 1 }}</div>
            <div>
              <p class="text-sm text-ls-text font-medium">{{ step.title }}</p>
              <p class="text-xs text-ls-muted mt-0.5">{{ step.desc }}</p>
            </div>
          </div>
        </div>
      </CCard>

      <!-- 接入方式标签页 -->
      <CCard no-padding>
        <template #header>
          <div class="px-5 py-3 flex items-center gap-1 overflow-x-auto">
            <button v-for="(tab, i) in tabs" :key="i" @click="activeTab = i"
              :class="activeTab === i ? 'bg-ls-accent text-ls-bg' : 'text-ls-dim hover:text-ls-text'"
              class="px-3 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap">{{ tab }}</button>
          </div>
        </template>

        <!-- Tab: OpenAI 协议 -->
        <div v-show="activeTab === 0" class="p-5 space-y-4">
          <div class="flex items-center gap-3">
            <span class="text-sm font-medium text-ls-text">OpenAI 协议</span>
            <code class="text-xs font-mono text-ls-accent">/openai/v1/chat/completions</code>
            <span class="text-xs text-ls-muted">· 鉴权 <span class="font-mono">Authorization: Bearer</span></span>
          </div>
          <div class="flex gap-1">
            <button v-for="(s, i) in openaiSnippets" :key="s.key" @click="activeOpenaiSnippet = i"
              :class="activeOpenaiSnippet === i ? 'bg-ls-accent text-ls-bg' : 'text-ls-dim hover:text-ls-text'"
              class="px-3 py-1.5 text-xs rounded-md transition-colors">{{ s.label }}</button>
          </div>
          <CodeBlock :lang="openaiSnippets[activeOpenaiSnippet].lang" :code="openaiSnippets[activeOpenaiSnippet].code" />
          <div v-if="activeOpenaiSnippet === 2">
            <h3 class="text-sm font-medium text-ls-text mt-3">流式响应（SSE）</h3>
            <p class="text-xs text-ls-muted mt-0.5">添加 <code class="text-ls-accent">"stream": true</code> 即可</p>
            <CodeBlock lang="bash" :code="curlStreamCode" />
          </div>
          <div class="bg-ls-bg rounded-md border border-ls-border p-3">
            <div class="flex items-center gap-2 mb-1">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--chart-green)" stroke-width="2.5"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>
              <span class="text-xs text-green-400">注意</span>
            </div>
            <p class="text-xs text-ls-dim">api_key 可填任意字符串，代理服务不校验；base_url 指向本服务 <code class="text-ls-accent">/openai/v1</code> 即可。</p>
          </div>
        </div>

        <!-- Tab: Anthropic 协议 -->
        <div v-show="activeTab === 1" class="p-5 space-y-4">
          <div class="flex items-center gap-3">
            <span class="text-sm font-medium text-ls-text">Anthropic 协议</span>
            <code class="text-xs font-mono text-ls-accent">/anthropic/v1/messages</code>
            <span class="text-xs text-ls-muted">· 鉴权 <span class="font-mono">x-api-key</span></span>
          </div>
          <div class="flex gap-1">
            <button v-for="(s, i) in anthropicSnippets" :key="s.key" @click="activeAnthropicSnippet = i"
              :class="activeAnthropicSnippet === i ? 'bg-ls-accent text-ls-bg' : 'text-ls-dim hover:text-ls-text'"
              class="px-3 py-1.5 text-xs rounded-md transition-colors">{{ s.label }}</button>
          </div>
          <CodeBlock :lang="anthropicSnippets[activeAnthropicSnippet].lang" :code="anthropicSnippets[activeAnthropicSnippet].code" />
          <div class="bg-ls-bg rounded-md border border-ls-border p-3">
            <div class="flex items-center gap-2 mb-1">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--chart-yellow)" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
              <span class="text-xs text-ls-accent">注意</span>
            </div>
            <p class="text-xs text-ls-dim">base_url 指向本服务 <code class="text-ls-accent">/anthropic/v1</code>；api_key 填供应商密钥，通过 <code class="font-mono">x-api-key</code> 头传递；请求体必须指定 <code class="font-mono">max_tokens</code>。</p>
          </div>
        </div>

        <!-- Tab: 第三方工具 -->
        <div v-show="activeTab === 2" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-ls-text">第三方工具对接</h3>
            <p class="text-xs text-ls-muted mt-0.5">兼容 OpenAI API 的工具均可直接接入</p>
          </div>

          <!-- 通用配置说明 -->
          <div class="bg-ls-bg rounded-md border border-ls-border p-4">
            <h4 class="text-xs font-medium text-ls-text mb-2">通用配置</h4>
            <div class="space-y-1.5">
              <div v-for="row in commonConfig" :key="row.label" class="flex items-center gap-3 text-xs">
                <span class="text-ls-muted w-32 flex-shrink-0">{{ row.label }}</span>
                <code class="text-ls-accent font-mono bg-ls-card px-1.5 py-0.5 rounded">{{ row.value }}</code>
              </div>
            </div>
          </div>

          <!-- 工具卡片 -->
          <div class="space-y-3">
            <div v-for="tool in tools" :key="tool.name" class="bg-ls-bg rounded-md border border-ls-border p-4">
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-xs font-medium text-ls-text">{{ tool.name }}</h4>
                <span class="text-xs text-ls-accent px-1.5 py-0.5 rounded bg-ls-accent/10">已兼容</span>
              </div>
              <div class="space-y-1 text-xs">
                <div class="flex items-center gap-2"><span class="text-ls-muted w-20">API Host</span><code class="font-mono text-ls-dim">{{ tool.host }}</code></div>
                <div class="flex items-center gap-2"><span class="text-ls-muted w-20">API Path</span><code class="font-mono text-ls-dim">{{ tool.path }}</code></div>
                <p class="text-ls-muted mt-1">{{ tool.desc }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab: 请求格式 -->
        <div v-show="activeTab === 3" class="p-5 space-y-5">
          <div>
            <h3 class="text-sm font-medium text-ls-text">请求 / 响应格式</h3>
            <p class="text-xs text-ls-muted mt-0.5">完全兼容 OpenAI API 格式</p>
          </div>
          <div>
            <p class="text-xs text-ls-dim mb-1.5">请求体</p>
            <CodeBlock lang="json" :code="requestFormat" />
          </div>
          <div>
            <p class="text-xs text-gray-400 mb-1.5">响应体</p>
            <CodeBlock lang="json" :code="responseFormat" />
          </div>
        </div>

        <!-- Tab: 错误处理 -->
        <div v-show="activeTab === 4" class="p-5 space-y-5">
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
      </CCard>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import CCard from '@/components/CCard.vue'
import CopyButton from '@/components/CopyButton.vue'
import CodeBlock from '@/components/CodeBlock.vue'

// ── 页面级数据 ──
const openaiBaseUrl = ref(window.location.origin + '/openai/v1')
const anthropicBaseUrl = ref(window.location.origin + '/anthropic/v1')

// ── 三步开始使用 ──
const steps = [
  { title: '添加供应商', desc: '在「供应商管理」中添加 ModelScope 账户' },
  { title: '配置别名映射', desc: '在「模型映射」中设置别名到真实模型 ID' },
  { title: '接入工具', desc: 'OpenAI 工具指向 /openai/v1；Anthropic 工具指向 /anthropic/v1' },
]

// ── 标签页 ──
const tabs = ['OpenAI 协议', 'Anthropic 协议', '第三方工具', '请求格式', '错误处理']
const activeTab = ref(0)

// ── OpenAI 协议代码示例（按语言切换）──
const openaiSnippets = [
  {
    key: 'python', label: 'Python', lang: 'python',
    code: `from openai import OpenAI

client = OpenAI(
    api_key="任意值",
    base_url="${window.location.origin}/openai/v1",
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
        print(chunk.choices[0].delta.content, end="")`,
  },
  {
    key: 'javascript', label: 'JavaScript / TypeScript', lang: 'javascript',
    code: `import { OpenAI } from "openai"

const client = new OpenAI({
  apiKey: "任意值",
  baseURL: "${window.location.origin}/openai/v1",
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
}`,
  },
  {
    key: 'curl', label: 'curl', lang: 'bash',
    code: `curl ${window.location.origin}/openai/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "hy3",
    "messages": [
      {"role": "system", "content": "你是一个助手"},
      {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "max_tokens": 512
  }'`,
  },
]
const activeOpenaiSnippet = ref(0)

// ── Anthropic 协议代码示例（按语言切换）──
const anthropicSnippets = [
  {
    key: 'python', label: 'Python', lang: 'python',
    code: `from anthropic import Anthropic

client = Anthropic(
    api_key="你的密钥",
    base_url="${window.location.origin}/anthropic/v1",
)
message = client.messages.create(
    model="hy3",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=1024,
)
print(message.content[0].text)`,
  },
  {
    key: 'curl', label: 'curl', lang: 'bash',
    code: `curl ${window.location.origin}/anthropic/v1/messages \\
  -H "content-type: application/json" \\
  -H "x-api-key: 你的密钥" \\
  -d '{
    "model": "hy3",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 1024
  }'`,
  },
]
const activeAnthropicSnippet = ref(0)

// ── curl 流式（仅 OpenAI curl 子 tab 时展示）──
const curlStreamCode = `curl ${window.location.origin}/openai/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "hy3",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'`

const commonConfig = [
  { label: 'OpenAI 端', value: openaiBaseUrl.value },
  { label: 'Anthropic 端', value: anthropicBaseUrl.value },
  { label: 'API Key', value: '任意字符串（OpenAI 端）/ 供应商密钥（Anthropic 端）' },
  { label: '模型名', value: '别名（如 hy3）' },
]

const tools = [
  {
    name: 'Cursor / Windsurf',
    host: new URL(openaiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '在设置中选择 "Custom OpenAI"，填入本服务的完整 URL 作为 API Base，API Key 任意填写即可。',
  },
  {
    name: 'Next.js / Vercel AI SDK',
    host: new URL(openaiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '使用 createOpenAI 时传入 baseURL 指向本服务，即可像调用 OpenAI 一样使用 ModelScope。',
  },
  {
    name: 'LangChain',
    host: new URL(openaiBaseUrl.value).host,
    path: '/chat/completions',
    desc: 'ChatOpenAI(base_url=本服务地址, api_key="任意值") 即可初始化，支持所有 LangChain 链和工具。',
  },
  {
    name: 'Dify / Coze / FastGPT',
    host: new URL(openaiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '在自定义模型/数据源设置中选择 OpenAI 兼容，填入本服务地址，模型名称填写已配置的别名。',
  },
  {
    name: 'Aider / 其他 OpenAI 客户端',
    host: new URL(openaiBaseUrl.value).host,
    path: '/chat/completions',
    desc: '设置自定义 API provider，base_url 指向本服务，即可通过代理调用 ModelScope 模型。',
  },
  {
    name: 'Claude Code（原生 Anthropic 模式）',
    host: new URL(anthropicBaseUrl.value).host,
    path: '/v1/messages',
    desc: '启用 Anthropic 模式并指向本服务的 Anthropic 端地址，通过 x-api-key 鉴权调用。',
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
</style>
