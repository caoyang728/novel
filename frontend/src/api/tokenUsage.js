/**
 * Token 用量相关 API
 */
import { api } from './request'

export const tokenUsageApi = {
  getToday: () => api.get('/api/token-usage/today/'),
  getStats: (params) => api.get('/api/token-usage/stats/', { params }),
}
