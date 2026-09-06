<template>
  <div class="outline-view" v-loading="loading">
    <div class="outline-workspace">
      <!-- 左：大纲编辑/预览 -->
      <section class="outline-main glass-panel">
        <template v-if="currentVersion">
          <div class="outline-toolbar">
            <div class="toolbar-left">
              <el-tag size="small" effect="dark" class="version-tag">v{{ currentVersion.version_number }}</el-tag>
              <span class="word-count">{{ content.length }} 字</span>
              <template v-if="!locked">
                <AppButton size="small" variant="warning" :disabled="isStreaming" @click="handleLockCurrent">
                  <el-icon><Lock /></el-icon> 锁定
                </AppButton>
                <AppButton size="small" variant="danger" :disabled="isStreaming" @click="handleDeleteVersion(currentVersion)">
                  <el-icon><Delete /></el-icon> 删除
                </AppButton>
                <AppButton
                  size="small"
                  variant="accent"
                  :loading="saving"
                  :disabled="isStreaming || !content.trim()"
                  @click="handleSave(false)"
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
                @click="handleSave(true)"
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

          <div class="outline-body">
            <el-input
              v-if="mode === 'edit'"
              v-model="content"
              type="textarea"
              class="outline-textarea"
              :disabled="locked"
              resize="none"
              placeholder="在这里编写大纲，或通过右侧 AI 助手描述需求自动生成..."
            />
            <div v-else class="outline-preview">
              <MarkdownRenderer v-if="content.trim()" :content="content" :highlight-new="true" :baseline="lastAiBaseline" />
              <EmptyState v-else icon="Document" text="暂无大纲内容" />
            </div>
          </div>
        </template>

        <EmptyState v-else icon="Document" text="暂无大纲版本，在右侧 AI 助手中描述你的故事，即可开始生成" class="outline-empty" />
      </section>

      <!-- 右：AI 聊天 -->
      <transition name="chat-slide">
        <ChatPanel
          v-if="chatVisible"
          class="outline-chat"
          title="大纲助手"
          :messages="messages"
          :is-streaming="isStreaming"
          :selection-mode="selectionMode"
          :selected-count="selectedMessages.size"
          :is-selected="isSelected"
          input-placeholder="描述你想要的大纲，或提出修改意见..."
          @send="handleSend"
          @stop="stopStreaming"
          @clear="clearMessages"
          @toggle-selection="enterSelectionMode"
          @exit-selection="exitSelectionMode"
          @toggle-select="toggleMessageSelect"
          @copy-selected="handleCopySelected"
        >
          <template #header-actions>
            <el-select v-model="contextCount" size="small" class="context-select" title="对话携带的上下文轮数">
              <el-option label="全部上下文" value="all" />
              <el-option label="最近 5 轮" value="5" />
              <el-option label="最近 10 轮" value="10" />
              <el-option label="最近 20 轮" value="20" />
            </el-select>
          </template>
        </ChatPanel>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount, watch } from 'vue'
import { EditPen, View, Lock, Delete, DocumentChecked, DocumentCopy } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { outlineApi } from '@/api/outline'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { useChat } from '@/composables/useChat'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'

const setPageHeader = inject('setPageHeader')
const pageHeaderRightRef = inject('pageHeaderRightRef')

const { projectId } = useProjectId()

const {
  messages,
  isStreaming,
  selectionMode,
  selectedMessages,
  stopStreaming,
  clearMessages,
  enterSelectionMode,
  exitSelectionMode,
  toggleMessageSelect,
  isSelected,
  getSelectedContent,
} = useChat()

// ---- 版本与内容状态 ----
const loading = ref(false)
const saving = ref(false)
const versions = ref([])
const currentVersion = ref(null)
const content = ref('')
const baseline = ref('') // 与数据库一致的内容基线，用于未保存检测
const lastAiBaseline = ref('') // AI 修改前的内容快照，用于 diff 高亮
const mode = ref('preview') // edit | preview
const chatVisible = ref(true)
const contextCount = ref('all')

const locked = computed(() => !!currentVersion.value?.is_finalized)
const hasUnsavedChanges = () => content.value !== baseline.value

