<template>
  <div class="wv-doc-view" v-loading="docLoading">
    <div class="wv-doc-workspace">
      <!-- 左：世界观文档编辑/预览 -->
      <section class="wv-doc-main glass-panel">
        <template v-if="currentVersion || content">
          <div class="wv-doc-toolbar">
            <div class="toolbar-left">
              <el-tag v-if="currentVersion" size="small" effect="dark" class="version-tag">v{{ currentVersion.version_number }}</el-tag>
              <span class="word-count">{{ content.length }} 字</span>
              <template v-if="!locked">
                <AppButton size="small" variant="warning" :disabled="isStreaming" @click="handleLock">
                  <el-icon><Lock /></el-icon> 锁定
                </AppButton>
                <AppButton size="small" variant="danger" :disabled="isStreaming" @click="handleDeleteVersion">
                  <el-icon><Delete /></el-icon> 删除
                </AppButton>
                <AppButton
                size="small"
                variant="accent"
                :loading="saving"
                :disabled="isStreaming || !content.trim()"
                @click="handleSave"
              >
                <el-icon><DocumentChecked /></el-icon> 保存
              </AppButton>
              </template>
              <template v-else>
                <AppButton size="small" variant="grey" @click="handleUnlock">
                  <el-icon><Lock /></el-icon> 解锁
                </AppButton>
              </template>
              <AppButton
                size="small"
                :loading="saving"
                :disabled="isStreaming || !content.trim()"
                @click="handleSaveAs"
              >
                <el-icon><DocumentCopy /></el-icon> 另存
              </AppButton>
            </div>
            <div class="toolbar-right">
              <el-radio-group v-model="mode" size="small" class="mode-switch">
                <el-radio-button value="edit">
                  <el-icon><EditPen /></el-icon> 编辑
                </el-radio-button>
                <el-radio-button value="preview">
                  <el-icon><View /></el-icon> 预览
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="wv-doc-body">
            <el-input
              v-if="mode === 'edit'"
              v-model="content"
              type="textarea"
              class="wv-doc-textarea"
              :disabled="locked"
              resize="none"
              placeholder="在这里编写世界观文档，或通过右侧 AI 助手描述需求自动生成..."
            />
            <div v-else class="wv-doc-preview">
              <template v-if="content.trim()">
                <MarkdownRenderer
                  :content="content"
                  :highlight-new="!locked && hasUnsavedChanges()"
                  :show-removed="!locked && hasUnsavedChanges()"
                  :baseline="baseline"
                />
              </template>
              <EmptyState v-else icon="Reading" text="暂无世界观文档" />
            </div>
          </div>
        </template>

        <EmptyState v-else icon="Reading" text="暂无世界观文档版本，在右侧 AI 助手中描述你的故事题材与设定，即可开始构建" class="wv-doc-empty" />
      </section>

      <!-- 右：AI 聊天 -->
      <ChatPanel
        class="wv-doc-chat"
        title="世界观构建助手"
        :messages="messages"
        :is-streaming="isStreaming"
        :streaming-msg-id="streamingMsgId"
        :disabled="locked"
        :locked="locked"
        :input-placeholder="locked ? '当前版本已锁定，无法发送消息' : '描述你想要的题材、风格、设定...'"
        @send="handleSend"
        @stop="stopStreaming"
        @new-chat="handleNewChat"
      >
        <template #header-actions>
          <el-select v-model="contextCount" size="small" class="context-select" title="对话携带的上下文轮数">
            <el-option label="全部上下文" value="all" />
            <el-option label="最近 5 轮" value="5" />
            <el-option label="最近 10 轮" value="10" />
            <el-option label="最近 20 轮" value="20" />
          </el-select>
        </template>
        <template #message-end>
          <div v-if="quickOptions.length && !isStreaming" class="quick-options">
            <button
              v-for="(opt, i) in quickOptions"
              :key="i"
              class="quick-option-btn"
              @click="handleSend(opt)"
            >
              {{ opt }}
            </button>
          </div>
        </template>
      </ChatPanel>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { EditPen, View, Lock, Delete, DocumentChecked, DocumentCopy } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { worldviewApi, worldviewUrls } from '@/api/worldview'
