<template>
  <div class="mapping-model-selector">
    <label class="form-label">绑定模型</label>

    <!-- Supplier selection -->
    <div class="mb-3">
      <label class="form-label">供应商</label>
      <CSelect v-model="selectedSupplier" :options="supplierOptions" placeholder="选择供应商" />
    </div>

    <!-- Model selection -->
    <div class="mb-3">
      <label class="form-label">模型</label>
      <CSelect v-model="selectedModel" :options="modelOptions" placeholder="选择模型" />
    </div>

    <!-- Add button -->
    <button @click="addModel" class="btn btn-secondary w-full">
      添加模型
    </button>

    <!-- Selected models list -->
    <div v-if="selectedModels.length > 0" class="mt-3">
      <label class="form-label">已选择的模型</label>
      <div class="tag-list">
        <div v-for="model in selectedModels" :key="model.id" class="tag-item">
          <span>{{ model.supplier_name }} {{ model.model_name }}</span>
          <button @click="removeModel(model.id)" class="tag-delete">×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getAllSuppliers, addMappingModel, removeMappingModel } from '@/api'

const props = defineProps(['modelList'])
const emit = defineEmits(['update:modelList'])

const suppliers = ref([])
const selectedSupplier = ref(null)
const selectedModel = ref(null)

const selectedModels = computed({
  get: () => props.modelList,
  set: (val) => emit('update:modelList', val)
})

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ label: s.name, value: s.id }))
)

const modelOptions = computed(() => {
  if (!selectedSupplier.value) return []
  const supplier = suppliers.value.find(s => s.id === selectedSupplier.value)
  if (!supplier?.models) return []
  return supplier.models.map(m => ({
    label: m.model_name,
    value: m.model_name
  }))
})

const loadSuppliers = async () => {
  try {
    const res = await getAllSuppliers()
    suppliers.value = res.data || []
  } catch (e) {
    console.error('Failed to load suppliers:', e)
  }
}

const addModel = async () => {
  if (!selectedSupplier.value || !selectedModel.value) {
    alert('请选择供应商和模型')
    return
  }

  // Check if already added
  const exists = selectedModels.value.some(
    m => m.supplier_id === selectedSupplier.value && m.model_name === selectedModel.value
  )
  if (exists) {
    alert('该模型已添加')
    return
  }

  // Get current alias name from first model or use placeholder
  const currentAlias = selectedModels.value.length > 0
    ? selectedModels.value[0].alias_name
    : 'current-alias'

  // Add to backend
  try {
    await addMappingModel(currentAlias, {
      supplier_id: selectedSupplier.value,
      model_name: selectedModel.value
    })
    // Add to local list
    selectedModels.value.push({
      id: Date.now(),
      supplier_id: selectedSupplier.value,
      model_name: selectedModel.value,
      alias_name: currentAlias,
      supplier_name: suppliers.value.find(s => s.id === selectedSupplier.value)?.name
    })
  } catch (e) {
    alert('添加失败: ' + (e.response?.data?.detail || e.message || ''))
  }

  selectedModel.value = null
}

const removeModel = async (modelId) => {
  try {
    await removeMappingModel(modelId)
    selectedModels.value = selectedModels.value.filter(m => m.id !== modelId)
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  }
}

onMounted(loadSuppliers)
</script>

<style scoped>
.mapping-model-selector {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.tag-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: var(--ls-bg);
  border: 1px solid var(--ls-border);
  border-radius: 6px;
  font-size: 0.875rem;
}

.tag-delete {
  background: none;
  border: none;
  color: var(--text-400);
  cursor: pointer;
  padding: 0.25rem;
  font-size: 1.25rem;
  line-height: 1;
}

.tag-delete:hover {
  color: var(--text-200);
}
</style>
