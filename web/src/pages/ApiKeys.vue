<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="API Keys // Credentials" subtitle="// 管理下游客户端 API 密钥">
      <template #action>
        <div class="flex items-center gap-3">
          <button @click="openAdd" class="btn btn-primary">
            <CIcon name="plus" :stroke-width="2.5" />
            生成 Key
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">

      <CTable>
        <thead>
          <tr>
            <th class="text-left">名称</th>
            <th class="text-left">状态</th>
            <th class="text-left">Key</th>
            <th class="text-center">日志</th>
            <th class="text-center">用量</th>
            <th class="text-center">对接指南</th>
            <th class="text-left">创建时间</th>
            <th class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="key in clientKeys" :key="key.id"
            :class="{ 'opacity-50': key.status !== 'active' }">
            <td>
              <div class="flex items-center gap-3">
                <Avatar :text="key.name" size="sm" accent />
                <div>
                  <p class="font-medium text-ls-text">{{ key.name }}</p>
                  <p v-if="key.description" class="text-xs text-ls-muted max-w-[180px] truncate">{{ key.description }}</p>
                </div>
              </div>
            </td>
            <td>
              <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
            </td>
            <td class="text-xs font-mono text-ls-dim cursor-pointer hover:text-ls-text transition-colors"
              @click="showFullKey = { show: true, key: key.key_value }">
              {{ key.key_value_masked }}
            </td>
            <td class="text-center">
              <button @click="openDetailTab(key, 'logs')" class="transition-colors p-1 text-ls-accent hover:text-ls-text" title="调用日志">
                <CIcon name="file" />
              </button>
            </td>
            <td class="text-center">
              <button @click="openDetailTab(key, 'stats')" class="transition-colors p-1 text-ls-accent hover:text-ls-text" title="使用统计">
                <CIcon name="chart" />
              </button>
            </td>
            <td class="text-center">
              <button @click="openDetailTab(key, 'docs')" class="transition-colors p-1 text-ls-accent hover:text-ls-text" title="对接文档">
                <CIcon name="book" />
              </button>
            </td>
            <td class="text-xs text-ls-dim">{{ fmtTime(key.created_at) }}</td>
            <td>
              <div class="flex items-center justify-end gap-1">
                <IconButton icon="edit" title="编辑" padded @click="openEdit(key)" />
                <IconButton icon="trash" title="删除" tone="danger" padded @click="openDeleteConfirm(key)" />
              </div>
            </td>
          </tr>
        </tbody>
      </CTable>

      <!-- ── 底部统计 ── -->
      <div v-if="clientKeys.length > 0" class="mt-6 flex items-center justify-center gap-2 text-sm text-ls-muted">
        共 {{ clientKeys.length }} 个 Key · {{ activeCount }} 个启用
      </div>
      <EmptyState v-else text="暂无 API Key，点击上方按钮生成第一个 Key" class="mt-6" />
      </PageState>
    </div>

    <!-- Add Key Drawer -->
    <Drawer v-model="showAddDrawer" title="生成 API Key">
      <div class="space-y-4">
        <FormField label="Key 名称">
          <input v-model="newKey.name" type="text" placeholder="如：生产环境、测试客户端"
            class="form-input" @keyup.enter="createKey" ref="addNameInput">
        </FormField>
        <FormField label="备注描述">
          <textarea v-model="newKey.description" type="text" placeholder="可选备注"
            class="form-input resize-none" rows="2" @keyup.enter="createKey"></textarea>
        </FormField>
      </div>
      <template #footer>
        <button @click="closeAdd" class="btn btn-secondary btn-esc">取消</button>
        <button @click="createKey" class="btn btn-primary" :disabled="adding">
          {{ adding ? '生成中...' : '生成 Key' }}
        </button>
      </template>
    </Drawer>

    <!-- Edit Key Drawer -->
    <Drawer v-model="showEditDrawer" title="编辑 API Key">
      <div class="space-y-4">
        <FormField label="Key 名称">
          <input v-model="editingKey.name" type="text" placeholder="Key 名称（唯一）"
            class="form-input" @keyup.enter="saveEdit">
        </FormField>
        <FormField label="备注描述">
          <textarea v-model="editingKey.description" placeholder="可选备注"
            class="form-input resize-none" rows="2"></textarea>
        </FormField>
        <FormField label="状态">
          <div class="flex items-center gap-3">
            <CCheckbox :model-value="editingKey.status === 'active'" @update:modelValue="(val) => editingKey.status = val ? 'active' : 'disabled'" />
            <span class="text-sm" :class="editingKey.status === 'active' ? 'text-green-400' : 'text-ls-muted'">
              {{ editingKey.status === 'active' ? '启用' : '禁用' }}
            </span>
          </div>
        </FormField>
      </div>
      <template #footer>
        <button @click="closeEdit" class="btn btn-secondary btn-esc">取消</button>
        <button @click="saveEdit" class="btn btn-primary" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </template>
    </Drawer>

    <!-- Delete Confirmation Modal -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定要删除 Key <strong class='text-ls-text'>${deletingKey?.name || ''}</strong> 吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销，使用该 Key 的客户端将无法再调用接口</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />

    <!-- Show Full Key Modal -->
    <ConfirmModal
      v-model="showFullKey.show"
      title="完整 API Key"
      :message="`<p class='text-sm text-ls-dim mb-4'>请妥善保管此 Key，创建后不再显示：</p><p class='font-mono text-ls-text bg-ls-bg rounded-lg border border-ls-border p-3 break-all text-sm'>${showFullKey.key || ''}</p><p class='text-xs text-ls-muted mt-2'>点击下方按钮可复制</p>`"
      :confirm-text="'复制 Key'"
      @confirm="copyText(showFullKey.key)"
    />

    <!-- Detail Panel -->
    <KeyDetailPanel :api-key="selectedKeyForDetail" :section="detailSection" @close="closeDetail" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import CTable from '@/components/CTable.vue'
