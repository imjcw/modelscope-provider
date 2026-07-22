<script setup>
/**
 * RoleBadge — 会话消息角色徽章。
 * system / user / assistant 为彩色徽章；tool / tool_call 展示
 * 类型徽章 + 工具名 + 调用 id。
 */
import { toolTypeClass, toolTypeLabel } from './toolType'

defineProps({
  role: { type: String, default: '' },
  toolName: { type: String, default: '' },
  toolId: { type: String, default: '' },
})

const isTool = (role) => role === 'tool' || role === 'tool_call'
</script>

<template>
  <span v-if="role === 'system'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-ls-accent/10 text-ls-accent">System</span>
  <span v-else-if="role === 'user'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-green-500/10 text-green-400">User</span>
  <span v-else-if="role === 'assistant'" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs bg-yellow-500/10 text-yellow-400">Assistant</span>
  <span v-else-if="isTool(role)" class="inline-flex items-center gap-2">
    <span :class="toolTypeClass(toolName)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
      {{ toolTypeLabel(toolName) }}
    </span>
    <span class="text-xs text-gray-400">{{ toolName || 'Tool' }}</span>
    <span v-if="toolId" class="text-xs text-gray-500 font-mono">{{ toolId }}</span>
  </span>
</template>
