<template>
  <AppModal
    :visible="visible"
    :title="title"
    width="420px"
    min-height="0"
    :show-close="true"
    :close-on-click-modal="false"
    :close-on-press-escape="true"
    @update:visible="$emit('update:visible', $event)"
    @cancel="handleCancel"
  >
    <div class="confirm-message" v-html="sanitizedMessage" />

    <template #footer>
      <div class="confirm-actions">
        <AppButton @click="handleCancel">{{ cancelText }}</AppButton>
        <AppButton
          :variant="danger ? 'danger' : 'accent'"
          :loading="confirmLoading"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </AppButton>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import DOMPurify from 'dompurify'
import AppModal from './AppModal.vue'
import AppButton from './AppButton.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '确认' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'confirm', 'cancel'])

const confirmLoading = ref(false)

const sanitizedMessage = computed(() => DOMPurify.sanitize(props.message))

let _closing = false
function handleCancel() {
  if (_closing) return
  _closing = true
  emit('update:visible', false)
  emit('cancel')
}

watch(() => props.visible, (val) => {
  if (val) _closing = false
})

function handleConfirm() {
  if (_closing) return
  _closing = true
  emit('confirm', () => {
    // close 函数：供外部异步操作完成后手动关闭
    emit('update:visible', false)
    confirmLoading.value = false
  })
  // 如果外部是同步操作，立即设置 loading
  confirmLoading.value = true
}
</script>

<style lang="scss" scoped>
.confirm-message {
  text-align: center;
  padding: 12px 0;
  color: var(--text-regular);
  font-size: 14px;
  line-height: 1.8;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
