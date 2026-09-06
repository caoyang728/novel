<template>
  <AppButton
    :variant="danger ? 'danger' : 'default'"
    @click="handleClick"
  >
    <slot>{{ label }}</slot>
  </AppButton>
</template>

<script setup>
import { showConfirmModal } from '@/utils/modal'
import AppButton from './AppButton.vue'

const props = defineProps({
  label: { type: String, default: '确认' },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' },
  danger: { type: Boolean, default: false },
  confirmText: { type: String, default: '确认' },
})

const emit = defineEmits(['confirm'])

function handleClick() {
  showConfirmModal({
    title: props.title,
    message: props.message,
    danger: props.danger,
    confirmText: props.confirmText,
    onConfirm: async (close) => {
      emit('confirm', close)
    },
  })
}
</script>
