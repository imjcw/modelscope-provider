<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">模型映射</h1>
        <p class="text-xs text-gray-500 mt-0.5">管理模型别名与实际模型 ID 的映射关系</p>
      </div>
      <button @click="openAdd"
        class="bg-ls-accent text-white font-medium rounded-lg h-9 px-4 text-sm hover:bg-ls-accentHover transition-all inline-flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        添加映射
      </button>
    </header>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>
      <div class="space-y-3">
        <!-- Mapping rows -->
        <div v-for="m in mappings" :key="m.alias_name"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all">
          <div class="flex items-center gap-6">
            <div>
              <p class="text-xs text-gray-500 mb-0.5">别名</p>
              <p class="text-sm font-mono text-ls-accent font-semibold">{{ m.alias_name }}</p>
            </div>
            <div class="flex items-center gap-2 text-gray-600">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </div>
            <div>
              <p class="text-xs text-gray-500 mb-0.5">实际模型 ID</p>
              <p class="text-sm font-mono text-white">{{ m.actual_model_id }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs">活跃</span>
            <button @click="openEdit(m)" class="text-gray-500 hover:text-white p-1 transition-colors" title="编辑">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button @click="openDeleteConfirm(m)" class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="mappings.length === 0"
          class="bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-600">
            <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
          <p class="text-sm text-gray-500">暂无映射规则</p>
          <button @click="openAdd" class="text-xs text-ls-accent hover:text-ls-accentHover">添加第一个映射 →</button>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ mappings.length }} 条映射
      </div>
      </div>
    </div>

    <!-- ── 添加/编辑 映射 抽屉 ── -->
    <Teleport to="body">
      <div v-if="showFormDrawer" class="drawer-overlay">
        <div class="drawer drawer-right">
          <div class="drawer-panel" :class="{ 'exiting': formExiting }">
            <div class="drawer-header">
              <h2 class="drawer-title">{{ isEditing ? '编辑映射' : '添加映射' }}</h2>
              <button @click="closeForm" class="drawer-close">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <div class="drawer-body space-y-4">
              <div>
                <label class="form-label">别名</label>
                <input v-model="form.alias" type="text" placeholder="my-alias"
                  class="form-input font-mono" :disabled="isEditing"
                  @keyup.enter="submitForm" ref="formAliasInput">
                <p v-if="isEditing" class="text-[10px] text-gray-600 mt-1">别名不可修改</p>
              </div>
              <div>
                <label class="form-label">实际模型 ID</label>
                <input v-model="form.model_id" type="text" placeholder="qwen-max"
                  class="form-input font-mono" @keyup.enter="submitForm">
              </div>
            </div>
            <div class="drawer-footer">
              <button @click="closeForm" class="btn btn-secondary">取消</button>
              <button @click="submitForm" class="btn btn-primary" :disabled="submitting">
                {{ submitting ? '保存中...' : isEditing ? '保存' : '添加' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── 删除确认 弹窗 ── -->
    <Teleport to="body">
      <div v-if="showDeleteModal" class="modal-overlay" @click.self="closeDeleteConfirm">
        <div class="modal">
          <div class="modal-icon modal-icon-danger">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </div>
          <h3 class="modal-title">确认删除</h3>
          <p class="modal-message">
            确定删除别名 <strong class="text-white">{{ deletingItem?.alias_name }}</strong> 的映射吗？<br>
            <span class="text-gray-500 text-xs">此操作不可撤销</span>
          </p>
          <div class="modal-actions">
            <button @click="closeDeleteConfirm" class="btn btn-secondary">取消</button>
            <button @click="confirmDelete" class="btn btn-danger" :disabled="deleting">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { getMappings, bulkUpdateMappings as apiBulkUpdate, deleteMapping as apiDelete } from '@/api'

const loading = ref(true)
const error = ref(null)
const mappings = ref([])

// ── Form drawer ──
const showFormDrawer = ref(false)
const formExiting = ref(false)
const submitting = ref(false)
const formAliasInput = ref(null)
const isEditing = ref(false)
const form = ref({ alias: '', model_id: '' })

// ── Delete modal ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

// ── Data loading ──
const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await getMappings()
    mappings.value = res.data || []
  } catch (e) {
    error.value = e.message || 'Failed to load mappings'
  }
  loading.value = false
}

// ── Form ──
const openAdd = async () => {
  isEditing.value = false
  form.value = { alias: '', model_id: '' }
  showFormDrawer.value = true
  formExiting.value = false
  await nextTick()
  formAliasInput.value?.focus()
}

const openEdit = (item) => {
  isEditing.value = true
  form.value = {
    alias: item.alias_name,
    model_id: item.actual_model_id,
  }
  showFormDrawer.value = true
  formExiting.value = false
}

const closeForm = async () => {
  formExiting.value = true
  await new Promise(r => setTimeout(r, 250))
  showFormDrawer.value = false
  formExiting.value = false
}

const submitForm = async () => {
  if (!form.value.alias || !form.value.model_id) {
    alert('请填写别名和实际模型 ID')
    return
  }
  submitting.value = true
  try {
    // Build full mappings dict (all existing + this one)
    const allMappings = {}
    for (const m of mappings.value) {
      allMappings[m.alias_name] = m.actual_model_id
    }
    allMappings[form.value.alias] = form.value.model_id

    await apiBulkUpdate(allMappings)
    await loadData()
    closeForm()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message || ''))
  } finally {
    submitting.value = false
  }
}

// ── Delete ──
const openDeleteConfirm = (item) => {
  deletingItem.value = item
  showDeleteModal.value = true
}

const closeDeleteConfirm = () => {
  showDeleteModal.value = false
  deletingItem.value = null
}

const confirmDelete = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await apiDelete(deletingItem.value.alias_name)
    await loadData()
    closeDeleteConfirm()
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  } finally {
    deleting.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.drawer-panel.exiting {
  animation: slideOutRight .25s cubic-bezier(.4, 0, .2, 1) forwards;
}
</style>
