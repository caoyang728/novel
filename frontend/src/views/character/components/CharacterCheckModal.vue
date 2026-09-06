<template>
  <AppModal
    :visible="visible"
    title="AI 角色检测"
    width="780px"
    height="82vh"
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="check-body" v-loading="loading" element-loading-text="AI 正在检测所有角色...">
      <!-- 检测结果 -->
      <template v-if="phase === 'issues'">
        <div class="check-summary">
          <span class="summary-item">共 <b>{{ issues.length }}</b> 个问题</span>
          <span v-if="severityCount.high" class="summary-item high">严重 <b>{{ severityCount.high }}</b></span>
          <span v-if="severityCount.medium" class="summary-item medium">中等 <b>{{ severityCount.medium }}</b></span>
          <span v-if="severityCount.low" class="summary-item low">轻微 <b>{{ severityCount.low }}</b></span>
        </div>

        <div v-for="(issue, idx) in issues" :key="idx" class="issue-card">
          <div class="issue-header">
            <div class="issue-chars">
              <el-tag
                v-for="name in issue.characters || []"
                :key="name"
                size="small"
                effect="dark"
                round
              >
                {{ name }}
              </el-tag>
            </div>
            <el-tag size="small" effect="plain">{{ typeLabel(issue.type) }}</el-tag>
            <el-tag size="small" :type="severityTagType(issue.severity)" effect="dark">
              {{ severityLabel(issue.severity) }}
            </el-tag>
          </div>
          <div v-if="issue.field" class="issue-field">涉及字段：<code>{{ issue.field }}</code></div>
          <div class="issue-desc">{{ issue.description }}</div>
          <div v-if="issue.suggestion" class="issue-suggestion">
            <span class="sug-label">建议：</span>{{ issue.suggestion }}
          </div>
          <el-input
            v-model="issue.instruction"
            size="small"
            class="issue-instruction"
            placeholder="输入优化指示（留空则按建议自动优化）"
          />
        </div>
      </template>

      <!-- 优化结果 -->
      <template v-else-if="phase === 'optimizations'">
        <div class="check-summary">
          <span class="summary-item">AI 优化建议 <b>{{ optimizations.length }}</b> 项</span>
        </div>
        <p class="opt-hint">勾选要应用的优化，点击「保存优化」确认；优化保存后会自动同步反向关系。</p>

        <div v-for="(item, idx) in optimizations" :key="idx" class="opt-card">
          <div class="opt-header">
            <el-checkbox v-model="item.selected" />
            <span class="opt-name">{{ item.name }}</span>
            <el-tag size="small" :type="optTagType(item.type)" effect="dark">
              {{ optTypeLabel(item.type) }}
            </el-tag>
          </div>

          <div v-if="(item.params || []).length" class="opt-params">
            <div v-for="(p, pi) in item.params" :key="pi" class="opt-param">
              <div class="opt-param-label">{{ fieldLabel(p.param) }}</div>

              <!-- 关系字段：双向列表展示 -->
              <template v-if="p.param === 'relationships'">
                <div v-if="item.type !== 'add'" class="opt-rel-list">
                  <span class="opt-rel-sub">原值：</span>
                  <span v-for="(r, ri) in toArray(p.origin)" :key="'o' + ri" class="opt-value-old">
                    {{ formatRel(r) }}
                  </span>
                  <span v-if="!toArray(p.origin).length" class="opt-value-empty">无</span>
                </div>
                <div class="opt-rel-list">
                  <span class="opt-rel-sub">新值：</span>
                  <span v-for="(r, ri) in toArray(p.new)" :key="'n' + ri" class="opt-value-new">
                    {{ formatRel(r) }}
                  </span>
                </div>
              </template>

              <!-- 新增：只展示新值 -->
              <template v-else-if="item.type === 'add'">
                <div class="opt-value-new">{{ formatValue(p.new) }}</div>
              </template>

              <!-- 修改：原值 → 新值 -->
              <template v-else>
                <div class="opt-change-row">
                  <span class="opt-value-old">{{ hasValue(p.origin) ? formatValue(p.origin) : '无' }}</span>
                  <el-icon class="opt-arrow"><Right /></el-icon>
                  <span class="opt-value-new">{{ formatValue(p.new) }}</span>
                </div>
              </template>
            </div>
          </div>
          <div v-else-if="item.type === 'delete'" class="opt-delete-notice">
            该角色将被删除（可在角色列表中恢复）
          </div>
        </div>
      </template>

      <!-- 无问题 -->
      <EmptyState
        v-else-if="!loading && phase === 'no-issues'"
        icon="CircleCheck"
        text="所有角色设定良好，未发现设定矛盾、角色重复或其他问题"
      />
    </div>

    <template #footer>
      <AppButton @click="close">{{ phase === 'optimizations' ? '取消' : '关闭' }}</AppButton>
      <AppButton
        v-if="phase === 'issues'"
        variant="ai"
        :loading="optimizing"
        @click="runOptimize"
      >
        <el-icon><MagicStick /></el-icon>
        AI 优化
      </AppButton>
      <AppButton
        v-else-if="phase === 'optimizations'"
        variant="accent"
        :loading="saving"
        @click="saveOptimizations"
      >
        <el-icon><Check /></el-icon>
        保存优化
      </AppButton>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Right, MagicStick, Check } from '@element-plus/icons-vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { characterApi } from '@/api/character'
