<template>
  <AppModal
    :visible="visible"
    title="AI 修改对比"
    width="92%"
    height="86vh"
    min-height="0"
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="compare-layout">
      <!-- 左：修改章节列表 -->
      <div class="compare-chapter-list glass-surface">
        <div class="compare-list-header">
          修改章节
          <el-tag size="small" type="primary" effect="dark" round>
            {{ modifiedKeys.length }}
          </el-tag>
        </div>
        <div class="compare-list-body">
          <div v-if="modifiedKeys.length === 0" class="compare-list-empty">暂无修改</div>
          <div
            v-for="cn in modifiedKeys"
            :key="cn"
            class="compare-chapter-item"
            :class="{ active: cn === currentChapterNumber }"
            @click="currentChapterNumber = cn"
          >
            <span class="compare-dot" />
            <span class="text-ellipsis">
              第{{ cn }}章{{ modifications[cn] ? ': ' + modifications[cn].modified.title : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 中：对比内容 -->
      <div class="compare-content glass-surface">
        <template v-if="currentMod">
          <div class="compare-content-header">
            <template v-if="titleChanged">
              <span class="title-original">第{{ currentChapterNumber }}章: {{ currentMod.original.title }}</span>
              <el-icon class="title-arrow"><Right /></el-icon>
              <span class="title-modified">第{{ currentChapterNumber }}章: {{ currentMod.modified.title }}</span>
            </template>
            <span v-else class="title-modified">
              第{{ currentChapterNumber }}章: {{ currentMod.modified.title }}
            </span>
            <el-tag v-if="streaming" size="small" type="warning" effect="plain" class="streaming-tag">
              生成中...
            </el-tag>
          </div>

          <div class="compare-content-body">
            <!-- 流式生成中：双栏 textarea -->
            <div v-if="streaming" class="compare-streaming">
              <div class="streaming-col">
                <div class="streaming-label">修改前</div>
                <textarea class="streaming-textarea" readonly :value="streamingOriginal" />
              </div>
              <div class="streaming-col">
                <div class="streaming-label">修改后（生成中...）</div>
                <textarea ref="streamingTextareaEl" class="streaming-textarea" readonly :value="streamingText" />
              </div>
            </div>

            <!-- 完成后：行级 diff -->
            <div v-else class="diff-rows">
              <div class="diff-row diff-row-header">
                <div class="diff-cell">修改前</div>
                <div class="diff-cell diff-cell-right">修改后</div>
              </div>
              <div v-for="(p, idx) in diffPairs" :key="idx" class="diff-row">
                <div class="diff-cell" :class="cellClass(p.left, 'del')">
                  <span class="diff-line-content">{{ p.left.line || ' ' }}</span>
                </div>
                <div class="diff-cell diff-cell-right" :class="cellClass(p.right, 'add')">
                  <span class="diff-line-content">{{ p.right.line || ' ' }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="compare-content-empty">选择章节查看对比</div>
      </div>

      <!-- 右：AI 对话 -->
      <div class="compare-chat glass-surface">
        <div class="compare-chat-header">
          <el-icon><ChatDotRound /></el-icon>
          <span>AI 对话</span>
        </div>
        <div ref="chatMessagesEl" class="compare-chat-messages">
          <div v-if="chatMessages.length === 0" class="compare-chat-empty">
            <span v-if="chatDisabled">章节处理中，请稍候...</span>
            <span v-else>可继续输入指令调整内容</span>
          </div>
          <div
            v-for="(msg, idx) in chatMessages"
            :key="idx"
            class="compare-msg"
            :class="msg.role"
          >
            <div class="compare-msg-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
            <div class="compare-msg-bubble">{{ msg.content }}</div>
          </div>
        </div>
        <div class="compare-chat-input-row">
          <textarea
            ref="chatInputEl"
            v-model="chatInput"
            class="compare-chat-input"
            rows="2"
            :disabled="chatDisabled || chatSending || !currentChapterNumber"
            placeholder="继续输入指令... (Enter发送, Shift+Enter换行)"
            @keydown="onChatKeydown"
          />
          <el-button
            type="primary"
            circle
            :loading="chatSending"
            :disabled="chatDisabled || !chatInput.trim() || !currentChapterNumber"
            @click="sendChat"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <AppButton :disabled="saving" @click="$emit('cancel')">
        <el-icon><Close /></el-icon> 取消修改
      </AppButton>
      <AppButton variant="accent" :loading="saving" :disabled="streaming" @click="$emit('save')">
        <el-icon><Check /></el-icon> 保存修改
      </AppButton>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import {
  Right, ChatDotRound, Promotion, Close, Check,
} from '@element-plus/icons-vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  // { [chapterNumber]: { chapter_id, original: {title, content}, modified: {title, content} } }
  modifications: { type: Object, default: () => ({}) },
  streaming: { type: Boolean, default: false },
  streamingText: { type: String, default: '' },
  streamingOriginal: { type: String, default: '' },
  chatMessages: { type: Array, default: () => [] },
  chatSending: { type: Boolean, default: false },
  chatDisabled: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'save', 'cancel', 'send'])

const currentChapterNumber = ref(null)
const chatInput = ref('')
const chatMessagesEl = ref(null)
const streamingTextareaEl = ref(null)
const chatInputEl = ref(null)

const MAX_DIFF_LINES = 500

// 仅有实际改动的章节
const modifiedKeys = computed(() => {
  return Object.keys(props.modifications)
    .map(Number)
    .filter((cn) => {
      const mod = props.modifications[cn]
      if (!mod) return false
      return mod.original.title !== mod.modified.title ||
        mod.original.content !== mod.modified.content
    })
    .sort((a, b) => a - b)
})

const currentMod = computed(() =>
  currentChapterNumber.value != null ? props.modifications[currentChapterNumber.value] : null,
)

const titleChanged = computed(() => {
  const mod = currentMod.value
  if (!mod) return false
  return mod.original.title !== mod.modified.title
})

// 弹窗打开或章节列表变化时，自动选中第一章
watch(
  () => [props.visible, modifiedKeys.value.length, modifiedKeys.value.join(',')],
  () => {
    if (props.visible) {
      if (currentChapterNumber.value == null || !modifiedKeys.value.includes(currentChapterNumber.value)) {
        currentChapterNumber.value = modifiedKeys.value[0] ?? null
      }
    } else {
      currentChapterNumber.value = null
      chatInput.value = ''
    }
  },
)

// 行级 LCS diff
function computeDiff(originalText, modifiedText) {
  const origLines = (originalText || '').split('\n')
  const modLines = (modifiedText || '').split('\n')

  // 超长文本降级
  if (origLines.length > MAX_DIFF_LINES || modLines.length > MAX_DIFF_LINES) {
    const pairs = []
    const maxLen = Math.max(origLines.length, modLines.length)
    for (let i = 0; i < maxLen; i++) {
      const origLine = i < origLines.length ? origLines[i] : ''
      const modLine = i < modLines.length ? modLines[i] : ''
      if (origLine === modLine) {
        pairs.push({ left: { line: origLine, type: 'same' }, right: { line: modLine, type: 'same' } })
      } else {
        pairs.push({
          left: { line: origLine || '', type: origLine ? 'deleted' : 'empty' },
          right: { line: modLine || '', type: modLine ? 'added' : 'empty' },
        })
      }
    }
    return pairs
  }

  const m = origLines.length
  const n = modLines.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (origLines[i - 1] === modLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  const pairs = []
  let i = m
  let j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origLines[i - 1] === modLines[j - 1]) {
      pairs.unshift({ left: { line: origLines[i - 1], type: 'same' }, right: { line: modLines[j - 1], type: 'same' } })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      pairs.unshift({ left: { line: '', type: 'empty' }, right: { line: modLines[j - 1], type: 'added' } })
      j--
    } else if (i > 0) {
      pairs.unshift({ left: { line: origLines[i - 1], type: 'deleted' }, right: { line: '', type: 'empty' } })
      i--
    }
  }
  return pairs
}