import { createSseController } from '@/api/sse'
import { useProjectId } from '@/composables/useProjectId'
import { useChat } from '@/composables/useChat'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'

const setPageHeader = inject('setPageHeader')
const pageHeaderRightRef = inject('pageHeaderRightRef')
const { projectId } = useProjectId()

const sseController = createSseController()

const {
  messages,
  isStreaming,
  stopStreaming,
  clearMessages,
} = useChat()

// ---- 版本与内容状态 ----
const docLoading = ref(false)
const saving = ref(false)
const versions = ref([])
const currentVersion = ref(null)
const content = ref('')
const baseline = ref('')
const mode = ref('preview')
// 保存时才持久化的最后一条 AI 消息
const pendingQuestion = ref('')
const pendingOptions = ref([])
const contextCount = ref('5')
const streamingMsgId = ref(null) // 当前正在流式的消息 ID
let typewriterTimer = null // 打字机效果定时器引用

const locked = computed(() => !!currentVersion.value?.is_finalized)
const hasUnsavedChanges = () => content.value !== baseline.value

/** 滚动聊天面板到底部 */
function scrollChatToBottom() {
  nextTick(() => {
    setTimeout(() => {
      const container = document.querySelector('.chat-panel-messages')
      if (container) container.scrollTop = container.scrollHeight
    }, 100)
  })
}

// ---- Diff 预览：由 MarkdownRenderer 组件内置处理 ----

// ---- 快捷选项 ----
const quickOptions = ref([])

const lastAssistantOptions = computed(() => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i]
    if (m.role === 'assistant' && m.content && Array.isArray(m.options) && m.options.length) {
      return [...m.options]
    }
  }
  return []
})

watch(lastAssistantOptions, (opts) => {
  quickOptions.value = opts
})

let msgSeq = 0
function nextMsgId() {
  msgSeq += 1
  return Date.now() + msgSeq
}

/** 根据 id 查找消息在 messages 中的索引（避免 indexOf 对象引用在 Vue 响应式代理中失效） */
function findMsgIndexById(id) {
  return messages.value.findIndex((m) => m.id === id)
}

/** 通过 id 更新消息内容并触发响应式 */
function updateMsgById(id, patch) {
  const idx = findMsgIndexById(id)
  if (idx !== -1) {
    messages.value[idx] = { ...messages.value[idx], ...patch }
  }
}

// ---- 版本加载 ----
async function loadVersions(selectId = null) {
  docLoading.value = true
  try {
    const res = await worldviewApi.getList(projectId.value)
    const data = res || {}
    versions.value = data.versions || []
    if (selectId) {
      const target = versions.value.find((v) => v.id === selectId)
      if (target) {
        await doLoadVersion(target)
        return
      }
    }
    if (versions.value.length > 0) {
      await doLoadVersion(versions.value[0])
    } else {
      // 无版本时：加载文档内容，显示虚拟 v1
      currentVersion.value = { id: null, version_number: 1, is_finalized: false }
      try {
        const docRes = await worldviewApi.get(projectId.value)
        const docData = docRes || {}
        content.value = docData.content || ''
        baseline.value = docData.content || ''
      } catch (e) { console.warn('加载文档内容失败:', e) }
    }
  } catch {
    // request.js 已统一提示
  } finally {
    docLoading.value = false
  }
}

async function doLoadVersion(version, { reloadChat = false } = {}) {
  try {
    const res = await worldviewApi.getVersion(projectId.value, version.id)
    const data = res || {}
    currentVersion.value = {
      ...version,
      version_number: data.version_number ?? version.version_number,
      is_finalized: data.is_finalized ?? version.is_finalized,
      last_question: data.last_question || '',
      last_options: data.last_options || [],
    }
    content.value = data.content || ''
    baseline.value = data.content || ''
    mode.value = 'preview'
    // 重置 pending 数据为版本中保存的值
    pendingQuestion.value = data.last_question || ''
    pendingOptions.value = data.last_options || []
    // 聊天重载由 watch(currentVersion) 统一处理，此处不再重复 clearMessages
  } catch {
    // 统一提示
  }
}

