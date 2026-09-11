<template>
  <AppModal
    :visible="visible"
    :title="modalTitle"
    width="860px"
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="modal-body-wrapper">
      <!-- 检测阶段 -->
      <div v-if="phase === 'candidates'" class="candidate-phase">
        <!-- 流式分析阶段 -->
        <div v-if="streaming" class="streaming-phase">
          <div class="streaming-header">
            <div class="streaming-spinner" />
            <span class="streaming-label">AI 正在分析大纲，提取角色信息...</span>
          </div>
          <div class="streaming-terminal" ref="terminalRef">
            <span class="streaming-text">{{ streamingText }}</span>
            <span class="streaming-cursor" />
          </div>
        </div>
        <!-- 候选列表阶段 -->
        <div v-else v-loading="loading" :element-loading-text="loadingText">
        <div class="candidate-summary">
          <span class="summary-item">共识别 <b>{{ candidates.length }}</b> 个角色</span>
          <span v-if="newCount > 0" class="summary-item new">新角色 <b>{{ newCount }}</b></span>
          <span v-if="existingCount > 0" class="summary-item existing">已有角色 <b>{{ existingCount }}</b></span>
        </div>

        <div class="candidate-list">
          <div v-if="candidates.length === 0 && !loading" class="candidate-empty">
            <el-icon class="empty-icon"><Warning /></el-icon>
            <span>未识别到角色，请检查大纲内容是否充分</span>
          </div>
          <div
            v-for="(item, idx) in candidates"
            :key="idx"
            class="candidate-card"
            :class="{ 'is-existing': !item.is_new, 'is-selected': item.selected, 'is-editing': editingIdx === idx }"
          >
            <!-- 查看模式 -->
            <template v-if="editingIdx !== idx">
              <div class="card-header">
                <el-checkbox v-model="item.selected" :disabled="!item.is_new" />
                <span class="card-name">{{ item.name }}</span>
                <el-tag v-if="!item.is_new" size="small" type="info" effect="plain">已有</el-tag>
                <el-tag v-else size="small" type="success" effect="dark">新</el-tag>
                <el-tag size="small" effect="plain">{{ item.role_type || '未知' }}</el-tag>
                <span v-if="item.gender" class="card-gender">{{ item.gender }}</span>
                <span v-if="item.age" class="card-age">{{ item.age }}岁</span>
                <el-icon
                  v-if="item.is_new"
                  class="card-edit-btn"
                  title="编辑候选角色"
                  @click.stop="startEdit(idx)"
                ><Edit /></el-icon>
              </div>
              <div class="card-details">
                <div v-if="item.identity" class="detail-row">
                  <span class="detail-label">身份：</span>
                  <span>{{ item.identity }}</span>
                </div>
                <div v-if="item.faction" class="detail-row">
                  <span class="detail-label">势力：</span>
                  <span>{{ item.faction }}</span>
                </div>
              </div>
              <div v-if="item.content" class="card-content-preview">
                <div class="detail-row">
                  <span class="detail-label">内容：</span>
                  <span>{{ truncate(item.content, 200) }}</span>
                </div>
              </div>
              <div v-if="item.relationships?.length" class="card-details">
                <div class="detail-row">
                  <span class="detail-label">关系：</span>
                  <span>{{ formatRelationships(item.relationships) }}</span>
                </div>
              </div>
            </template>

            <!-- 编辑模式 -->
            <template v-else>
              <div class="edit-form">
                <div class="edit-row">
                  <label class="edit-label">姓名</label>
                  <el-input v-model="editDraft.name" size="small" placeholder="角色名称" maxlength="100" class="edit-input" />
                </div>
                <div class="edit-row">
                  <label class="edit-label">角色定位</label>
                  <el-select v-model="editDraft.role_type" size="small" class="edit-input">
                    <el-option label="主角" value="主角" />
                    <el-option label="反派" value="反派" />
                    <el-option label="配角" value="配角" />
                    <el-option label="路人" value="路人" />
                  </el-select>
                </div>
                <div class="edit-row-half">
                  <div class="edit-row">
                    <label class="edit-label">性别</label>
                    <el-select v-model="editDraft.gender" size="small" class="edit-input">
                      <el-option label="男" value="男" />
                      <el-option label="女" value="女" />
                      <el-option label="未知" value="未知" />
                    </el-select>
                  </div>
                  <div class="edit-row">
                    <label class="edit-label">年龄</label>
                    <el-input-number v-model="editDraft.age" size="small" :min="0" :max="9999" controls-position="right" class="edit-input" />
                  </div>
                </div>
                <div class="edit-row">
                  <label class="edit-label">身份/称号</label>
                  <el-input v-model="editDraft.identity" size="small" placeholder="如：青云门执法堂首座" maxlength="200" class="edit-input" />
                </div>
                <div class="edit-actions">
                  <AppButton variant="default" size="small" @click="cancelEdit">
                    <el-icon><Close /></el-icon> 取消
                  </AppButton>
                  <AppButton variant="accent" size="small" @click="confirmEdit">
                    <el-icon><Check /></el-icon> 确认
                  </AppButton>
                </div>
              </div>
            </template>
          </div>
        </div>
        </div>
      </div>

      <!-- 结果阶段 -->
      <div v-else-if="phase === 'result'" class="result-phase">
        <div class="result-body">
          <div v-if="createdCount > 0" class="result-success">
            <el-icon class="result-icon"><CircleCheck /></el-icon>
            <span>成功创建 <b>{{ createdCount }}</b> 个角色</span>
          </div>
          <div v-if="resultErrors.length" class="result-errors">
            <div v-for="(err, i) in resultErrors" :key="i" class="result-error-item">
              {{ err }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <AppButton @click="close">{{ phase === 'result' ? '关闭' : '取消' }}</AppButton>
      <AppButton
        v-if="phase === 'candidates'"
        variant="accent"
        :loading="creating"
        :disabled="selectedNewCount === 0"
        @click="handleBatchCreate"
      >
        <el-icon><Plus /></el-icon>
        创建选中角色（{{ selectedNewCount }}）
      </AppButton>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { Plus, CircleCheck, Warning, Edit, Check, Close } from '@element-plus/icons-vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import { streamRequestRaw } from '@/api/sse'
import { characterApi } from '@/api/character'
import { showSuccess, showError } from '@/utils/notify'
import { normalizeRoleType } from '../characterUtils'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: '' },
  source: { type: String, default: 'outline' }, // outline | volume | chapter
  volumeId: { type: [String, Number], default: null },
  outlineId: { type: [String, Number], default: null },
})

