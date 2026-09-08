<template>
  <div class="chat-panel glass-surface">
    <!-- 聊天头部 -->
    <div class="chat-panel-header">
      <span class="chat-panel-title">{{ title }}</span>
      <div class="chat-panel-header-actions">
        <slot name="header-actions" />
        <el-button size="small" text @click="$emit('newChat')" title="新对话">
          <el-icon><ChatDotRound /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 锁定状态：居中显示锁定提示 -->
    <div v-if="locked" class="chat-panel-locked">
      <div class="chat-panel-locked-card">
        <el-icon :size="36" class="locked-icon"><Lock /></el-icon>
        <h3>版本已锁定</h3>
        <p>当前版本已锁定，不支持修改。如需修改文档，请先解锁当前版本，或点击「另存」创建一个可编辑的新版本后再进行修改。</p>
      </div>
    </div>

    <!-- 正常状态：消息列表 -->
    <template v-else>
      <div ref="messagesContainer" class="chat-panel-messages">
        <div v-if="messages.length === 0" class="chat-panel-empty">
          <el-icon :size="32" class="empty-icon"><ChatDotRound /></el-icon>
          <p>开始对话吧</p>
        </div>
        <template v-for="(msg, idx) in messages" :key="msg.id">
          <ChatMessage
            :role="msg.role"
            :content="msg.content"
            :thinking="msg.thinking || ''"
            :is-streaming="msg.role === 'assistant' && msg.id === streamingMsgId"
            :patches="msg.patches || []"
            :edits-summary="msg.editsSummary || ''"
            :raw-json="msg.rawJson || ''"
          />
          <slot v-if="idx === messages.length - 1" name="message-end" />
        </template>
      </div>

      <!-- 快捷提示插槽 -->
      <slot name="quick-prompts" />

      <!-- 输入区 -->
      <ChatInput
        :streaming="isStreaming"
        :disabled="disabled"
        :placeholder="inputPlaceholder"
        @send="$emit('send', $event)"
        @stop="$emit('stop')"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, Lock } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'

const props = defineProps({
  title: { type: String, default: 'AI 对话' },
  messages: { type: Array, default: () => [] },
  isStreaming: { type: Boolean, default: false },
  streamingMsgId: { type: [Number, String, null], default: null },
  inputPlaceholder: { type: String, default: '输入消息...' },
  disabled: { type: Boolean, default: false },
  locked: { type: Boolean, default: false },
})

defineEmits([
  'send',
  'stop',
  'newChat',
  'toggleSelect',
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

// 选项变化时也滚动到底部
watch(
  () => props.messages[props.messages.length - 1]?.options,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
  { deep: true },
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

// ---- 锁定状态 ----
.chat-panel-locked {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.chat-panel-locked-card {
  text-align: center;
  max-width: 320px;

  .locked-icon {
    color: #fbbf24;
    margin-bottom: 16px;
    opacity: 0.8;
  }

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 12px;
  }

  p {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.7;
    margin: 0;
  }
}
</style>
