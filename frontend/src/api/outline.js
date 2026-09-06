/**
 * 大纲相关 API
 */
import { api } from './request'

export const outlineApi = {
  // 版本列表
  getVersions: (projectId) => api.get(`/api/projects/${projectId}/outline/versions/`),

  // 版本详情
  getVersion: (projectId, versionId) => api.get(`/api/projects/${projectId}/outline/versions/${versionId}/`),

  // 加载版本
  loadVersion: (projectId, versionId) => api.get(`/api/projects/${projectId}/outline/versions/${versionId}/load/`),

  // 保存版本
  saveVersion: (projectId, data) => api.post(`/api/projects/${projectId}/outline/versions/save/`, data),

  // 定稿版本
  finalizeVersion: (projectId, versionId) => api.post(`/api/projects/${projectId}/outline/versions/finalize/`, { version_id: versionId }),

  // 最新大纲
  getLatest: (projectId) => api.get(`/api/projects/${projectId}/outline/latest/`),

  // 定稿大纲
  finalize: (projectId, versionId) => api.post(`/api/projects/${projectId}/outline/finalize/`, { version_id: versionId }),

  // 删除大纲
  deleteOutline: (projectId, versionId) => api.post(`/api/projects/${projectId}/outline/delete/`, { version_id: versionId }),

  // 锁定大纲
  lock: (projectId, versionId) => api.post(`/api/projects/${projectId}/outline/lock/`, { version_id: versionId }),

  // 解锁大纲
  unlock: (projectId, versionId) => api.post(`/api/projects/${projectId}/outline/unlock/`, { version_id: versionId }),

  // 聊天
  chat: (projectId, data) => api.post(`/api/projects/${projectId}/outline/chat/`, data),

  // 删除聊天历史
  deleteChatHistory: (projectId) => api.post(`/api/projects/${projectId}/outline/chat-history/delete/`),
}
