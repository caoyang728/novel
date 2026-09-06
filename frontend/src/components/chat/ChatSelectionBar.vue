<template>
  <div v-if="visible" class="selection-bar glass-surface">
    <span class="selection-count">已选择 {{ count }} 条消息</span>
    <div class="selection-actions">
      <AppButton size="small" @click="$emit('copy')">
        <el-icon><CopyDocument /></el-icon>
        复制
      </AppButton>
      <AppButton size="small" @click="$emit('exit')">
        退出选择
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import { CopyDocument } from '@element-plus/icons-vue'
import AppButton from '@/components/common/AppButton.vue'

defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
})

defineEmits(['copy', 'exit'])
</script>

<style lang="scss" scoped>
.selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  margin: 0 16px;
  border-radius: var(--radius-sm);
}

.selection-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.selection-actions {
  display: flex;
  gap: 8px;
}
</style>
