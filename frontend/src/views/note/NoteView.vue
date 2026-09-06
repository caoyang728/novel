<template>
  <div class="note-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="accent" @click="openAddModal">
        <el-icon><Plus /></el-icon> 新建笔记
      </AppButton>
    </Teleport>
    <div class="note-layout" v-loading="loading">
      <!-- 左侧：列表 -->
      <aside class="note-list glass-surface">
        <div class="list-filters">
          <el-input
            v-model="searchQuery"
            placeholder="搜索笔记..."
            clearable
            size="small"
            :prefix-icon="Search"
          />
          <el-select v-model="statusFilter" size="small" class="status-filter">
            <el-option label="全部" value="" />
            <el-option label="未使用" value="unused" />
            <el-option label="已使用" value="used" />
            <el-option label="已发布" value="published" />
          </el-select>
        </div>

        <div class="list-body">
          <EmptyState v-if="filteredNotes.length === 0" icon="EditPen" text="暂无随手记" />
          <div
            v-for="note in filteredNotes"
            :key="note.id"
            class="note-item"
            :class="{ active: currentNote?.id === note.id }"
            @click="selectNote(note.id)"
          >
            <div class="note-item-title text-ellipsis">{{ note.title || '无标题' }}</div>
            <div class="note-item-preview">{{ note.content }}</div>
            <div class="note-item-footer">
              <span class="note-item-date">{{ note.created_at }}</span>
              <el-tag size="small" :type="statusTagType(note.status)" effect="plain">
                {{ note.status_display || STATUS_LABELS[note.status] }}
              </el-tag>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：编辑器 -->
      <section class="note-editor glass-panel">
        <EmptyState v-if="!currentNote" icon="EditPen" text="选择左侧笔记查看，或新建一条" />

        <template v-else>
          <div class="editor-header">
            <el-input
              v-model="form.title"
              class="title-input"
              :disabled="!editing"
              placeholder="标题"
              size="large"
            />
            <div class="editor-meta">
              <span class="update-time">
                <el-icon><Clock /></el-icon>
                {{ currentNote.updated_at }}
              </span>
              <el-select
                v-model="form.status"
                size="small"
                class="status-select"
                :disabled="editing"
                @change="updateStatus"
              >
                <el-option label="📝 未使用" value="unused" />
                <el-option label="✅ 已使用" value="used" />
                <el-option label="🚀 已发布" value="published" />
              </el-select>
            </div>
          </div>

          <el-input
            v-model="form.content"
            type="textarea"
            class="content-textarea"
            :disabled="!editing"
            placeholder="输入内容..."
            resize="none"
            @input="wordCount = form.content.length"
          />

          <div class="editor-footer">
            <span class="word-count">{{ wordCount }} 字</span>
            <div class="footer-actions">
              <template v-if="!editing">
                <AppButton variant="ai" :loading="polishing" @click="aiPolish('edit')">
                  <el-icon><MagicStick /></el-icon> AI 润色
                </AppButton>
                <AppButton variant="accent" @click="enterEdit">
                  <el-icon><Edit /></el-icon> 编辑
                </AppButton>
                <AppButton variant="danger" @click="confirmDelete">
                  <el-icon><Delete /></el-icon> 删除
                </AppButton>
              </template>
              <template v-else>
                <AppButton variant="ai" :loading="polishing" @click="aiPolish('edit')">
                  <el-icon><MagicStick /></el-icon> AI 润色
                </AppButton>
                <AppButton @click="cancelEdit">取消</AppButton>
                <AppButton variant="accent" :loading="saving" @click="saveNote">
                  保存
                </AppButton>
              </template>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- 新建笔记弹窗 -->
    <AppModal
      v-model:visible="addModalVisible"
      title="新建随手记"
      width="520px"
    >
      <div class="add-form">
        <div class="form-field">
          <label class="form-label">标题</label>
          <el-input v-model="addForm.title" placeholder="给灵感起个名字（可选）..." />
        </div>
        <div class="form-field">
          <label class="form-label">
            灵感内容
            <span class="form-label-hint">{{ addWordCount }} 字</span>
          </label>
          <el-input
            v-model="addForm.content"
            type="textarea"
            :rows="8"
            placeholder="记录你突然想到的小说片段、对话、情节..."
            resize="none"
            @input="addWordCount = addForm.content.length"
          />
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-content">
          <AppButton variant="ai" :loading="polishing" @click="aiPolish('new')">
            <el-icon><MagicStick /></el-icon> AI 润色
          </AppButton>
          <div class="footer-right">
            <AppButton @click="addModalVisible = false">取消</AppButton>
            <AppButton variant="accent" :loading="saving" @click="addNote">
              <el-icon><Plus /></el-icon> 添加
            </AppButton>
          </div>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, inject } from 'vue'