function handleSelectVersion(versionId) {
  const version = versions.value.find((v) => v.id === versionId)
  if (!version || version.id === currentVersion.value?.id) return
  if (isStreaming.value) {
    showWarning('AI 正在生成内容，请等待完成后再切换版本')
    return
  }
  if (hasUnsavedChanges()) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前文档有未保存的修改，切换版本将丢失。确定切换吗？',
      confirmText: '切换',
      onConfirm: (close) => {
        close()
        doLoadVersion(version, { reloadChat: true })
      },
      onCancel: () => {
        // 重置下拉框到当前版本（用户取消切换）
        refreshHeader()
      },
    })
    return
  }
  doLoadVersion(version, { reloadChat: true })
}

// ---- Header 右侧：版本选择下拉 ----
// 使用全局回调处理 v-html 渲染的 select 事件（v-html 无法绑定 Vue 事件）

function refreshHeader() {
  const v = currentVersion.value
  const versionOptions = versions.value
    .map((ver) => `<option value="${ver.id}" ${ver.id === v?.id ? 'selected' : ''}>v${ver.version_number}${ver.is_finalized ? ' (已定稿)' : ''}</option>`)
    .join('')
  pageHeaderRightRef.value = `
    <div style="display:flex;align-items:center;gap:8px;">
      <select id="wv-version-select" onchange="window.__wvVersionSelect(parseInt(this.value))" style="height:28px;padding:0 8px;border-radius:6px;background:#1e293b;color:#e2e8f0;border:1px solid #334155;font-size:12px;cursor:pointer;outline:none;">
        ${versionOptions || '<option value="">暂无版本</option>'}
      </select>
    </div>
  `
}

/** 刷新版本列表元数据（不重新加载版本内容，避免清空聊天） */
async function refreshVersionList(switchToId = null) {
  const res = await worldviewApi.getList(projectId.value)
  const data = res || {}
  versions.value = data.versions || []
  // 切换到指定版本（如另存后跳转到新版本）
  if (switchToId) {
    const target = versions.value.find(v => v.id === switchToId)
    if (target) {
      currentVersion.value = {
        ...target,
        last_question: pendingQuestion.value || '',
        last_options: pendingOptions.value || [],
      }
    }
  } else if (currentVersion.value?.id) {
    // 保持当前版本，同步最新状态（如 is_finalized）
    const updated = versions.value.find(v => v.id === currentVersion.value.id)
    if (updated) {
      currentVersion.value = {
        ...updated,
        last_question: currentVersion.value.last_question || '',
        last_options: currentVersion.value.last_options || [],
      }
    }
  }
  refreshHeader()
}

watch(currentVersion, (newVal, oldVal) => {
  refreshHeader()
  // 版本切换时自动重载聊天
  if (newVal && oldVal && newVal.id !== oldVal.id && !isStreaming.value) {
    clearMessages()
    if (!locked.value) loadWelcome()
  }
})

// ---- 版本操作 ----
async function handleSave() {
  if (!projectId.value) return
  if (!content.value.trim()) {
    showError('文档为空，无法保存')
    return
  }
  saving.value = true
  try {
    // 有当前版本则更新，无则创建新版本
    const saveData = {
      content: content.value,
      last_question: pendingQuestion.value,
      last_options: pendingOptions.value,
    }
    if (currentVersion.value?.id) {
      saveData.version_id = currentVersion.value.id
      await worldviewApi.updateVersion(projectId.value, saveData)
    } else {
      await worldviewApi.saveVersion(projectId.value, saveData)
    }
    showSuccess('已保存')
    baseline.value = content.value
    // 刷新版本列表，保持当前版本选中（刷新失败不影响保存结果）
    try {
      await refreshVersionList()
    } catch (e) { console.warn('刷新版本列表失败:', e) }
  } catch (err) {
    showError('保存失败')
    console.error(err)
  } finally {
    saving.value = false
  }
}

