/**
 * 角色相关 API
 * 注意：AI 生成/润色/检测/优化均为同步接口，返回的 data 为 LLM 文本（需 extractJsonFromString 解析）
 */
import { api } from './request'

export const characterApi = {
  // 角色列表（含已删除，is_deleted 标记）
  list: (projectId) => api.get(`/api/projects/${projectId}/characters/`),

  // 创建角色
  create: (projectId, data) => api.post(`/api/projects/${projectId}/characters/`, data),

  // 角色详情
  get: (projectId, characterId) => api.get(`/api/projects/${projectId}/characters/${characterId}/`),

  // 更新角色（后端为 PUT）
  update: (projectId, characterId, data) => api.put(`/api/projects/${projectId}/characters/${characterId}/`, data),

  // 删除角色（软删除）
  remove: (projectId, characterId) => api.del(`/api/projects/${projectId}/characters/${characterId}/`),

  // 恢复已删除角色（PUT + action=restore）
  restore: (projectId, characterId) =>
    api.put(`/api/projects/${projectId}/characters/${characterId}/`, { action: 'restore' }),

  // AI 生成角色（同步，data 为 LLM 文本）
  generate: (projectId, data) => api.post(`/api/projects/${projectId}/characters/generate/`, data),

  // AI 润色角色（同步）
  polish: (projectId, data) => api.post(`/api/projects/${projectId}/characters/polish/`, data),

  // 一致性检查（同步）
  check: (projectId, data) => api.post(`/api/projects/${projectId}/characters/check/`, data || {}),

  // 优化角色（同步，data 为 JSON 数组文本）
  optimize: (projectId, data) => api.post(`/api/projects/${projectId}/characters/optimize/`, data),

  // 保存优化结果
  optimizeSave: (projectId, data) => api.post(`/api/projects/${projectId}/characters/optimize/save/`, data),

  // 关系类型配置
  getRelationshipTypes: (projectId) => api.get(`/api/projects/${projectId}/characters/relationship-types/`),

  // 从大纲生成角色候选
  generateFromOutline: (projectId, data) =>
    api.post(`/api/projects/${projectId}/characters/generate-from-outline/`, data),

  // 从卷生成角色候选
  generateFromVolume: (projectId, data) =>
    api.post(`/api/projects/${projectId}/characters/generate-from-volume/`, data),

  // 批量确认创建角色
  batchCreate: (projectId, data) =>
    api.post(`/api/projects/${projectId}/characters/batch-create/`, data),

  // 查询角色轨迹
  getTrajectories: (projectId, characterId) =>
    api.get(`/api/projects/${projectId}/characters/${characterId}/trajectories/`),

  // 更新角色轨迹
  updateTrajectory: (projectId, characterId, trajectoryId, data) =>
    api.put(`/api/projects/${projectId}/characters/${characterId}/trajectories/${trajectoryId}/`, data),

  // 删除角色轨迹
  deleteTrajectory: (projectId, characterId, trajectoryId) =>
    api.del(`/api/projects/${projectId}/characters/${characterId}/trajectories/${trajectoryId}/`),
}
