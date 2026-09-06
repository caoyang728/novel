/**
 * 格式化工具函数
 */

/**
 * 格式化日期
 * @param {string|Date} date
 * @param {string} format - 'datetime' | 'date' | 'time'
 * @returns {string}
 */
export function formatDate(date, format = 'datetime') {
  if (!date) return ''
  const d = new Date(date)
  if (isNaN(d.getTime())) return ''

  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  switch (format) {
    case 'date':
      return `${year}-${month}-${day}`
    case 'time':
      return `${hours}:${minutes}:${seconds}`
    case 'datetime':
    default:
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  }
}

/**
 * 格式化 Token 数量
 * @param {number} count
 * @returns {string}
 */
export function formatTokenCount(count) {
  if (count == null) return '0'
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`
  return String(count)
}

/**
 * HTML 转义
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
  if (!str) return ''
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return str.replace(/[&<>"']/g, (c) => map[c])
}

/**
 * 截断文本
 * @param {string} text
 * @param {number} maxLen
 * @returns {string}
 */
export function truncate(text, maxLen = 100) {
  if (!text || text.length <= maxLen) return text || ''
  return text.slice(0, maxLen) + '...'
}
