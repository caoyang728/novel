/**
 * 卷相关 API
 */
import { api } from './request'

export const volumeApi = {
  // 版本列表
  getVersions: (projectId) => api.get(`/api/projects/${projectId}/volume-versions/`),

  // 版本详情
  getVersion: (projectId, versionId) => api.get(`/api/projects/${projectId}/volume-versions/${versionId}/`),

  // 保存版本（覆盖当前版本的卷数据，PUT）
  updateVersion: (projectId, versionId, data) => api.put(`/api/projects/${projectId}/volume-versions/${versionId}/`, data),

  // 删除版本
  deleteVersion: (projectId, versionId) => api.del(`/api/projects/${projectId}/volume-versions/${versionId}/`),

  // 另存为新版本
  saveVersion: (projectId, versionId, data) => api.post(`/api/projects/${projectId}/volume-versions/${versionId}/save/`, data),

  // 定稿/锁定版本（切换锁定状态）
  finalizeVersion: (projectId, versionId) => api.post(`/api/projects/${projectId}/volume-versions/${versionId}/finalize/`),

  // 优化版本（流式）
  optimizeVersion: (projectId, versionId, data) => api.post(`/api/projects/${projectId}/volume-versions/${versionId}/optimize/`, data),

  // 聊天（流式）
  chat: (projectId, versionId, data) => api.post(`/api/projects/${projectId}/volume-versions/${versionId}/chat/`, data),

  // 单卷锁定/解锁（PUT）
  lockVolume: (projectId, volumeId, isLocked) =>
    api.put(`/api/projects/${projectId}/volumes/${volumeId}/lock/`, { is_locked: isLocked }),

  // 生成单卷大纲（流式）
  generateVolume: (projectId, volumeId) => api.post(`/api/projects/${projectId}/volumes/${volumeId}/generate/`, {}),

  // AI 优化单卷（流式）
  optimize: (projectId, data) => api.post(`/api/projects/${projectId}/volumes/optimize/`, data),
}
