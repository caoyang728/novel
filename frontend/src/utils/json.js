/**
 * JSON 工具函数
 */

/**
 * 从字符串中提取 JSON
 * @param {string} str - 可能包含 JSON 的字符串
 * @returns {object|null}
 */
export function extractJsonFromString(str) {
  if (!str) return null

  // 尝试直接解析
  try {
    return JSON.parse(str)
  } catch {
    // ignore
  }

  // 尝试提取 ```json ... ``` 代码块
  const jsonBlockMatch = str.match(/```(?:json)?\s*\n?([\s\S]*?)\n?```/)
  if (jsonBlockMatch) {
    try {
      return JSON.parse(jsonBlockMatch[1].trim())
    } catch {
      // ignore
    }
  }

  // 尝试提取 { ... } 或 [ ... ]
  const objectMatch = str.match(/(\{[\s\S]*\})/)
  if (objectMatch) {
    try {
      return JSON.parse(objectMatch[1])
    } catch {
      // ignore
    }
  }

  const arrayMatch = str.match(/(\[[\s\S]*\])/)
  if (arrayMatch) {
    try {
      return JSON.parse(arrayMatch[1])
    } catch {
      // ignore
    }
  }

  return null
}

/**
 * 安全解析 JSON
 * @param {string} str
 * @param {*} fallback - 解析失败的默认值
 * @returns {*}
 */
export function safeJsonParse(str, fallback = null) {
  if (!str) return fallback
  try {
    return JSON.parse(str)
  } catch {
    return fallback
  }
}
