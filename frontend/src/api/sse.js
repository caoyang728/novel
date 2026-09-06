/**
 * SSE 流式请求封装
 *
 * 后端所有流式端点均为 SSE 帧格式：
 *   data: {"type": "task_id", "data": "..."}\n\n
 *   data: {"type": "chunk", "data"|"chunk"|"content": "文本"}\n\n
 *   data: {"type": "complete", ...}\n\n
 *   data: {"type": "error", "message": "..."}\n\n
 *
 * - streamRequest: 聚合返回完整文本
 * - streamRequestRaw: 实时回调，onChunk 收到纯文本增量；
 *   options 可传 onEvent(完整事件对象) / onComplete(complete 事件) / onTaskId(taskId)
 * - 支持 AbortController 中断
 * - 401 自动刷新 token 重放
 * - 超时检测与中断
 */

// 刷新 token 的共享 Promise
let refreshPromise = null

function getToken() {
  return localStorage.getItem('access_token') || ''
}

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
 * 创建 SSE 帧解析器
 * @param {object} handlers - { onChunk(text), onEvent(evt), onComplete(evt), onTaskId(id), onError(message) }
 */
function createSseParser(handlers = {}) {
  const { onChunk, onEvent, onComplete, onTaskId, onError } = handlers
  let buffer = ''
  let fullText = ''

  function processFrame(frame) {
    const data = frame.replace(/^data:\s?/, '').trim()
    if (!data || data === '[DONE]') {
      if (data === '[DONE]') onComplete?.({ type: 'done' })
      return
    }
    let parsed
    try {
      parsed = JSON.parse(data)
    } catch {
      // 非 JSON 帧，按纯文本处理
      return
    }

    onEvent?.(parsed)

    switch (parsed.type) {
      case 'chunk':
      case 'thinking_chunk': {
        // 不同端点字段名不同：content / data / chunk
        const text = parsed.content ?? parsed.data ?? parsed.chunk ?? ''
        if (text) {
          if (parsed.type !== 'thinking_chunk') fullText += text
          onChunk?.(text, parsed.type)
        }
        break
      }
      case 'complete':
        onComplete?.(parsed)
        break
      case 'task_id':
        onTaskId?.(parsed.data)
        break
      case 'error':
        onError?.(parsed.message || '生成失败')
        throw new Error(parsed.message || '生成失败')
      default:
        break
    }
  }

  function feed(text) {
    buffer += text
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.trim().startsWith('data:')) processFrame(line)
    }
  }

  function flush() {
    // 处理流结束时残留在 buffer 中的最后一帧
    if (buffer.trim().startsWith('data:')) processFrame(buffer)
    buffer = ''
  }

  return { feed, flush, getFullText: () => fullText }
}

/**
 * 内部：发起流式请求并逐帧读取
 */
async function doStream(url, options = {}, parser) {
  const { method = 'POST', body, headers: customHeaders = {}, signal, timeout = 600000, _isRetry = false } = options

  const headers = {
    'Content-Type': 'application/json',
    ...customHeaders,
  }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // 超时控制
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  // 合并外部 signal
  if (signal) {
    signal.addEventListener('abort', () => controller.abort())
  }

  try {
    const res = await fetch(url, {
      method,
      headers,
      body: body ? (typeof body === 'string' ? body : JSON.stringify(body)) : undefined,
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    // 401 处理（仅重试一次）
    if (res.status === 401 && !_isRetry) {
      try {
        if (!refreshPromise) {
          refreshPromise = doRefreshToken()
        }
        const newToken = await refreshPromise
        refreshPromise = null
        return doStream(
          url,
          { ...options, headers: { ...customHeaders, Authorization: `Bearer ${newToken}` }, _isRetry: true },
          parser,
        )
      } catch (err) {
        refreshPromise = null
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        throw new Error('认证已过期，请重新登录')
      }
    }

    if (!res.ok) {
      const text = await res.text()
      let msg = text
      try {
        const j = JSON.parse(text)
        msg = j.message || j.error || msg
      } catch {
        // 非 JSON 错误体
      }
      throw new Error(msg || `请求失败 (${res.status})`)
    }

    // 读取 SSE 流
    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parser.feed(decoder.decode(value, { stream: true }))
    }
    parser.flush()

    return parser.getFullText()
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      throw new Error('请求已取消或超时')
    }
    throw err
  }
}

/**
 * 流式请求 — 聚合返回完整文本
 * @param {string} url
 * @param {object} options - { method, body, headers, signal, timeout, onEvent, onComplete, onTaskId }
 * @returns {Promise<string>} 完整的 chunk 文本
 */
export function streamRequest(url, options = {}) {
  const { onChunk, onEvent, onComplete, onTaskId } = options
  const parser = createSseParser({ onChunk, onEvent, onComplete, onTaskId })
  return doStream(url, options, parser)
}

/**
 * 流式请求 — 实时逐块回调
 * @param {string} url
 * @param {object} options - { method, body, headers, signal, timeout, onEvent, onComplete, onTaskId }
 * @param {function} [onChunk] - 每收到 chunk 文本时回调 (text: string) => void
 * @returns {Promise<string>} 完整的 chunk 文本
 */
export function streamRequestRaw(url, options = {}, onChunk) {
  const { onEvent, onComplete, onTaskId } = options
  const parser = createSseParser({ onChunk, onEvent, onComplete, onTaskId })
  return doStream(url, options, parser)
}

/**
 * 创建可复用的 SSE 请求控制器
 * @returns {{ stream: Function, abort: Function }}
 */
export function createSseController() {
  let abortController = null

  function stream(url, options = {}, onChunk) {
    abort()
    abortController = new AbortController()
    return streamRequestRaw(url, { ...options, signal: abortController.signal }, onChunk)
  }

  function abort() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  return { stream, abort }
}
