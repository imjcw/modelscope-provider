<template>
  <div>
    <PageHeader title="API Keys" subtitle="管理下游客户端 API 密钥">
      <template #action>
        <div class="flex items-center gap-3">
          <ViewToggle v-model="viewMode" />
          <button @click="openAdd" class="btn btn-primary">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            生成 Key
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>

      <!-- ═══════════════════════════════════════════
           视图 1：卡片行（默认）
           ═══════════════════════════════════════════ -->
      <div v-if="viewMode === 'row'" class="space-y-3">
        <div v-for="key in clientKeys" :key="key.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all"
          :class="{ 'opacity-50': key.status !== 'active' }">
          <div class="flex items-center gap-4 flex-1 min-w-0">
            <div class="w-10 h-10 rounded-md bg-ls-elevated flex items-center justify-center flex-shrink-0">
              <span class="font-semibold text-sm text-ls-accent">{{ (key.name || '').slice(0, 2).toUpperCase() }}</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="font-medium text-sm text-white truncate">{{ key.name }}</p>
                <span :class="key.status === 'active' ? 'status-badge-active' : 'status-badge-inactive'">
                  {{ key.status === 'active' ? '启用' : '禁用' }}
                </span>
              </div>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-xs font-mono text-gray-400 cursor-pointer hover:text-white transition-colors"
                  @click="showFullKey = { show: true, key: key.key_value }">
                  {{ key.key_value_masked }}
                </span>
              </div>
              <div class="flex items-center gap-3 mt-2 text-xs text-gray-500">
                <span>创建于 {{ formatTime(key.created_at) }}</span>
                <span v-if="key.description" class="text-gray-400 truncate">{{ key.description }}</span>
              </div>
              <div class="flex items-center gap-4 mt-2 text-xs">
                <span class="flex items-center gap-1">
                  <span class="text-gray-500">今日调用</span>
                  <span class="text-white font-mono">{{ key.today_requests || 0 }}</span>
                </span>
                <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
              </div>
            </div>
          </div>
          <div class="flex items-center gap-4 flex-shrink-0">
            <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
            <div class="flex items-center gap-1">
              <button @click="openDetailTab(key, 'logs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="调用日志">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
              </button>
              <button @click="openDetailTab(key, 'stats')" class="text-ls-accent hover:text-white p-1 transition-colors" title="使用统计">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V5"/><path d="M15 17v-8"/>
                </svg>
              </button>
              <button @click="openDetailTab(key, 'docs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="对接文档">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14"/>
                </svg>
              </button>
            </div>
            <span class="text-ls-border">|</span>
            <button @click="openEdit(key)" class="text-gray-500 hover:text-white transition-colors" title="编辑">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button @click="openDeleteConfirm(key)" class="text-gray-500 hover:text-red-400 transition-colors" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 2：网格卡片
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        <div v-for="key in clientKeys" :key="key.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 hover:border-gray-700 transition-all flex flex-col gap-3"
          :class="{ 'opacity-50': key.status !== 'active' }">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-10 h-10 rounded-md bg-ls-elevated flex items-center justify-center flex-shrink-0">
                <span class="font-semibold text-sm text-ls-accent">{{ (key.name || '').slice(0, 2).toUpperCase() }}</span>
              </div>
              <div class="min-w-0">
                <p class="font-medium text-sm text-white truncate">{{ key.name }}</p>
                <p class="text-[11px] text-gray-500 mt-0.5 truncate font-mono">{{ key.key_value_masked }}</p>
              </div>
            </div>
            <span :class="key.status === 'active' ? 'status-badge-active' : 'status-badge-inactive'">
              {{ key.status === 'active' ? '启用' : '禁用' }}
            </span>
          </div>

          <div class="flex items-center gap-3 text-xs text-gray-500">
            <span>创建于 {{ formatTime(key.created_at) }}</span>
            <span v-if="key.description" class="text-gray-400 truncate">{{ key.description }}</span>
          </div>

          <div class="flex items-center gap-4 text-xs">
            <span class="flex items-center gap-1">
              <span class="text-gray-500">调用</span>
              <span class="text-white font-mono">{{ key.today_requests || 0 }}</span>
            </span>
            <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-ls-border">
            <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
            <div class="flex items-center gap-1">
              <button @click="openDetailTab(key, 'logs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="调用日志">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
              </button>
              <button @click="openDetailTab(key, 'stats')" class="text-ls-accent hover:text-white p-1 transition-colors" title="使用统计">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V5"/><path d="M15 17v-8"/>
                </svg>
              </button>
              <button @click="openDetailTab(key, 'docs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="对接文档">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14"/>
                </svg>
              </button>
              <span class="text-ls-border mx-1">|</span>
              <button @click="openEdit(key)" class="text-gray-500 hover:text-white p-1 transition-colors" title="编辑">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button @click="openDeleteConfirm(key)" class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 3：表格
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'table'" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border text-xs">
              <th class="text-left px-5 py-3 font-medium">名称</th>
              <th class="text-left px-5 py-3 font-medium">状态</th>
              <th class="text-left px-5 py-3 font-medium">Key</th>
              <th class="text-left px-5 py-3 font-medium">创建时间</th>
              <th class="text-right px-5 py-3 font-medium">今日调用</th>
              <th class="text-right px-5 py-3 font-medium">Token</th>
              <th class="text-right px-5 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="key in clientKeys" :key="key.id"
              class="border-b border-ls-border/50 hover:bg-ls-elevated/30 transition-colors"
              :class="{ 'opacity-50': key.status !== 'active' }">
              <td class="px-5 py-3">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-md bg-ls-elevated flex items-center justify-center flex-shrink-0">
                    <span class="font-semibold text-xs text-ls-accent">{{ (key.name || '').slice(0, 2).toUpperCase() }}</span>
                  </div>
                  <div>
                    <p class="font-medium text-white">{{ key.name }}</p>
                    <p v-if="key.description" class="text-xs text-gray-500 max-w-[180px] truncate">{{ key.description }}</p>
                  </div>
                </div>
              </td>
              <td class="px-5 py-3">
                <CCheckbox :model-value="key.status === 'active'" @update:modelValue="(val) => toggleKey(val, key)" />
              </td>
              <td class="px-5 py-3 text-xs font-mono text-gray-400 cursor-pointer hover:text-white transition-colors"
                @click="showFullKey = { show: true, key: key.key_value }">
                {{ key.key_value_masked }}
              </td>
              <td class="px-5 py-3 text-xs text-gray-400">{{ formatTime(key.created_at) }}</td>
              <td class="px-5 py-3 text-xs text-white font-mono text-right">{{ key.today_requests || 0 }}</td>
              <td class="px-5 py-3 text-right">
                <TokenStack :input="key.today_input_tokens || 0" :output="key.today_output_tokens || 0" compact />
              </td>
              <td class="px-5 py-3">
                <div class="flex items-center justify-end gap-1">
                  <button @click="openDetailTab(key, 'logs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="调用日志">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                  </button>
                  <button @click="openDetailTab(key, 'stats')" class="text-ls-accent hover:text-white p-1 transition-colors" title="使用统计">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V5"/><path d="M15 17v-8"/>
                    </svg>
                  </button>
                  <button @click="openDetailTab(key, 'docs')" class="text-ls-accent hover:text-white p-1 transition-colors" title="对接文档">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14"/>
                    </svg>
                  </button>
                  <span class="text-ls-border mx-1">|</span>
                  <button @click="openEdit(key)" class="text-gray-500 hover:text-white p-1 transition-colors" title="编辑">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button @click="openDeleteConfirm(key)" class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="clientKeys.length === 0">
              <td colspan="7" class="px-5 py-8 text-center text-gray-500">暂无 API Key，点击上方按钮生成第一个 Key</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── 底部统计 ── -->
      <div v-if="clientKeys.length > 0" class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ clientKeys.length }} 个 Key · {{ activeCount }} 个启用
      </div>
      <div v-else class="mt-6 bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
        <p class="text-sm text-gray-500">暂无 API Key，点击上方按钮生成第一个 Key</p>
      </div>
      </div>
    </div>

    <!-- Add Key Drawer -->
    <Drawer v-model="showAddDrawer" title="生成 API Key">
      <div class="space-y-4">
        <div>
          <label class="form-label">Key 名称</label>
          <input v-model="newKey.name" type="text" placeholder="如：生产环境、测试客户端"
            class="form-input" @keyup.enter="createKey" ref="addNameInput">
        </div>
        <div>
          <label class="form-label">备注描述</label>
          <textarea v-model="newKey.description" type="text" placeholder="可选备注"
            class="form-input resize-none" rows="2" @keyup.enter="createKey"></textarea>
        </div>
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
        <div>
          <label class="form-label">Key 名称</label>
          <input v-model="editingKey.name" type="text" placeholder="Key 名称（唯一）"
            class="form-input" @keyup.enter="saveEdit">
        </div>
        <div>
          <label class="form-label">备注描述</label>
          <textarea v-model="editingKey.description" placeholder="可选备注"
            class="form-input resize-none" rows="2"></textarea>
        </div>
        <div>
          <label class="form-label">状态</label>
          <div class="flex items-center gap-3">
            <CCheckbox :model-value="editingKey.status === 'active'" @update:modelValue="(val) => editingKey.status = val ? 'active' : 'disabled'" />
            <span class="text-sm" :class="editingKey.status === 'active' ? 'text-green-400' : 'text-gray-500'">
              {{ editingKey.status === 'active' ? '启用' : '禁用' }}
            </span>
          </div>
        </div>
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
      :message="`确定要删除 Key <strong class='text-white'>${deletingKey?.name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销，使用该 Key 的客户端将无法再调用接口</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />

    <!-- Show Full Key Modal -->
    <ConfirmModal
      v-model="showFullKey.show"
      title="完整 API Key"
      :message="`<p class='text-sm text-gray-300 mb-4'>请妥善保管此 Key，创建后不再显示：</p><p class='font-mono text-white bg-ls-bg rounded-lg border border-ls-border p-3 break-all text-sm'>${showFullKey.key || ''}</p><p class='text-xs text-gray-500 mt-2'>点击下方按钮可复制</p>`"
      :confirm-text="'复制 Key'"
      @confirm="copyText(showFullKey.key)"
    />

    <!-- Detail Panel -->
    <div v-if="selectedKeyForDetail" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50" @click.self="closeDetail">
      <div class="fixed top-0 right-0 bottom-0 w-[1100px] bg-ls-bg border-l border-ls-border z-50 flex flex-col shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-3 border-b border-ls-border bg-ls-card flex-shrink-0">
          <div>
            <h2 class="text-base font-semibold text-white">{{ selectedKeyForDetail.name }}</h2>
            <p class="text-xs text-gray-500 mt-0.5 font-mono">{{ selectedKeyForDetail.key_value_masked }}</p>
          </div>
          <div class="flex items-center gap-2">
            <button @click="detailTab = 'docs'" class="text-xs text-ls-accent hover:text-ls-accentHover px-2 py-1">
              对接文档
            </button>
            <button @click="closeDetail" class="text-gray-500 hover:text-white p-1">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Tabs -->
        <div class="flex border-b border-ls-border bg-ls-card flex-shrink-0">
          <button @click="detailTab = 'logs'"
            class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
            :class="detailTab === 'logs' ? 'text-white border-ls-accent' : 'text-gray-500 hover:text-white border-transparent'">
            调用日志
          </button>
          <button @click="detailTab = 'stats'"
            class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
            :class="detailTab === 'stats' ? 'text-white border-ls-accent' : 'text-gray-500 hover:text-white border-transparent'">
            使用统计
          </button>
          <button @click="detailTab = 'docs'"
            class="px-4 py-2 text-sm font-medium transition-colors border-b-2"
            :class="detailTab === 'docs' ? 'text-white border-ls-accent' : 'text-gray-500 hover:text-white border-transparent'">
            对接文档
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto">
          <!-- Logs Tab -->
          <div v-if="detailTab === 'logs'" class="p-4">
            <div v-if="detailLoading" class="flex items-center justify-center h-48">
              <div class="text-gray-500">Loading...</div>
            </div>
            <div v-else-if="detailLogs.length === 0" class="flex items-center justify-center h-48 text-gray-500 text-sm">
              暂无调用记录
            </div>
            <div v-else class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
              <table class="w-full text-xs">
                <thead>
                  <tr class="text-gray-500 border-b border-ls-border bg-ls-bg">
                    <th class="text-left px-4 py-2.5 font-medium">时间戳</th>
                    <th class="text-left px-4 py-2.5 font-medium">请求 ID</th>
                    <th class="text-left px-4 py-2.5 font-medium">模型</th>
                    <th class="text-left px-4 py-2.5 font-medium">状态</th>
                    <th class="text-left px-4 py-2.5 font-medium">Token</th>
                    <th class="text-left px-4 py-2.5 font-medium">延迟</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in detailLogs" :key="log.id"
                    class="border-b border-ls-border/50 hover:bg-ls-elevated transition-colors">
                    <td class="px-4 py-3 text-gray-400">{{ formatTime(log.timestamp) }}</td>
                    <td class="px-4 py-3 text-gray-300 font-mono">{{ log.request_id }}</td>
                    <td class="px-4 py-3 text-white font-mono">{{ log.model }}</td>
                    <td class="px-4 py-3">
                      <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                        :class="log.status_code >= 500 ? 'bg-red-500/10 text-red-400' : log.status_code >= 400 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-green-500/10 text-green-400'">
                        {{ log.status_code }}
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <TokenStack :input="log.input_tokens || 0" :output="log.output_tokens || 0" compact />
                    </td>
                    <td class="px-4 py-3 font-mono text-gray-400">{{ log.latency_ms ? log.latency_ms + ' ms' : '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="flex items-center justify-between mt-4">
              <p class="text-xs text-gray-500">共 {{ detailTotal }} 条记录</p>
              <div class="flex items-center gap-2">
                <button @click="detailPage--" :disabled="detailPage <= 0"
                  class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">← 上页</button>
                <span class="text-xs text-gray-500">{{ detailPage + 1 }}</span>
                <button @click="detailPage++"
                  class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card">下页 →</button>
              </div>
            </div>
          </div>

          <!-- Stats Tab -->
          <div v-else-if="detailTab === 'stats'" class="p-4">
            <div v-if="statsLoading" class="flex items-center justify-center h-48">
              <div class="text-gray-500">Loading...</div>
            </div>
            <div v-else class="space-y-4">
              <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500">总请求数</p>
                  <p class="text-2xl font-bold text-white mt-1">{{ keyStats.total_requests || 0 }}</p>
                </div>
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500">成功请求</p>
                  <p class="text-2xl font-bold text-green-400 mt-1">{{ keyStats.success_count || 0 }}</p>
                </div>
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500">失败请求</p>
                  <p class="text-2xl font-bold text-red-400 mt-1">{{ keyStats.error_count || 0 }}</p>
                </div>
              </div>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500 mb-2">Token</p>
                  <TokenStack :input="keyStats.total_input_tokens || 0" :output="keyStats.total_output_tokens || 0" />
                </div>
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500">平均延迟</p>
                  <p class="text-xl font-bold text-white mt-1">{{ keyStats.avg_latency_ms || 0 }} ms</p>
                </div>
                <div class="bg-ls-card rounded-lg border border-ls-border p-4">
                  <p class="text-xs text-gray-500">成功率</p>
                  <p class="text-xl font-bold mt-1"
                    :class="keyStats.success_count / Math.max(keyStats.total_requests, 1) >= 0.9 ? 'text-green-400' : 'text-yellow-400'">
                    {{ keyStats.total_requests > 0 ? Math.round(keyStats.success_count / keyStats.total_requests * 100) : 0 }}%
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Docs Tab -->
          <div v-else-if="detailTab === 'docs'" class="p-4">
            <div v-if="docsLoading" class="flex items-center justify-center h-48">
              <div class="text-gray-500">Loading...</div>
            </div>
            <div v-else>
              <div class="flex items-center gap-2 mb-4">
                <span class="text-sm text-gray-400">API Key:</span>
                <span class="font-mono text-ls-accent text-sm">{{ selectedKeyForDetail.key_value }}</span>
                <button @click="copyText(selectedKeyForDetail.key_value)" class="text-gray-500 hover:text-white ml-auto">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
              </div>
              <MarkdownRender :source="keyDocs" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, inject, watch } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import MarkdownRender from '@/components/MarkdownRender.vue'
import ViewToggle from '@/components/ViewToggle.vue'
import TokenStack from '@/components/TokenStack.vue'
import { useViewPreference } from '@/composables/useViewPreference'
import {
  getClientKeys,
  createClientKey,
  updateClientKey,
  deleteClientKey,
  getClientKeyLogs,
 getClientKeyStats,
  getClientKeyDocs,
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
const detailTab = ref('logs')
const detailLoading = ref(false)
const detailLogs = ref([])
const detailTotal = ref(0)
const detailPage = ref(0)
const statsLoading = ref(false)
const keyStats = ref({})
const docsLoading = ref(false)
const keyDocs = ref('')

// Helpers
const formatTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts.replace(' ', 'T'))
  if (isNaN(d.getTime())) return ts
  const pad = (n, l = 2) => String(n).padStart(l, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

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
  selectedKeyForDetail.value = key
  detailTab.value = tab
  detailPage.value = 0
  loadDetailLogs()
  loadKeyStats()
  loadKeyDocs()
}

const openDetail = (key) => openDetailTab(key, 'logs')

const closeDetail = () => {
  selectedKeyForDetail.value = null
}

const loadDetailLogs = async () => {
  if (!selectedKeyForDetail.value) return
  detailLoading.value = true
  try {
    const res = await getClientKeyLogs(selectedKeyForDetail.value.id, {
      page: detailPage.value,
      page_size: 20,
    })
    detailLogs.value = res.data.records || []
    detailTotal.value = res.data.total || 0
  } catch {
    detailLogs.value = []
    detailTotal.value = 0
  }
  detailLoading.value = false
}

const loadKeyStats = async () => {
  if (!selectedKeyForDetail.value) return
  statsLoading.value = true
  try {
    const res = await getClientKeyStats(selectedKeyForDetail.value.id)
    keyStats.value = res.data || {}
  } catch {
    keyStats.value = {}
  }
  statsLoading.value = false
}

const loadKeyDocs = async () => {
  if (!selectedKeyForDetail.value) return
  docsLoading.value = true
  try {
    const res = await getClientKeyDocs(selectedKeyForDetail.value.id)
    keyDocs.value = res.data.markdown || ''
  } catch {
    keyDocs.value = ''
  }
  docsLoading.value = false
}

// Reload logs when page changes
watch(detailPage, () => loadDetailLogs())

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.status-badge-active,
.status-badge-inactive {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.status-badge-active { background: #a6e3a118; color: #a6e3a1; }
.status-badge-inactive { background: var(--surface-2); color: #6b7280; }
.status-badge-active::before,
.status-badge-inactive::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
}
.status-badge-active::before { background: #a6e3a1; }
.status-badge-inactive::before { background: #6b7280; }
</style>
