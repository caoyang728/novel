<template>
  <div class="empty-state">
    <el-icon class="empty-icon" :size="48">
      <component :is="icon" />
    </el-icon>
    <p class="empty-text">{{ text }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  icon: { type: [Object, String], default: 'Document' },
  text: { type: String, default: '暂无数据' },
})
</script>

<style lang="scss" scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
  flex: 1;
  height: 100%;
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-text {
  color: var(--text-muted);
  font-size: 14px;
  margin-bottom: 16px;
}
</style>
