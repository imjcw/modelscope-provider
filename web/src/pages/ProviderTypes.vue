<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="供应商类型 // Provider Types" subtitle="// 管理供应商类型及其限流策略配置">
      <template #action>
        <button @click="openCreate" class="btn btn-primary" v-if="!loading">
          <CIcon name="plus" :stroke-width="2.5" />
          新增类型
        </button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">
        <CTable v-if="providerTypes.length > 0" size="sm" head-bg hover="full">
          <thead>
            <tr>
              <th class="text-left">标识</th>
              <th class="text-left">名称</th>
              <th class="text-left">策略类型</th>
              <th class="text-left">参数配置</th>
              <th class="text-left">内置</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pt in providerTypes" :key="pt.id">
              <td>
                <span class="inline-flex items-center gap-2">
                  <span class="w-3 h-3 rounded-full" :style="{ background: pt.color || '#89b4fa' }"></span>
                  <span class="font-mono text-ls-accent font-semibold">{{ pt.type_key }}</span>
                </span>
              </td>
              <td class="text-ls-text">{{ pt.name }}</td>
              <td>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-mono"
                  :class="pt.strategy_type === 'fixed_window' || pt.strategy_type === 'fixed_window_per_model' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-cyan-500/10 text-cyan-400'">
                  {{ pt.strategy_type === 'fixed_window' ? '固定窗口' : pt.strategy_type === 'fixed_window_per_model' ? '按模型窗口' : '被动限流' }}
                </span>
              </td>
              <td class="text-xs text-ls-dim font-mono">
                <template v-if="pt.strategy_type === 'fixed_window'">
                  窗口 {{ formatDuration(pt.config?.window_seconds || 0) }} · 上限 {{ pt.config?.max_requests || 0 }} 次
                </template>
                <template v-else-if="pt.strategy_type === 'fixed_window_per_model'">
                  <span v-if="modelCount(pt.config)" class="text-ls-accent">{{ modelCount(pt.config) }} 个模型自定义</span>
                  <span v-else class="text-ls-muted">未配置模型</span>
                </template>
                <span v-else class="text-ls-muted">—</span>
              </td>
              <td>
                <span class="text-xs" :class="pt.built_in ? 'text-ls-muted' : 'text-ls-text'">{{ pt.built_in ? '是' : '否' }}</span>
              </td>
              <td class="text-right">
                <IconButton icon="edit" title="编辑" padded @click="openEdit(pt)" />
                <IconButton v-if="!pt.built_in" icon="trash" title="删除" tone="danger" padded @click="confirmDelete(pt)" />
              </td>
            </tr>
          </tbody>
        </CTable>
        <div v-else-if="!loading" class="text-center py-12 text-ls-muted">暂无供应商类型</div>
      </PageState>
    </div>

    <!-- Create / Edit Drawer -->
    <Drawer v-model="showDrawer" :title="editingId ? '编辑供应商类型' : '新增供应商类型'">
      <div class="space-y-4">
        <FormField label="名称">
          <input v-model="form.name" type="text" placeholder="如：自定义供应商"
            class="form-input" @keyup.enter="save" @input="autoGenerateKey">
        </FormField>
        <FormField label="限流策略">
          <CSelect v-model="form.strategy_type" :options="STRATEGY_OPTIONS" placeholder="选择策略类型" />
        </FormField>
        <template v-if="form.strategy_type === 'fixed_window'">
          <FormField label="窗口时长（秒）">
            <input v-model.number="form.config.window_seconds" type="number" placeholder="18000"
              class="form-input font-mono" min="1">
          </FormField>
          <FormField label="最大请求数">
            <input v-model.number="form.config.max_requests" type="number" placeholder="1500"
              class="form-input font-mono" min="1">
          </FormField>
        </template>
        <template v-if="form.strategy_type === 'fixed_window_per_model'">
          <FormField label="模型自定义配置">
            <div class="space-y-2">
              <div v-for="(ov, idx) in modelOverrides" :key="idx"
                class="flex items-start gap-2 p-2 rounded-lg border border-ls-border">
                <div class="flex-1 grid grid-cols-3 gap-2">
                  <input v-model="ov.model_name" type="text" placeholder="模型名"
                    class="form-input font-mono text-xs" @keyup.enter="addModelOverride">
                  <input v-model.number="ov.window_seconds" type="number" placeholder="窗口秒数"
                    class="form-input font-mono text-xs" min="1">
                  <input v-model.number="ov.max_requests" type="number" placeholder="请求上限"
                    class="form-input font-mono text-xs" min="1">
                </div>
                <button @click="removeModelOverride(idx)" class="btn btn-icon btn-ghost text-ls-danger shrink-0 mt-0.5"
                  title="移除">
                  <CIcon name="x" :stroke-width="2.5" />
                </button>
              </div>
              <button @click="addModelOverride" class="btn btn-secondary btn-sm w-full">
                + 添加模型
              </button>
            </div>
          </FormField>
        </template>
        <FormField label="颜色">
          <input v-model="form.color" type="color" class="h-9 w-full rounded-lg border border-ls-border bg-ls-bg cursor-pointer">
        </FormField>
        <FormField label="描述">
          <textarea v-model="form.description" placeholder="可选备注"
            class="form-input resize-none" rows="2"></textarea>
        </FormField>
      </div>
      <template #footer>
        <button @click="closeDrawer" class="btn btn-secondary btn-esc">取消</button>
        <button @click="save" class="btn btn-primary btn-enter" :disabled="saving">
          {{ saving ? '保存中...' : editingId ? '保存' : '创建' }}
        </button>
      </template>
    </Drawer>

    <!-- Delete confirmation -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定要删除供应商类型 <strong class='text-ls-text'>${deletingItem?.name || ''}</strong> 吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="doDelete"
    />

    <!-- Model override delete confirmation -->
    <ConfirmModal
      v-model="showModelDeleteModal"
      title="移除模型配置"
      :message="`确定要移除模型 <strong class='text-ls-text font-mono'>${pendingModelName || ''}</strong> 的自定义配置吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销</span>`"
      danger
      confirm-text="移除"
      @confirm="confirmModelDelete"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import CTable from '@/components/CTable.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import FormField from '@/components/FormField.vue'