import { Search, Plus, Edit, Delete, Clock, MagicStick } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import { noteApi } from '@/api/note'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'

const setPageHeader = inject('setPageHeader')

const { projectId } = useProjectId()

const STATUS_LABELS = { unused: '未使用', used: '已使用', published: '已发布' }

const loading = ref(false)
const saving = ref(false)
const polishing = ref(false)
const notes = ref([])
const currentNote = ref(null)
const editing = ref(false)

const searchQuery = ref('')
const statusFilter = ref('')

const form = reactive({ title: '', content: '', status: 'unused' })
const wordCount = ref(0)
let originalTitle = ''
let originalContent = ''

const addModalVisible = ref(false)
const addForm = reactive({ title: '', content: '' })
const addWordCount = ref(0)

const filteredNotes = computed(() => {
  let list = notes.value
  if (statusFilter.value) list = list.filter((n) => n.status === statusFilter.value)
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (n) => (n.title || '').toLowerCase().includes(q) || (n.content || '').toLowerCase().includes(q),
    )
  }
  return list
})

function statusTagType(status) {
  return { unused: 'info', used: 'success', published: 'warning' }[status] || 'info'
}

async function loadNotes() {
  loading.value = true
  try {
    const data = await noteApi.list(projectId.value)
    notes.value = data.data || data.results || (Array.isArray(data) ? data : [])
  } catch {
    // request.js 已统一提示
  } finally {
    loading.value = false
  }
}

async function selectNote(id) {
  try {
    const data = await noteApi.get(projectId.value, id)
    const note = data.note || data
    currentNote.value = note
    form.title = note.title || ''
    form.content = note.content || ''
    form.status = note.status || 'unused'
    wordCount.value = form.content.length
    originalTitle = form.title
    originalContent = form.content
    editing.value = false
  } catch {
    // 统一提示
  }
}

function enterEdit() {
  editing.value = true
}

function cancelEdit() {
  form.title = originalTitle
  form.content = originalContent
  wordCount.value = form.content.length
  editing.value = false
}

