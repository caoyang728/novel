<!--
  AppModal — 通用弹窗组件

  基于 el-dialog 封装，提供蒙层、动画、z-index 管理、焦点管理等能力。

  DOM 结构:
    el-overlay                      ← Element Plus 蒙层（自动管理）
      el-dialog.app-glass-dialog    ← 弹窗主体
        el-dialog__header           ← 标题 + 关闭按钮
        el-dialog__body
          .app-modal-body           ← body 容器（默认 padding: 10px 14px）
            <slot />                ← 页面内容
        el-dialog__footer
          <slot name="footer" />    ← 按钮区（单个 slot，由页面自行布局）

  Props:
    visible          Boolean  控制弹窗显示/隐藏（v-model:visible）
    title            String   弹窗标题
    width            String   弹窗宽度，默认 '520px'
    height           String   弹窗高度，默认 'auto'（非 auto 时启用 overflow-y）
    minHeight        String   最小高度覆盖
    showClose        Boolean  是否显示关闭按钮，默认 true
    closeOnClickModal Boolean 点击蒙层是否关闭，默认 false
    closeOnPressEscape Boolean 按 ESC 是否关闭，默认 true
    alignCenter      Boolean  居中显示，默认 true
    blur             Boolean  蒙层模糊效果，默认 true

  Events:
    update:visible   v-model 绑定
    close            关闭时触发
    closed           关闭动画结束后触发
    cancel           取消操作时触发
    confirm          确认操作时触发

  Body padding 策略:
    - 简单表单弹窗：直接使用 .app-modal-body 默认 padding，无需额外处理
    - 全高滚动弹窗：页面容器（如 .edit-modal-container）自行控制 padding，
      用 margin: 0 -14px 抵消父级默认 padding

  Footer 按钮规范:
    footer 使用单个 #footer slot，页面自行组织按钮位置。统一使用以下 class：
    - .footer-btn   统一按钮尺寸（36px 高、8px 圆角、hover 上浮动效）
    - .ai-btn       AI 按钮（紫色半透明背景）
    - .save-btn     保存按钮（加粗字体）

    布局结构：
    <template #footer>
      <div class="modal-footer-content">
        <el-button class="footer-btn ai-btn">左侧按钮</el-button>
        <div class="footer-right">
          <el-button class="footer-btn">取消</el-button>
          <el-button type="primary" class="footer-btn save-btn">保存</el-button>
        </div>
      </div>
    </template>
-->
<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    :width="width"
    :show-close="showClose"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="closeOnPressEscape"
    :align-center="alignCenter"
    class="app-glass-dialog"
    @close="handleClose"
    @closed="handleClosed"
  >
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <div
      class="app-modal-body"
      :style="bodyStyle"
    >
      <slot />
    </div>

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '520px' },
  height: { type: String, default: 'auto' },
  minHeight: { type: String, default: undefined },
  showClose: { type: Boolean, default: true },
  closeOnClickModal: { type: Boolean, default: false },
  closeOnPressEscape: { type: Boolean, default: true },
  alignCenter: { type: Boolean, default: true },
  blur: { type: Boolean, default: true },
})

const emit = defineEmits(['update:visible', 'close', 'closed', 'cancel', 'confirm'])

const bodyStyle = computed(() => {
  const style = {}
  if (props.height && props.height !== 'auto') {
    style.height = props.height
    style.overflowY = 'auto'
  }
  if (props.minHeight) {
    style.minHeight = props.minHeight
  }
  return style
})

function handleClose() {
  emit('update:visible', false)
  emit('cancel')
}

function handleClosed() {
  emit('closed')
}
</script>

<style lang="scss" scoped>
.app-modal-body {
  color: var(--text-regular);
  line-height: 1.6;
  flex: 1;
  min-height: 0; // 允许 flex 子元素收缩
  padding: 10px 14px;
}
</style>
