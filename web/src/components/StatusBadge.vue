<script setup>
/**
 * StatusBadge — 带圆点的启用/禁用状态徽章。
 * 对齐 demo/cyberpunk-dark.html 的请求结果分布徽章：
 *   可用：bg-green-500/10 text-green-400 border border-green-500/20 rounded-full
 *   不可用：bg-ls-border/50 text-ls-dim
 */
defineProps({
  active: { type: Boolean, default: false },
  activeText: { type: String, default: '活跃' },
  inactiveText: { type: String, default: '禁用' },
})
</script>

<template>
  <span :class="active ? 'status-badge status-badge-active' : 'status-badge status-badge-inactive'">
    {{ active ? activeText : inactiveText }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.status-badge::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
}
.status-badge-active { background: rgba(34,197,94,0.1); color: var(--chart-green); border-radius: 9999px; }
.status-badge-active::before { background: var(--chart-green); }
.status-badge-inactive { background: rgb(var(--ls-border-rgb) / 0.5); color: var(--text-dim); }
.status-badge-inactive::before { background: var(--text-muted); }
</style>
