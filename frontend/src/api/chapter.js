/**
 * 章节相关 API
 */
import { api } from './request'

/**
 * 流式端点 URL 构建器（配合 @/api/sse 的 streamRequestRaw 使用）
 */
export const chapterUrls = {
  generate: (pid) => `/api/projects/${pid}/chapters/generate/`,
  content: (pid) => `/api/projects/${pid}/chapters/content/`,
  verify: (pid) => `/api/projects/${pid}/chapters/verify/`,
  verifyFix: (pid) => `/api/projects/${pid}/chapters/verify-fix/`,
  split: (pid) => `/api/projects/${pid}/chapters/split/`,
  chat: (pid) => `/api/projects/${pid}/chapters/chat/`,
  readerReview: (pid) => `/api/projects/${pid}/chapters/reader-review/`,
  batchCheck: (pid) => `/api/projects/${pid}/chapters/batch-check/`,
  batchFix: (pid) => `/api/projects/${pid}/chapters/batch-fix/`,
  save: (pid) => `/api/projects/${pid}/chapters/save/`,
  status: (pid) => `/api/projects/${pid}/chapters/status/`,
  hardDelete: (pid) => `/api/projects/${pid}/chapters/hard-delete/`,
  reorder: (pid) => `/api/projects/${pid}/chapters/reorder/`,
  detail: (pid, cid) => `/api/projects/${pid}/chapters/${cid}/`,
  loadByVolume: (pid, vid) => `/api/projects/${pid}/chapters/volume/${vid}/load/`,
}

export const chapterApi = {
  // 生成章节
  generate: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/generate/`, data),

  // 获取/更新章节内容（后端均为 POST）
  getContent: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/content/`, data),
  updateContent: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/content/`, data),

  // 章节详情
  getDetail: (projectId, chapterId) => api.get(`/api/projects/${projectId}/chapters/${chapterId}/`),

  // 加载章节（按卷）
  loadByVolume: (projectId, volumeId) => api.get(`/api/projects/${projectId}/chapters/volume/${volumeId}/load/`),

  // 保存章节
  save: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/save/`, data),

  // 章节状态（后端为 POST）
  getStatus: (projectId) => api.post(`/api/projects/${projectId}/chapters/status/`),

  // 验证章节
  verify: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/verify/`, data),

  // 修复验证问题
  verifyFix: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/verify-fix/`, data),

  // 拆分章节
  split: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/split/`, data),

  // 重排序
  reorder: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/reorder/`, data),

  // 硬删除
  hardDelete: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/hard-delete/`, data),

  // 聊天
  chat: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/chat/`, data),

  // 读者审阅
  readerReview: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/reader-review/`, data),

  // 批量检查
  batchCheck: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/batch-check/`, data),

  // 批量修复
  batchFix: (projectId, data) => api.post(`/api/projects/${projectId}/chapters/batch-fix/`, data),
}
