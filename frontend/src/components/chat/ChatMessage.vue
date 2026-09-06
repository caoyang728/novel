<template>
  <div
    class="chat-message"
    :class="[`chat-message--${role}`, { selected, selectable }]"
    @click="selectable && $emit('toggleSelect')"
  >
    <div class="chat-message-avatar">
      <el-icon v-if="role === 'user'" :size="20"><User /></el-icon>
      <el-icon v-else :size="20"><MagicStick /></el-icon>
    </div>
    <div class="chat-message-content">
      <div class="chat-message-role">{{ role === 'user' ? '你' : 'AI' }}</div>
      <!-- 思考区：流式时展开带滚动，完成后折叠 -->
      <div v-if="thinking" class="thinking-box" :class="{ 'thinking-box--done': !isStreaming }">
        <div v-if="isStreaming" class="thinking-box-header">
          ⏳ 思考中 ⬇
        </div>
        <el-collapse v-else>
          <el-collapse-item>
            <template #title>
              <span class="thinking-box-header">🧠 思考 ▶ 点击展开</span>
            </template>
            <div class="thinking-box-body">{{ thinking }}</div>
          </el-collapse-item>
        </el-collapse>
        <div v-if="isStreaming" ref="thinkingBodyRef" class="thinking-box-body thinking-box-body--streaming">
          {{ thinking }}
        </div>
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
        <MarkdownRenderer v-if="content" :content="content" />
        <span v-else-if="isStreaming && !thinking && !rawJson" class="chat-message-placeholder">正在生成...</span>
      </div>
    </div>
    <div v-if="selectable" class="chat-message-check">
      <el-icon v-if="selected"><CircleCheck /></el-icon>
      <span v-else class="check-ring" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { User, MagicStick, CircleCheck } from '@element-plus/icons-vue'
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

const thinkingBodyRef = ref(null)
const patchesBodyRef = ref(null)

// thinking 内容更新时自动滚动到底部
watch(() => props.thinking, async () => {
  if (props.isStreaming && thinkingBodyRef.value) {
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
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);

  &--user {
    background: rgba(255, 255, 255, 0.03);
  }

  &--assistant {
    background: rgba(129, 140, 248, 0.04);
  }

  &.selectable {
    cursor: pointer;

    &:hover {
      background: rgba(255, 255, 255, 0.06);
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
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}

.chat-message--user .chat-message-avatar {
  background: rgba(129, 140, 248, 0.15);
  color: var(--primary);
}

.chat-message-content {
  flex: 1;
  min-width: 0;
}

.chat-message-role {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.chat-message-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-regular);
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

.thinking-box-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  padding: 0 12px 8px;
}

.thinking-box-body--streaming {
  max-height: 200px;
  overflow-y: auto;
  padding: 0 12px 8px;
  scroll-behavior: smooth;
}

.thinking-box--done {
  background: rgba(99, 102, 241, 0.03);
  border-color: rgba(99, 102, 241, 0.12);
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
  max-height: 200px;
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
