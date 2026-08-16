/**
 * providerType.js — 供应商类型的唯一定义。
 */

export const PROVIDER_TYPE_OPTIONS = [
  { label: '无', value: '' },
  { label: 'ModelScope', value: 'modelscope' },
  { label: '商汤', value: 'sensetime' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Per-Model', value: 'per_model' },
]

export const PROVIDER_TYPE_LABELS = {
  modelscope: 'ModelScope',
  sensetime: '商汤',
  anthropic: 'Anthropic',
  per_model: 'Per-Model',
}

export const PROVIDER_TYPE_COLORS = {
  modelscope: '#89b4fa',
  sensetime: '#f38ba8',
  anthropic: '#6c5ce7',
  per_model: '#00b894',
}

export const providerTypeLabel = (type) => PROVIDER_TYPE_LABELS[type] || type || '—'

export const providerTypeColor = (type) => PROVIDER_TYPE_COLORS[type] || '#89b4fa'