const emit = defineEmits(['update:visible', 'created'])

const SOURCE_TITLES = {
  outline: '从大纲生成角色',
  volume: '从卷生成角色',
  chapter: '章节中发现新角色',
}

const loading = ref(false)
const creating = ref(false)
const streaming = ref(false)
const streamingText = ref('')
const phase = ref('candidates') // candidates | result
const candidates = ref([])
const existingCharacters = ref([])
const createdCount = ref(0)
const resultErrors = ref([])
const terminalRef = ref(null)
let abortController = null

const modalTitle = computed(() => SOURCE_TITLES[props.source] || '生成角色')
const loadingText = computed(() => creating.value ? '正在创建角色...' : 'AI 正在分析中...')
const newCount = computed(() => candidates.value.filter(c => c.is_new).length)
const existingCount = computed(() => candidates.value.filter(c => !c.is_new).length)
const selectedNewCount = computed(() => candidates.value.filter(c => c.is_new && c.selected).length)

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function formatRelationships(rels) {
  if (!Array.isArray(rels)) return ''
  return rels.map(r => {
    if (typeof r === 'object') {
      return `${r.targetName}(${r.relationshipType})`
    }
    return String(r)
  }).join('、')
}

function close() {
  // 关闭时中止 SSE 流
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  emit('update:visible', false)
}

onUnmounted(() => {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
})

// ---- 内联编辑 ----
const editingIdx = ref(-1)
const editDraft = ref({})

function startEdit(idx) {
  const c = candidates.value[idx]
  editDraft.value = {
    name: c.name || '',
    role_type: c.role_type || '配角',
    gender: c.gender || '未知',
    age: c.age ?? null,
    identity: c.identity || '',
  }
  editingIdx.value = idx
}

function confirmEdit() {
  const idx = editingIdx.value
  if (idx < 0) return
  const c = candidates.value[idx]
  c.name = editDraft.value.name.trim() || c.name
  c.role_type = normalizeRoleType(editDraft.value.role_type)
  c.gender = editDraft.value.gender
  c.age = editDraft.value.age === '' || editDraft.value.age === null ? null : Number(editDraft.value.age)
  c.identity = editDraft.value.identity
  editingIdx.value = -1
}

function cancelEdit() {
  editingIdx.value = -1
}

async function fetchCandidates() {
  if (!props.projectId) return
  loading.value = true
  streaming.value = true
  streamingText.value = ''
  phase.value = 'candidates'
  candidates.value = []
  resultErrors.value = []
  createdCount.value = 0

  // 构建请求 URL 和 body
  let url, body
  if (props.source === 'volume') {
    url = `/api/projects/${props.projectId}/characters/generate-from-volume/`
    body = { volume_id: props.volumeId }
  } else {
    url = `/api/projects/${props.projectId}/characters/generate-from-outline/`
    body = { outline_id: props.outlineId }
  }

  abortController = new AbortController()

  try {
    await streamRequestRaw(
      url,
      {
        method: 'POST',
        body,
        signal: abortController.signal,
        timeout: 600000,
        // onComplete: 解析最终候选列表
        onComplete: (evt) => {
          const list = Array.isArray(evt.candidates) ? evt.candidates : []
          existingCharacters.value = evt.existing_characters || []
          candidates.value = list.map(c => ({
            ...c,
            selected: c.is_new !== false,
            expanded: false,
          }))
        },
      },
      // onChunk: 实时追加流式文本
      (chunk) => {
        streamingText.value += chunk
        // 自动滚动到底部
        nextTick(() => {
          if (terminalRef.value) {
            terminalRef.value.scrollTop = terminalRef.value.scrollHeight
          }
        })
      },
    )
  } catch (err) {
    if (err.message !== '请求已取消或超时') {
      console.error('生成角色候选失败:', err)
      showError(err.message || '生成失败，请重试')
      close()
    }
  } finally {
    streaming.value = false
    loading.value = false
    abortController = null
  }
}

