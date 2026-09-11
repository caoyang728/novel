<template>
  <div class="rel-editor">
    <div v-for="(rel, index) in modelValue" :key="index" class="rel-row">
      <el-select
        v-model="rel.targetName"
        filterable
        allow-create
        default-first-option
        class="rel-target"
        placeholder="选择或输入角色名"
      >
        <el-option
          v-for="c in characters"
          :key="c.id ?? c.name"
          :label="c.name"
          :value="c.name"
        />
      </el-select>

      <el-select
        v-model="rel.relationshipType"
        filterable
        allow-create
        default-first-option
        class="rel-type"
        placeholder="关系类型"
      >
        <el-option v-for="t in relationshipTypes" :key="t" :label="t" :value="t" />
      </el-select>

      <el-input
        v-model="rel.description"
        class="rel-desc"
        placeholder="关系描述（可选）"
        maxlength="200"
      />

      <el-button class="rel-del" circle text @click="removeRel(index)">
        <el-icon><Delete /></el-icon>
      </el-button>
    </div>

    <el-button class="rel-add" plain @click="addRel">
      <el-icon><Plus /></el-icon>
      添加关系
    </el-button>

    <p v-if="!modelValue.length" class="rel-hint">
      暂无人际关系。约定：以当前角色为基准，描述对方相对于本人的关系，保存时系统会自动同步反向关系。
    </p>
  </div>
</template>

<script setup>
import { Delete, Plus } from '@element-plus/icons-vue'
import AppButton from '@/components/common/AppButton.vue'

const props = defineProps({
  // [{ targetName, relationshipType, description, createReverse }]
  modelValue: { type: Array, default: () => [] },
  // 可选角色列表 [{ id, name }]
  characters: { type: Array, default: () => [] },
  // 关系类型白名单（后端动态获取）
  relationshipTypes: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

function addRel() {
  emit('update:modelValue', [
    ...props.modelValue,
    { targetName: '', relationshipType: '朋友', description: '', createReverse: true },
  ])
}

function removeRel(index) {
  const list = [...props.modelValue]
  list.splice(index, 1)
  emit('update:modelValue', list)
}
</script>

<style lang="scss" scoped>
.rel-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rel-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1.6fr auto;
  gap: 8px;
  align-items: center;
}

.rel-del {
  color: var(--danger);
  flex-shrink: 0;
}

.rel-add {
  align-self: flex-start;
}

.rel-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0;
}

@media (max-width: 768px) {
  .rel-row {
    grid-template-columns: 1fr 1fr;
  }
  .rel-desc {
    grid-column: 1 / -1;
  }
}
</style>
