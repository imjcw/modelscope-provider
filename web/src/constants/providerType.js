/**
 * providerType.js — 供应商类型的唯一定义。
 */

export const PROVIDER_TYPE_OPTIONS = [
  { label: 'ModelScope', value: 'modelscope' },
  { label: '商汤', value: 'sensetime' },
]

export const PROVIDER_TYPE_LABELS = {
  modelscope: 'ModelScope',
  sensetime: '商汤',
}

export const PROVIDER_TYPE_COLORS = {
  modelscope: '#89b4fa',
  sensetime: '#f38ba8',
}

export const providerTypeLabel = (type) => PROVIDER_TYPE_LABELS[type] || type || '—'

export const providerTypeColor = (type) => PROVIDER_TYPE_COLORS[type] || '#89b4fa'
