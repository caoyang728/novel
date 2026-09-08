<template>
  <div class="chat-input-container">
    <div class="chat-input-wrapper glass-surface">
      <el-input
        ref="inputRef"
        v-model="inputText"
        type="textarea"
        :rows="1"
        :autosize="{ minRows: 1, maxRows: 6 }"
        :placeholder="placeholder"
        :disabled="disabled"
        resize="none"
        @keydown.enter.exact="handleEnter"
      />
      <div class="chat-input-actions">
        <el-button
          v-if="streaming"
          type="danger"
          size="small"
          circle
          @click="$emit('stop')"
        >
          <el-icon><VideoPause /></el-icon>
        </el-button>
        <el-button
          v-else
          type="primary"
          size="small"
          circle
          :disabled="!canSend"
          @click="handleSend"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { Promotion, VideoPause } from '@element-plus/icons-vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '输入消息...' },
})

const emit = defineEmits(['send', 'stop'])

const inputRef = ref(null)
const inputText = ref('')

const canSend = computed(() => inputText.value.trim() && !props.disabled)

function handleEnter(e) {
  // Shift+Enter 换行，Enter 发送
  if (e.shiftKey) return
  e.preventDefault()
  handleSend()
}

function handleSend() {
  if (!canSend.value) return
  emit('send', inputText.value.trim())
  inputText.value = ''
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus })
</script>

<style lang="scss" scoped>
.chat-input-container {
  padding: 12px 16px;
}

.chat-input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
}

.chat-input-wrapper :deep(.el-textarea__inner) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 4px 0;
  resize: none;
  color: var(--text-primary);

  &::placeholder {
    color: var(--text-muted);
  }
}

.chat-input-actions {
  flex-shrink: 0;
  padding-bottom: 2px;
}

</style>
