/**
 * 全局 Loading — 基于 ElLoading 的玻璃风格封装
 */
import { ElLoading } from 'element-plus'

let loadingInstance = null

export function showLoading(text = '加载中...') {
  if (loadingInstance) return
  loadingInstance = ElLoading.service({
    lock: true,
    text,
    background: 'rgba(0, 0, 0, 0.5)',
    customClass: 'glass-loading',
  })
}

export function hideLoading() {
  if (loadingInstance) {
    loadingInstance.close()
    loadingInstance = null
  }
}
