import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // 全局加载状态
  const globalLoading = ref(false)
  const globalLoadingText = ref('')

  // 侧边栏折叠状态
  const sidebarCollapsed = ref(false)

  // 聊天面板折叠状态（项目工作区）
  const chatPanelCollapsed = ref(false)

  // 顶栏右侧操作按钮组件（由子页面设置）
  const headerActions = shallowRef(null)

  function showGlobalLoading(text = '加载中...') {
    globalLoading.value = true
    globalLoadingText.value = text
  }

  function hideGlobalLoading() {
    globalLoading.value = false
    globalLoadingText.value = ''
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleChatPanel() {
    chatPanelCollapsed.value = !chatPanelCollapsed.value
  }

  function setHeaderActions(component) {
    headerActions.value = component
  }

  function clearHeaderActions() {
    headerActions.value = null
  }

  return {
    globalLoading,
    globalLoadingText,
    sidebarCollapsed,
    chatPanelCollapsed,
    headerActions,
    showGlobalLoading,
    hideGlobalLoading,
    toggleSidebar,
    toggleChatPanel,
    setHeaderActions,
    clearHeaderActions,
  }
})
