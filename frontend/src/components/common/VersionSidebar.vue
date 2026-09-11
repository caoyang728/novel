<template>
  <div class="version-sidebar glass-surface">
    <div class="version-header">
      <span class="version-title">版本列表</span>
      <el-button size="small" text @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <div class="version-list" v-loading="loading">
      <div v-if="versions.length === 0" class="version-empty">
        暂无版本
      </div>
      <div
        v-for="version in versions"
        :key="version.id"
        class="version-item"
        :class="{ active: currentVersionId === version.id, finalized: version.is_finalized }"
        @click="$emit('select', version)"
      >
        <div class="version-info">
          <span class="version-number">v{{ version.version_number }}</span>
          <el-tag v-if="version.is_finalized" type="success" size="small">已定稿</el-tag>
        </div>
        <div class="version-meta">
          {{ formatDate(version.created_at, 'datetime') }}
        </div>
        <div class="version-actions" @click.stop>
          <el-button
            v-if="!version.is_finalized"
            size="small"
            text
            type="success"
            @click="$emit('finalize', version)"
          >
            定稿
          </el-button>
          <el-button
            size="small"
            text
            type="danger"
            @click="$emit('delete', version)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Refresh } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'

defineProps({
  versions: { type: Array, default: () => [] },
  currentVersionId: { type: [Number, String, null], default: null },
  loading: { type: Boolean, default: false },
})

defineEmits(['select', 'delete', 'finalize', 'refresh'])
</script>

<style lang="scss" scoped>
.version-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--glass-border);
}

.version-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.version-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.version-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 24px 0;
  font-size: 13px;
}

.version-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 4px;

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  &.active {
    background: rgba(129, 140, 248, 0.1);
    border: 1px solid rgba(129, 140, 248, 0.2);
  }

  &.finalized {
    opacity: 0.7;
  }
}

.version-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.version-number {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}

.version-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.version-actions {
  display: flex;
  gap: 4px;
}
</style>
