<script setup>
/**
 * FormField — label + 控件包装。
 * 默认 .form-label 样式（大写小标签，抽屉表单用）；
 * plain 模式为 Config / Test 的 text-xs 普通样式。
 *
 * Usage:
 *   <FormField label="别名"><input class="form-input" ... /></FormField>
 *   <FormField label="虚拟模型ID" required>...</FormField>
 *   <FormField label="描述" optional>...</FormField>
 *   <FormField label="监听地址" plain hint="(读取配置文件)">...</FormField>
 */
defineProps({
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  optional: { type: Boolean, default: false }, // (可选) 标记
  hint: { type: String, default: '' },         // 灰色提示，如 (读取配置文件)
  plain: { type: Boolean, default: false },
})
</script>

<template>
  <div>
    <label v-if="plain" class="block text-xs text-gray-500 mb-1.5">
      {{ label }}<span v-if="required" class="text-red-400"> *</span>
      <span v-if="hint" class="text-gray-600"> {{ hint }}</span>
    </label>
    <label v-else class="form-label">
      {{ label }}<span v-if="required" class="text-red-400"> *</span>
      <span v-if="optional" class="text-gray-600 normal-case text-[10px]">(可选)</span>
    </label>
    <slot />
  </div>
</template>
