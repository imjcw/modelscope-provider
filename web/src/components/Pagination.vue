<script setup>
/**
 * Pagination — 分页器。
 * 完整模式：首页 / 上页 / 页码 / 下页 / 末页（请求日志）
 * simple 模式：上页 / 页码 / 下页（API Key 调用日志）
 *
 * Usage:
 *   <Pagination v-model:page="page" :total="total" :page-size="20" />
 *   <Pagination v-model:page="detailPage" :total="detailTotal" simple />
 */
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 20 },
  simple: { type: Boolean, default: false },
})

const emit = defineEmits(['update:page'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const set = (p) => emit('update:page', p)

const BTN = 'text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30'
</script>

<template>
  <div class="flex items-center justify-between mt-4">
    <p class="text-xs text-gray-500">共 {{ total }} 条记录</p>
    <div class="flex items-center gap-2">
      <button v-if="!simple" @click="set(0)" :disabled="page <= 0" :class="BTN">⇤ 首页</button>
      <button @click="set(page - 1)" :disabled="page <= 0" :class="BTN">← 上页</button>
      <span class="text-xs text-gray-500">{{ page + 1 }}{{ simple ? '' : ` / ${totalPages}` }}</span>
      <button @click="set(page + 1)" :disabled="!simple && page >= totalPages - 1" :class="BTN">下页 →</button>
      <button v-if="!simple" @click="set(totalPages - 1)" :disabled="page >= totalPages - 1" :class="BTN">末页 ⇥</button>
    </div>
  </div>
</template>
