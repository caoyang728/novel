<template>
  <div class="char-fields">
    <template v-for="group in visibleGroups" :key="group.key">
      <div v-if="tab === 'all'" class="fields-section-title">
        <span class="title-bar"></span>{{ group.title }}
      </div>
      <div class="fields-grid">
        <div
          v-for="f in group.fields"
          :key="f.key"
          class="field-item"
          :class="{ 'field-full': f.full }"
        >
          <label class="field-label">
            {{ f.label }}<span v-if="f.required" class="req">*</span>
          </label>

          <el-select
            v-if="f.type === 'select'"
            v-model="form[f.key]"
            class="field-control"
            :placeholder="f.placeholder"
          >
            <el-option v-for="o in f.options" :key="o" :label="o" :value="o" />
          </el-select>

          <el-input-number
            v-else-if="f.type === 'number'"
            v-model="form[f.key]"
            class="field-control"
            :min="0"
            :max="9999"
            controls-position="right"
            :placeholder="f.placeholder"
          />

          <el-input
            v-else-if="f.type === 'textarea'"
            v-model="form[f.key]"
            type="textarea"
            :autosize="{ minRows: f.rows || 2, maxRows: 12 }"
            resize="vertical"
            :placeholder="f.placeholder"
            :maxlength="5000"
            show-word-limit
          />

          <el-input
            v-else
            v-model="form[f.key]"
            :placeholder="f.placeholder"
            :maxlength="f.maxlength"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 响应式角色表单对象（直接 v-model 绑定其属性）
  form: { type: Object, required: true },
  // 'all' 显示全部分组（带分组标题）；或指定单个分组 key
  tab: { type: String, default: 'all' },
})

const GENDER_OPTIONS = ['未知', '男', '女']
const ROLE_OPTIONS = ['配角', '主角', '反派', '路人']

const GROUPS = [
  {
    key: 'basic',
    title: '基础身份',
    fields: [
      { key: 'name', label: '角色名称', type: 'input', required: true, placeholder: '输入角色名称', maxlength: 100 },
      { key: 'gender', label: '性别', type: 'select', options: GENDER_OPTIONS },
      { key: 'role_type', label: '角色定位', type: 'select', options: ROLE_OPTIONS },
      { key: 'age', label: '年龄', type: 'number', placeholder: '如：25' },
      { key: 'identity', label: '身份/称号', type: 'input', placeholder: '如：青云门执法堂首座', full: true },
      { key: 'faction', label: '势力/阵营', type: 'input', placeholder: '多个势力用逗号分隔', full: true },
      { key: 'tagline', label: '标签', type: 'input', placeholder: '3-6 个关键词，逗号分隔', full: true },
    ],
  },
  {
    key: 'mind',
    title: '性格与心理',
    fields: [
      { key: 'personality', label: '性格特点', type: 'textarea', rows: 3, full: true, placeholder: '外在表现 + 内在真实 + 矛盾核心' },
      { key: 'strengths', label: '优点/特长', type: 'textarea', rows: 2, placeholder: '天赋、品性、资源等' },
      { key: 'flaws', label: '缺点', type: 'textarea', rows: 2, placeholder: '性格/认知缺陷' },
      { key: 'obsession', label: '执念/软肋', type: 'textarea', rows: 2, placeholder: '角色行为的底层驱动力' },
      { key: 'motivation', label: '核心动机', type: 'textarea', rows: 2, placeholder: '当前阶段最想达成的目标' },
      { key: 'taboos', label: '禁忌', type: 'textarea', rows: 2, placeholder: '绝对不可触碰的底线' },
    ],
  },
  {
    key: 'ability',
    title: '外貌与能力',
    fields: [
      { key: 'appearance', label: '外貌特征', type: 'textarea', rows: 3, full: true, placeholder: '突出 1-2 个高辨识度特征' },
      { key: 'abilities', label: '能力', type: 'textarea', rows: 2, placeholder: '具体可执行的技能/功法' },
      { key: 'weaknesses', label: '弱点/代价', type: 'textarea', rows: 2, placeholder: '生理/能力层面的明确短板' },
    ],
  },
  {
    key: 'story',
    title: '背景与成长',
    fields: [
      { key: 'backstory', label: '背景故事', type: 'textarea', rows: 4, full: true, placeholder: '出身、关键转折、何以走到当前处境' },
      { key: 'development', label: '成长轨迹', type: 'textarea', rows: 3, full: true, placeholder: '从故事开端到结局的转变路径' },
    ],
  },
]

const visibleGroups = computed(() =>
  props.tab === 'all' ? GROUPS : GROUPS.filter((g) => g.key === props.tab),
)
</script>

<style lang="scss" scoped>
.fields-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 18px 0 12px;

  &:first-child {
    margin-top: 0;
  }

  .title-bar {
    width: 3px;
    height: 14px;
    border-radius: 2px;
    background: var(--primary);
  }
}

.fields-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;

  .req {
    color: var(--danger);
    margin-left: 2px;
  }
}

.field-control {
  width: 100%;
}

@media (max-width: 768px) {
  .fields-grid {
    grid-template-columns: 1fr;
  }
}
</style>
