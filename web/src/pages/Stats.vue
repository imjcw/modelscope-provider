<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">使用统计</h1>
        <p class="text-xs text-gray-500 mt-0.5">Token 消耗与模型使用分布</p>
      </div>
      <select class="bg-ls-card border border-ls-border rounded-md px-2.5 py-1 text-sm text-white focus:outline-none focus:border-ls-accent">
        <option>最近 7 天</option>
        <option selected>最近 30 天</option>
        <option>最近 90 天</option>
      </select>
    </header>

    <div class="p-6 space-y-6">
      <!-- Activity Heatmap -->
      <div class="bg-ls-card rounded-lg border border-ls-border p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold tracking-tight text-sm">活跃热力图</h2>
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-500">较少</span>
            <div v-for="i in 4" :key="i" class="w-3 h-3 rounded-sm" :style="{ backgroundColor: `rgba(94,106,210,${0.12 + i * 0.22})` }"></div>
            <span class="text-xs text-gray-500">较多</span>
          </div>
        </div>
        <div class="flex gap-0.5">
          <div class="flex flex-col justify-between text-[9px] text-gray-600 w-5 text-center">
            <div>日</div><div>一</div><div>二</div><div>三</div><div>四</div><div>五</div><div>六</div>
          </div>
          <div class="flex-1">
            <div v-for="(row, ri) in heatmap" :key="ri" class="flex gap-0.5 mt-0.5 first:mt-0">
              <div v-for="(cell, ci) in row" :key="ci" class="flex-1 h-4 rounded-sm"
                :style="{ backgroundColor: cell > 0 ? `rgba(94,106,210,${Math.min(1, 0.15 + cell * 0.12)})` : '#232329' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Daily Token Trend -->
      <div class="bg-ls-card rounded-lg border border-ls-border p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold tracking-tight text-sm">按天 Token 趋势</h2>
          <div class="flex items-center gap-4">
            <span v-for="m in modelColors" :key="m.name" class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-2.5 h-2.5 rounded" :style="{ backgroundColor: m.color }"></span>{{ m.name }}
            </span>
          </div>
        </div>
        <div class="flex items-end gap-1.5 h-48 border-b border-ls-border pb-1">
          <div v-for="(col, i) in trendColumns" :key="i" class="flex-1 flex flex-col-reverse gap-0">
            <div v-for="seg in col" :key="seg.model"
              class="w-full rounded-sm"
              :style="{ height: seg.h + '%', backgroundColor: seg.color }"></div>
          </div>
        </div>
        <div class="flex justify-between text-[10px] text-gray-600 mt-2">
          <span>6/16</span><span>6/21</span><span>6/26</span><span>7/1</span><span>7/6</span><span>7/11</span><span>7/16</span>
        </div>
      </div>

      <!-- Model Usage Donut -->
      <div class="bg-ls-card rounded-lg border border-ls-border p-5">
        <h2 class="font-semibold tracking-tight text-sm mb-5">模型用量</h2>
        <div class="flex items-center gap-8">
          <div class="flex-shrink-0">
            <svg width="176" height="176" viewBox="0 0 176 176">
              <circle cx="88" cy="88" r="68" fill="none" stroke="#0e0e10" stroke-width="22"/>
              <circle v-for="seg in donutSegs" :key="seg.label" cx="88" cy="88" r="68" fill="none"
                :stroke="seg.color" :stroke-width="22"
                :stroke-dasharray="seg.dash" :stroke-dashoffset="seg.offset"
                transform="rotate(-90 88 88)"/>
              <text x="88" y="84" text-anchor="middle" style="font-size:20px;font-weight:700" fill="white">1.1亿</text>
              <text x="88" y="102" text-anchor="middle" style="font-size:11px" fill="#6b7280">tokens</text>
            </svg>
          </div>
          <div class="flex-1 space-y-3">
            <div v-for="seg in donutSegs" :key="seg.label" class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded" :style="{ backgroundColor: seg.color }"></span>
                <span class="text-sm text-white">{{ seg.label }}</span>
              </div>
              <div class="flex items-center gap-4">
                <span class="text-xs text-gray-400">{{ seg.tokens }}</span>
                <span class="text-sm font-mono text-white w-8 text-right">{{ seg.pct }}%</span>
              </div>
            </div>
            <hr class="border-ls-border">
            <div class="flex items-center justify-between">
              <span class="text-sm text-gray-400">总计</span>
              <span class="text-lg font-bold text-white font-mono">1.1亿</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const heatmap = [
  [0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,1,1,1,0],
  [0,0,0,0,0,0,0,0,2,2,1,1,0,0,0,0,0,0,0,0,2,2,3,2],
  [0,0,0,0,0,0,0,0,3,4,3,2,0,0,0,0,0,0,0,0,3,4,4,3],
  [0,0,0,0,0,0,0,0,1,2,2,1,0,0,0,0,0,0,0,0,2,2,3,4],
  [0,0,0,0,0,0,0,0,2,3,4,3,0,0,0,0,0,0,0,0,2,2,3,2],
  [0,0,0,0,0,0,0,0,1,1,2,2,0,0,0,0,0,0,0,0,1,2,2,3],
  [0,0,0,0,0,0,0,0,1,2,3,4,3,2,0,0,0,0,0,2,2,3,4,3],
]

const modelColors = [
  { name: 'hy3', color: '#3b82f6' },
  { name: 'qwen2.5-7b', color: '#22c55e' },
  { name: 'qwen2.5-14b', color: '#a855f7' },
  { name: '其他', color: '#f97316' },
]

const trendColumns = Array.from({ length: 30 }, (_, i) => {
  const intensity = Math.min(1, i / 25)
  return [
    { model: 'hy3', h: Math.min(55, intensity * 60), color: '#3b82f6' },
    { model: 'q7b', h: Math.min(18, i > 5 ? intensity * 15 : 0), color: '#22c55e' },
    { model: 'q14b', h: Math.min(6, i > 10 ? intensity * 8 : 0), color: '#a855f7' },
    { model: 'other', h: Math.min(3, i > 15 ? intensity * 4 : 0), color: '#f97316' },
  ]
})

const donutSegs = [
  { label: 'hy3', tokens: '6,240.8万 tokens', pct: 55, color: '#3b82f6', dash: '234.6', offset: '0' },
  { label: 'qwen2.5-7b', tokens: '1,973.6万 tokens', pct: 17, color: '#22c55e', dash: '73.0', offset: '-234.6' },
  { label: 'qwen2.5-14b', tokens: '1,720.7万 tokens', pct: 15, color: '#a855f7', dash: '64.1', offset: '-307.6' },
  { label: 'deepseek-v3', tokens: '965万 tokens', pct: 8.5, color: '#f97316', dash: '36.3', offset: '-371.7' },
  { label: 'GLM-5', tokens: '258万 tokens', pct: 2.2, color: '#ef4444', dash: '9.4', offset: '-408.0' },
]
</script>
