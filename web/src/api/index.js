import axios from 'axios'

// API base — works both in dev (proxy) and prod (static files served by FastAPI)
const api = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Suppliers ──
export const getSuppliers = () => api.get('/suppliers')
export const getAllSuppliers = () => api.get('/suppliers')  // alias for compatibility
export const createSupplier = (data) => api.post('/suppliers', data)
export const updateSupplier = (id, data) => api.put(`/suppliers/${id}`, data)
export const deleteSupplier = (id) => api.delete(`/suppliers/${id}`)
export const toggleSupplier = (id) => api.patch(`/suppliers/${id}/status`)

// ── Supplier Models ──
export const getSupplierModels = (id) => api.get(`/suppliers/${id}/models`)
export const createSupplierModel = (id, data) => api.post(`/suppliers/${id}/models`, data)
export const deleteSupplierModel = (id, modelId) => api.delete(`/suppliers/${id}/models/${modelId}`)
export const bulkSetSupplierModels = (id, data) => api.put(`/suppliers/${id}/models/bulk`, data)

// ── Mappings ──
export const getMappings = () => api.get('/mappings')
export const bulkUpdateMappings = (mappings) => api.put('/mappings/bulk', { mappings })
export const updateMapping = (alias, data) => api.patch(`/mappings/${alias}`, data)
export const toggleMappingStatus = (alias) => api.patch(`/mappings/${alias}/status`)
export const deleteMapping = (alias) => api.delete(`/mappings/${alias}`)

// ── Mapping Models ──
export const getMappingModels = (aliasName) => api.get(`/mappings/${aliasName}/models`)
export const addMappingModel = (aliasName, data) => api.post(`/mappings/${aliasName}/models`, data)
export const reorderMappingModels = (aliasName, orderedIds) =>
  api.put(`/mappings/${aliasName}/models/reorder`, { ordered_ids: orderedIds })
export const removeMappingModel = (modelId) => api.delete(`/mappings/models/${modelId}`)

// ── Mapping usage (使用情况) ──
export const getMappingUsage = (alias, params) => api.get(`/mappings/${encodeURIComponent(alias)}/logs`, { params })

// ── Supplier Import / Export ──
export const exportSuppliers = (format = 'json') =>
  api.get('/suppliers/export', { params: { format }, responseType: 'blob' })

export const importSuppliers = (file, strategy = 'skip') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('strategy', strategy)
  return api.post('/suppliers/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── Config ──
export const getConfig = () => api.get('/config')
export const updateConfig = (config) => api.put('/config', { config })
export const getAppInfo = () => api.get('/info')

// ── Logs ──
export const getLogs = (params) => api.get('/logs', { params })
export const getLogDetail = (id) => api.get(`/logs/${id}`)

// ── Stats ──
export const getStats = (days = 30) => api.get('/stats', { params: { days } })

// ── Alerts ──
export const getAlerts = (days = 7) => api.get('/alerts', { params: { days } })

// ── Model Quotas ──
export const getModelQuotas = () => api.get('/model-quota')

// ── Client API Keys ──
export const getClientKeys = () => api.get('/client-keys')
export const createClientKey = (data) => api.post('/client-keys', data)
export const updateClientKey = (id, data) => api.put(`/client-keys/${id}`, data)
export const deleteClientKey = (id) => api.delete(`/client-keys/${id}`)
export const getClientKeyLogs = (id, params) => api.get(`/client-keys/${id}/logs`, { params })
export const getClientKeyStats = (id) => api.get(`/client-keys/${id}/stats`)
export const getClientKeyDocs = (id) => api.get(`/client-keys/${id}/docs`)