import { extractJsonFromString } from '@/utils/json'
import { showSuccess, showError, showWarning } from '@/utils/notify'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: '' },
})

const emit = defineEmits(['update:visible', 'saved'])

const CHECK_TYPE_LABELS = {
  contradiction: '设定矛盾',
  duplicate: '角色重复',
  conflict: '关系冲突',
  missing: '设定缺失',
  unreasonable: '逻辑不合理',
}

const OPT_TYPE_LABELS = { modify: '修改', add: '新增', delete: '删除' }

const FIELD_LABELS = {
  name: '姓名', gender: '性别', role_type: '角色定位', age: '年龄',
  identity: '身份/称号', personality: '性格特点', appearance: '外貌特征',
  faction: '势力/阵营', backstory: '背景故事', motivation: '核心动机',
  tagline: '标签', strengths: '优点', flaws: '缺点', obsession: '执念/软肋',
  abilities: '能力', taboos: '禁忌', secrets: '秘密', dark_history: '过往黑历史',
  development: '成长轨迹', weaknesses: '弱点/代价', relationships: '人际关系',
  experiences: '经历',
}

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 }

const loading = ref(false)
const optimizing = ref(false)
const saving = ref(false)
const phase = ref('idle') // idle | issues | no-issues | optimizations
const issues = ref([])
const optimizations = ref([])

const severityCount = computed(() => ({
  high: issues.value.filter((i) => i.severity === 'high').length,
  medium: issues.value.filter((i) => i.severity === 'medium').length,
  low: issues.value.filter((i) => i.severity === 'low').length,
}))

function typeLabel(t) {
  return CHECK_TYPE_LABELS[t] || t
}

function severityLabel(s) {
  return s === 'high' ? '严重' : s === 'medium' ? '中等' : '轻微'
}

function severityTagType(s) {
  return s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'info'
}

function optTypeLabel(t) {
  return OPT_TYPE_LABELS[t] || t
}

function optTagType(t) {
  return t === 'add' ? 'success' : t === 'delete' ? 'danger' : 'primary'
}

function fieldLabel(p) {
  return FIELD_LABELS[p] || p
}

function hasValue(v) {
  return v !== null && v !== undefined && v !== ''
}

function toArray(v) {
  if (!v) return []
  return Array.isArray(v) ? v : [v]
}

function formatValue(v) {
  if (v === null || v === undefined || v === '') return '无'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}

function formatRel(r) {
  if (r && typeof r === 'object') {
    const type = r.relationshipType || '其他'
    const target = r.targetName || '?'
    const desc = r.description ? `（${r.description}）` : ''
    return `${target} → ${type}${desc}`
  }
  if (typeof r === 'string') {
    const m = r.match(/(.+?)是我的(.+?)(?:\s*-\s*(.+))?$/)
    if (m) return `${m[1].trim()} → ${m[2].trim()}${m[3] ? `（${m[3].trim()}）` : ''}`
    return r
  }
  return String(r)
}

function close() {
  emit('update:visible', false)
}

