<script setup>
/**
 * ModelListEditor — 模型行编辑器（供应商 添加/编辑 抽屉共用）。
 * models 为 { model_name, model_type, context_length } 数组；行内字段
 * 通过对象引用就地修改，增/删行由事件通知父组件（删除可接确认弹窗）。
 *
 * Usage:
 *   <ModelListEditor :models="newSupplier.models" animate
 *     @add="addNewModel" @remove="removeNewModel" />
 *   <ModelListEditor :models="editingSupplier.models" empty-text="暂无配置模型"
 *     @add="addEditModel" @remove="removeEditModel" />
 */
import CSelect from './CSelect.vue'
import CIcon from './CIcon.vue'
import { MODEL_TYPE_OPTIONS } from '@/constants/modelType'

defineProps({
  models: { type: Array, required: true },
  emptyText: { type: String, default: '' },  // 提供后，列表为空时展示空态文案
  animate: { type: Boolean, default: false }, // 行入场交错动画（添加抽屉）
})

defineEmits(['add', 'remove'])
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <label class="form-label m-0">支持模型</label>
      <span class="text-[11px] text-gray-500">{{ models.length }} 个模型</span>
    </div>
    <div v-if="emptyText && models.length === 0" class="text-center py-6 text-gray-500 text-sm">
      {{ emptyText }}
    </div>
    <div class="space-y-3">
      <div v-for="(m, idx) in models" :key="idx"
        class="bg-ls-bg rounded-lg border border-ls-border p-3"
        :style="animate ? { animation: 'rowIn .2s ease-out ' + idx * 50 + 'ms both' } : {}">
        <div class="grid grid-cols-1 md:grid-cols-[1fr_140px_120px_28px] gap-3 items-center">
          <input v-model="m.model_name" type="text" placeholder="模型名称，如 qwen-max"
            class="form-input h-10 px-3 font-mono text-sm" />
          <CSelect v-model="m.model_type" :options="MODEL_TYPE_OPTIONS" size="md" placeholder="类型" />
          <input v-model.number="m.context_length" type="number" placeholder="上下文"
            class="form-input h-10 px-3 text-sm font-mono" />
          <button type="button" @click="$emit('remove', idx)" class="action-icon" title="删除">
            <CIcon name="x" />
          </button>
        </div>
      </div>
    </div>
    <button type="button" @click="$emit('add')"
      class="mt-3 w-full h-10 rounded-lg border border-dashed border-ls-border text-ls-accent hover:text-ls-accentHover hover:border-ls-accent/30 transition-all flex items-center justify-center gap-2 text-sm">
      <CIcon name="plus" :size="16" />
      添加模型
    </button>
  </div>
</template>
