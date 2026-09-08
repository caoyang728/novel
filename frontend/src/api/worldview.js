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
  // 世界观文档（Markdown 新版）
  docChatStream: (pid) => `/api/projects/${pid}/worldview-doc/chat/stream/`,
}

/**
 * 世界观文档（Markdown 新版）题材选项
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

export const worldviewDocApi = {
  // 获取世界观文档
  get: (projectId) => api.get(`/api/projects/${projectId}/worldview-doc/`),

  // 保存文档（手动编辑/切换题材）
  save: (projectId, data) => api.put(`/api/projects/${projectId}/worldview-doc/`, data),

  // 打开聊天（返回引导问题）
  openChat: (projectId) => api.post(`/api/projects/${projectId}/worldview-doc/chat/open/`, {}),

  // 获取最近聊天历史
  getChatHistory: (projectId, limit = 10) => api.get(`/api/projects/${projectId}/worldview-doc/chat/history/?limit=${limit}`),

  // 提取阵营索引（供角色下拉框）
  extractFactions: (projectId) => api.post(`/api/projects/${projectId}/worldview-doc/factions/extract/`, {}),

  // 版本管理
  getVersions: (projectId) => api.get(`/api/projects/${projectId}/worldview-doc/versions/`),
  loadVersion: (projectId, versionId) => api.get(`/api/projects/${projectId}/worldview-doc/versions/${versionId}/load/`),
  saveVersion: (projectId, data) => api.post(`/api/projects/${projectId}/worldview-doc/versions/save/`, data),
  updateVersion: (projectId, data) => api.post(`/api/projects/${projectId}/worldview-doc/versions/update/`, data),
  lockVersion: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldview-doc/versions/${versionId}/lock/`),
  unlockVersion: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldview-doc/versions/${versionId}/unlock/`),
  deleteVersion: (projectId, versionId) => api.post(`/api/projects/${projectId}/worldview-doc/versions/${versionId}/delete/`),
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
