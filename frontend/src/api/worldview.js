/**
 * 世界观相关 API
 */
import { api } from './request'

/**
 * 流式端点 URL 构建器（配合 @/api/sse 的 streamRequestRaw 使用）
 */
export const worldviewUrls = {
  optimize: (pid, wid, layer) => `/api/projects/${pid}/worldviews/${wid}/optimize/${layer}/`,
  chatStream: (pid) => `/api/projects/${pid}/worldviews/chat/stream/`,
}

export const worldviewApi = {
  // 获取世界观数据（项目下唯一世界观）
  get: (projectId) => api.get(`/api/projects/${projectId}/worldviews/`),

  // 获取指定世界观
  getById: (projectId, worldviewId) => api.get(`/api/projects/${projectId}/worldviews/${worldviewId}/`),

  // 生成深化问题（后端为 POST）
  generateDeepeningQuestions: (projectId, worldviewId) =>
    api.post(`/api/projects/${projectId}/worldviews/${worldviewId}/deepening/questions/`, {}),

  // 提交深化回答
  submitDeepening: (projectId, worldviewId, data) =>
    api.post(`/api/projects/${projectId}/worldviews/${worldviewId}/deepening/submit/`, data),

  // 应用深化结果
  applyDeepening: (projectId, worldviewId, data) =>
    api.post(`/api/projects/${projectId}/worldviews/${worldviewId}/deepening/apply/`, data),

  // 一致性检查（后端为 POST）
  checkConsistency: (projectId, worldviewId) =>
    api.post(`/api/projects/${projectId}/worldviews/${worldviewId}/consistency/check/`, {}),

  // 修复一致性问题
  fixConsistency: (projectId, worldviewId, data) =>
    api.post(`/api/projects/${projectId}/worldviews/${worldviewId}/consistency/fix/`, data),

  // 获取层级
  getLayer: (projectId, worldviewId, layer) =>
    api.get(`/api/projects/${projectId}/worldviews/${worldviewId}/layer/${layer}/`),

  // 更新层级（后端为 PUT，body 为扁平字段）
  updateLayer: (projectId, worldviewId, layer, data) =>
    api.put(`/api/projects/${projectId}/worldviews/${worldviewId}/layer/${layer}/`, data),

  // 导出 Markdown
  exportMarkdown: (projectId) => api.get(`/api/projects/${projectId}/worldviews/export/markdown/`),

  // 打开聊天（返回引导问题）
  openChat: (projectId) => api.post(`/api/projects/${projectId}/worldviews/chat/open/`, {}),
}