// ---- 版本加载 ----
async function loadVersions(selectId = null) {
  loading.value = true
  try {
    const data = await outlineApi.getVersions(projectId.value)
    versions.value = data.versions || []
    if (selectId) {
      const target = versions.value.find((v) => v.id === selectId)
      if (target) {
        await doLoadVersion(target)
        return
      }
    }
    // 默认加载最新版本（后端按 version_number 倒序返回）
    if (versions.value.length > 0) {
      await doLoadVersion(versions.value[0])
    } else {
      currentVersion.value = null
      content.value = ''
      baseline.value = ''
    }
  } catch {
    // request.js 已统一提示
  } finally {
    loading.value = false
  }
}

async function doLoadVersion(version) {
  try {
    const data = await outlineApi.getVersion(projectId.value, version.id)
    currentVersion.value = {
      ...version,
      version_number: data.version_number ?? version.version_number,
      is_finalized: data.is_finalized ?? version.is_finalized,
    }
    content.value = data.content || ''
    baseline.value = data.content || ''
    lastAiBaseline.value = ''
    mode.value = 'preview'
    // 聊天记录仅在前端维护，切换版本时清空
    clearMessages()
  } catch {
    // 统一提示
  }
}

function handleSelectVersion(versionId) {
  const version = versions.value.find((v) => v.id === versionId)
  if (!version || version.id === currentVersion.value?.id) return
  if (isStreaming.value) {
    showWarning('AI 正在生成内容，请等待生成完成后再切换版本')
    return
  }
  if (hasUnsavedChanges()) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前大纲有未保存的修改，切换版本将丢失这些修改。确定要切换吗？',
      confirmText: '切换',
      onConfirm: (close) => {
        close()
        doLoadVersion(version)
      },
    })
    return
  }
  doLoadVersion(version)
}

// ---- Header 右侧：仅版本选择 ----
function refreshHeader() {
  const v = currentVersion.value
  const versionOptions = versions.value
    .map((ver) => `<option value="${ver.id}" ${ver.id === v?.id ? 'selected' : ''}>v${ver.version_number}${ver.is_finalized ? ' (已定稿)' : ''}</option>`)
    .join('')

  pageHeaderRightRef.value = `
    <div style="display:flex;align-items:center;gap:8px;">
      <select id="outline-version-select" style="height:28px;padding:0 8px;border-radius:6px;background:#1e293b;color:#e2e8f0;border:1px solid #334155;font-size:12px;cursor:pointer;outline:none;" onchange="window.__outlineVersionSelect(this.value)">
        ${versionOptions}
      </select>
    </div>
  `
}

// ---- Header 全局事件处理 ----
window.__outlineVersionSelect = (id) => handleSelectVersion(Number(id))

function handleLockCurrent() {
  const v = currentVersion.value
  if (!v) return
  ;(async () => {
    try {
      await outlineApi.finalize(projectId.value, v.id)
      showSuccess('版本已锁定')
      currentVersion.value = { ...v, is_finalized: true }
      await loadVersions(v.id)
      refreshHeader()
    } catch {
      // 统一提示
    }
  })()
}

function handleUnlock() {
  const v = currentVersion.value
  if (!v) return
  showConfirmModal({
    title: '解锁版本',
    message: '确定要解锁这个版本吗？解锁后可以修改内容。',
    confirmText: '解锁',
    onConfirm: async (close) => {
      close()
      try {
        await outlineApi.unlock(projectId.value, v.id)
        showSuccess('版本已解锁')
        currentVersion.value = { ...v, is_finalized: false }
        await loadVersions(v.id)
        refreshHeader()
      } catch {
        // 统一提示
      }
    },
  })
}

function handleDeleteVersion(version) {
  if (version.is_finalized) {
    showError('锁定版本不能删除')
    return
  }
  showConfirmModal({
    title: '删除版本',
    message: `确定要删除 v${version.version_number} 吗？此操作不可恢复。`,
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      close()
      try {
        await outlineApi.deleteOutline(projectId.value, version.id)
        showSuccess('版本已删除')
        const wasCurrent = currentVersion.value?.id === version.id
        if (wasCurrent) {
          currentVersion.value = null
          content.value = ''
          baseline.value = ''
          clearMessages()
        }
        await loadVersions(wasCurrent ? null : currentVersion.value?.id)
        refreshHeader()
      } catch {
        // 统一提示
      }
    },
  })
}