async function saveNote() {
  if (!form.content.trim()) {
    showError('内容不能为空')
    return
  }
  saving.value = true
  try {
    const data = await noteApi.update(projectId.value, currentNote.value.id, {
      title: form.title,
      content: form.content,
    })
    const note = data.note || data
    currentNote.value = { ...currentNote.value, ...note }
    originalTitle = form.title
    originalContent = form.content
    editing.value = false
    await loadNotes()
    showSuccess('保存成功')
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

async function updateStatus() {
  try {
    await noteApi.update(projectId.value, currentNote.value.id, { status: form.status })
    await loadNotes()
    showSuccess('状态已更新')
  } catch {
    // 统一提示
  }
}

function confirmDelete() {
  showConfirmModal({
    title: '删除笔记',
    message: '确定要删除这条笔记吗？此操作不可撤销。',
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      try {
        await noteApi.delete(projectId.value, currentNote.value.id)
        close()
        currentNote.value = null
        await loadNotes()
        showSuccess('删除成功')
      } catch {
        // 统一提示
      }
    },
  })
}

function openAddModal() {
  addForm.title = ''
  addForm.content = ''
  addWordCount.value = 0
  addModalVisible.value = true
}

async function addNote() {
  if (!addForm.content.trim()) {
    showError('内容不能为空')
    return
  }
  saving.value = true
  try {
    const data = await noteApi.create(projectId.value, {
      title: addForm.title,
      content: addForm.content,
    })
    addModalVisible.value = false
    await loadNotes()
    const note = data.note || data
    if (note?.id) await selectNote(note.id)
    showSuccess('添加成功')
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

// ===== AI 润色（流式，解析 ════TITLE/CONTENT 标记） =====
const TITLE_START = '════TITLE_START════'
const TITLE_END = '════TITLE_END════'
const CONTENT_START = '════CONTENT_START════'
const CONTENT_END = '════CONTENT_END════'

function parseMarkers(buffer) {
  let title = ''
  let content = ''
  const ts = buffer.indexOf(TITLE_START)
  const te = buffer.indexOf(TITLE_END)
  if (ts !== -1 && te !== -1 && te > ts) {
    title = buffer.substring(ts + TITLE_START.length, te).trim()
  }
  const cs = buffer.indexOf(CONTENT_START)
  const ce = buffer.indexOf(CONTENT_END)
  if (cs !== -1 && ce !== -1 && ce > cs) {
    content = buffer.substring(cs + CONTENT_START.length, ce).trim()
  }
  return { title, content }
}

async function aiPolish(mode) {
  const isEdit = mode === 'edit'
  const content = isEdit ? form.content : addForm.content
  if (!content.trim()) {
    showError(isEdit ? '请先进入编辑模式并填写内容' : '请先输入内容')
    return
  }

  polishing.value = true
  let buffer = ''
  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/notes/polish/`,
      {
        body: { content, title: isEdit ? form.title : addForm.title || undefined },
      },
      (chunk) => {
        buffer += chunk
        // 标题解析后实时回填
        const { title } = parseMarkers(buffer)
        if (title) {
          if (isEdit) form.title = title
          else addForm.title = title
        }
      },
    )

    const { title, content: finalContent } = parseMarkers(buffer)
    if (!finalContent) {
      showError('AI 润色失败：未解析到内容')
      return
    }

    if (isEdit) {
      form.title = title || form.title
      form.content = finalContent
      wordCount.value = finalContent.length
      // 自动保存
      saving.value = true
      try {
        const data = await noteApi.update(projectId.value, currentNote.value.id, {
          title: form.title,
          content: form.content,
        })
        const note = data.note || data
        currentNote.value = { ...currentNote.value, ...note }
        originalTitle = form.title
        originalContent = form.content
        await loadNotes()
        showSuccess('AI 优化完成')
      } finally {
        saving.value = false
      }
    } else {
      addForm.title = title || addForm.title
      addForm.content = finalContent
      addWordCount.value = finalContent.length
      showSuccess('AI 润色完成')
    }
  } catch (err) {
    if (err.message !== '请求已取消或超时') {
      showError('AI 润色失败: ' + err.message)
    }
  } finally {
    polishing.value = false
  }
}

onMounted(() => {
  setPageHeader('随手记', '灵感与备忘速记')
  loadNotes()
})

onBeforeUnmount(() => {
  sseController.abort()
})
</script>

<style lang="scss">
.project-layout:has(.note-view) {
  height: 100vh;
  overflow: hidden;
}
.project-layout:has(.note-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}
.project-layout:has(.note-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.note-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.note-layout {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// 左侧列表
.note-list {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.list-filters {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--glass-border);
}

.status-filter {
  width: 100px;
  flex-shrink: 0;
}

.list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.note-item {
  padding: 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 6px;

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  &.active {
    background: rgba(129, 140, 248, 0.1);
    border: 1px solid rgba(129, 140, 248, 0.2);
  }
}

.note-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.note-item-preview {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 8px;
}

.note-item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.note-item-date {
  font-size: 11px;
  color: var(--text-muted);
}

// 右侧编辑器
.note-editor {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.editor-header {
  margin-bottom: 16px;
}

.title-input {
  margin-bottom: 8px;
  font-weight: 600;
}

.editor-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.update-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.status-select {
  width: 130px;
}

.content-textarea {
  flex: 1;
  display: flex;

  :deep(.el-textarea__inner) {
    height: 100% !important;
    min-height: 320px;
    background: rgba(255, 255, 255, 0.03);
    color: var(--text-primary);
    line-height: 1.8;
  }
}

.editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
}

.word-count {
  font-size: 12px;
  color: var(--text-muted);
}

.footer-actions {
  display: flex;
  gap: 8px;
}

.form-field {
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }
}

.form-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-regular);
  margin-bottom: 8px;
}

.form-label-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}

// ===== 底部按钮栏（参考 character 页面样式） =====
.modal-footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 768px) {
  .note-layout {
    flex-direction: column;
    gap: 8px;
    padding: 8px;
  }
  .note-list {
    width: 100%;
    max-height: 240px;
  }
}
</style>