const diffPairs = computed(() => {
  const mod = currentMod.value
  if (!mod) return []
  return computeDiff(mod.original.content || '', mod.modified.content || '')
})

function cellClass(cell, kind) {
  if (cell.type === 'empty') return 'diff-cell-empty'
  if (kind === 'del' && cell.type === 'deleted') return 'diff-cell-del'
  if (kind === 'add' && cell.type === 'added') return 'diff-cell-add'
  return ''
}

function sendChat() {
  const text = chatInput.value.trim()
  if (!text) return
  emit('send', text)
  chatInput.value = ''
  nextTick(() => {
    if (chatInputEl.value) chatInputEl.value.style.height = 'auto'
  })
}

function onChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendChat()
  }
}

// 流式文本 / 新消息时自动滚动
watch(
  () => props.streamingText,
  () => {
    nextTick(() => {
      if (streamingTextareaEl.value) {
        streamingTextareaEl.value.scrollTop = streamingTextareaEl.value.scrollHeight
      }
    })
  },
)

watch(
  () => props.chatMessages.length,
  () => {
    nextTick(() => {
      if (chatMessagesEl.value) {
        chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight
      }
    })
  },
)
</script>

<style lang="scss" scoped>
.compare-layout {
  display: grid;
  grid-template-columns: 200px 1fr 300px;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.compare-chapter-list,
.compare-content,
.compare-chat {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.compare-list-header {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--glass-border);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.compare-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.compare-list-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 24px 0;
}

.compare-chapter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-regular);
  transition: all var(--transition-fast);

  .compare-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary);
    flex-shrink: 0;
    box-shadow: 0 0 6px var(--primary);
  }

  &:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  &.active {
    background: rgba(129, 140, 248, 0.18);
    color: var(--text-primary);
  }
}