async function handleSaveAs() {
  if (!projectId.value) return
  if (!content.value.trim()) {
    showError('文档为空，无法保存')
    return
  }
  showConfirmModal({
    title: '另存为新版本',
    message: '将当前内容保存为一个新的版本？',
    confirmText: '确认另存',
    variant: 'accent',
    onConfirm: async (close) => {
      close()
      saving.value = true
      try {
        const res = await worldviewApi.saveVersion(projectId.value, {
          content: content.value,
          last_question: pendingQuestion.value,
          last_options: pendingOptions.value,
        })
        const data = res || {}
        showSuccess(`已保存为 v${data.version_number || '?'} 版本`)
        baseline.value = content.value
        // 刷新版本列表并切换到新版本（刷新失败不影响保存结果）
        try {
          await refreshVersionList(data.id)
        } catch (e) { console.warn('刷新版本列表失败:', e) }
      } catch (err) {
        showError('另存失败')
        console.error(err)
      } finally {
        saving.value = false
      }
    },
  })
}

async function handleLock() {
  if (!currentVersion.value) return
  showConfirmModal({
    title: '锁定版本',
    message: `确定锁定 v${currentVersion.value.version_number} 版本吗？锁定后将无法修改文档内容和发送聊天消息。`,
    confirmText: '确认锁定',
    variant: 'accent',
    onConfirm: async (close) => {
      close()
      try {
        await worldviewApi.lock(projectId.value, currentVersion.value.id)
        showSuccess('版本已锁定')
        clearMessages()
        await loadVersions(currentVersion.value.id)
      } catch {
        showError('锁定失败')
      }
    },
  })
}

async function handleUnlock() {
  if (!currentVersion.value) return
  showConfirmModal({
    title: '解锁版本',
    message: `确定解锁 v${currentVersion.value.version_number} 版本吗？解锁后可编辑文档内容和发送聊天消息。`,
    confirmText: '确认解锁',
    variant: 'accent',
    onConfirm: async (close) => {
      close()
      try {
        await worldviewApi.unlock(projectId.value, currentVersion.value.id)
        showSuccess('版本已解锁')
        await loadVersions(currentVersion.value.id)
        clearMessages()
        loadWelcome()
      } catch {
        showError('解锁失败')
      }
    },
  })
}

async function handleDeleteVersion() {
  if (!currentVersion.value) return
  if (currentVersion.value.is_finalized) {
    showWarning('已定稿版本不能删除，请先解锁')
    return
  }
  const deletedVersionId = currentVersion.value.id
  showConfirmModal({
    title: '删除版本',
    message: `确定删除 v${currentVersion.value.version_number} 版本吗？此操作不可恢复。`,
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
    onConfirm: async (close) => {
      close()
      try {
        await worldviewApi.remove(projectId.value, deletedVersionId)
        showSuccess('版本已删除')
        // 重新加载版本列表并切换到最新版本
        await loadVersions()
        // loadVersions 会加载 versions[0]（最新版本），确保聊天也重新加载
        if (currentVersion.value && !locked.value) {
          clearMessages()
          loadWelcome()
        }
      } catch {
        showError('删除失败')
      }
    },
  })
}

// ---- 开场引导 ----
const defaultWelcomeText = '你好！我是你的世界观构建助手，可以一步步帮你搭建完整的世界观。\n\n告诉我你想从哪里开始吧——可以描述一个设定构想、补充某个板块的细节，或者直接说说你还想完善哪些部分。'

async function loadWelcome() {
  if (!projectId.value) return
  const placeholderId = nextMsgId()

  try {
    // 优先从版本数据读取最后一条 AI 问题（随版本保存，无需额外 API 调用）
    const lastQ = currentVersion.value?.last_question
    const lastOpts = currentVersion.value?.last_options || []
    if (lastQ) {
      messages.value.push({
        id: placeholderId,
        role: 'assistant',
        content: lastQ,
        thinking: '',
        options: lastOpts,
        timestamp: new Date().toISOString(),
      })
      return
    }

    // 无历史：直接显示通用欢迎语，无需等待 API
    // 先添加占位消息，typewriterReveal 通过 updateMsgById 更新此消息
    messages.value.push({
      id: placeholderId,
      role: 'assistant',
      content: '',
      thinking: '',
      options: [],
      timestamp: new Date().toISOString(),
    })
    await typewriterReveal(placeholderId, defaultWelcomeText, [])
  } catch (err) {
    console.error('加载引导问题失败:', err)
    // 兜底：显示默认欢迎消息
    const existing = messages.value.find(m => m.id === placeholderId)
    if (existing && !existing.content) {
      await typewriterReveal(placeholderId, defaultWelcomeText, [])
    }
  }
}

