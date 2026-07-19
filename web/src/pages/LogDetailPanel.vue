<template>
  <Teleport to="body">
    <!-- Overlay -->
    <div v-if="modelValue" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50" @click.self="close"></div>

    <!-- Drawer -->
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

            <!-- ── History messages (before the last user message) ── -->
            <template v-if="historyMessages.length > 0">
              <button @click="showHistory = !showHistory"
                class="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-dashed border-ls-border text-xs text-gray-500 hover:text-white hover:border-gray-500 transition-colors">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="transition-transform" :class="showHistory ? 'rotate-180' : ''">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
                <span>{{ showHistory ? '收起历史消息' : '加载历史消息' }}</span>
                <span class="text-gray-600">{{ historyMessages.length }} 条</span>
              </button>
              <div v-if="showHistory" class="space-y-2">
                <div v-for="(msg, i) in historyMessages" :key="'hist-' + i"
                  class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
                  <button @click="toggleHistoryCollapsed(i)"
                    class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                    <span v-if="msg.role === 'system'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-ls-accent/10 text-ls-accent">System</span>
                    <span v-else-if="msg.role === 'user'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-green-500/10 text-green-400">User</span>
                    <span v-else-if="msg.role === 'assistant'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                    <span v-else-if="msg.role === 'tool_call'" class="inline-flex items-center gap-2">
                      <span :class="toolTypeColor(msg.toolName || 'tool')" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                        {{ toolTypeLabel(msg.toolName || 'tool') }}
                      </span>
                      <span class="text-xs text-gray-400">{{ msg.toolName || 'Tool' }}</span>
                      <span v-if="msg.toolId" class="text-xs text-gray-500 font-mono">{{ msg.toolId }}</span>
                    </span>
                    <span v-else-if="msg.role === 'tool'" class="inline-flex items-center gap-2">
                      <span :class="toolTypeColor(msg.toolName || 'tool')" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                        {{ toolTypeLabel(msg.toolName || 'tool') }}
                      </span>
                      <span class="text-xs text-gray-400">{{ msg.toolName || 'Tool' }}</span>
                      <span v-if="msg.toolId" class="text-xs text-gray-500 font-mono">{{ msg.toolId }}</span>
                    </span>
                    <span v-if="msg.content || msg.toolArguments || msg.toolResult" @click.stop="toggleHistoryRender(i)"
                      class="text-xs text-gray-500 hover:text-white px-1.5 py-0.5 rounded transition-colors"
                      :class="renderModes[String(i)] === 'raw' ? 'bg-ls-elevated text-gray-300' : ''">
                      {{ renderModes[String(i)] === 'raw' ? 'RAW' : 'MD' }}
                    </span>
                    <span class="ml-auto text-gray-500 text-xs transition-transform" :class="!historyCollapsed[String(i)] ? 'rotate-90' : ''">▶</span>
                  </button>
                  <div v-if="!historyCollapsed[String(i)]" class="px-4 py-3 text-xs text-gray-300">
                    <!-- Tool call card: 入参 + 出参 (merged from tool role) -->
                    <template v-if="msg.role === 'tool_call'">
                      <div class="mb-2">
                        <span class="text-gray-500">入参:</span>
                        <MarkdownRender v-if="msg.toolArguments && renderModes[String(i)] !== 'raw'" :source="msg.toolArguments" />
                        <pre v-if="msg.toolArguments && renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolArguments }}</pre>
                      </div>
                      <div v-if="msg.toolResult" class="mt-2 pt-2 border-t border-ls-border">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                        </div>
                        <MarkdownRender v-if="renderModes[String(i)] !== 'raw'" :source="msg.toolResult" />
                        <pre v-if="renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolResult }}</pre>
                      </div>
                    </template>
                    <!-- Tool card: 入参 + 出参 -->
                    <template v-if="msg.role === 'tool'">
                      <div class="mb-2">
                        <span class="text-gray-500">入参:</span>
                        <MarkdownRender v-if="msg.toolArguments && renderModes[String(i)] !== 'raw'" :source="msg.toolArguments" />
                        <pre v-if="msg.toolArguments && renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolArguments }}</pre>
                      </div>
                      <div v-if="msg.content" class="mt-2 pt-2 border-t border-ls-border">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                        </div>
                        <MarkdownRender v-if="renderModes[String(i)] !== 'raw'" :source="msg.content" />
                        <pre v-if="renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
                      </div>
                    </template>
                    <!-- Normal message content -->
                    <div v-if="msg.role !== 'tool' && msg.role !== 'tool_call' && msg.content && renderModes[String(i)] !== 'raw'">
                      <MarkdownRender :source="msg.content" />
                    </div>
                    <pre v-if="msg.role !== 'tool' && msg.role !== 'tool_call' && msg.content && renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
                    <!-- Assistant toolCalls with inline results -->
                    <div v-if="msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0" class="mt-3 pt-3 border-t border-ls-border space-y-2">
                      <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="bg-ls-bg rounded-lg border border-ls-border p-3">
                        <div class="flex items-center gap-2 mb-2">
                          <span :class="toolTypeColor(tc.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                            {{ toolTypeLabel(tc.name) }}
                          </span>
                          <span class="text-xs text-gray-400 font-medium">{{ tc.name }}</span>
                          <span v-if="tc.id" class="text-xs text-gray-500 font-mono">{{ tc.id }}</span>
                        </div>
                        <div class="mb-2">
                          <span class="text-gray-500">入参:</span>
                          <MarkdownRender :source="tc.arguments" />
                        </div>
                        <div v-if="tc.result" class="mt-2 pt-2 border-t border-ls-border">
                          <div class="flex items-center gap-2 mb-1">
                            <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                          </div>
                          <MarkdownRender :source="tc.result" />
                        </div>
                      </div>
                    </div>
                    <span v-if="!msg.content && !msg.toolCalls && msg.role !== 'tool' && msg.role !== 'tool_call'" class="text-gray-600 text-xs italic">—</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- ── Current conversation (from the last user message onwards) ── -->
            <div v-for="(msg, i) in currentMessages" :key="'cur-' + i"
              :class="['bg-ls-card rounded-lg border overflow-hidden', i === 0 ? 'border-ls-accent' : 'border-ls-border']">
              <button @click="toggleExpanded(currentStartIndex + i)"
                class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                <span v-if="msg.role === 'system'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-ls-accent/10 text-ls-accent">System</span>
                <span v-else-if="msg.role === 'user'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-green-500/10 text-green-400">User</span>
                <span v-else-if="msg.role === 'assistant'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                <span v-else-if="msg.role === 'tool_call'" class="inline-flex items-center gap-2">
                  <span :class="toolTypeColor(msg.toolName || 'tool')" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                    {{ toolTypeLabel(msg.toolName || 'tool') }}
                  </span>
                  <span class="text-xs text-gray-400">{{ msg.toolName || 'Tool' }}</span>
                  <span v-if="msg.toolId" class="text-xs text-gray-500 font-mono">{{ msg.toolId }}</span>
                </span>
                <span v-else-if="msg.role === 'tool'" class="inline-flex items-center gap-2">
                  <span :class="toolTypeColor(msg.toolName || 'tool')" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                    {{ toolTypeLabel(msg.toolName || 'tool') }}
                  </span>
                  <span class="text-xs text-gray-400">{{ msg.toolName || 'Tool' }}</span>
                  <span v-if="msg.toolId" class="text-xs text-gray-500 font-mono">{{ msg.toolId }}</span>
                </span>
                <span v-if="i === 0 && msg.role === 'user'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] bg-green-500/20 text-green-300 border border-green-500/30">本次输入</span>
                <button v-if="msg.content || msg.toolArguments || msg.toolResult" @click.stop="toggleRender(currentStartIndex + i)"
                  class="text-xs text-gray-500 hover:text-white px-1.5 py-0.5 rounded transition-colors"
                  :class="renderModes[String(currentStartIndex + i)] === 'raw' ? 'bg-ls-elevated text-gray-300' : ''">
                  {{ renderModes[String(currentStartIndex + i)] === 'raw' ? 'RAW' : 'MD' }}
                </button>
                <span class="ml-auto text-gray-500 text-xs transition-transform" :class="expandedMap.get(currentStartIndex + i) ? 'rotate-90' : ''">▶</span>
              </button>
              <div v-if="expandedMap.get(currentStartIndex + i)" class="px-4 py-3 text-xs text-gray-300">
                <!-- Tool call card: 入参 + 出参 (merged from tool role) -->
                <template v-if="msg.role === 'tool_call'">
                      <div class="mb-2">
                        <span class="text-gray-500">入参:</span>
                        <MarkdownRender v-if="msg.toolArguments && renderModes[String(i)] !== 'raw'" :source="msg.toolArguments" />
                        <pre v-if="msg.toolArguments && renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolArguments }}</pre>
                      </div>
                      <div v-if="msg.toolResult" class="mt-2 pt-2 border-t border-ls-border">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                        </div>
                        <MarkdownRender v-if="renderModes[String(i)] !== 'raw'" :source="msg.toolResult" />
                        <pre v-if="renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolResult }}</pre>
                      </div>
                    </template>
                    <!-- Tool card: 入参 + 出参 -->
                    <template v-if="msg.role === 'tool'">
                      <div class="mb-2">
                        <span class="text-gray-500">入参:</span>
                        <MarkdownRender v-if="msg.toolArguments && renderModes[String(i)] !== 'raw'" :source="msg.toolArguments" />
                        <pre v-if="msg.toolArguments && renderModes[String(i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.toolArguments }}</pre>
                      </div>
                  <div v-if="msg.content" class="mt-2 pt-2 border-t border-ls-border">
                    <div class="flex items-center gap-2 mb-1">
                      <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                    </div>
                    <MarkdownRender v-if="renderModes[String(currentStartIndex + i)] !== 'raw'" :source="msg.content" />
                    <pre v-if="renderModes[String(currentStartIndex + i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
                  </div>
                </template>
                <!-- Normal message content -->
                <div v-if="msg.role !== 'tool' && msg.role !== 'tool_call' && msg.content && renderModes[String(currentStartIndex + i)] !== 'raw'">
                  <MarkdownRender :source="msg.content" />
                </div>
                <pre v-if="msg.role !== 'tool' && msg.role !== 'tool_call' && msg.content && renderModes[String(currentStartIndex + i)] === 'raw'" class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
                <!-- Assistant toolCalls with inline results -->
                <div v-if="msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0" class="mt-3 pt-3 border-t border-ls-border space-y-2">
                  <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="bg-ls-bg rounded-lg border border-ls-border p-3">
                    <div class="flex items-center gap-2 mb-2">
                      <span :class="toolTypeColor(tc.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
                        {{ toolTypeLabel(tc.name) }}
                      </span>
                      <span class="text-xs text-gray-400 font-medium">{{ tc.name }}</span>
                      <span v-if="tc.id" class="text-xs text-gray-500 font-mono">{{ tc.id }}</span>
                    </div>
                    <div class="text-xs text-gray-300 mb-2">
                      <span class="text-gray-500">入参:</span>
                      <MarkdownRender :source="tc.arguments" />
                    </div>
                    <div v-if="tc.result" class="mt-2 pt-2 border-t border-ls-border">
                      <div class="flex items-center gap-2 mb-1">
                        <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-purple-500/10 text-purple-400">出参</span>
                      </div>
                      <MarkdownRender :source="tc.result" />
                    </div>
                  </div>
                </div>
                <span v-if="!msg.content && !msg.toolCalls && msg.role !== 'tool' && msg.role !== 'tool_call'" class="text-gray-600 text-xs italic">—</span>
              </div>
            </div>

            <!-- Assistant response (concatenated) -->
            <div v-if="responseContentText" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
              <button @click="toggleResponseExpanded"
                class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
                <span v-if="responseChunks.length > 1" class="text-xs text-gray-600">{{ responseChunks.length }} chunks</span>
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
              <div class="flex justify-between text-sm">
                <span class="text-gray-400">Cache 命中</span>
                <span class="font-mono text-green-400">{{ ((modelValue.cached_tokens || 0) + (modelValue.prompt_partial_cached || 0)).toLocaleString() }}</span>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-gray-400">Cache 未命中</span>
                <span class="font-mono text-gray-500">{{ Math.max(0, (modelValue.input_tokens || 0) - (modelValue.cached_tokens || 0) - (modelValue.prompt_partial_cached || 0)).toLocaleString() }}</span>
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
                <div class="text-xs text-gray-500">首次响应</div>
                <div class="text-xs text-ls-accent font-mono">{{ formatMsTime(modelValue.first_response) }}</div>
              </div>
              <div v-if="modelValue.request_start && ttfr">
                <div class="text-xs text-gray-500">首次响应耗时</div>
                <div class="text-xs text-white font-mono">{{ ttfr }}</div>
              </div>
              <div v-if="modelValue.end_time">
                <div class="text-xs text-gray-500">响应结束</div>
                <div class="text-xs text-white font-mono">{{ formatMsTime(modelValue.end_time) }}</div>
              </div>
              <div v-if="totalDuration">
                <div class="text-xs text-gray-500">总耗时</div>
                <div class="text-xs text-white font-mono">{{ totalDuration }}</div>
              </div>
              <div v-if="!modelValue.request_start && !modelValue.end_time" class="text-xs text-gray-600">—</div>
            </div>
          </div>

          <!-- 性能指标 -->
          <div class="p-4 border-b border-ls-border">
            <h3 class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">性能指标</h3>
            <div class="space-y-2">
              <div class="flex justify-between text-sm"><span class="text-gray-400">延迟</span><span class="text-white font-mono">{{ modelValue.latency_ms ? formatDuration(modelValue.latency_ms) : '-' }}</span></div>
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
            <div class="space-y-1.5">
              <div v-for="(val, key) in responseHeaders" :key="key">
                <div class="text-xs text-gray-500 font-mono">{{ key }}</div>
                <div class="text-xs text-white font-mono" :title="val">{{ val }}</div>
              </div>
            </div>
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
const showHistory = ref(false)

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
const renderModes = ref({})