import Avatar from '@/components/Avatar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import IconButton from '@/components/IconButton.vue'
import CIcon from '@/components/CIcon.vue'
import FormField from '@/components/FormField.vue'
import EmptyState from '@/components/EmptyState.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import KeyDetailPanel from './KeyDetailPanel.vue'
import { formatTime } from '@/utils/format'
import {
  getClientKeys,
  createClientKey,
  updateClientKey,
  deleteClientKey,
} from '@/api'

const toast = inject('$toast')


// State
const loading = ref(true)
const error = ref(null)
const clientKeys = ref([])
const activeCount = computed(() => clientKeys.value.filter(k => k.status === 'active').length)

// Add drawer
const showAddDrawer = ref(false)
const adding = ref(false)
const addNameInput = ref(null)
const newKey = ref({ name: '', description: '' })

// Edit drawer
const showEditDrawer = ref(false)
const saving = ref(false)
const editingKey = ref(null)

// Delete confirmation
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingKey = ref(null)

// Show full key
const showFullKey = ref({ show: false, key: '' })

// Detail panel
const selectedKeyForDetail = ref(null)
const detailSection = ref('logs')

// Helpers
const fmtTime = (ts) => formatTime(ts)

const copyText = (text) => {
  navigator.clipboard.writeText(text).then(() => {
    toast('已复制到剪贴板', 'success')
    showFullKey.value.show = false
  }).catch(() => {
    toast('复制失败', 'error')
  })
}

// Data loading
const loadData = async () => {
  loading.value = true
  try {
    const res = await getClientKeys()
    clientKeys.value = res.data || []
  } catch (e) {
    error.value = e.message || 'Failed to load API keys'
  }
  loading.value = false
}

// Add (drawer)
const openAdd = async () => {
  newKey.value = { name: '', description: '' }
  showAddDrawer.value = true
  await nextTick()
  addNameInput.value?.focus()
}

const closeAdd = () => {
  showAddDrawer.value = false
}

const createKey = async () => {
  if (!newKey.value.name) {
    toast('请填写 Key 名称', 'error')
    return
  }
  adding.value = true
  try {
    const res = await createClientKey({
      name: newKey.value.name,
      description: newKey.value.description,
    })
    const fullKey = res.data
    showFullKey.value = { show: true, key: fullKey.key_value }
    await loadData()
    closeAdd()
  } catch (e) {
    toast('创建失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    adding.value = false
  }
}

// Edit (drawer)
const openEdit = (key) => {
  editingKey.value = {
    id: key.id,
    name: key.name,
    description: key.description || '',
    status: key.status,
  }
  showEditDrawer.value = true
}

const closeEdit = () => {
  showEditDrawer.value = false
}

const saveEdit = async () => {
  if (!editingKey.value) return
  saving.value = true
  try {
    const body = {
      name: editingKey.value.name,
      description: editingKey.value.description,
      status: editingKey.value.status,
    }
    await updateClientKey(editingKey.value.id, body)
    await loadData()
    closeEdit()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    saving.value = false
  }
}

// Toggle (checkbox)
const toggleKey = async (enabled, key) => {
  try {
    await updateClientKey(key.id, { status: enabled ? 'active' : 'disabled' })
    key.status = enabled ? 'active' : 'disabled'
  } catch (e) {
    toast('操作失败: ' + (e.message || ''), 'error')
  }
}

// Delete (confirmation modal)
const openDeleteConfirm = (key) => {
  deletingKey.value = key
  showDeleteModal.value = true
}

const confirmDelete = async () => {
  if (!deletingKey.value) return
  deleting.value = true
  try {
    await deleteClientKey(deletingKey.value.id)
    clientKeys.value = clientKeys.value.filter(k => k.id !== deletingKey.value.id)
    showDeleteModal.value = false
    deletingKey.value = null
  } catch (e) {
    toast('删除失败: ' + e.message, 'error')
  } finally {
    deleting.value = false
  }
}

// Detail panel
const openDetailTab = (key, section = 'logs') => {
  detailSection.value = section
  selectedKeyForDetail.value = key
}

const closeDetail = () => {
  selectedKeyForDetail.value = null
}

onMounted(() => {
  loadData()
})
</script>