import CSelect from '@/components/CSelect.vue'
import CIcon from '@/components/CIcon.vue'
import IconButton from '@/components/IconButton.vue'
import { getProviderTypes, createProviderType, updateProviderType, deleteProviderType } from '@/api'

const toast = inject('$toast')

const STRATEGY_OPTIONS = [
  { label: '被动限流（header_based）', value: 'header_based' },
  { label: '固定窗口（fixed_window）', value: 'fixed_window' },
  { label: '按模型窗口（fixed_window_per_model）', value: 'fixed_window_per_model' },
]

const loading = ref(true)
const error = ref(null)
const providerTypes = ref([])

const showDrawer = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({
  type_key: '',
  name: '',
  description: '',
  strategy_type: 'header_based',
  config: { window_seconds: 18000, max_requests: 1500 },
  color: '#89b4fa',
})

const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

const showModelDeleteModal = ref(false)
const pendingModelDeleteIdx = ref(null)
const pendingModelName = ref('')

const modelOverrides = ref([])

const slugify = (text) => {
  return text.toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]+/g, '-')  // 非单词字符（含中文）→ 连字符
    .replace(/^-+|-+$/g, '')               // 去掉首尾连字符
    || 'untitled'
}

const autoGenerateKey = () => {
  if (editingId.value) return
  form.type_key = slugify(form.name)
}

const modelCount = (config) => {
  if (!config || !config.models) return 0
  return Object.keys(config.models).length
}

const addModelOverride = () => {
  modelOverrides.value.push({ model_name: '', window_seconds: null, max_requests: null })
}

const removeModelOverride = (idx) => {
  const ov = modelOverrides.value[idx]
  pendingModelName.value = ov?.model_name?.trim() || '未命名'
  pendingModelDeleteIdx.value = idx
  showModelDeleteModal.value = true
}

