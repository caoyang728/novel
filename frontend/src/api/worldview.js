/**
 * 世界观相关 API
 */
import { api } from './request'

/**
 * 流式端点 URL 构建器（配合 @/api/sse 的 streamRequestRaw 使用）
 */
export const worldviewUrls = {
  stream: (pid) => `/api/projects/${pid}/worldviews/stream/`,
}

/**
 * 世界观题材选项
 */
export const WORLDVIEW_GENRES = [
  { value: 'xuanhuan', label: '玄幻/仙侠' },
  { value: 'wuxia', label: '武侠' },
  { value: 'fantasy', label: '西方奇幻' },
  { value: 'scifi', label: '科幻' },
  { value: 'history', label: '历史/架空' },
  { value: 'urban', label: '都市' },
  { value: 'apocalypse', label: '末世/灾变' },
  { value: 'general', label: '通用' },
]

export const worldviewApi = {
  // 获取世界观文档
  get: (projectId) => api.get(`/api/projects/${projectId}/worldviews/`),

  // 保存文档（手动编辑/切换题材）
  save: (projectId, data) => api.put(`/api/projects/${projectId}/worldviews/`, data),

  // 打开聊天（返回引导问题）
  open: (projectId) => api.post(`/api/projects/${projectId}/worldviews/open/`, {}),

  // 获取最近聊天历史
  getChatHistory: (projectId, limit = 10) => api.get(`/api/projects/${projectId}/worldviews/chat/history/?limit=${limit}`),

  // 提取阵营索引（供角色下拉框）
  extractFactions: (projectId) => api.post(`/api/projects/${projectId}/worldviews/factions/extract/`, {}),

  // 版本管理
  getList: (projectId) => api.get(`/api/projects/${projectId}/worldviews/versions/`),
  getVersion: (projectId, versionId) => api.get(`/api/projects/${projectId}/worldviews/versions/${versionId}/load/`),
  saveVersion: (projectId, data) => api.post(`/api/projects/${projectId}/worldviews/versions/save/`, data),
  updateVersion: (projectId, data) => api.post(`/api/projects/${projectId}/worldviews/versions/update/`, data),
  lock: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldviews/versions/${versionId}/lock/`),
  unlock: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldviews/versions/${versionId}/unlock/`),
  remove: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldviews/versions/${versionId}/delete/`),
}
