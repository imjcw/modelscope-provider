<template>
  <div>
    <PageHeader title="API Keys" subtitle="管理下游客户端 API 密钥">
      <template #action>
        <div class="flex items-center gap-3">
          <ViewToggle v-model="viewMode" />
          <button @click="openAdd" class="btn btn-primary">
            <CIcon name="plus" :stroke-width="2.5" />
            生成 Key
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">

      <!-- ═══════════════════════════════════════════
           视图 1：卡片行（默认）
           ═══════════════════════════════════════════ -->
      <div v-if="viewMode === 'row'" class="space-y-3">
        <div v-for="key in clientKeys" :key="key.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-ls-dim/50 transition-all neon-glow"
          :class="{ 'opacity-50': key.status !== 'active' }">
          <div class="flex items-center gap-4 flex-1 min-w-0">
            <Avatar :text="key.name" accent />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="font-medium text-sm text-ls-text truncate">{{ key.name }}</p>
                <StatusBadge :active="key.status === 'active'" active-text="启用" inactive-text="禁用" />
              </div>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-xs font-mono text-ls-dim cursor-pointer hover:text-ls-text transition-colors"
                  @click="showFullKey = { show: true, key: key.key_value }">
                  {{ key.key_value_masked }}
                </span>
              </div>
              <div class="flex items-center gap-3 mt-2 text-xs text-ls-muted">
                <span>创建于 {{ fmtTime(key.created_at) }}</span>
                <span v-if="key.description" class="text-ls-dim truncate">{{ key.description }}</span>
              </div>
              <div class="flex items-center gap-4 mt-2 text-xs">
                <span class="flex items-center gap-1">
                  <span class="text-ls-muted">今日调用</span>
                  <span class="text-ls-text font-mono">{{ key.today_requests || 0 }}</span>
                </span>
                <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
              </div>
            </div>
          </div>
          <div class="flex items-center gap-4 flex-shrink-0">
            <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
            <div class="flex items-center gap-1">
              <IconButton icon="file" title="调用日志" tone="accent" padded @click="openDetailTab(key, 'logs')" />
              <IconButton icon="chart" title="使用统计" tone="accent" padded @click="openDetailTab(key, 'stats')" />
              <IconButton icon="book" title="对接文档" tone="accent" padded @click="openDetailTab(key, 'docs')" />
            </div>
            <span class="text-ls-border">|</span>
            <IconButton icon="edit" title="编辑" @click="openEdit(key)" />
            <IconButton icon="trash" title="删除" tone="danger" @click="openDeleteConfirm(key)" />
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 2：网格卡片
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="key in clientKeys" :key="key.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 hover:border-ls-dim/50 transition-all flex flex-col gap-3 neon-glow"
          :class="{ 'opacity-50': key.status !== 'active' }">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3 min-w-0">
              <Avatar :text="key.name" accent />
              <div class="min-w-0">
                <p class="font-medium text-sm text-ls-text truncate">{{ key.name }}</p>
                <p class="text-[11px] text-ls-muted mt-0.5 truncate font-mono">{{ key.key_value_masked }}</p>
              </div>
            </div>
            <StatusBadge :active="key.status === 'active'" active-text="启用" inactive-text="禁用" />
          </div>

          <div class="flex items-center gap-3 text-xs text-ls-muted">
            <span>创建于 {{ fmtTime(key.created_at) }}</span>
            <span v-if="key.description" class="text-ls-dim truncate">{{ key.description }}</span>
          </div>

          <div class="flex items-center gap-4 text-xs">
            <span class="flex items-center gap-1">
              <span class="text-ls-muted">调用</span>
              <span class="text-ls-text font-mono">{{ key.today_requests || 0 }}</span>
            </span>
            <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-ls-border">
            <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
            <div class="flex items-center gap-1">
              <IconButton icon="file" title="调用日志" tone="accent" padded @click="openDetailTab(key, 'logs')" />
              <IconButton icon="chart" title="使用统计" tone="accent" padded @click="openDetailTab(key, 'stats')" />
              <IconButton icon="book" title="对接文档" tone="accent" padded @click="openDetailTab(key, 'docs')" />
              <span class="text-ls-border mx-1">|</span>
              <IconButton icon="edit" title="编辑" padded @click="openEdit(key)" />
              <IconButton icon="trash" title="删除" tone="danger" padded @click="openDeleteConfirm(key)" />
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 3：表格
           ═══════════════════════════════════════════ -->
      <CTable v-else-if="viewMode === 'table'">
        <thead>
          <tr>
            <th class="text-left">名称</th>
            <th class="text-left">状态</th>
            <th class="text-left">Key</th>
            <th class="text-left">创建时间</th>
            <th class="text-right">今日调用</th>
            <th class="text-right">Token</th>
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
            <td class="text-xs text-ls-dim">{{ fmtTime(key.created_at) }}</td>
            <td class="text-xs text-ls-text font-mono text-right">{{ key.today_requests || 0 }}</td>
            <td class="text-right">
              <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
            </td>
            <td>
              <div class="flex items-center justify-end gap-1">
                <IconButton icon="file" title="调用日志" tone="accent" padded @click="openDetailTab(key, 'logs')" />
                <IconButton icon="chart" title="使用统计" tone="accent" padded @click="openDetailTab(key, 'stats')" />
                <IconButton icon="book" title="对接文档" tone="accent" padded @click="openDetailTab(key, 'docs')" />
                <span class="text-ls-border mx-1">|</span>
                <IconButton icon="edit" title="编辑" padded @click="openEdit(key)" />
                <IconButton icon="trash" title="删除" tone="danger" padded @click="openDeleteConfirm(key)" />
              </div>
            </td>
          </tr>
          <tr v-if="clientKeys.length === 0">
            <td colspan="7" class="py-8 text-center text-ls-muted">暂无 API Key，点击上方按钮生成第一个 Key</td>
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
    <KeyDetailPanel :api-key="selectedKeyForDetail" :initial-tab="detailInitialTab" @close="closeDetail" />
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
import TokenStack from '@/components/TokenStack.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import ViewToggle from '@/components/ViewToggle.vue'
import KeyDetailPanel from './KeyDetailPanel.vue'
import { useViewPreference } from '@/composables/useViewPreference'
import { formatTime } from '@/utils/format'
import {
  getClientKeys,
  createClientKey,
  updateClientKey,
  deleteClientKey,
} from '@/api'

const toast = inject('$toast')

// ── 视图切换（持久化到 localStorage） ──
const viewMode = useViewPreference('apikeys_view_mode', 'row')

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
const detailInitialTab = ref('logs')

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
const openDetailTab = (key, tab = 'logs') => {
  detailInitialTab.value = tab
  selectedKeyForDetail.value = key
}

const closeDetail = () => {
  selectedKeyForDetail.value = null
}

onMounted(() => {
  loadData()
})
</script>
