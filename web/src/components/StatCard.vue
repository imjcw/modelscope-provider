<script setup>
/**
 * StatCard — 赛博朋克霓虹指标卡。
 * 对齐 demo/cyberpunk-dark.html 的 KPI 卡片写法：
 *   bg-ls-card rounded-lg border border-ls-border p-5 neon-glow
 *   label（uppercase tracking-[0.15em] text-[10px]）+ 大数值 + 次级说明/趋势
 *
 * 数值区可用默认插槽自定义（如 TokenStack、带颜色的成功率）。
 * 带 #icon 插槽时切换为 demo KPI 布局：label 行右侧图标方块，
 * 数值行 items-baseline（可挂 unit 与 delta 趋势芯片），#footer 放 sparkline/进度条。
 *
 * Usage:
 *   <StatCard label="今日请求" value="1,234" sub="今日" />
 *   <StatCard :label="card.label" :value="card.value" :sub="card.sub" :sub-class="card.trendColor" />
 *   <StatCard label="Token" size="sm" label-class="mb-2"><TokenStack ... /></StatCard>
 *   <StatCard label="总请求" :value="fmt(total)" :delta="'+12.5%'" delta-class="bg-green-500/10 text-green-400"
 *             icon-bg-class="bg-ls-accent/10">
 *     <template #icon><svg class="w-3.5 h-3.5 text-ls-accent">…</svg></template>
 *     <template #footer><KpiSparkline … /></template>
 *   </StatCard>
 */
defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '' },
  sub: { type: String, default: '' },
  subClass: { type: String, default: 'text-ls-muted' },
  labelClass: { type: String, default: '' },
  size: { type: String, default: 'lg' },
  // demo KPI 布局（仅在有 #icon 插槽时生效）
  unit: { type: String, default: '' },          // 数值右侧单位，如 'ms' / 'req/s'
  delta: { type: String, default: '' },         // 趋势芯片文本，如 '+12.5%'
  deltaClass: { type: String, default: '' },    // 趋势芯片配色
  iconBgClass: { type: String, default: '' },   // 图标方块底色，如 'bg-ls-accent/10'
})
</script>

<template>
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow" :class="size === 'sm' ? 'p-4' : 'p-5'">
    <!-- label 行：有图标时右置图标方块（demo 布局） -->
    <div v-if="$slots.icon" class="flex items-center justify-between">
      <p class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]" :class="labelClass">{{ label }}</p>
      <span class="w-7 h-7 rounded flex items-center justify-center" :class="iconBgClass">
        <slot name="icon" />
      </span>
    </div>
    <p v-else class="text-[10px] font-medium text-ls-dim uppercase tracking-[0.15em]" :class="[size === 'lg' && 'mb-1', labelClass]">{{ label }}</p>

    <!-- 数值行：有图标时 baseline 排列 + 单位 + delta 芯片 -->
    <div v-if="$slots.icon" class="mt-3 flex items-baseline gap-1.5">
      <slot>
        <p class="text-2xl font-bold text-ls-text">{{ value }}</p>
      </slot>
      <span v-if="unit" class="text-xs text-ls-muted">{{ unit }}</span>
      <span v-if="delta" class="text-xs px-1.5 py-0.5 rounded font-medium" :class="deltaClass">{{ delta }}</span>
    </div>
    <slot v-else>
      <p v-if="size === 'lg'" class="text-2xl font-bold text-ls-text">{{ value }}</p>
      <p v-else class="text-2xl font-bold text-ls-text mt-1">{{ value }}</p>
    </slot>

    <!-- sparkline / 进度条区 -->
    <div v-if="$slots.footer" class="mt-2">
      <slot name="footer" />
    </div>
    <p v-if="sub" class="text-xs mt-1" :class="subClass">{{ sub }}</p>
  </div>
</template>
