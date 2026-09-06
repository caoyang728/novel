<template>
  <div class="wv-chat-view">
    <div class="wv-chat-workspace">
      <!-- 左：世界观 Markdown 预览 -->
      <section class="wv-preview glass-panel" v-loading="markdownLoading" element-loading-text="加载世界观...">
        <div class="wv-preview-header">
          <span class="wv-preview-title">
            <el-icon><Reading /></el-icon>
            世界观预览
          </span>
          <el-tag v-if="isStreaming" type="primary" effect="dark" size="small" round>
            AI 正在更新世界观...
          </el-tag>
        </div>
        <div class="wv-preview-body">
          <div v-if="markdown" class="markdown-body" v-html="renderedMarkdown"></div>
          <EmptyState
            v-else
            icon="ChatLineSquare"
            text="还没有世界观数据，在右侧对话框向 AI 描述题材、风格与基本设定，开始构建吧"
          />
        </div>
      </section>

      <!-- 右：AI 聊天（参考 outline 页面布局） -->
      <transition name="chat-slide">
        <ChatPanel
          v-if="chatVisible"
          class="wv-chat"
          title="世界观构建助手"
          :messages="messages"
          :is-streaming="isStreaming"
          :selection-mode="selectionMode"
          :selected-count="selectedMessages.size"
          :is-selected="isSelected"
          input-placeholder="描述你想要的题材、风格、设定..."
          input-hint="AI 会根据对话自动整理世界观，并同步到左侧预览"
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
          <template #quick-prompts>
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
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, inject } from 'vue'
// import { useRouter } from 'vue-router'
import { /* Back, RefreshLeft, */ Reading } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { worldviewApi, worldviewUrls } from '@/api/worldview'
import { createSseController } from '@/api/sse'
import { useProjectId } from '@/composables/useProjectId'
import { useChat } from '@/composables/useChat'
import { showSuccess, showError } from '@/utils/notify'
import { safeMarkdownParse } from '@/utils/markdown'

// const router = useRouter()
const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')
const pageHeaderRightRef = inject('pageHeaderRightRef')

const {
  messages,
  isStreaming,
  selectionMode,
  selectedMessages,
  enterSelectionMode,
  exitSelectionMode,
  toggleMessageSelect,
  isSelected,
  getSelectedContent,
  addUserMessage,
  clearMessages,
} = useChat()

// 流式控制器（支持停止）
const sseController = createSseController()

// ---- 世界观 Markdown 预览 ----
const markdown = ref('')
const markdownLoading = ref(false)
const chatVisible = ref(true)
const contextCount = ref('all')

const renderedMarkdown = computed(() => safeMarkdownParse(markdown.value))

// 最后一条助手消息携带的快捷选项
const quickOptions = computed(() => {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && Array.isArray(last.options) && last.options.length) {
    return last.options
  }
  return []
})

let msgSeq = 0
function nextMsgId() {
  msgSeq += 1
  return Date.now() + msgSeq
}

// ---- 加载世界观 Markdown（毫秒级，先渲染）----
async function loadMarkdown() {
  if (!projectId.value) return
  markdownLoading.value = true
  try {
    const res = await worldviewApi.exportMarkdown(projectId.value)
    const md = res?.data?.markdown || ''
    if (md && md.trim()) {
      markdown.value = md
    }
  } catch (err) {
    console.error('加载世界观 Markdown 失败:', err)
  } finally {
    markdownLoading.value = false
  }
}

// ---- 加载 AI 引导问题（慢速，LLM 调用）----
async function loadWelcome() {
  if (!projectId.value) return
  try {
    const res = await worldviewApi.openChat(projectId.value)
    const data = res?.data
    if (data && data.has_content !== false && data.question) {
      messages.value.push({
        id: nextMsgId(),
        role: 'assistant',
        content: data.question,
        options: Array.isArray(data.options) ? data.options : [],
        timestamp: new Date().toISOString(),
      })
    } else {
      pushDefaultWelcome()
    }
  } catch (err) {
    console.error('加载引导问题失败:', err)
    pushDefaultWelcome()
  }
}

function pushDefaultWelcome() {
  messages.value.push({
    id: nextMsgId(),
    role: 'assistant',
    content:
      '你好！我是你的世界观构建助手。\n\n告诉我你想创作什么类型的故事（玄幻、科幻、都市、末世、古风等），以及大致的世界背景构想，我会一步步帮你搭建完整的世界观体系。',
    options: [],
    timestamp: new Date().toISOString(),
  })
}