async function handleBatchCreate() {
  const selected = candidates.value.filter(c => c.is_new && c.selected)
  if (!selected.length) {
    showError('请至少选择一个新角色')
    return
  }
  creating.value = true
  try {
    const characters = selected.map(c => ({
      name: c.name,
      role_type: c.role_type || '配角',
      gender: c.gender || '未知',
      age: c.age || null,
      identity: c.identity || '',
      faction: c.faction || '',
      tagline: c.tagline || '',
      content: c.content || '',
      relationships: c.relationships || [],
      source: props.source === 'outline' ? 'outline_extract'
        : props.source === 'volume' ? 'volume_extract'
        : 'chapter_discover',
    }))
    const res = await characterApi.batchCreate(props.projectId, { characters })
    createdCount.value = res.created_count || 0
    resultErrors.value = res.errors || []
    phase.value = 'result'
    if (createdCount.value > 0) {
      showSuccess(`成功创建 ${createdCount.value} 个角色`)
      emit('created')
    }
  } catch (err) {
    console.error('批量创建角色失败:', err)
    showError(err.message || '创建失败，请重试')
  } finally {
    creating.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      fetchCandidates()
    }
  },
)
</script>

<style lang="scss" scoped>
/*
  布局结构 (纯 flex，无固定高度):
  el-dialog.app-glass-dialog (flex column, max-height: 90vh)
  ├── el-dialog__header (固定)
  ├── el-dialog__body (flex: 1, flex column, overflow: hidden)
  │   └── .app-modal-body (flex: 1, flex column)
  │       └── .modal-body-wrapper (flex: 1, flex column, overflow: hidden)
  │           ├── .candidate-phase (flex: 1, flex column) — 检测阶段
  │           │   ├── .candidate-summary (固定, flex-shrink: 0)
  │           │   └── .candidate-list (flex: 1, overflow-y: auto) ← 内部滚动
  │           └── .result-phase (flex: 1, flex column) — 结果阶段
  └── el-dialog__footer (固定)
*/

.modal-body-wrapper {
  flex: 1;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.candidate-phase,
.result-phase {
  flex: 1;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ---- 流式分析阶段 ---- */
.streaming-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.streaming-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--text-secondary);
}

.streaming-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(99, 102, 241, 0.25);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.streaming-label {
  font-weight: 500;
}

.streaming-terminal {
  flex: 1;
  min-height: 80px;
  max-height: 120px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--glass-bg, rgba(0, 0, 0, 0.2));
  border: 1px solid var(--glass-border);
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.streaming-text {
  opacity: 0.85;
}

.streaming-cursor {
  display: inline-block;
  width: 6px;
  height: 14px;
  background: var(--primary);
  margin-left: 1px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.candidate-summary {
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
  flex-shrink: 0;

  b {
    color: var(--text-primary);
    font-size: 15px;
  }

  .summary-item.new b { color: var(--success); }
  .summary-item.existing b { color: var(--text-muted); }
}

.candidate-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.candidate-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: 14px;

  .empty-icon {
    font-size: 36px;
    opacity: 0.4;
  }
}

.candidate-card {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: var(--glass-bg, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--glass-border);
  transition: all 0.2s;

  &:hover {
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
  }

  &.is-selected {
    border-color: var(--primary);
    background: rgba(99, 102, 241, 0.06);
  }

  &.is-existing {
    opacity: 0.55;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-right: auto;
}

.card-gender,
.card-age {
  font-size: 12px;
  color: var(--text-muted);
}

.card-details {
  padding-left: 32px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-row {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);

  .detail-label {
    color: var(--text-muted);
    flex-shrink: 0;
  }
}

.card-expand {
  padding-left: 32px;
  margin-top: 6px;
}

.result-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.result-success {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: var(--text-primary);

  .result-icon {
    font-size: 24px;
    color: var(--success);
  }

  b {
    color: var(--success);
    font-size: 20px;
  }
}

.result-errors {
  width: 100%;
  max-width: 500px;
}

.result-error-item {
  font-size: 13px;
  color: var(--warning);
  padding: 6px 10px;
  background: rgba(251, 191, 36, 0.08);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
}

// 内联编辑
.card-edit-btn {
  margin-left: auto;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 14px;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.2s;

  &:hover {
    color: var(--primary);
    background: rgba(99, 102, 241, 0.1);
  }
}

.is-editing {
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.06);
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.edit-row-half {
  display: flex;
  gap: 12px;

  .edit-row {
    flex: 1;
  }
}

.edit-label {
  width: 72px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-muted);
  text-align: right;
}

.edit-input {
  flex: 1;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>
