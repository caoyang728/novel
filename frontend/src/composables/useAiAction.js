/**
 * AI 按钮 loading/防重入通用逻辑
 */
import { ref } from 'vue'

export function useAiAction() {
  const loading = ref(false)

  /**
   * 包装一个异步 AI 操作，自动管理 loading 状态并防止重入
   * @param {Function} action - 异步操作函数
   * @returns {Function} 包装后的函数
   */
  function wrapAction(action) {
    return async (...args) => {
      if (loading.value) return
      loading.value = true
      try {
        return await action(...args)
      } finally {
        loading.value = false
      }
    }
  }

  return {
    loading,
    wrapAction,
  }
}
