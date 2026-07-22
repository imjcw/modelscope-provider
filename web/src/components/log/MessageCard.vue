<script setup>
/**
 * MessageCard — 日志详情里的可折叠消息卡。
 * 统一了 LogDetailPanel 中「历史消息」与「当前会话」两段几乎相同的模板：
 * 角色徽章 + MD/RAW 切换 + 展开箭头 + 正文 / 工具调用卡。
 *
 * Usage:
 *   <MessageCard :msg="msg" :expanded="!collapsed" :render-mode="mode"
 *     :highlight="i === 0" :input-badge="i === 0 && msg.role === 'user'"
 *     @toggle-expand="..." @toggle-render="..." />
 */
import { computed } from 'vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import RoleBadge from './RoleBadge.vue'
import ToolIO from './ToolIO.vue'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps({
  msg: { type: Object, required: true },
  expanded: { type: Boolean, default: false },
  renderMode: { type: String, default: 'md' },    // md | raw
  highlight: { type: Boolean, default: false },   // 当前轮首条（accent 边框）
  inputBadge: { type: Boolean, default: false },  // 「本次输入」徽章
})

defineEmits(['toggle-expand', 'toggle-render'])

const isTool = computed(() => props.msg.role === 'tool' || props.msg.role === 'tool_call')
const isRaw = computed(() => props.renderMode === 'raw')
// tool 角色的输出在 content；tool_call 的输出在 toolResult（已由解析阶段合并）
const toolOutput = computed(() =>
  props.msg.role === 'tool_call' ? props.msg.toolResult
  : props.msg.role === 'tool' ? props.msg.content
  : ''
)
</script>

<template>
  <div :class="['bg-ls-card rounded-lg border overflow-hidden', highlight ? 'border-ls-accent' : 'border-ls-border']">
    <button @click="$emit('toggle-expand')"
      class="flex items-center gap-2 px-4 py-2.5 w-full text-left hover:bg-ls-elevated transition-colors">
      <RoleBadge :role="msg.role" :tool-name="msg.toolName" :tool-id="msg.toolId" />
      <span v-if="inputBadge"
        class="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] bg-green-500/20 text-green-300 border border-green-500/30">本次输入</span>
      <button v-if="msg.content || msg.toolArguments || msg.toolResult" @click.stop="$emit('toggle-render')"
        class="text-xs text-gray-500 hover:text-white px-1.5 py-0.5 rounded transition-colors"
        :class="isRaw ? 'bg-ls-elevated text-gray-300' : ''">
        {{ isRaw ? 'RAW' : 'MD' }}
      </button>
      <span class="ml-auto text-gray-500 text-xs transition-transform" :class="expanded ? 'rotate-90' : ''">▶</span>
    </button>
    <div v-if="expanded" class="px-4 py-3 text-xs text-gray-300">
      <!-- tool_call / tool：入参 + 出参 -->
      <template v-if="isTool">
        <div class="mb-2">
          <ToolIO label="入参" :source="msg.toolArguments" :raw="isRaw" />
        </div>
        <div v-if="toolOutput" class="mt-2 pt-2 border-t border-ls-border">
          <ToolIO label="出参" tone="out" :source="toolOutput" :raw="isRaw" />
        </div>
      </template>
      <!-- 普通消息内容 -->
      <div v-if="!isTool && msg.content && !isRaw">
        <MarkdownRender :source="msg.content" />
      </div>
      <pre v-if="!isTool && msg.content && isRaw"
        class="bg-ls-bg rounded-lg border border-ls-border p-3 text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ msg.content }}</pre>
      <!-- assistant 内联 toolCalls -->
      <div v-if="msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0"
        class="mt-3 pt-3 border-t border-ls-border space-y-2">
        <ToolCallCard v-for="(tc, ti) in msg.toolCalls" :key="ti" :tc="tc" />
      </div>
      <span v-if="!msg.content && !msg.toolCalls && !isTool" class="text-gray-600 text-xs italic">—</span>
    </div>
  </div>
</template>
