<template>
  <div
    class="chat-message"
    :class="[`chat-message--${role}`, { selected, selectable }]"
    @click="selectable && $emit('toggleSelect')"
  >
    <!-- AI 头像在左侧 -->
    <div v-if="role === 'assistant'" class="chat-message-avatar chat-message-avatar--ai">AI</div>

    <div class="chat-message-content">
      <!-- 思考区：流式时展开带滚动，完成后短暂显示"思考完成"，有内容后消失 -->
      <div v-if="showThinking" class="thinking-box" :class="{ 'thinking-box--streaming': isStreaming }">
        <div v-if="isStreaming" class="thinking-box-header">
          <span class="thinking-spinner">⏳</span> 思考中 ⬇
        </div>
        <div v-if="isStreaming" ref="thinkingBodyRef" class="thinking-box-body thinking-box-body--streaming">
          <pre class="thinking-raw">{{ thinking }}</pre>
        </div>
        <template v-else>
          <div class="thinking-box-header" :class="content ? 'thinking-box-header--done' : ''">
            <span v-if="!content" class="thinking-spinner">⏳</span>
            {{ content ? '🧠 思考完成 ▶' : '正在检查现有世界观内容…' }}
          </div>
          <!-- 打字机效果：thinking 有内容但 content 为空时显示思考内容 -->
          <div v-if="thinking && !content" class="thinking-box-body thinking-box-body--streaming">
            <pre class="thinking-raw">{{ thinking }}</pre>
          </div>
        </template>
      </div>
      <!-- 正文 -->
      <div class="chat-message-body">
        <!-- 思考区：流式时展开，完成后折叠 -->
        <div v-if="rawJson" class="patches-box" :class="{ 'patches-box--done': !isStreaming }">
          <template v-if="isStreaming">
            <div class="patches-box-header">
              🧠 思考 ⬇
            </div>
            <div ref="patchesBodyRef" class="patches-box-body patches-box-body--streaming">
              {{ rawJson }}
            </div>
          </template>
          <el-collapse v-else>
            <el-collapse-item>
              <template #title>
                <span class="patches-box-header">🧠 思考</span>
              </template>
              <div class="patches-box-body patches-box-body--streaming">{{ rawJson }}</div>
            </el-collapse-item>
          </el-collapse>
        </div>
        <!-- 修改结果摘要 -->
        <div v-if="editsSummary" class="edits-summary">{{ editsSummary }}</div>
        <div v-if="content" class="chat-bubble" :class="role === 'user' ? 'chat-bubble--user' : 'chat-bubble--ai'">
          <MarkdownRenderer :content="content" />
        </div>
        <span v-else-if="isStreaming && !thinking && !rawJson" class="chat-message-placeholder">正在生成...</span>
      </div>
    </div>

    <!-- ME 头像在右侧 -->
    <div v-if="role === 'user'" class="chat-message-avatar chat-message-avatar--me">Me</div>

    <div v-if="selectable" class="chat-message-check">
      <el-icon v-if="selected"><CircleCheck /></el-icon>
      <span v-else class="check-ring" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { CircleCheck } from '@element-plus/icons-vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'

const props = defineProps({
  role: { type: String, default: 'user' },
  content: { type: String, default: '' },
  thinking: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  patches: { type: Array, default: () => [] },
  editsSummary: { type: String, default: '' },
  rawJson: { type: String, default: '' },
})

defineEmits(['toggleSelect'])

const showThinking = computed(() => {
  // 流式进行中：始终显示思考区
  if (props.isStreaming) return true
  // 流式已完成且有内容：隐藏思考区
  if (props.content) return false
  // 等待中（如 loadWelcome）：有 thinking 就显示
  return !!props.thinking
})

const thinkingBodyRef = ref(null)
const patchesBodyRef = ref(null)

// thinking 内容更新时自动滚动到底部（流式或打字机效果）
watch(() => props.thinking, async () => {
  if (thinkingBodyRef.value) {
    await nextTick()
    thinkingBodyRef.value.scrollTop = thinkingBodyRef.value.scrollHeight
  }
})

// rawJson 内容更新时自动滚动到底部
watch(() => props.rawJson, async () => {
  if (props.isStreaming && patchesBodyRef.value) {
    await nextTick()
    patchesBodyRef.value.scrollTop = patchesBodyRef.value.scrollHeight
  }
})
</script>

