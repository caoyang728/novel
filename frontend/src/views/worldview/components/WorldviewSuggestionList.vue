<template>
  <div class="suggestion-list">
    <div class="suggestion-toolbar">
      <span class="suggestion-count">共 {{ items.length }} 条修改建议</span>
      <div class="toolbar-btns">
        <AppButton size="small" @click="$emit('select-all', true)">
          <el-icon><SelectCheck /></el-icon>全选
        </AppButton>
        <AppButton size="small" @click="$emit('select-all', false)">
          <el-icon><Close /></el-icon>取消全选
        </AppButton>
      </div>
    </div>

    <div
      v-for="(s, i) in items"
      :key="i"
      class="suggestion-card glass-surface"
      :class="{ 'is-unchecked': !s.selected }"
    >
      <div class="suggestion-head">
        <el-checkbox v-model="s.selected">
          <span class="suggestion-index">修改 {{ i + 1 }}</span>
        </el-checkbox>
        <el-tag size="small" :type="impactType(s.impact)" effect="light">
          {{ impactLabel(s.impact) }}
        </el-tag>
      </div>

      <p class="suggestion-target">
        <el-tag size="small" type="primary" effect="plain">{{ layerName(s.targetLayer) }}</el-tag>
        <code class="field-path">{{ translatePath(s.targetField) }}</code>
      </p>

      <div class="suggestion-row">
        <span class="row-label">原值</span>
        <div class="old-value">{{ hasValue(s.oldValue) ? s.oldValue : '无' }}</div>
      </div>

      <div class="suggestion-row">
        <span class="row-label">新值</span>
        <el-input
          v-model="s.newValue"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 10 }"
          :disabled="!s.selected"
          placeholder="新设定内容"
        />
      </div>

      <div v-if="s.reason" class="suggestion-row">
        <span class="row-label">原因</span>
        <div class="reason">{{ s.reason }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/common/AppButton.vue'

defineProps({
  items: { type: Array, default: () => [] },
  layerName: { type: Function, required: true },
  translatePath: { type: Function, required: true },
})

defineEmits(['select-all'])

function hasValue(v) {
  return v !== null && v !== undefined && String(v).trim() !== '' && String(v).trim() !== '无'
}

function impactLabel(impact) {
  return { high: '影响较大', medium: '中等影响', low: '影响较小' }[impact] || impact || '影响未知'
}

function impactType(impact) {
  return { high: 'danger', medium: 'warning', low: 'info' }[impact] || 'info'
}
</script>

<style lang="scss" scoped>
.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.suggestion-count {
  font-size: 13px;
  color: var(--text-muted);
}

.toolbar-btns {
  display: flex;
  gap: 8px;
}

.suggestion-card {
  padding: 16px 18px;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: opacity var(--transition-fast);

  &.is-unchecked {
    opacity: 0.55;
  }
}

.suggestion-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.suggestion-index {
  font-weight: 600;
  color: var(--text-primary);
}

.suggestion-target {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.field-path {
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
}

.suggestion-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.row-label {
  flex-shrink: 0;
  width: 36px;
  font-size: 12px;
  color: var(--text-muted);
  padding-top: 4px;
}

.old-value {
  flex: 1;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.reason {
  flex: 1;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}
</style>
