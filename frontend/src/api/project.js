/**
 * 项目相关 API
 */
import { api } from './request'

export const projectApi = {
  list: () => api.get('/api/projects/'),
  get: (id) => api.get(`/api/projects/${id}/`),
  create: (data) => api.post('/api/projects/create/', data),
  update: (id, data) => api.put(`/api/projects/${id}/`, data),
  delete: (id) => api.del(`/api/projects/${id}/`),
  suggestTitle: (id) => api.post(`/api/projects/${id}/title/suggest/`),
  suggestDescription: (id) => api.post(`/api/projects/${id}/description/suggest/`),
  optimizeDescription: (id, data) => api.post(`/api/projects/${id}/description-optimization/`, data),
  getStats: (id) => api.get(`/api/projects/${id}/stats/`),
}
