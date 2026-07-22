/**
 * toolType.js — 工具调用类型（MCP / Skill / Tool）的徽章样式与标签。
 * RoleBadge 与 ToolCallCard 共用。
 */

export function toolTypeClass(name) {
  const n = (name || '').toLowerCase()
  if (n.startsWith('mcp_')) return 'bg-blue-500/10 text-blue-400'
  if (n.startsWith('skill:')) return 'bg-orange-500/10 text-orange-400'
  return 'bg-ls-accent/10 text-ls-accent'
}

export function toolTypeLabel(name) {
  const n = (name || '').toLowerCase()
  if (n.startsWith('mcp_')) return 'MCP'
  if (n.startsWith('skill:')) return 'Skill'
  return 'Tool'
}