// ---- 保存 / 锁定 ----
function handleSave(asNew) {
  if (!content.value.trim()) {
    showError('请先输入大纲内容')
    return
  }
  if (isStreaming.value) {
    showWarning('AI 正在生成中，请等待完成后再保存')
    return
  }
  if (!asNew && locked.value) {
    showError('当前版本已锁定，无法修改')
    return
  }
  if (asNew) {
    showConfirmModal({
      title: '另存新版本',
      message: '将当前内容保存为新的版本，现有版本不受影响。',
      confirmText: '保存',
      onConfirm: (close) => {
        close()
        doSave(true)
      },
    })
    return
  }
  doSave(false)
}

async function doSave(asNew) {
  saving.value = true
  try {
    const data = await outlineApi.saveVersion(projectId.value, {
      content: content.value,
      version_id: asNew ? undefined : currentVersion.value?.id,
      new_version: asNew ? 'true' : 'false',
    })
    baseline.value = content.value
    showSuccess(`保存成功！版本号：v${data.version_number}`)
    await loadVersions()
    refreshHeader()
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

// ---- AI 聊天（流式，解析 JSON patches） ----
const MAX_INPUT_LENGTH = 5000

async function handleSend(message) {
  if (isStreaming.value) return
  if (locked.value) {
    showError('当前版本已锁定，无法进行修改')
    return
  }
  const text = (message || '').trim()
  if (!text) return
  if (text.length > MAX_INPUT_LENGTH) {
    showError(`消息内容不能超过 ${MAX_INPUT_LENGTH} 字符`)
    return
  }

  // 保存 AI 修改前的内容快照，用于 diff 高亮
  lastAiBaseline.value = content.value

  // 组装上下文历史
  let history = messages.value.map((m) => ({ role: m.role, content: m.content }))
  if (contextCount.value !== 'all') {
    history = history.slice(-parseInt(contextCount.value, 10) * 2)
  }

  const userMsg = { id: Date.now(), role: 'user', content: text }
  const aiMsg = { id: Date.now() + 1, role: 'assistant', content: '', thinking: '', patches: [], editsSummary: '', rawJson: '' }
  messages.value.push(userMsg)
  messages.value.push(aiMsg)

  isStreaming.value = true
  const versionNumber = currentVersion.value?.version_number ?? 0
  const streamVersionId = currentVersion.value?.id ?? null
  let thinkingBuffer = ''
  let jsonBuffer = ''
  let completeData = null

  function tryParsePatches(text) {
    try {
      const match = text.match(/"patch_list"\s*:\s*\[/)
      if (!match) return null
      const arrStart = text.indexOf(match[0]) + match[0].length - 1
      let depth = 1, i = arrStart + 1
      for (; i < text.length && depth > 0; i++) {
        if (text[i] === '[') depth++
        else if (text[i] === ']') depth--
      }
      if (depth !== 0) return null
      return JSON.parse(text.substring(arrStart, i))
    } catch {
      return null
    }
  }

  function updateAiMessage() {
      // thinking 内容单独存到 aiMsg.thinking，由 ChatMessage 的思考框渲染
      aiMsg.thinking = thinkingBuffer

      // content 只放问题和错误（editsSummary 由 ChatMessage 独立渲染）
      let parts = []
      if (aiMsg._error) {
        parts.push(`> ${aiMsg._error}`)
      }
      if (aiMsg._question) {
        parts.push(aiMsg._question)
      }
      aiMsg.content = parts.join('\n')
    }

  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/outline/chat/`,
      {
        body: {
          version_number: versionNumber,
          message: text,
          current_outline: content.value,
          messages: history,
        },
        onComplete: (evt) => {
          completeData = evt.data || evt
        },
      },
      (chunk, type) => {
        if (type === 'thinking_chunk') {
          thinkingBuffer += chunk
          aiMsg.thinking = thinkingBuffer
          updateAiMessage()
          return
        }

        jsonBuffer += chunk
        // 实时存储原始内容用于流式显示
        aiMsg.rawJson = jsonBuffer
        // 触发 Vue 响应式更新
        messages.value = [...messages.value]

        // 增量解析 patch_list
        const patches = tryParsePatches(jsonBuffer)
        if (patches && patches.length > aiMsg.patches.length) {
          aiMsg.patches = patches
          updateAiMessage()
        }
      },
    )

    // 从 completeData 获取 question 和 error
    if (completeData && typeof completeData === 'object') {
      const q = completeData.question || ''
      if (q) aiMsg._question = q
      const errMsg = completeData.error || ''
      if (errMsg) aiMsg._error = errMsg

      // 如果有 edits，使用后端返回的新内容更新编辑区（不自动保存）
      const editsApplied = completeData.edits_applied || 0
      const editsTotal = completeData.edits_total || 0
      if (editsApplied > 0) {
        aiMsg.editsSummary = `✅ 已应用 ${editsApplied}/${editsTotal} 处修改`
        if (completeData.new_content) {
          content.value = completeData.new_content
          showSuccess(`已修改 ${editsApplied} 处，请点击保存按钮保存修改`)
        }
      } else if (editsTotal > 0) {
        aiMsg.editsSummary = `⚠️ ${editsTotal} 处修改未成功应用`
      }
    }

    updateAiMessage()

    // 如果 AI 没有产生任何内容（无 thinking、无 patches、无 question），显示默认消息
    if (!aiMsg.content.trim() && !aiMsg.thinking.trim()) {
      aiMsg.content = aiMsg._error ? `生成失败：${aiMsg._error}` : 'AI 已完成处理'
    }

    // 重新同步版本列表（不清空聊天）
    try {
      const data = await outlineApi.getVersions(projectId.value)
      versions.value = data.versions || []
      refreshHeader()
    } catch {
      // ignore
    }
  } catch (err) {
    if (err.message !== '请求已取消或超时') {
      showError('生成失败：' + err.message)
    }
    if (!aiMsg.content.trim() && !aiMsg.thinking.trim()) {
      aiMsg.content = `生成失败：${err.message}`
    }
  } finally {
    isStreaming.value = false
    refreshHeader()
  }
}

async function handleCopySelected() {
  const text = getSelectedContent()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showSuccess('已复制选中内容')
  } catch {
    showError('复制失败')
  }
  exitSelectionMode()
}

// ---- 监听状态变化，刷新 header 右侧 ----
watch(currentVersion, refreshHeader)
watch(() => content.value?.trim(), refreshHeader)
watch(isStreaming, refreshHeader)

// 用户手动编辑内容时清除 diff 高亮
watch(content, (val) => {
  if (lastAiBaseline.value && val !== lastAiBaseline.value) {
    // 如果是 AI 修改后的 reload，diff 保持；如果是用户手动编辑，清除
    // 通过 isStreaming 判断：AI 完成后 isStreaming=false，此时用户编辑会清除
    if (!isStreaming.value) {
      lastAiBaseline.value = ''
    }
  }
})

onMounted(() => {
  setPageHeader('大纲', 'AI 协作构建故事大纲')
  loadVersions()
})

onBeforeUnmount(() => {
  sseController.abort()
  pageHeaderRightRef.value = ''
  delete window.__outlineVersionSelect
})
</script>

<style lang="scss">
// 覆盖父级布局（unscoped），锁定大纲页面为视口高度，内部滚动
.project-layout:has(.outline-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.outline-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.outline-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.outline-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.outline-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// 大纲编辑区
.outline-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.outline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  margin: 0 0 1px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-tag {
  font-weight: 600;
}

// 右侧聊天
.outline-chat {
  width: 360px;
  flex-shrink: 0;

  // 隐藏 ChatPanel 自带的选择/清空按钮
  :deep(.chat-panel-header-actions > .el-button) {
    display: none;
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-switch {
  :deep(.el-radio-button__inner) {
    padding: 5px 12px;
    font-size: 12px;
  }
}

.word-count {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.outline-body {
  flex: 1;
  min-height: 0;
  padding: 0 16px 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.outline-textarea {
  flex: 1;
  display: flex;

  :deep(.el-textarea__inner) {
    height: 100% !important;
    background: rgba(255, 255, 255, 0.02);
    border-color: var(--glass-border);
    color: var(--text-primary);
    line-height: 1.9;
    font-size: 14px;
    border-radius: var(--radius-sm);

    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.15);
    }
  }
}

.outline-preview {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px;
}

// 右侧聊天
.outline-chat {
  width: 360px;
  flex-shrink: 0;
}

.context-select {
  width: 120px;
}

.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all var(--transition-normal);
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 1200px) {
  .outline-chat {
    width: 300px;
  }
}

@media (max-width: 768px) {
  .outline-workspace {
    flex-direction: column;
    padding: 8px;
    gap: 8px;
  }
  .outline-chat {
    width: 100%;
    max-height: 420px;
  }
  .word-count {
    display: none;
  }
}
</style>