/** 打字机效果：先在思考区逐步显示文本，完成后切换到正文区 */
function typewriterReveal(msgId, text, options) {
  return new Promise((resolve) => {
    // 清除上一次可能残留的打字机定时器
    if (typewriterTimer) clearInterval(typewriterTimer)
    // 将思考区清空，开始打字机
    updateMsgById(msgId, { thinking: '', content: '', options: [] })
    let idx = 0
    const chunkSize = 3 // 每次显示3个字符
    const interval = 16 // 每16ms更新一次（约60fps）
    typewriterTimer = setInterval(() => {
      idx += chunkSize
      const partial = text.slice(0, idx)
      updateMsgById(msgId, { thinking: partial })
      if (idx >= text.length) {
        clearInterval(typewriterTimer)
        typewriterTimer = null
        // 打字完成，切换到正文显示
        updateMsgById(msgId, {
          content: text,
          thinking: '',
          options: options,
          timestamp: new Date().toISOString(),
        })
        resolve()
      }
    }, interval)
  })
}

// ---- 新对话 ----
async function handleNewChat() {
  if (isStreaming.value) {
    showWarning('AI 正在生成内容，请等待完成')
    return
  }
  if (hasUnsavedChanges()) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前文档有未保存的修改，开始新对话将丢失。确定继续吗？',
      confirmText: '继续',
      onConfirm: (close) => {
        close()
        content.value = baseline.value
        pendingQuestion.value = ''
        pendingOptions.value = []
        clearMessages()
        loadWelcome()
      },
    })
    return
  }
  pendingQuestion.value = ''
  pendingOptions.value = []
  clearMessages()
  loadWelcome()
}

// ---- 发送消息 ----
async function handleSend(rawText) {
  if (isStreaming.value) return
  if (locked.value) {
    showWarning('当前版本已锁定，无法发送消息')
    return
  }
  const text = (rawText || '').trim()
  if (!text) return

  const contextAll = messages.value.filter((m) => m.content)
  const contextSliced = contextCount.value === 'all'
    ? contextAll
    : contextAll.slice(-parseInt(contextCount.value, 10) * 2)
  const context = contextSliced.map((m) => ({ role: m.role, content: m.content }))

  // 添加用户消息
  messages.value.push({
    id: nextMsgId(),
    role: 'user',
    content: text,
    timestamp: new Date().toISOString(),
  })

  const msgId = nextMsgId()
  messages.value.push({
    id: msgId,
    role: 'assistant',
    content: '',
    thinking: '正在思考中…',
    options: [],
    timestamp: new Date().toISOString(),
  })

  const oldBaseline = content.value
  isStreaming.value = true
  streamingMsgId.value = msgId
  let streamReply = ''
  let streamDoc = ''
  let completed = false

  try {
    await sseController.stream(
      worldviewUrls.stream(projectId.value),
      {
        body: { message: text, messages: context, current_content: content.value },
        onEvent: (evt) => {
          if (evt.type === 'status' && evt.message) {
            // 后端重试/修复进度提示
            updateMsgById(msgId, { thinking: evt.message })
          } else if (evt.type === 'reply_chunk' && evt.chunk) {
            streamReply += evt.chunk
            updateMsgById(msgId, { thinking: streamReply })
          } else if (evt.type === 'doc_chunk' && evt.chunk) {
            streamDoc += evt.chunk
            content.value = streamDoc
          } else if (evt.type === 'complete') {
            completed = true
            if (evt.content) content.value = evt.content
            const reply = evt.reply || '世界观文档已更新，请查看左侧预览区'
            const opts = Array.isArray(evt.options) ? [...evt.options] : []
            updateMsgById(msgId, {
              content: reply,
              thinking: '',
              options: opts,
              timestamp: new Date().toISOString(),
            })
            // 记录最后一条 AI 消息，保存/另存时才持久化到版本
            pendingQuestion.value = reply
            pendingOptions.value = opts
            scrollChatToBottom()
          } else if (evt.type === 'error') {
            updateMsgById(msgId, { content: `抱歉，生成失败：${evt.message || '请重试'}`, thinking: '' })
          }
        },
      },
      () => {},
    )

    if (!completed) {
      updateMsgById(msgId, { content: streamReply || '世界观文档已更新，请查看左侧预览区', thinking: '' })
      scrollChatToBottom()
    }

    // 注意：不在这里同步 baseline，让 diff 持续显示修改内容
    // baseline 仅在用户手动保存/另存时同步（见 handleSave）
    // 只刷新版本列表，不加载版本内容（避免清空聊天）
    try {
      await refreshVersionList()
    } catch (e) { console.warn('刷新版本列表失败:', e) }
  } catch (err) {
    if (err.message === '请求已取消或超时') {
      updateMsgById(msgId, { content: '已停止生成，文档已保存的内容可在左侧预览查看' })
    } else {
      console.error('世界观文档聊天流式失败:', err)
      updateMsgById(msgId, { content: `抱歉，生成失败：${err.message || '请重试'}` })
      showError(err.message || '生成失败，请重试')
    }
    content.value = oldBaseline
  } finally {
    isStreaming.value = false
    streamingMsgId.value = null
  }
}

