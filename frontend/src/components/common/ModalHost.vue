<template>
  <!-- 命令式弹窗宿主：渲染 utils/modal.js 推入 modalStack 的弹窗 -->
  <template v-for="m in modalStack" :key="m.id">
    <!-- 确认弹窗 -->
    <AppConfirmModal
      v-if="m.kind === 'confirm'"
      :visible="m.visible"
      :title="m.props.title"
      :message="m.props.message"
      :confirm-text="m.props.confirmText"
      :cancel-text="m.props.cancelText"
      :danger="m.props.danger"
      @update:visible="(v) => handleVisibleChange(m, v)"
      @confirm="() => handleConfirm(m)"
      @cancel="() => handleCancel(m)"
    />

    <!-- 通用弹窗 -->
    <AppModal
      v-else
      :visible="m.visible"
      v-bind="m.props"
      @update:visible="(v) => handleVisibleChange(m, v)"
      @cancel="() => handleModalCancel(m)"
    >
      <VNodeRenderer :vnode="m.bodyVnode" />
      <template v-if="m.footerVnode" #footer>
        <VNodeRenderer :vnode="m.footerVnode" />
      </template>
    </AppModal>
  </template>
</template>

<script setup>
import { defineComponent } from 'vue'
import AppModal from './AppModal.vue'
import AppConfirmModal from './AppConfirmModal.vue'
import { modalStack } from '@/utils/modal'

// 渲染外部传入的 VNode
const VNodeRenderer = defineComponent({
  name: 'VNodeRenderer',
  props: { vnode: { type: [Object, null], default: null } },
  render() {
    return this.vnode
  },
})

function dismiss(m) {
  if (m._dismissing) return
  m._dismissing = true
  m.visible = false
  // 等待关闭过渡结束后从栈中移除（与 utils/modal.js 的 CLOSE_DELAY 对齐）
  setTimeout(() => {
    const i = modalStack.findIndex((x) => x.id === m.id)
    if (i !== -1) modalStack.splice(i, 1)
  }, 320)
}

function handleVisibleChange(m, val) {
  if (!val) dismiss(m)
}

function handleConfirm(m) {
  if (typeof m.onConfirm === 'function') {
    m.onConfirm(() => dismiss(m))
  } else {
    dismiss(m)
  }
}

function handleCancel(m) {
  if (typeof m.onCancel === 'function') m.onCancel()
  dismiss(m)
}

function handleModalCancel(m) {
  if (typeof m.onCancel === 'function') m.onCancel()
  dismiss(m)
}
</script>
