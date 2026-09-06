/**
 * 时间线相关 API
 *
 * 说明：generate / generate-fields / optimize-single / check / check-optimize
 * 均为 SSE 流式端点，视图中通过 streamRequestRaw/streamRequest 配合 timelineUrls 调用。
 */
import { api } from './request'

/** 流式端点 URL 构建器 */
export const timelineUrls = {
  generate: (projectId) => `/api/projects/${projectId}/timeline/generate/`,
  chatGenerate: (projectId) => `/api/projects/${projectId}/timeline/chat-generate/`,
  optimizeSingle: (projectId) => `/api/projects/${projectId}/timeline/optimize-single/`,
  generateFields: (projectId) => `/api/projects/${projectId}/timeline/generate-fields/`,
  check: (projectId) => `/api/projects/${projectId}/timeline/check/`,
  checkOptimize: (projectId) => `/api/projects/${projectId}/timeline/check/optimize/`,
}

export const timelineApi = {
  // 事件列表
  getEvents: (projectId) => api.get(`/api/projects/${projectId}/timeline/events/`),

  // 事件详情
  getEvent: (projectId, eventId) => api.get(`/api/projects/${projectId}/timeline/events/${eventId}/`),

  // 新增事件
  createEvent: (projectId, data) => api.post(`/api/projects/${projectId}/timeline/events/`, data),

  // 更新事件（后端为 PUT）
  updateEvent: (projectId, eventId, data) => api.put(`/api/projects/${projectId}/timeline/events/${eventId}/`, data),

  // 删除事件（后端为 DELETE）
  deleteEvent: (projectId, eventId) => api.del(`/api/projects/${projectId}/timeline/events/${eventId}/`),

  // 合并事件（普通 POST JSON）
  merge: (projectId, data) => api.post(`/api/projects/${projectId}/timeline/merge/`, data),

  // 拆分事件（普通 POST JSON）
  split: (projectId, data) => api.post(`/api/projects/${projectId}/timeline/split/`, data),
}
