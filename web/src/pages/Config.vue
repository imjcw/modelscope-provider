<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">系统配置</h1>
        <p class="text-xs text-gray-500 mt-0.5">全局参数和服务设置</p>
      </div>
    </header>

    <div class="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Server Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">服务设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">监听地址</label>
            <input v-model="config.listenHost" type="text"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">监听端口</label>
            <input v-model.number="config.listenPort" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">API 前缀</label>
            <input v-model="config.apiPrefix" type="text"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
        </div>
      </div>

      <!-- Database Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">数据库设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">数据库路径</label>
            <input v-model="config.dbPath" type="text"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">数据库大小</label>
            <p class="text-sm text-gray-400 font-mono">2.4 MB</p>
          </div>
        </div>
      </div>

      <!-- Log Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">日志设置</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">日志级别</label>
            <select v-model="config.logLevel"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white focus:outline-none focus:border-ls-accent appearance-none"
              style="background-image: url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2712%27 height=%2712%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%236b7280%27 stroke-width=%272%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27%3E%3Cpolyline points=%276 9 12 15 18 9%27%3E%3C/polyline%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: right 12px center;">
              <option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option>
            </select>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">请求日志持久化</p>
              <p class="text-xs text-gray-500 mt-0.5">将请求日志写入数据库</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="config.persistLogs" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
        </div>
      </div>

      <!-- Load Balancer -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">负载均衡策略</h2></div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">策略</label>
            <select v-model="config.lbStrategy"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white focus:outline-none focus:border-ls-accent appearance-none"
              style="background-image: url('data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2712%27 height=%2712%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%236b7280%27 stroke-width=%272%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27%3E%3Cpolyline points=%276 9 12 15 18 9%27%3E%3C/polyline%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: right 12px center;">
              <option>round_robin</option><option>least_conn</option><option>random</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">超时 (ms)</label>
            <input v-model.number="config.timeoutMs" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1.5">重试次数</label>
            <input v-model.number="config.retryCount" type="number"
              class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-ls-accent">
          </div>
        </div>
      </div>

      <!-- Quota Settings -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">配额设置</h2></div>
        <div class="p-5 space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">配额耗尽自动禁用</p>
              <p class="text-xs text-gray-500 mt-0.5">供应商配额耗尽时自动标记为不可用</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="config.autoDisable" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-white">每日自动重置配额</p>
              <p class="text-xs text-gray-500 mt-0.5">每日 00:00 自动刷新配额状态</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="config.autoReset" type="checkbox" class="sr-only peer">
              <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:bg-ls-accent transition-all after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
            </label>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border"><h2 class="font-semibold tracking-tight text-sm">关于</h2></div>
        <div class="p-5 space-y-2">
          <div class="flex justify-between text-sm"><span class="text-gray-500">版本</span><span class="text-white font-mono">v0.2.0</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">运行时长</span><span class="text-white font-mono">3d 14h 22m</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">Python</span><span class="text-white font-mono">3.12.4</span></div>
          <div class="flex justify-between text-sm"><span class="text-gray-500">Uvicorn</span><span class="text-white font-mono">0.51.0</span></div>
        </div>
      </div>
    </div>

    <!-- Save bar -->
    <div class="px-6 pb-6">
      <div class="bg-ls-card rounded-lg border border-ls-border px-5 py-3 flex items-center justify-between">
        <p class="text-xs text-gray-500">修改后请点击保存以应用配置</p>
        <div class="flex items-center gap-2.5">
          <button @click="resetConfig" class="text-sm text-gray-400 hover:text-white px-4 py-1.5 rounded-md">取消</button>
          <button @click="saveConfig" class="bg-ls-accent text-white font-medium rounded-lg h-9 px-6 text-sm hover:bg-ls-accentHover transition-all">保存配置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const originalConfig = () => ({
  listenHost: '0.0.0.0', listenPort: 8000, apiPrefix: '/api',
  dbPath: 'modelscope_proxy.db', logLevel: 'INFO', persistLogs: true,
  lbStrategy: 'round_robin', timeoutMs: 30000, retryCount: 0,
  autoDisable: true, autoReset: true,
})

const config = ref(originalConfig())

const saveConfig = async () => {
  const payload = {
    log_level: config.value.logLevel,
    load_balancer_strategy: config.value.lbStrategy,
    request_timeout_ms: String(config.value.timeoutMs),
    retry_count: String(config.value.retryCount),
    auto_disable_on_quota: String(config.value.autoDisable),
    auto_reset_daily: String(config.value.autoReset),
  }
  try {
    await fetch('/api/admin/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: payload }),
    })
    alert('配置已保存')
  } catch (e) {
    alert('保存失败: ' + e.message)
  }
}

const resetConfig = () => {
  Object.assign(config.value, originalConfig())
}
</script>
