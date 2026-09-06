/**
 * 图谱相关 API
 */
import { api } from './request'

export const graphApi = {
  // 获取图谱数据
  getData: (projectId) => api.get(`/api/projects/${projectId}/graph/`),

  // 获取子图
  getSubgraph: (projectId, params) => api.get(`/api/projects/${projectId}/graph/subgraph/`, { params }),

  // 重建图谱
  rebuild: (projectId) => api.post(`/api/projects/${projectId}/graph/rebuild/`),

  // 图谱统计
  getStats: (projectId) => api.get(`/api/projects/${projectId}/graph/stats/`),
}