async function runCheck() {
  if (!props.projectId) return
  loading.value = true
  phase.value = 'idle'
  issues.value = []
  try {
    const res = await characterApi.check(props.projectId)
    const parsed = extractJsonFromString(res?.data || '') || {}
    const list = Array.isArray(parsed.issues) ? parsed.issues : []
    list.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 2) - (SEVERITY_ORDER[b.severity] ?? 2))
    issues.value = list.map((i) => ({ ...i, instruction: '' }))
    phase.value = list.length ? 'issues' : 'no-issues'
  } catch (err) {
    console.error('角色检测失败:', err)
    showError(err.message || '检测失败，请重试')
    phase.value = 'no-issues'
  } finally {
    loading.value = false
  }
}

async function runOptimize() {
  if (!issues.value.length) return
  optimizing.value = true
  try {
    const issuesPayload = issues.value.map((i) => ({
      type: i.type,
      characters: i.characters || [],
      description: i.description || '',
      instruction: i.instruction?.trim() || i.suggestion || '请自动优化',
    }))
    const res = await characterApi.optimize(props.projectId, { issues: issuesPayload })
    const parsed = extractJsonFromString(res?.data || '')
    let list = []
    if (Array.isArray(parsed)) {
      list = parsed
    } else if (parsed && typeof parsed === 'object') {
      list = parsed.optimizations || parsed.data || []
    }
    optimizations.value = (Array.isArray(list) ? list : []).map((item) => ({ ...item, selected: true }))
    if (optimizations.value.length) {
      phase.value = 'optimizations'
      showSuccess('优化方案已生成，请勾选后保存')
    } else {
      showWarning('AI 未找到需要修改的内容')
    }
  } catch (err) {
    console.error('角色优化失败:', err)
    showError(err.message || '优化失败，请重试')
  } finally {
    optimizing.value = false
  }
}

async function saveOptimizations() {
  const items = optimizations.value.filter((i) => i.selected)
  if (!items.length) {
    showError('请至少选择一项优化')
    return
  }
  saving.value = true
  try {
    const res = await characterApi.optimizeSave(props.projectId, { optimizations: items })
    showSuccess(`已保存 ${res.saved_count ?? 0} 个角色的优化`)
    if (Array.isArray(res.warnings) && res.warnings.length) {
      showWarning(res.warnings.join('；'))
    }
    emit('saved')
    close()
  } catch (err) {
    console.error('保存优化失败:', err)
    showError(err.message || '保存失败，请重试')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      optimizations.value = []
      issues.value = []
      runCheck()
    }
  },
)
</script>

<style lang="scss" scoped>
.check-body {
  height: 100%;
  min-height: 300px;
}

.check-summary {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: var(--radius-sm);
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--text-secondary);

  b {
    color: var(--text-primary);
    font-size: 15px;
  }

  .summary-item.high b { color: var(--danger); }
  .summary-item.medium b { color: var(--warning); }
  .summary-item.low b { color: var(--text-muted); }
}

.issue-card,
.opt-card {
  padding: 14px 16px;
  margin-bottom: 12px;
  border-radius: var(--radius-md);
  background: var(--glass-bg, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--glass-border);
}

.issue-header,
.opt-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.issue-chars {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-right: auto;
}

.issue-field {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;

  code {
    background: rgba(99, 102, 241, 0.12);
    padding: 1px 6px;
    border-radius: 4px;
    color: var(--primary);
  }
}

.issue-desc {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.7;
  margin-bottom: 8px;
}

.issue-suggestion {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.7;
  padding: 8px 10px;
  margin-bottom: 10px;
  border-radius: var(--radius-sm);
  background: rgba(34, 197, 94, 0.06);
  border-left: 2px solid var(--success);

  .sug-label {
    color: var(--success);
    font-weight: 600;
  }
}

.issue-instruction {
  margin-top: 4px;
}

.opt-hint {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0 0 14px;
}

.opt-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-right: auto;
}

.opt-params {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-left: 28px;
}

.opt-param-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.opt-change-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
}

.opt-arrow {
  color: var(--primary);
  margin-top: 3px;
  flex-shrink: 0;
}

.opt-value-old {
  color: var(--text-muted);
  text-decoration: line-through;
  word-break: break-all;
  background: rgba(239, 68, 68, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}

.opt-value-new {
  color: var(--success);
  word-break: break-all;
  background: rgba(34, 197, 94, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
  white-space: pre-wrap;
}

.opt-value-empty {
  color: var(--text-muted);
  font-size: 12px;
}

.opt-rel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 4px;
}

.opt-rel-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.opt-delete-notice {
  padding-left: 28px;
  font-size: 13px;
  color: var(--danger);
}
</style>
