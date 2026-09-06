/**
 * 随手记相关 API
 */
import { api } from './request'

export const noteApi = {
  // 笔记列表
  list: (projectId) => api.get(`/api/projects/${projectId}/notes/`),

  // 笔记详情
  get: (projectId, noteId) => api.get(`/api/projects/${projectId}/notes/${noteId}/`),

  // 创建笔记
  create: (projectId, data) => api.post(`/api/projects/${projectId}/notes/`, data),

  // 更新笔记（后端为 PUT）
  update: (projectId, noteId, data) => api.put(`/api/projects/${projectId}/notes/${noteId}/`, data),

  // 删除笔记（后端为 DELETE）
  delete: (projectId, noteId) => api.del(`/api/projects/${projectId}/notes/${noteId}/`),

  // AI 润色
  polish: (projectId, data) => api.post(`/api/projects/${projectId}/notes/polish/`, data),
}
