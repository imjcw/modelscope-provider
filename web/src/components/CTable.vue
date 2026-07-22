<script setup>
/**
 * CTable — 卡片式表格外壳。
 * 结构样式（表头 / 行分隔线 / hover / 单元格内边距）统一在 main.css 的
 * .c-table 规则里；页面只写 thead/tbody 内容与内容级 class
 * （文字颜色、font-mono、text-left/right 等；勿再写 px-、py-、hover:bg- 类）。
 *
 * Usage:
 *   <CTable>                                 text-sm + px-5 py-3（供应商 / 虚拟模型 / API Keys / 告警）
 *   <CTable size="sm" head-bg hover="full">  text-xs + px-4（请求日志）
 *   <CTable pad="sm">                        text-sm + px-4（模型用量抽屉）
 *   <CTable size="sm" head-bg dense>         text-xs + px-4 py-2.5（使用统计）
 *   <CTable head-dense :hover="false">       表头 py-2.5、无 hover（仪表盘供应商列表）
 *
 * Props:
 *   size      'md' (text-sm) | 'sm' (text-xs)
 *   pad       'lg' (px-5) | 'sm' (px-4)
 *   dense     th + td 纵向内边距 py-2.5
 *   headDense 仅 th 纵向内边距 py-2.5（td 仍 py-3）
 *   headBg    thead 底色（bg-ls-bg）
 *   hover     'dim' (elevated/30) | 'full' (elevated) | false
 */
defineProps({
  size: { type: String, default: 'md' },
  pad: { type: String, default: 'lg' },
  dense: { type: Boolean, default: false },
  headDense: { type: Boolean, default: false },
  headBg: { type: Boolean, default: false },
  hover: { type: [String, Boolean], default: 'dim' },
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border overflow-hidden overflow-x-auto neon-glow">
    <table class="c-table"
      :class="[
        size === 'sm' && 'size-sm',
        pad === 'sm' && 'pad-sm',
        dense && 'dense',
        headDense && 'head-dense',
        headBg && 'head-bg',
        hover === 'dim' ? 'hover-dim' : hover === 'full' ? 'hover-full' : '',
      ]">
      <slot />
    </table>
  </div>
</template>
