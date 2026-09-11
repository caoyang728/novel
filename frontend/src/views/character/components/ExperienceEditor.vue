<template>
  <div class="exp-editor">
    <div v-for="(exp, index) in modelValue" :key="index" class="exp-row">
      <el-input
        v-model="exp.chapter"
        class="exp-chapter"
        placeholder="章节范围，如：第3章、第1-5章"
        maxlength="100"
      />
      <el-input
        v-model="exp.event"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 4 }"
        class="exp-event"
        placeholder="描述该章节发生的重要事件..."
        maxlength="2000"
      />
      <AppButton variant="danger" size="small" circle text @click="removeExp(index)">
        <el-icon><Delete /></el-icon>
      </AppButton>
    </div>

    <AppButton variant="accent" size="small" class="exp-add" @click="addExp">
      <el-icon><Plus /></el-icon>
      添加经历
    </AppButton>

    <p v-if="!modelValue.length" class="exp-hint">暂无经历记录，可按章节记录角色的关键事件。</p>
  </div>
</template>

<script setup>
import { Delete, Plus } from '@element-plus/icons-vue'

const props = defineProps({
  // [{ chapter, event }]
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

function addExp() {
  emit('update:modelValue', [...props.modelValue, { chapter: '', event: '' }])
}

function removeExp(index) {
  const list = [...props.modelValue]
  list.splice(index, 1)
  emit('update:modelValue', list)
}
</script>

<style lang="scss" scoped>
.exp-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.exp-row {
  display: grid;
  grid-template-columns: 180px 1fr auto;
  gap: 8px;
  align-items: start;
}

.exp-del {
  color: var(--danger);
  margin-top: 2px;
}

.exp-add {
  align-self: flex-start;
}

.exp-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

@media (max-width: 768px) {
  .exp-row {
    grid-template-columns: 1fr;
  }
}
</style>
