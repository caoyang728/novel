/**
 * API 请求封装 — 基于 fetch
 *
 * - 自动注入 Authorization Bearer token
 * - 统一解析 JSON，按后端 { success: false, error } 约定抛错
 * - 401 自动刷新 token 并重放请求（共享单个刷新 Promise，防并发竞态）
 * - 错误默认通过 ElMessage 提示
 */
import { ElMessage } from 'element-plus'

// 刷新 token 的共享 Promise（防并发竞态）
let refreshPromise = null

/**
 * 获取存储的 access token
 */
function getToken() {
  return localStorage.getItem('access_token') || ''
}

/**
 * 刷新 token（内部调用，共享 Promise）
 */
async function doRefreshToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('No refresh token')

  const res = await fetch('/api/auth/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: refreshToken }),
  })

  if (!res.ok) throw new Error('Refresh failed')

  const data = await res.json()
  localStorage.setItem('access_token', data.access)
  if (data.refresh) localStorage.setItem('refresh_token', data.refresh)
  return data.access
}

/**
 * 构建 query string
 */
function buildQueryString(params) {
  if (!params || typeof params !== 'object') return ''
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')
  return qs ? `?${qs}` : ''
}

/**
 * 核心请求函数
 */
async function request(url, options = {}) {
  const {
    method = 'GET',
    body,
    params,
    headers: customHeaders = {},
    showError = true,
    _isRetry = false,
  } = options

  // 拼接 query string
  const fullUrl = method === 'GET' && params ? `${url}${buildQueryString(params)}` : url

  const headers = {
    'Content-Type': 'application/json',
    ...customHeaders,
  }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const fetchOptions = {
    method,
    headers,
  }

  if (body && method !== 'GET') {
    fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body)
  }

  const res = await fetch(fullUrl, fetchOptions)

  // 401 处理：尝试刷新 token
  if (res.status === 401 && !_isRetry) {
    try {
      if (!refreshPromise) {
        refreshPromise = doRefreshToken()
      }
      const newToken = await refreshPromise
      refreshPromise = null

      // 用新 token 重放原请求
      return request(url, {
        ...options,
        headers: { ...customHeaders, Authorization: `Bearer ${newToken}` },
        _isRetry: true,
      })
    } catch (err) {
      refreshPromise = null
      // 刷新失败，清除登录态，跳转登录页
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
      throw new Error('认证已过期，请重新登录')
    }
  }

  // 解析响应
  let data
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    data = await res.json()
  } else {
    data = await res.text()
  }

  // 请求失败
  if (!res.ok) {
    const errorMsg = (data && data.error) || (data && data.detail) || `请求失败 (${res.status})`
    if (showError) {
      ElMessage.error(errorMsg)
    }
    const err = new Error(errorMsg)
    err.status = res.status
    err.data = data
    throw err
  }

  // 后端约定的业务错误
  if (data && typeof data === 'object' && data.success === false) {
    const errorMsg = data.error || data.message || '操作失败'
    if (showError) {
      ElMessage.error(errorMsg)
    }
    throw new Error(errorMsg)
  }

  return data
}

/**
 * 导出的 API 对象
 */
export const api = {
  get: (url, options = {}) => request(url, { ...options, method: 'GET' }),
  post: (url, body, options = {}) => request(url, { ...options, method: 'POST', body }),
  put: (url, body, options = {}) => request(url, { ...options, method: 'PUT', body }),
  del: (url, options = {}) => request(url, { ...options, method: 'DELETE' }),
}

export default api
