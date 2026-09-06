<template>
  <div class="chat-panel glass-surface">
    <!-- 聊天头部 -->
    <div class="chat-panel-header">
      <span class="chat-panel-title">{{ title }}</span>
      <div class="chat-panel-header-actions">
        <slot name="header-actions" />
        <el-button size="small" text @click="$emit('toggleSelection')">
          <el-icon><Select /></el-icon>
        </el-button>
        <el-button size="small" text @click="$emit('clear')">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 选择模式操作条 -->
    <ChatSelectionBar
      :visible="selectionMode"
      :count="selectedCount"
      @copy="$emit('copySelected')"
      @exit="$emit('exitSelection')"
    />

    <!-- 消息列表 -->
    <div ref="messagesContainer" class="chat-panel-messages">
      <div v-if="messages.length === 0" class="chat-panel-empty">
        <el-icon :size="32" class="empty-icon"><ChatDotRound /></el-icon>
        <p>开始对话吧</p>
      </div>
      <ChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :role="msg.role"
        :content="msg.content"
        :thinking="msg.thinking || ''"
        :is-streaming="msg.role === 'assistant' && isStreaming"
        :selectable="selectionMode"
        :selected="isSelected(msg.id)"
        :patches="msg.patches || []"
        :edits-summary="msg.editsSummary || ''"
        :raw-json="msg.rawJson || ''"
        @toggle-select="$emit('toggleSelect', msg.id)"
      />
    </div>

    <!-- 快捷提示插槽 -->
    <slot name="quick-prompts" />

    <!-- 输入区 -->
    <ChatInput
      :streaming="isStreaming"
      :placeholder="inputPlaceholder"
      :hint="inputHint"
      @send="$emit('send', $event)"
      @stop="$emit('stop')"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, Delete, Select } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'
import ChatSelectionBar from './ChatSelectionBar.vue'

const props = defineProps({
  title: { type: String, default: 'AI 对话' },
  messages: { type: Array, default: () => [] },
  isStreaming: { type: Boolean, default: false },
  selectionMode: { type: Boolean, default: false },
  selectedCount: { type: Number, default: 0 },
  inputPlaceholder: { type: String, default: '输入消息...' },
  inputHint: { type: String, default: '' },
  isSelected: { type: Function, default: () => false },
})

defineEmits([
  'send',
  'stop',
  'clear',
  'toggleSelection',
  'exitSelection',
  'toggleSelect',
  'copySelected',
])

const messagesContainer = ref(null)

// 自动滚动到底部
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
)

// 流式内容变化时也滚动
watch(
  () => props.messages[props.messages.length - 1]?.content,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
)

// 流式 thinking 变化时也滚动
watch(
  () => props.messages[props.messages.length - 1]?.thinking,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
)
</script>

<style lang="scss" scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.chat-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-panel-header-actions {
  display: flex;
  gap: 4px;
}

.chat-panel-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.chat-panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);

  .empty-icon {
    margin-bottom: 12px;
    opacity: 0.5;
  }

  p {
    font-size: 14px;
  }
}
</style>
