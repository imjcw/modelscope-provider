<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">模型映射</h1>
        <p class="text-xs text-gray-500 mt-0.5">管理模型别名与实际模型 ID 的映射关系</p>
      </div>
      <button @click="showAddDialog = true"
        class="bg-ls-accent text-white font-medium rounded-lg h-9 px-4 text-sm hover:bg-ls-accentHover transition-all inline-flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        添加映射
      </button>
    </header>

    <div class="p-6">
      <!-- Mapping Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div v-for="group in groupedMappings" :key="group.alias"
          class="bg-ls-card rounded-lg border border-ls-border p-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <p class="text-xs text-gray-500 mb-0.5">别名</p>
              <p class="text-sm font-mono text-ls-accent font-semibold">{{ group.alias }}</p>
            </div>
            <div class="flex items-center gap-2">
              <span class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs">活跃</span>
              <button @click="editMapping(group)" class="text-gray-500 hover:text-white p-1 transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button @click="deleteMap(group.alias)" class="text-gray-500 hover:text-red-400 p-1 transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <p class="text-xs text-gray-500 mb-1.5">中国大陆</p>
              <p class="text-sm font-mono text-white bg-ls-bg rounded-md px-3 py-2">{{ group.china }}</p>
            </div>
            <div>
              <p class="text-xs text-gray-500 mb-1.5">海外</p>
              <p class="text-sm font-mono text-white bg-ls-bg rounded-md px-3 py-2">{{ group.overseas || '—' }}</p>
            </div>
          </div>
        </div>

        <!-- Add new placeholder -->
        <div class="bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-5 flex flex-col items-center justify-center gap-2 min-h-[180px] hover:border-gray-600 transition-colors cursor-pointer"
          @click="showAddDialog = true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-500">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="12" y2="12"/>
          </svg>
          <p class="text-sm text-gray-500">添加新的模型映射</p>
        </div>
      </div>

      <!-- Bulk Edit JSON -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border">
          <h2 class="font-semibold tracking-tight text-sm">批量编辑 (JSON)</h2>
        </div>
        <div class="p-5">
          <textarea v-model="jsonText"
            class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-3 text-sm text-white font-mono focus:outline-none focus:border-ls-accent resize-none"
            rows="10"></textarea>
          <div class="flex items-center justify-between mt-3">
            <p class="text-xs text-gray-500">JSON 格式：key 为别名，value 为各区域对应的实际模型 ID</p>
            <button @click="saveJson"
              class="bg-ls-accent text-white font-medium rounded-lg h-9 px-6 text-sm hover:bg-ls-accentHover transition-all">保存</button>
          </div>
        </div>
      </div>

      <!-- Add Mapping Dialog -->
      <div v-if="showAddDialog" class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showAddDialog = false">
        <div class="bg-ls-card border border-ls-border rounded-lg w-full max-w-md p-6">
          <h2 class="text-lg font-semibold text-white mb-4">添加模型映射</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">别名</label>
              <input v-model="addForm.alias" type="text" placeholder="my-alias"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">中国大陆模型</label>
              <input v-model="addForm.china" type="text" placeholder="hy3"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">海外模型（可选）</label>
              <input v-model="addForm.overseas" type="text" placeholder="hy3 overseas"
                class="w-full bg-ls-bg rounded-lg border border-ls-border px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-ls-accent font-mono">
            </div>
          </div>
          <div class="flex items-center justify-end gap-2.5 mt-6">
            <button @click="showAddDialog = false" class="text-sm text-gray-400 hover:text-white px-4 py-1.5 rounded-md">取消</button>
            <button @click="addMapping" class="bg-ls-accent text-white font-medium rounded-lg h-9 px-6 text-sm hover:bg-ls-accentHover transition-all">添加</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const showAddDialog = ref(false)
const jsonText = ref('')

const addForm = ref({ alias: '', china: '', overseas: '' })

const mappings = ref([
  { id: 1, alias_name: 'hy3', region: 'china', actual_model_id: 'hy3' },
  { id: 2, alias_name: 'hy3', region: 'overseas', actual_model_id: 'hy3 overseas' },
  { id: 3, alias_name: 'qwen2.5-7b', region: 'china', actual_model_id: 'qwen2.5-7b' },
  { id: 4, alias_name: 'qwen2.5-7b', region: 'overseas', actual_model_id: 'qwen2.5-7b-instruct' },
])

const groupedMappings = computed(() => {
  const groups = {}
  for (const m of mappings.value) {
    if (!groups[m.alias_name]) groups[m.alias_name] = {}
    groups[m.alias_name][m.region] = m.actual_model_id
  }
  return Object.entries(groups).map(([alias, regions]) => ({ alias, ...regions }))
})

const syncJson = () => {
  const groups = {}
  for (const m of mappings.value) {
    if (!groups[m.alias_name]) groups[m.alias_name] = {}
    groups[m.alias_name][m.region] = m.actual_model_id
  }
  jsonText.value = JSON.stringify(groups, null, 2)
}

onMounted(() => syncJson())

const addMapping = () => {
  if (!addForm.value.alias || !addForm.value.china) return
  const nextId = Math.max(1, ...mappings.value.map(m => m.id)) + 1
  mappings.value.push({ id: nextId, alias_name: addForm.value.alias, region: 'china', actual_model_id: addForm.value.china })
  if (addForm.value.overseas) {
    mappings.value.push({ id: nextId + 1, alias_name: addForm.value.alias, region: 'overseas', actual_model_id: addForm.value.overseas })
  }
  showAddDialog.value = false
  addForm.value = { alias: '', china: '', overseas: '' }
  syncJson()
}

const deleteMap = (alias) => {
  if (!confirm(`确定删除 ${alias} 的所有映射？`)) return
  mappings.value = mappings.value.filter(m => m.alias_name !== alias)
  syncJson()
}

const editMapping = (group) => {
  alert(`编辑 ${group.alias} — 请在下方 JSON 区域修改后保存`)
  syncJson()
  setTimeout(() => {
    const groups = JSON.parse(jsonText.value)
    groups[group.alias] = { china: group.china, overseas: group.overseas || '' }
    jsonText.value = JSON.stringify(groups, null, 2)
  }, 100)
}

const saveJson = () => {
  try {
    const data = JSON.parse(jsonText.value)
    const newMappings = []
    let id = 0
    for (const [alias, regions] of Object.entries(data)) {
      for (const [region, actualId] of Object.entries(regions)) {
        id++
        newMappings.push({ id, alias_name: alias, region, actual_model_id: actualId })
      }
    }
    mappings.value = newMappings
  } catch (e) {
    alert('JSON 格式错误: ' + e.message)
  }
}
</script>