<style lang="scss" scoped>
.chat-message {
  display: flex;
  gap: 10px;
  padding: 8px 12px;
  align-items: flex-start;

  &--user {
    .chat-message-avatar {
      order: 2;
    }

    .chat-message-content {
      order: 1;
      align-items: flex-end;
    }
  }

  &--assistant {
    .chat-message-avatar {
      order: 1;
    }

    .chat-message-content {
      order: 2;
    }
  }

  &.selectable {
    cursor: pointer;
    border-radius: var(--radius-md);

    &:hover {
      background: rgba(255, 255, 255, 0.04);
    }

    &.selected {
      background: rgba(129, 140, 248, 0.1);
      border: 1px solid rgba(129, 140, 248, 0.2);
    }
  }
}

.chat-message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;

  &--ai {
    background: rgba(129, 140, 248, 0.12);
    color: var(--primary);
  }

  &--me {
    background: rgba(45, 138, 94, 0.2);
    color: #5eba8d;
  }
}

.chat-message-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-message--user .chat-message-content {
  align-items: flex-end;
}

.chat-message--assistant .chat-message-content {
  align-items: flex-start;
}

.chat-message-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-regular);
  max-width: 85%;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  word-break: break-word;

  &--ai {
    background: rgba(255, 255, 255, 0.06);
    border-top-left-radius: 4px;
    color: var(--text-regular);
  }

  &--user {
    background: #2d8a5e;
    color: #fff;
    border-top-right-radius: 4px;
    text-align: left;

    :deep(.markdown-body) {
      color: #e8f5ee;

      a { color: #b2dfbc; }
      code { background: rgba(255,255,255,0.12); color: #fff; }
      pre { background: rgba(0,0,0,0.12); color: #e8f5ee; }
      strong { color: #fff; }
      p { color: #e8f5ee; }
      li { color: #e8f5ee; }
      h1, h2, h3, h4, h5, h6 { color: #fff; }
      blockquote { color: rgba(255,255,255,0.7); border-left-color: rgba(255,255,255,0.25); }
      table { color: #e8f5ee; }
      th, td { border-color: rgba(255,255,255,0.15); }
    }
  }
}

.chat-message-placeholder {
  color: var(--text-muted);
  font-style: italic;
}

.chat-message-check {
  display: flex;
  align-items: flex-start;
  padding-top: 4px;
  color: var(--text-muted);
  font-size: 18px;

  .selected & {
    color: var(--primary);
  }
}

.check-ring {
  width: 16px;
  height: 16px;
  border: 2px solid var(--text-muted);
  border-radius: 50%;
  margin-top: 2px;
  opacity: 0.6;
}

/* 思考区样式 */
.thinking-box {
  margin-bottom: 8px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(99, 102, 241, 0.2);
  background: rgba(99, 102, 241, 0.06);
  overflow: hidden;
  max-width: 85%;
}

.thinking-box-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.15);
}

@keyframes thinking-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.thinking-spinner {
  display: inline-block;
  animation: thinking-spin 1.5s linear infinite;
}

.thinking-box-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  padding: 0 12px 8px;

  :deep(.markdown-body) {
    font-size: 13px;
    color: var(--text-secondary);
  }
}

.thinking-box-body--streaming {
  max-height: 140px;
  overflow-y: auto;
  padding: 0 12px 8px;
  scroll-behavior: smooth;
}

.thinking-raw {
  margin: 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  background: none;
  border: none;
  padding: 0;
}

.thinking-box--streaming {
  background: rgba(99, 102, 241, 0.06);
}

.thinking-box-header--done {
  border-bottom: none;
  padding: 6px 12px;
  font-size: 11px;
  color: var(--text-muted);
}

:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item__header) {
  background: transparent;
  border: none;
  height: auto;
  line-height: normal;
  padding: 0;
  font-size: inherit;
}

:deep(.el-collapse-item__wrap) {
  background: transparent;
  border: none;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

/* 修改计划样式 */
.patches-box {
  margin-bottom: 8px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(99, 102, 241, 0.2);
  background: rgba(99, 102, 241, 0.06);
  overflow: hidden;
  max-width: 85%;
}

.patches-box-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.15);
}

.patches-box-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  padding: 8px 12px;
}

.patches-box-body--streaming {
  max-height: 140px;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.patches-box--done {
  background: rgba(99, 102, 241, 0.03);
  border-color: rgba(99, 102, 241, 0.12);
}

/* 修改结果摘要 */
.edits-summary {
  margin: 8px 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: rgba(129, 140, 248, 0.08);
  border: 1px solid rgba(129, 140, 248, 0.15);
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
}
</style>
