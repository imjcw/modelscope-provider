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

// ── Provider Types ──
export const getProviderTypes = () => api.get('/provider-types')
export const createProviderType = (data) => api.post('/provider-types', data)
export const updateProviderType = (id, data) => api.put(`/provider-types/${id}`, data)
export const deleteProviderType = (id) => api.delete(`/provider-types/${id}`)

// ── Mappings ──
export const getMappings = () => api.get('/mappings')
export const bulkUpdateMappings = (mappings) => api.put('/mappings/bulk', { mappings })
export const updateMapping = (alias, data) => api.patch(`/mappings/${alias}`, data)
export const renameMapping = (oldAlias, newAlias) => api.put(`/mappings/${oldAlias}/rename`, { alias_name: newAlias })
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

// ── Config Import / Export ──
export const exportSuppliers = (format = 'json') =>
  api.get('/suppliers/export', { params: { format }, responseType: 'blob' })

export const exportConfig = (format = 'json') =>
  api.get('/config/export', { params: { format }, responseType: 'blob' })

export const importConfig = (file, strategy = 'skip') => {
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
export const getWindowStats = (seconds = 300) => api.get('/stats/window', { params: { seconds } })

// ── Alerts ──
export const getAlerts = (days = 7, extra = {}) =>
  api.get('/alerts', { params: { days, ...extra } })

// ── Model Quotas ──
export const getModelQuotas = (days = 0, keyId = null) => api.get('/model-quota', { params: { days, key_id: keyId } })

// ── Client API Keys ──
export const getClientKeys = () => api.get('/client-keys')
export const createClientKey = (data) => api.post('/client-keys', data)
export const updateClientKey = (id, data) => api.put(`/client-keys/${id}`, data)
export const deleteClientKey = (id) => api.delete(`/client-keys/${id}`)
export const getClientKeyLogs = (id, params) => api.get(`/client-keys/${id}/logs`, { params })
export const getClientKeyStats = (id, params) => api.get(`/client-keys/${id}/stats`, { params })
export const getClientKeyDocs = (id) => api.get(`/client-keys/${id}/docs`)

// ── Account API Keys (multi-key management) ──
export const listApiKeys = (supplierId) => api.get(`/suppliers/${supplierId}/api-keys`)
export const addApiKey = (supplierId, data) => api.post(`/suppliers/${supplierId}/api-keys`, data)
export const updateApiKeyStatus = (supplierId, keyId, data) =>
  api.put(`/suppliers/${supplierId}/api-keys/${keyId}/status`, data)
export const deleteApiKey = (supplierId, keyId) =>
  api.delete(`/suppliers/${supplierId}/api-keys/${keyId}`)

// ── Circuit Breaker ──
export const getCircuitBreakerStates = () => api.get('/circuit-breaker')
export const resetCircuitBreaker = (body) => api.post('/circuit-breaker/reset', body)
