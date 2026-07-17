import axios from 'axios'

// API base — works both in dev (proxy) and prod (static files served by FastAPI)
const api = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Suppliers ──
export const getSuppliers = () => api.get('/suppliers')
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
export const deleteMapping = (alias) => api.delete(`/mappings/${alias}`)

// ── Config ──
export const getConfig = () => api.get('/config')
export const updateConfig = (config) => api.put('/config', { config })

// ── Logs ──
export const getLogs = (params) => api.get('/logs', { params })
export const getLogDetail = (id) => api.get(`/logs/${id}`)

// ── Stats ──
export const getStats = (days = 30) => api.get('/stats', { params: { days } })

// ── Alerts ──
export const getAlerts = (days = 7) => api.get('/alerts', { params: { days } })
