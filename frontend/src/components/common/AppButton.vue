<!--
  AppButton — 统一按钮组件

  封装 el-button，提供弹窗底部按钮等场景的统一变体样式。
  可直接替代 el-button 使用，额外支持 variant / size 属性。

  Props:
    variant  String   按钮变体：'default' | 'primary' | 'ai' | 'danger' | 'success' | 'warning'（默认 'default'）
    size     String   按钮尺寸：'small' | 'medium' | 'large'（默认 'medium'）
                       也可传具体值如 '32px'、'40px'，会覆盖高度
    其余 props 透传至 el-button（type / loading / disabled / icon 等）

  Events:
    click    点击事件

  Slots:
    default  按钮内容

  尺寸对照表：
    small  → 24px 高 / 8px 水平内边距 / 12px 字号
    medium → 36px 高 / 20px 水平内边距 / 13px 字号（默认）
    large  → 44px 高 / 28px 水平内边距 / 14px 字号

  使用示例：
    <AppButton>取消</AppButton>
    <AppButton size="small">小按钮</AppButton>
    <AppButton size="large">大按钮</AppButton>
    <AppButton variant="primary">新增</AppButton>
    <AppButton variant="ai" :loading="polishing">AI 润色</AppButton>
    <AppButton variant="danger">删除</AppButton>
    <AppButton variant="success">版本锁定</AppButton>
    <AppButton variant="warning">版本解锁</AppButton>

  弹窗 footer 布局示例：
    <template #footer>
      <div class="modal-footer-content">
        <AppButton variant="ai">AI 润色</AppButton>
        <div class="footer-right">
          <AppButton>取消</AppButton>
          <AppButton variant="primary">保存</AppButton>
        </div>
      </div>
    </template>
-->
<template>
  <el-button
    :class="['app-btn', variantClass, namedSizeClass]"
    :style="customSizeStyle"
    :size="elSize"
    v-bind="$attrs"
    @click="$emit('click', $event)"
  >
    <slot />
  </el-button>
</template>

<script setup>
import { computed } from 'vue'

const NAMED_SIZES = ['small', 'medium', 'large']

const props = defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'accent', 'ai', 'danger', 'success', 'warning', 'grey'].includes(v),
  },
  size: {
    type: String,
    default: 'medium',
  },
})

defineEmits(['click'])

const variantClass = computed(() => (props.variant !== 'default' ? `app-btn--${props.variant}` : ''))

// 映射到 el-button 的 size 属性
const elSize = computed(() => {
  if (props.size === 'small') return 'small'
  if (props.size === 'large') return 'large'
  return 'default'
})

// 命名尺寸走 class，具体值走 inline style
const namedSizeClass = computed(() => (NAMED_SIZES.includes(props.size) ? `app-btn--${props.size}` : ''))
const customSizeStyle = computed(() => {
  if (NAMED_SIZES.includes(props.size)) return {}
  // 传入具体尺寸值，如 '32px'、'40px'
  return { '--btn-h': props.size }
})
</script>

<style lang="scss" scoped>
// 基础样式：中号（默认）
.app-btn {
  --btn-h: 36px;
  --btn-px: 20px;
  --btn-fz: 13px;

  height: var(--btn-h);
  padding: 0 var(--btn-px);
  font-size: var(--btn-fz);
  font-weight: 500;
  border-radius: var(--radius-sm);
  transition: all var(--transition-normal);

  &:hover {
    transform: translateY(-1px);
  }

  &:active {
    transform: scale(0.97) translateY(0);
  }
}

// 小号
.app-btn--small {
  --btn-h: 24px;
  --btn-px: 8px;
  --btn-fz: 12px;
}

// 中号（与默认一致，显式声明便于理解）
.app-btn--medium {
  --btn-h: 36px;
  --btn-px: 20px;
  --btn-fz: 13px;
}

// 大号
.app-btn--large {
  --btn-h: 44px;
  --btn-px: 28px;
  --btn-fz: 14px;
}

// ===== 变体样式 =====
// 统一镂空风格：半透明背景 + 对应颜色边框 + 对应颜色文字
// disabled 时降低透明度，保留颜色语义

// 主操作（蓝色）
.app-btn--accent {
  background: rgba(99, 102, 241, 0.10) !important;
  border-color: rgba(99, 102, 241, 0.35) !important;
  color: #6366f1 !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(99, 102, 241, 0.20) !important;
    border-color: rgba(99, 102, 241, 0.55) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// AI 操作（蓝紫色）
.app-btn--ai {
  background: rgba(139, 92, 246, 0.10) !important;
  border-color: rgba(139, 92, 246, 0.35) !important;
  color: #8b5cf6 !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(139, 92, 246, 0.20) !important;
    border-color: rgba(139, 92, 246, 0.55) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// 危险操作（红色）
.app-btn--danger {
  background: rgba(248, 113, 113, 0.10) !important;
  border-color: rgba(248, 113, 113, 0.35) !important;
  color: #f87171 !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(248, 113, 113, 0.20) !important;
    border-color: rgba(248, 113, 113, 0.55) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// 成功操作（绿色）
.app-btn--success {
  background: rgba(52, 211, 153, 0.10) !important;
  border-color: rgba(52, 211, 153, 0.35) !important;
  color: #34d399 !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(52, 211, 153, 0.20) !important;
    border-color: rgba(52, 211, 153, 0.55) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// 警告操作（琥珀色）
.app-btn--warning {
  background: rgba(251, 191, 36, 0.10) !important;
  border-color: rgba(251, 191, 36, 0.35) !important;
  color: #fbbf24 !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(251, 191, 36, 0.20) !important;
    border-color: rgba(251, 191, 36, 0.55) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// 灰色（禁用态 / 低优先级操作）
.app-btn--grey {
  background: rgba(100, 116, 139, 0.06) !important;
  border-color: rgba(100, 116, 139, 0.25) !important;
  color: #64748b !important;

  &:hover:not(.is-disabled):not(:disabled) {
    background: rgba(100, 116, 139, 0.12) !important;
    border-color: rgba(100, 116, 139, 0.40) !important;
  }

  &.is-disabled, &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}
</style>