const close = () => {
  showDrawer.value = false
  setTimeout(() => {
    emit('update:modelValue', null)
  }, 350)
}

const handleKeydown = (e) => {
  if (e.key === 'Escape') close()
}
onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

watch(() => props.modelValue, (val) => {
  if (val) {
    nextTick(() => {
      showDrawer.value = true
      renderModes.value = {}
      responseExpanded.value = true
      responseRenderMode.value = 'md'
      showHistory.value = false

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
    })
  } else {
    showDrawer.value = false
    collapsedMsgs.value = {}
    historyCollapsed.value = {}
    renderModes.value = {}
    responseExpanded.value = true
    responseRenderMode.value = 'md'
    showHistory.value = false
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
      const content = typeof msg.content === 'string' ? msg.content : ''
      const calls = msg.tool_calls || msg.toolCalls

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
          toolCalls: null,
          toolResult: '',
          // Preserve tool_call_id on tool role messages so Pass 2 can match
          tool_call_id: msg.tool_call_id || msg.toolCallId || '',
        })
      }
    }

    // Pass 2: merge tool results into matching tool_call entries by tool_call_id
    const result = []
    let i = 0
    while (i < out.length) {
      const msg = out[i]

      if (msg.role === 'tool_call' && msg.toolId) {
        // Look ahead for tool results with matching tool_call_id
        let j = i + 1
        while (j < out.length && out[j].role === 'tool') {
          const toolMsg = out[j]
          const tcId = toolMsg.tool_call_id || toolMsg.toolCallId || ''
          // If this tool result matches the current tool_call, attach it and consume
          if (tcId === msg.toolId) {
            msg.toolResult = typeof toolMsg.content === 'string' ? toolMsg.content : ''
            j++ // consume this tool message (don't add to result)
            continue
          }
          // If it's a tool result for a different tool_call, stop looking ahead
          break
        }
        result.push(msg)
        i = j
      } else {
        result.push(msg)
        i++
      }
    }

    return result
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

const responseContentText = computed(() => responseChunks.value.join(''))

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
function formatMsTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    const pad = (n, l = 2) => String(n).padStart(l, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`
  } catch { return ts }
}
function formatDuration(ms) {
  if (!ms || ms <= 0) return ''
  if (ms < 1000) return `${ms}ms`
  const totalSec = Math.round(ms / 1000)
  if (totalSec < 60) return `${totalSec}s`
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min < 60) return sec > 0 ? `${min}m ${sec}s` : `${min}m`
  const hr = Math.floor(min / 60)
  const m = min % 60
  return m > 0 ? `${hr}h ${m}m` : `${hr}h`
}
const responseHeaders = computed(() => {
  const raw = props.modelValue?.response_headers
  if (!raw) return null
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw } catch { return null }
})
const copyText = (text) => navigator.clipboard.writeText(text).catch(() => {})

</script>