// ---- 生命周期 ----
function handleBeforeUnload(e) {
  if (hasUnsavedChanges()) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(async () => {
  if (setPageHeader) setPageHeader('世界观构建', '与 AI 对话增量构建世界观文档')
  // 注册全局回调处理 v-html 渲染的 select 的 onchange 事件
  window.__wvVersionSelect = handleSelectVersion
  refreshHeader()
  await loadVersions()
  loadWelcome()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeRouteLeave((to, from, next) => {
  if (hasUnsavedChanges()) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前文档有未保存的修改，离开页面将丢失。确定离开吗？',
      confirmText: '离开',
      onConfirm: (close) => {
        close()
        next()
      },
      onCancel: () => {
        next(false)
      },
    })
  } else {
    next()
  }
})

onBeforeUnmount(() => {
  // 清除打字机效果定时器
  if (typewriterTimer) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
  // 清理全局回调
  delete window.__wvVersionSelect
  sseController.abort()
  window.removeEventListener('beforeunload', handleBeforeUnload)
  pageHeaderRightRef.value = ''
})
</script>

<style lang="scss">
/* 覆盖父级布局，锁定为视口高度 */
.project-layout:has(.wv-doc-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.wv-doc-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.wv-doc-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.wv-doc-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.wv-doc-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// ---- 左侧文档区 ----
.wv-doc-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wv-doc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-tag {
  font-family: monospace;
  font-weight: 600;
}

.word-count {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.mode-switch {
  --el-radio-button-checked-bg: #6366f1;
  --el-radio-button-checked-border-color: #6366f1;
}

.wv-doc-body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.wv-doc-textarea {
  height: 100%;

  :deep(.el-textarea__inner) {
    height: 100% !important;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
    color: var(--text-primary);
    font-size: 14px;
    line-height: 1.7;
    padding: 16px 20px;
  }
}

.wv-doc-preview {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.wv-doc-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

// ---- 右侧聊天区 ----
.wv-doc-chat {
  width: 460px;
  flex-shrink: 0;
}

.context-select {
  width: 120px;
}

// ---- 快捷选项 ----
.quick-options {
  padding: 8px 12px;
  border-top: 1px solid var(--glass-border);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.quick-option-btn {
  padding: 6px 12px;
  font-size: 12px;
  color: #8b9cf7;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.4);
    transform: translateY(-1px);
  }
}

// ---- 用户消息样式覆盖 ----
:deep(.wv-doc-chat) {
  .chat-message--user {
    .chat-message-avatar {
      margin-left: 0;
      margin-right: 0;
    }

    .chat-message-content {
      align-items: flex-end;
    }
  }
}

@media (max-width: 1200px) {
  .wv-doc-workspace {
    flex-direction: column;
  }
  .wv-doc-chat {
    width: 100%;
    max-height: 480px;
  }
}
</style>