const confirmModelDelete = () => {
  if (pendingModelDeleteIdx.value != null) {
    modelOverrides.value.splice(pendingModelDeleteIdx.value, 1)
  }
  pendingModelDeleteIdx.value = null
  pendingModelName.value = ''
}

const formatDuration = (sec) => {
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.round(sec / 60)}m`
  const h = Math.floor(sec / 3600)
  const m = Math.round((sec % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

const load = async () => {
  loading.value = true
  try {
    const res = await getProviderTypes()
    providerTypes.value = res.data || []
  } catch (e) {
    error.value = e.message || '加载失败'
  }
  loading.value = false
}

const openCreate = () => {
  editingId.value = null
  form.type_key = ''
  form.name = ''
  form.description = ''
  form.strategy_type = 'header_based'
  form.config = { window_seconds: 18000, max_requests: 1500 }
  form.color = '#89b4fa'
  modelOverrides.value = []
  showDrawer.value = true
}

const openEdit = (pt) => {
  editingId.value = pt.id
  form.type_key = pt.type_key
  form.name = pt.name
  form.description = pt.description || ''
  form.strategy_type = pt.strategy_type || 'header_based'
  if (pt.strategy_type === 'fixed_window_per_model') {
    form.config = { ...(pt.config || {}), models: { ...((pt.config || {}).models || {}) } }
  } else {
    form.config = { ...(pt.config || {}), window_seconds: pt.config?.window_seconds || 18000, max_requests: pt.config?.max_requests || 1500 }
  }
  form.color = pt.color || '#89b4fa'
  // Convert config.models object to array for editing
  const models = pt.config?.models || {}
  modelOverrides.value = Object.entries(models).map(([name, cfg]) => ({
    model_name: name,
    window_seconds: cfg.window_seconds ?? null,
    max_requests: cfg.max_requests ?? null,
  }))
  showDrawer.value = true
}

const closeDrawer = () => {
  showDrawer.value = false
}

const save = async () => {
  if (!form.name) {
    toast('请填写名称', 'error')
    return
  }
  // Auto-generate type_key for new items
  if (!editingId.value && !form.type_key) {
    form.type_key = slugify(form.name)
  }
  if (!form.type_key) {
    toast('无法生成标识，请检查名称', 'error')
    return
  }
  saving.value = true
  try {
    // Build config payload
    const payload = {
      ...form,
      config: { ...form.config },
    }
    // Convert modelOverrides array back to config.models object
    if (form.strategy_type === 'fixed_window_per_model') {
      const models = {}
      for (const ov of modelOverrides.value) {
        const name = ov.model_name?.trim()
        if (!name) continue
        const cfg = {}
        if (ov.window_seconds != null && ov.window_seconds > 0) cfg.window_seconds = ov.window_seconds
        if (ov.max_requests != null && ov.max_requests > 0) cfg.max_requests = ov.max_requests
        if (Object.keys(cfg).length > 0) models[name] = cfg
      }
      payload.config = { models }
    } else {
      // Ensure models field is not sent for non-per-model types
      delete payload.config.models
    }
    if (editingId.value) {
      await updateProviderType(editingId.value, {
        name: payload.name,
        description: payload.description,
        strategy_type: payload.strategy_type,
        config: payload.config,
        color: payload.color,
      })
      toast('已更新', 'success')
    } else {
      await createProviderType({
        type_key: payload.type_key,
        name: payload.name,
        description: payload.description,
        strategy_type: payload.strategy_type,
        config: payload.config,
        color: payload.color,
      })
      toast('已创建', 'success')
    }
    await load()
    closeDrawer()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || ''
    toast('操作失败: ' + msg, 'error')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (pt) => {
  deletingItem.value = pt
  showDeleteModal.value = true
}

const doDelete = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await deleteProviderType(deletingItem.value.id)
    await load()
    showDeleteModal.value = false
    deletingItem.value = null
    toast('已删除', 'success')
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || ''
    toast('删除失败: ' + msg, 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  load()
})
</script>