// ---- 发送消息 ----
async function handleSend(rawText) {
  if (isStreaming.value) return
  const text = (rawText || '').trim()
  if (!text) return

  // 上下文消息（不含思考占位），按设置截取最近轮数
  const contextAll = messages.value
    .filter((m) => m.content && m.content !== '正在思考中…')
  const contextSliced = contextCount.value === 'all'
    ? contextAll
    : contextAll.slice(-parseInt(contextCount.value, 10) * 2)
  const context = contextSliced.map((m) => ({ role: m.role, content: m.content }))

  addUserMessage(text)

  // 助手思考占位
  const placeholder = {
    id: nextMsgId(),
    role: 'assistant',
    content: '正在思考中…',
    options: [],
    timestamp: new Date().toISOString(),
  }
  messages.value.push(placeholder)

  isStreaming.value = true
  let streamMarkdown = ''
  let completed = false

  try {
    await sseController.stream(
      worldviewUrls.chatStream(projectId.value),
      {
        body: { message: text, messages: context },
        onEvent: (evt) => {
          if (evt.type === 'chunk' && evt.chunk) {
            // chunk 是完整新世界观 Markdown 的切片，替换式累积
            streamMarkdown += evt.chunk
            markdown.value = streamMarkdown
          } else if (evt.type === 'complete') {
            completed = true
            if (evt.markdown) markdown.value = evt.markdown
            placeholder.content = evt.reply || '世界观内容已更新，请查看左侧预览区'
            placeholder.options = Array.isArray(evt.options) ? evt.options : []
            placeholder.timestamp = new Date().toISOString()
          }
        },
      },
      () => {},
    )

    if (!completed) {
      placeholder.content = '世界观内容已更新，请查看左侧预览区'
    }

    // 从后端重新拉取最终 Markdown（比流式拼装更可靠）
    await loadMarkdown()
  } catch (err) {
    if (err.message === '请求已取消或超时') {
      placeholder.content = '已停止生成，世界观已保存的内容可在左侧预览查看'
    } else {
      console.error('世界观聊天流式失败:', err)
      placeholder.content = `抱歉，生成失败：${err.message || '请重试'}`
      showError(err.message || '生成失败，请重试')
    }
  } finally {
    isStreaming.value = false
  }
}

function stopStreaming() {
  sseController.abort()
  isStreaming.value = false
}

async function handleCopySelected() {
  const text = getSelectedContent()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showSuccess('已复制选中消息')
  } catch {
    showError('复制失败，请手动选择复制')
  }
}

// function goWorkbench() {
//   router.push({ name: 'Worldview', params: { projectId: projectId.value } })
// }

// ---- Header 右侧：上下文轮数选择（参考 outline 布局） ----
function refreshHeader() {
  pageHeaderRightRef.value = `
    <div style="display:flex;align-items:center;gap:8px;">
      <select id="wv-context-select" style="height:28px;padding:0 8px;border-radius:6px;background:#1e293b;color:#e2e8f0;border:1px solid #334155;font-size:12px;cursor:pointer;outline:none;" onchange="window.__wvContextSelect(this.value)">
        <option value="all" ${contextCount.value === 'all' ? 'selected' : ''}>全部上下文</option>
        <option value="5" ${contextCount.value === '5' ? 'selected' : ''}>最近 5 轮</option>
        <option value="10" ${contextCount.value === '10' ? 'selected' : ''}>最近 10 轮</option>
        <option value="20" ${contextCount.value === '20' ? 'selected' : ''}>最近 20 轮</option>
      </select>
    </div>
  `
}

window.__wvContextSelect = (value) => {
  contextCount.value = value
}

watch(contextCount, refreshHeader)

onMounted(() => {
  setPageHeader('世界观构建', '与 AI 对话，逐步搭建完整的世界观体系')
  refreshHeader()
  // 并行：Markdown 快速渲染 + LLM 引导问题异步更新
  loadMarkdown()
  loadWelcome()
})

onBeforeUnmount(() => {
  sseController.abort()
  pageHeaderRightRef.value = ''
  delete window.__wvContextSelect
})
</script>

<style lang="scss">
/* 参考 outline 页面布局，覆盖父级布局，锁定为视口高度 */
.project-layout:has(.wv-chat-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.wv-chat-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.wv-chat-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.wv-chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.wv-chat-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// 左：预览
.wv-preview {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow: hidden;
}

.wv-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.wv-preview-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.wv-preview-body {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

// 右：聊天
.wv-chat {
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

// 快捷选项按钮
.quick-options {
  padding: 8px 12px;
  border-top: 1px solid var(--glass-border);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 120px;
  overflow-y: auto;
}

.quick-option-btn {
  padding: 6px 12px;
  font-size: 12px;
  color: var(--primary);
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;

  &:hover {
    background: rgba(99, 102, 241, 0.2);
    border-color: var(--primary);
    transform: translateY(-1px);
  }
}

@media (max-width: 1200px) {
  .wv-chat-workspace {
    flex-direction: column;
  }
  .wv-chat {
    width: 100%;
    max-height: 480px;
  }
}

@media (max-width: 768px) {
  // .btn-text {
  //   display: none;
  // }
}
</style>
