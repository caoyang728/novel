/**
 * 聊天 composable — 消息管理、SSE 收发、停止生成、选择模式
 */
import { ref, nextTick } from 'vue'
import { createSseController } from '@/api/sse'

export function useChat(options = {}) {
  const {
    onMessageComplete,
    onError,
  } = options

  // ---- State ----
  const messages = ref([])
  const isStreaming = ref(false)
  const streamingContent = ref('')
  const selectionMode = ref(false)
  const selectedMessages = ref(new Set())

  // SSE 控制器
  const sseController = createSseController()

  // ---- Methods ----

  /**
   * 添加用户消息
   */
  function addUserMessage(content) {
    messages.value.push({
      id: Date.now(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    })
  }

  /**
   * 添加 AI 消息
   */
  function addAiMessage(content) {
    messages.value.push({
      id: Date.now(),
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
    })
  }

  /**
   * 发送消息（流式）
   */
  async function sendMessage(url, body, headers = {}) {
    if (isStreaming.value) return

    // 添加用户消息
    addUserMessage(body.message || body.content || '')

    isStreaming.value = true
    streamingContent.value = ''

    // 添加空的 AI 消息占位
    const aiMsg = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(aiMsg)

    try {
      await sseController.stream(
        url,
        { method: 'POST', body, headers },
        (chunk) => {
          streamingContent.value += chunk
          aiMsg.content = streamingContent.value
        },
      )

      onMessageComplete?.(aiMsg.content)
    } catch (err) {
      if (err.message !== '请求已取消或超时') {
        onError?.(err)
      }
      // 移除空的 AI 消息
      if (!aiMsg.content) {
        messages.value = messages.value.filter((m) => m.id !== aiMsg.id)
      }
    } finally {
      isStreaming.value = false
      streamingContent.value = ''
    }
  }

  /**
   * 停止生成
   */
  function stopStreaming() {
    sseController.abort()
    isStreaming.value = false
  }

  /**
   * 滚动到底部
   */
  function scrollToBottom(containerRef) {
    nextTick(() => {
      if (containerRef?.value) {
        containerRef.value.scrollTop = containerRef.value.scrollHeight
      }
    })
  }

  /**
   * 清空消息
   */
  function clearMessages() {
    messages.value = []
    streamingContent.value = ''
  }

  /**
   * 设置消息列表（加载历史记录）
   */
  function setMessages(msgs) {
    messages.value = msgs.map((m, i) => ({
      id: Date.now() + i,
      role: m.role || (m.is_ai ? 'assistant' : 'user'),
      content: m.content || '',
      timestamp: m.created_at || new Date().toISOString(),
    }))
  }

  // ---- 选择模式 ----
  function enterSelectionMode() {
    selectionMode.value = true
    selectedMessages.value.clear()
  }

  function exitSelectionMode() {
    selectionMode.value = false
    selectedMessages.value.clear()
  }

  function toggleMessageSelect(msgId) {
    if (selectedMessages.value.has(msgId)) {
      selectedMessages.value.delete(msgId)
    } else {
      selectedMessages.value.add(msgId)
    }
  }

  function isSelected(msgId) {
    return selectedMessages.value.has(msgId)
  }

  function getSelectedContent() {
    return messages.value
      .filter((m) => selectedMessages.value.has(m.id))
      .map((m) => m.content)
      .join('\n\n')
  }

  return {
    // State
    messages,
    isStreaming,
    streamingContent,
    selectionMode,
    selectedMessages,
    // Methods
    sendMessage,
    stopStreaming,
    scrollToBottom,
    clearMessages,
    setMessages,
    addUserMessage,
    addAiMessage,
    // Selection
    enterSelectionMode,
    exitSelectionMode,
    toggleMessageSelect,
    isSelected,
    getSelectedContent,
  }
}