.compare-content-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--glass-border);
  font-size: 13px;
  flex-shrink: 0;
  flex-wrap: wrap;

  .title-original {
    color: var(--text-muted);
    text-decoration: line-through;
  }

  .title-arrow {
    color: var(--text-muted);
  }

  .title-modified {
    color: var(--text-primary);
    font-weight: 600;
  }

  .streaming-tag {
    margin-left: auto;
  }
}

.compare-content-body {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.compare-content-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 13px;
}

.compare-streaming {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  height: 100%;
  padding: 8px;
}

.streaming-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.streaming-label {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 6px;
  flex-shrink: 0;
}

.streaming-textarea {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  color: var(--text-regular);
  padding: 10px;
  font-size: 13px;
  line-height: 1.7;
  resize: none;
  outline: none;
  font-family: inherit;
}

.diff-rows {
  height: 100%;
  overflow-y: auto;
  padding: 8px;
}

.diff-row {
  display: grid;
  grid-template-columns: 1fr 1fr;

  &.diff-row-header {
    position: sticky;
    top: 0;
    z-index: 2;

    .diff-cell {
      background: rgba(129, 140, 248, 0.15);
      color: var(--text-primary);
      font-weight: 600;
      font-size: 12px;
    }
  }
}

.diff-cell {
  padding: 2px 10px;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  border-left: 1px solid var(--glass-border);
  color: var(--text-regular);

  &.diff-cell-right {
    border-left: none;
    border-right: 1px solid var(--glass-border);
  }

  &.diff-cell-del {
    background: rgba(248, 113, 113, 0.12);
    color: #fca5a5;
  }

  &.diff-cell-add {
    background: rgba(74, 222, 128, 0.12);
    color: #86efac;
  }

  &.diff-cell-empty {
    background: rgba(255, 255, 255, 0.02);
  }
}

.compare-chat-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.compare-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.compare-chat-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 24px 8px;
}

.compare-msg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;

  .compare-msg-avatar {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    flex-shrink: 0;
    background: rgba(129, 140, 248, 0.2);
    color: var(--primary);
  }

  .compare-msg-bubble {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--text-regular);
    white-space: pre-wrap;
    word-break: break-word;
  }

  &.user {
    flex-direction: row-reverse;

    .compare-msg-avatar {
      background: rgba(74, 222, 128, 0.15);
      color: var(--success);
    }

    .compare-msg-bubble {
      background: rgba(129, 140, 248, 0.14);
    }
  }
}

.compare-chat-input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 10px;
  border-top: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.compare-chat-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;

  &:focus {
    border-color: var(--primary);
  }

  &:disabled {
    opacity: 0.5;
  }
}
</style>
