/**
 * Toast 通知 — 基于 ElMessage 的玻璃风格封装
 */
import { ElMessage } from 'element-plus'

export function showToast(message, type = 'info', duration = 3000) {
  ElMessage({
    message,
    type,
    duration,
    showClose: true,
    grouping: true,
  })
}

export function showSuccess(message, duration = 3000) {
  showToast(message, 'success', duration)
}

export function showError(message, duration = 4000) {
  showToast(message, 'error', duration)
}

export function showWarning(message, duration = 3500) {
  showToast(message, 'warning', duration)
}

export function showInfo(message, duration = 3000) {
  showToast(message, 'info', duration)
}
