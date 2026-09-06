/**
 * LLM 配置相关 API
 */
import { api } from './request'

export const llmConfigApi = {
  // 获取所有配置（含场景、Provider 选项）
  getAll: () => api.get('/api/llm-config/'),

  // 创建配置
  create: (data) => api.post('/api/llm-config/', { ...data, action: 'create' }),

  // 更新配置
  update: (data) => api.post('/api/llm-config/', { ...data, action: 'update' }),

  // 删除配置
  delete: (configId) => api.post('/api/llm-config/', { action: 'delete', config_id: configId }),

  // 启用/停用配置
  toggleActive: (configId, isActive) =>
    api.post('/api/llm-config/', { action: 'toggle_active', config_id: configId, is_active: isActive }),

  // 测试已保存配置的连通性
  test: (configId) => api.post('/api/llm-config/', { action: 'test_connection', config_id: configId }),

  // 用弹窗中填写的参数直接测试（未保存）
  testParams: (data) => api.post('/api/llm-config/', { action: 'test_connection_params', ...data }),

  // 设置任务配置
  setTask: (data) => api.post('/api/llm-config/', { ...data, action: 'set_task' }),

  // 设为默认
  setDefault: (configId) => api.post('/api/llm-config/', { action: 'set_default', config_id: configId }),
}

export const embeddingConfigApi = {
  // 获取 Embedding/Rerank 配置
  get: () => api.get('/api/embedding-config/'),

  // 保存 Embedding/Rerank 配置
  save: (data) => api.post('/api/embedding-config/', { ...data, action: 'save' }),

  // 测试连接
  test: (data) => api.post('/api/embedding-config/', { ...data, action: 'test' }),
}
