/**
 * modelType.js — 模型类型（文本/图像/代码/语音/多模态）的唯一定义。
 * 此前 Accounts 与 Mappings 各自维护一份 label / color / tag class 映射，
 * 且 image 的中文标签不一致（图像 vs 图片），现统一为「图像」。
 */

export const MODEL_TYPE_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '图像', value: 'image' },
  { label: '代码', value: 'code' },
  { label: '语音', value: 'voice' },
  { label: '多模态', value: 'multimodal' },
]

export const MODEL_TYPE_LABELS = {
  text: '文本', image: '图像', code: '代码', voice: '语音', multimodal: '多模态',
}

/** 类型圆点颜色（模型徽章 :style 用） */
export const MODEL_TYPE_COLORS = {
  text: '#89b4fa',
  image: '#f0c674',
  code: '#a6e3a1',
  voice: '#cba6f7',
  multimodal: '#f38ba8',
}

/** 绑定模型表格使用的 tag 样式类 */
const MODEL_TYPE_TAG_CLASSES = {
  text: 'tag-accent',
  image: 'tag-warning',
  code: 'tag-success',
  voice: 'tag-danger',
  multimodal: 'tag',
}

export const modelTypeColor = (type) => MODEL_TYPE_COLORS[type] || '#89b4fa'

export const modelTypeLabel = (type) => MODEL_TYPE_LABELS[type] || type || '—'

export const modelTypeTagClass = (type) => MODEL_TYPE_TAG_CLASSES[type] || 'tag'
