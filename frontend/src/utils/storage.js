/**
 * localStorage 数据迁移工具（pendingData 兼容）
 *
 * SPA 中优先使用 Pinia / 路由 state 传递数据，
 * 此模块保留用于异常兜底和旧版兼容。
 */

const PENDING_DATA_PREFIX = 'pendingData_'

/**
 * 保存待恢复数据
 * @param {string} key - 数据键
 * @param {*} data - 数据内容
 */
export function savePendingData(key, data) {
  try {
    localStorage.setItem(PENDING_DATA_PREFIX + key, JSON.stringify(data))
  } catch (err) {
    console.error('Failed to save pending data:', err)
  }
}

/**
 * 恢复待恢复数据
 * @param {string} key - 数据键
 * @param {boolean} clear - 读取后是否清除
 * @returns {*}
 */
export function restorePendingData(key, clear = true) {
  try {
    const raw = localStorage.getItem(PENDING_DATA_PREFIX + key)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (clear) localStorage.removeItem(PENDING_DATA_PREFIX + key)
    return data
  } catch (err) {
    console.error('Failed to restore pending data:', err)
    return null
  }
}

/**
 * 清除待恢复数据
 * @param {string} key
 */
export function clearPendingData(key) {
  localStorage.removeItem(PENDING_DATA_PREFIX + key)
}
