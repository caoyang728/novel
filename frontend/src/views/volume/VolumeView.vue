<template>
  <div class="volume-view">
    <Teleport defer to="#header-right-teleport">
      <el-select
        v-model="outlineVersionId"
        size="small"
        style="width: 140px"
      >
        <el-option
          v-for="v in outlineVersions"
          :key="v.id"
          :label="`大纲 v${v.version_number}${v.is_finalized ? '（锁定）' : ''}`"
          :value="v.id"
        />
      </el-select>
      <el-select
        v-model="currentVersionId"
        size="small"
        style="width: 140px"
        :disabled="volumeVersions.length === 0"
        @change="loadVersionDetail"
      >
        <el-option
          v-for="v in volumeVersions"
          :key="v.version"
          :label="`卷 v${v.version}（${v.volume_count}卷）`"
          :value="v.version"
        />
      </el-select>
      <AppButton
        variant="accent"
        :disabled="!currentVersionId"
        @click="saveAsNewVersion"
      >
        <el-icon><DocumentCopy /></el-icon> 另存新版本
      </AppButton>
      <AppButton
        :variant="isVersionFinalized ? 'warning' : 'success'"
        :disabled="!currentVersionId"
        @click="toggleFinalize"
      >
        <el-icon><component :is="isVersionFinalized ? 'Unlock' : 'Lock'" /></el-icon>
        {{ isVersionFinalized ? '版本解锁' : '版本锁定' }}
      </AppButton>
      <AppButton
        v-if="isVersionFinalized && currentVersionId"
        variant="ai"
        @click="showCandidateModal = true"
      >
        <el-icon><MagicStick /></el-icon> 从卷生成角色
      </AppButton>
    </Teleport>
    <div
      class="volume-workspace"
      v-loading="generating"
      :element-loading-text="genStatus"
    >
      <!-- 左：卷列表 -->
      <aside class="volume-list glass-surface">
        <div class="list-header">
          <span class="list-title">卷列表（{{ volumes.length }}）</span>
          <AppButton
            size="small"
            variant="accent"
            :disabled="isVersionFinalized || generating"
            @click="openAddModal"
          >
            <el-icon><Plus /></el-icon> 新增
          </AppButton>
        </div>
        <div class="list-body">
          <EmptyState v-if="volumes.length === 0" icon="Files" text="暂无卷，选择大纲版本后点击 AI 生成卷" />
          <div
            v-for="vol in sortedVolumes"
            :key="vol.volume_number"
            class="volume-item"
            :class="{
              active: selectedVolumeNumber === vol.volume_number,
              locked: vol.is_locked,
              failed: vol._failed,
            }"
            @click="selectVolume(vol.volume_number)"
          >
            <div class="volume-item-row">
              <span class="volume-item-number">{{ vol.volume_number }}</span>
              <span class="volume-item-title text-ellipsis">{{ vol.title }}</span>
              <el-icon v-if="vol.is_locked" class="lock-icon"><Lock /></el-icon>
            </div>
            <div class="volume-item-meta">
              <el-tag v-if="vol._failed" type="danger" size="small">生成失败</el-tag>
              <template v-else>
                <span v-if="vol.chapter_count">预估 {{ vol.chapter_count }} 章 · </span>
                <span>{{ vol.content ? vol.content.length + ' 字' : '暂无大纲' }}</span>
              </template>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中：卷详情 -->
      <section class="volume-detail glass-panel">
        <template v-if="selectedVolume">
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-number">{{ selectedVolume.volume_number }}</span>
              <span class="detail-name">{{ selectedVolume.title }}</span>
              <el-tag v-if="selectedVolume.is_locked" type="warning" size="small">
                <el-icon><Lock /></el-icon> 已锁定
              </el-tag>
              <el-tag v-if="selectedVolume.chapter_count" type="info" size="small">
                预估 {{ selectedVolume.chapter_count }} 章
              </el-tag>
            </div>
            <div class="detail-actions">
              <AppButton
                size="small"
                :variant="selectedVolume.is_locked ? 'warning' : 'success'"
                :disabled="isVersionFinalized || generating || !selectedVolume.id"
                @click="toggleVolumeLock"
              >
                <el-icon><Unlock v-if="selectedVolume.is_locked" /><Lock v-else /></el-icon>
                {{ selectedVolume.is_locked ? '解锁' : '锁定' }}
              </AppButton>
              <AppButton
                size="small"
                variant="accent"
                :disabled="isVersionFinalized || selectedVolume.is_locked || generating"
                @click="openEditModal"
              >
                <el-icon><EditPen /></el-icon> 编辑
              </AppButton>
              <AppButton
                size="small"
                variant="danger"
                :disabled="isVersionFinalized || selectedVolume.is_locked || generating"
                @click="deleteVolume"
              >
                <el-icon><Delete /></el-icon> 删除
              </AppButton>
            </div>
          </div>

          <div class="detail-body">
            <template v-if="selectedVolume.content">
              <MarkdownRenderer :content="selectedVolume.content" />
            </template>
            <div v-else class="detail-empty">
              <p>该卷暂无大纲</p>
              <AppButton
                variant="ai"
                type="primary"
                :loading="singleGenerating"
                :disabled="isVersionFinalized || selectedVolume.is_locked || !selectedVolume.id"
                @click="generateSingle"
              >
                <el-icon><MagicStick /></el-icon> AI 生成卷大纲
              </AppButton>
            </div>
          </div>
        </template>

        <EmptyState v-else-if="volumes.length === 0" icon="Files" text="暂无卷，选择大纲版本后点击 AI 生成卷">
          <AppButton
            variant="ai"
            type="primary"
            :loading="generating"
            :disabled="!outlineVersionId"
            @click="generateAll"
          >
            <el-icon><MagicStick /></el-icon> AI 生成卷
          </AppButton>
        </EmptyState>

        <EmptyState v-else icon="Files" text="请从左侧选择一个卷" />
      </section>

      <!-- 右：AI 聊天 -->
      <transition name="chat-slide">
        <div v-if="chatVisible" class="volume-chat">
          <ChatPanel
            title="卷调整助手"
            :messages="messages"
            :is-streaming="isStreaming"
            :selection-mode="selectionMode"
            :selected-count="selectedMessages.size"
            :is-selected="isSelected"
            input-placeholder="选中一卷后，描述调整需求..."
            @send="handleSend"
            @stop="stopStreaming"
            @clear="clearMessages"
            @toggle-selection="enterSelectionMode"
            @exit-selection="exitSelectionMode"
            @toggle-select="toggleMessageSelect"
            @copy-selected="handleCopySelected"
          />
          <!-- 流式预览：loading 下方显示最后 3 行 -->
          <transition name="fade">
            <div v-if="isStreaming && streamingPreviewText" class="streaming-preview">
              <div class="streaming-preview-header">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>AI 正在生成...</span>
              </div>
              <pre class="streaming-preview-text">{{ streamingPreviewText }}</pre>
            </div>
          </transition>
        </div>
      </transition>
    </div>

    <!-- 聊天结果弹窗 -->
    <AppModal
      v-model:visible="chatResultModalVisible"
      :title="`卷调整结果 — 第${chatResultData?.volumeNumber || ''}卷 ${chatResultData?.volumeTitle || ''}`"
      width="720px"
      height="65vh"
    >
      <div v-if="chatResultData" class="chat-result-container">
        <div class="chat-result-reply">
          <div class="result-section-label">AI 回复</div>
          <MarkdownRenderer :content="chatResultData.reply" />
        </div>
        <div v-if="chatResultData.content" class="chat-result-content">
          <div class="result-section-label">更新后卷大纲</div>
          <MarkdownRenderer :content="chatResultData.content" />
        </div>
        <div v-if="chatResultData.targetVolume" class="chat-result-target">
          <div class="result-section-label">
            跨卷更新 — 第{{ chatResultData.targetVolume.volume_number }}卷 {{ chatResultData.targetVolume.title }}
          </div>
          <MarkdownRenderer :content="chatResultData.targetVolume.content" />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-content">
          <div />
          <div class="footer-right">
            <AppButton variant="accent" @click="chatResultModalVisible = false">确定</AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- 新增/编辑卷弹窗 -->
    <AppModal
      v-model:visible="editModalVisible"
      :title="editForm.isNew ? '新增卷' : '编辑卷'"
      width="800px"
      height="65vh"
    >
      <div class="edit-modal-container">
        <div class="edit-form">
          <div class="edit-row">
            <div class="edit-field">
              <label>卷编号</label>
              <el-input-number v-model="editForm.volumeNumber" :min="1" :max="999" controls-position="right" />
            </div>
            <div class="edit-field">
              <label>预估章节数</label>
              <el-input-number v-model="editForm.chapterCount" :min="0" :max="999" controls-position="right" />
            </div>
            <div class="edit-field">
              <label>卷标题</label>
              <el-input v-model="editForm.title" placeholder="例如：第一卷 风起" maxlength="100" />
            </div>
          </div>
          <div class="edit-field">
            <label>卷概述</label>
            <el-input 
              v-model="editForm.summary" 
              type="textarea" 
              :autosize="{ minRows: 4, maxRows: 4 }" 
              resize="none" 
              placeholder="本卷概要（可选）" 
              maxlength="2000" 
              show-word-limit 
            />
          </div>
          <div class="form-section fill-remaining">
            <label>卷大纲</label>
            <el-input
              v-model="editForm.content"
              type="textarea"
              class="edit-content-textarea"
              resize="none"
              placeholder="输入卷大纲内容，或点击 AI 优化自动生成"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-content">
          <AppButton
            variant="ai"
            :loading="optimizing"
            :disabled="!editForm.content?.trim() && !editForm.title?.trim()"
            @click="aiOptimize"
          >
            <el-icon><MagicStick /></el-icon> AI 优化
          </AppButton>
          <div class="footer-right">
            <AppButton @click="editModalVisible = false">取消</AppButton>
            <AppButton variant="accent" :loading="saving" @click="saveEditVolume">保存</AppButton>
          </div>
        </div>
      </template>
    </AppModal>

  <CharacterCandidateModal
    v-model:visible="showCandidateModal"
    :project-id="projectId"
    source="volume"
    :volume-id="selectedVolumeId"
    @created="onCandidatesCreated"
  />
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { MagicStick, Plus, EditPen, Delete, Lock, Unlock, Loading, DocumentCopy } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import CharacterCandidateModal from '@/views/character/components/CharacterCandidateModal.vue'
import { volumeApi } from '@/api/volume'
import { outlineApi } from '@/api/outline'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { useChat } from '@/composables/useChat'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'

const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')

const {
  messages,
  isStreaming,
  selectionMode,
  selectedMessages,
  stopStreaming,
  clearMessages,
  enterSelectionMode,
  exitSelectionMode,
  toggleMessageSelect,
  isSelected,
  getSelectedContent,
} = useChat()

// ---- 版本状态 ----
const loading = ref(false)
const generating = ref(false)
const genStatus = ref('')
const singleGenerating = ref(false)
const saving = ref(false)
const optimizing = ref(false)

const outlineVersions = ref([])
const outlineVersionId = ref(null)
const volumeVersions = ref([])
const currentVersionId = ref(null)
const isVersionFinalized = ref(false)
const volumes = ref([])
const selectedVolumeNumber = ref(null)
const chatVisible = ref(true)

const sortedVolumes = computed(() =>
  [...volumes.value].sort((a, b) => (a.volume_number || 0) - (b.volume_number || 0)),
)

const selectedVolume = computed(
  () => volumes.value.find((v) => v.volume_number === selectedVolumeNumber.value) || null,
)

// ---- 从卷生成角色 ----
const showCandidateModal = ref(false)
const selectedVolumeId = computed(() => selectedVolume.value?.id || null)

function onCandidatesCreated() {
  showCandidateModal.value = false
}

// 流式预览：最后 3 行原始输出
const streamingPreviewText = ref('')
// 聊天结果弹窗
const chatResultModalVisible = ref(false)
const chatResultData = ref(null)

// ---- 初始加载 ----
async function loadAll() {
  loading.value = true
  try {
    const [outlineData, versionData] = await Promise.all([
      outlineApi.getVersions(projectId.value),
      volumeApi.getVersions(projectId.value),
    ])
    outlineVersions.value = outlineData.versions || []
    if (outlineVersions.value.length > 0 && !outlineVersionId.value) {
      outlineVersionId.value = outlineVersions.value[0]?.id
    }
    volumeVersions.value = versionData.versions || []
    // 默认选最新版本（后端按创建时间倒序）
    if (volumeVersions.value.length > 0) {
      currentVersionId.value = volumeVersions.value[0].version
      await doLoadVersion(currentVersionId.value)
    }
  } catch {
    // 统一提示
  } finally {
    loading.value = false
  }
}

async function loadVersionDetail(versionId) {
  if (!versionId) return
  if (generating.value || isStreaming.value) {
    showWarning('正在生成内容，请等待完成后再切换版本')
    return
  }
  await doLoadVersion(versionId)
}

async function doLoadVersion(versionId) {
  try {
    const data = await volumeApi.getVersion(projectId.value, versionId)
    currentVersionId.value = versionId
    volumes.value = data.volumes || []
    isVersionFinalized.value = data.is_version_locked || false
    if (data.outline_version_id) outlineVersionId.value = data.outline_version_id
    selectedVolumeNumber.value = null
    clearMessages()
  } catch {
    // 统一提示
  }
}

function selectVolume(volumeNumber) {
  selectedVolumeNumber.value = volumeNumber
}

// ---- AI 批量生成卷 ----
async function generateAll() {
  if (!outlineVersionId.value) {
    showError('请先选择大纲版本')
    return
  }
  generating.value = true
  genStatus.value = '正在分析大纲...'
  volumes.value = []
  selectedVolumeNumber.value = null

  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/volume-versions/`,
      {
        body: { outline_version_id: outlineVersionId.value },
        onEvent: (evt) => {
          switch (evt.type) {
            case 'progress':
              genStatus.value = evt.message || '生成中...'
              break
            case 'analysis':
              genStatus.value = `大纲分析完成：共 ${evt.total_volumes} 卷，${evt.total_chapters} 章`
              break
            case 'volume':
              volumes.value.push(evt.volume)
              genStatus.value = `正在生成第 ${evt.volume_count}/${evt.total_volumes} 卷（已生成 ${evt.total_chars} 字）`
              break
            case 'volume_failed':
              volumes.value.push({
                id: evt.volume_id,
                volume_number: evt.volume_number,
                title: `第${evt.volume_number}卷`,
                content: '',
                _failed: true,
              })
              showWarning(evt.message || '部分卷生成失败')
              break
            case 'complete':
              showSuccess(`共生成 ${evt.volume_count} 卷`)
              break
            case 'phase3_result':
              if (evt.quality) {
                const score = evt.quality.score
                const issues = evt.validation?.errors?.length || 0
                genStatus.value = `校验完成：评分 ${score}/100，${issues} 个问题`
              }
              break
            case 'error':
            case 'volume_error':
              showError(evt.message || '生成失败')
              break
          }
        },
      },
      () => {},
    )
    // 重新加载版本列表并选中新版本
    const versionData = await volumeApi.getVersions(projectId.value)
    volumeVersions.value = versionData.versions || []
    if (volumeVersions.value.length > 0) {
      currentVersionId.value = volumeVersions.value[0].version
      await doLoadVersion(currentVersionId.value)
    }
  } catch (err) {
    if (err.message !== '请求已取消或超时') showError('生成过程出错，请重试')
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ---- 单卷生成 ----
async function generateSingle() {
  const vol = selectedVolume.value
  if (!vol?.id) {
    showError('卷ID不存在，请刷新后重试')
    return
  }
  singleGenerating.value = true
  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/volumes/${vol.id}/generate/`,
      {
        body: {},
        onEvent: (evt) => {
          if (evt.type === 'complete' && evt.volume) {
            const idx = volumes.value.findIndex(
              (v) => v.volume_number === evt.volume.volume_number,
            )
            if (idx !== -1) {
              volumes.value[idx] = { ...volumes.value[idx], ...evt.volume, _failed: false }
            }
            showSuccess(`第 ${evt.volume.volume_number} 卷生成完成`)
          } else if (evt.type === 'error') {
            showError(evt.message || '生成失败')
          }
        },
      },
      () => {},
    )
  } catch (err) {
    if (err.message !== '请求已取消或超时') showError('生成过程出错，请重试')
  } finally {
    singleGenerating.value = false
  }
}

// ---- 单卷锁定/解锁 ----
async function toggleVolumeLock() {
  const vol = selectedVolume.value
  if (!vol) return
  if (isVersionFinalized.value) {
    showError('该版本已锁定，无法操作单卷锁定')
    return
  }
  const newState = !vol.is_locked
  if (vol.id) {
    try {
      await volumeApi.lockVolume(projectId.value, vol.id, newState)
    } catch {
      return
    }
  }
  const idx = volumes.value.findIndex((v) => v.volume_number === vol.volume_number)
  if (idx !== -1) volumes.value[idx].is_locked = newState
  showSuccess(newState ? '已锁定' : '已解锁')
}

// ---- 版本锁定/解锁 ----
function toggleFinalize() {
  const action = isVersionFinalized.value ? '解锁' : '锁定'
  showConfirmModal({
    title: `版本${action}`,
    message: `确定要${action}当前卷版本吗？${isVersionFinalized.value ? '' : '锁定后版本不可修改。'}`,
    confirmText: action,
    onConfirm: async (close) => {
      close()
      try {
        const data = await volumeApi.finalizeVersion(projectId.value, currentVersionId.value)
        isVersionFinalized.value = data.is_locked
        showSuccess(`版本${action}成功`)
        const list = await volumeApi.getVersions(projectId.value)
        volumeVersions.value = list.versions || []
      } catch {
        // 统一提示
      }
    },
  })
}

// ---- 另存新版本 ----
function saveAsNewVersion() {
  if (!currentVersionId.value) {
    showError('请先选择或生成一个卷版本')
    return
  }
  showConfirmModal({
    title: '另存为新版本',
    message: '将当前卷数据另存为一个新版本，现有版本不受影响。',
    confirmText: '另存',
    onConfirm: async (close) => {
      close()
      saving.value = true
      try {
        const data = await volumeApi.saveVersion(projectId.value, currentVersionId.value, {
          outline_version_id: outlineVersionId.value || '',
          volumes: volumes.value,
        })
        showSuccess(`另存成功！版本号：v${data.version}`)
        const list = await volumeApi.getVersions(projectId.value)
        volumeVersions.value = list.versions || []
        currentVersionId.value = data.version
        await doLoadVersion(data.version)
      } catch {
        // 统一提示
      } finally {
        saving.value = false
      }
    },
  })
}

// ---- 新增/编辑弹窗 ----
const editModalVisible = ref(false)
const editForm = reactive({
  isNew: true,
  volumeNumber: 1,
  title: '',
  summary: '',
  chapterCount: 0,
  content: '',
})

watch(editModalVisible, (val) => {
  if (val) {
    nextTick(() => {
      const section = document.querySelector('.form-section.fill-remaining')
      if (!section) return
      const inner = section.querySelector('.el-textarea__inner')
      if (inner) {
        inner.style.height = '100%'
        inner.style.minHeight = '0'
      }
    })
  }
})

function openAddModal() {
  if (isVersionFinalized.value) {
    showError('该版本已锁定，无法新增卷')
    return
  }
  const maxNum = volumes.value.reduce((m, v) => Math.max(m, v.volume_number || 0), 0)
  editForm.isNew = true
  editForm.volumeNumber = maxNum + 1
  editForm.title = ''
  editForm.summary = ''
  editForm.chapterCount = 0
  editForm.content = ''
  editModalVisible.value = true
}

function openEditModal() {
  const vol = selectedVolume.value
  if (!vol) return
  if (isVersionFinalized.value || vol.is_locked) {
    showError('版本或该卷已锁定，无法编辑')
    return
  }
  editForm.isNew = false
  editForm.volumeNumber = vol.volume_number
  editForm.title = vol.title || ''
  editForm.summary = vol.summary || ''
  editForm.chapterCount = vol.chapter_count || 0
  editForm.content = vol.content || ''
  editModalVisible.value = true
}

async function aiOptimize() {
  if (editForm.isNew) {
    showError('新增卷不支持 AI 优化，请先保存')
    return
  }
  if (!editForm.title.trim() && !editForm.summary.trim()) {
    showError('请先输入卷标题或概述')
    return
  }
  optimizing.value = true
  let streamText = editForm.content || ''
  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/volumes/optimize/`,
      {
        body: {
          version_id: currentVersionId.value,
          volume_number: editForm.volumeNumber,
          volume_title: editForm.title.trim(),
          volume_summary: editForm.summary.trim(),
          current_content: editForm.content || '',
          user_feedback: '请优化这一卷的大纲，以扩展和丰富内容为主',
        },
        onEvent: (evt) => {
          if (evt.type === 'complete' && evt.volume?.content) {
            streamText = evt.volume.content
          } else if (evt.type === 'error') {
            showError(evt.message || 'AI 优化失败')
          }
        },
      },
      (chunk) => {
        streamText += chunk
        editForm.content = streamText
      },
    )
    editForm.content = streamText
    showSuccess('AI 优化完成')
  } catch (err) {
    if (err.message !== '请求已取消或超时') showError('AI 优化失败，请重试')
  } finally {
    optimizing.value = false
  }
}

async function persistVolumes(volumesToSave) {
  const payload = {
    outline_version_id: outlineVersionId.value || '',
    volumes: volumesToSave,
  }
  if (currentVersionId.value) {
    return volumeApi.updateVersion(projectId.value, currentVersionId.value, payload)
  }
  // 无现有版本时，通过另存为接口创建新版本（后端会自动分配新版本号）
  const data = await volumeApi.saveVersion(projectId.value, 0, payload)
  currentVersionId.value = data.version
  return data
}

async function saveEditVolume() {
  const title = editForm.title.trim()
  if (!title) {
    showError('请输入卷标题')
    return
  }
  if (!editForm.volumeNumber || editForm.volumeNumber < 1) {
    showError('卷编号必须为正整数')
    return
  }

  const volumesToSave = volumes.value.map((v) => ({ ...v }))
  const targetNumber = editForm.volumeNumber

  if (editForm.isNew) {
    // 编号冲突时自动顺延
    const used = new Set(volumesToSave.map((v) => v.volume_number))
    let num = targetNumber
    while (used.has(num)) num++
    volumesToSave.push({
      volume_number: num,
      title,
      summary: editForm.summary.trim(),
      chapter_count: editForm.chapterCount || 0,
      content: editForm.content,
      is_locked: false,
    })
  } else {
    const idx = volumesToSave.findIndex((v) => v.volume_number === selectedVolumeNumber.value)
    if (idx === -1) {
      showError('未找到要编辑的卷')
      return
    }
    // 编号冲突处理：被占用则顺延占用者
    const conflictIdx = volumesToSave.findIndex(
      (v, i) => i !== idx && v.volume_number === targetNumber,
    )
    if (conflictIdx !== -1) {
      const used = new Set(volumesToSave.map((v) => v.volume_number))
      used.delete(volumesToSave[conflictIdx].volume_number)
      let num = targetNumber + 1
      while (used.has(num)) num++
      volumesToSave[conflictIdx].volume_number = num
    }
    volumesToSave[idx] = {
      ...volumesToSave[idx],
      volume_number: targetNumber,
      title,
      summary: editForm.summary.trim(),
      chapter_count: editForm.chapterCount || 0,
      content: editForm.content,
    }
  }

  saving.value = true
  try {
    await persistVolumes(volumesToSave)
    editModalVisible.value = false
    await doLoadVersion(currentVersionId.value)
    const target = editForm.isNew
      ? volumesToSave[volumesToSave.length - 1].volume_number
      : targetNumber
    selectedVolumeNumber.value = volumes.value.find((v) => v.volume_number === target)
      ? target
      : selectedVolumeNumber.value
    showSuccess(editForm.isNew ? '新增成功' : '修改成功')
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

// ---- 删除卷 ----
function deleteVolume() {
  const vol = selectedVolume.value
  if (!vol) return
  if (isVersionFinalized.value || vol.is_locked) {
    showError('版本或该卷已锁定，无法删除')
    return
  }
  const isLast = volumes.value.length === 1
  showConfirmModal({
    title: '删除卷',
    message: isLast
      ? `该版本仅剩此卷，删除后版本将一并删除且无法恢复。确定删除「${vol.title}」吗？`
      : `确定删除「${vol.title}」吗？`,
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      close()
      saving.value = true
      try {
        if (isLast) {
          await volumeApi.deleteVersion(projectId.value, currentVersionId.value)
          showSuccess('版本已删除')
          const list = await volumeApi.getVersions(projectId.value)
          volumeVersions.value = list.versions || []
          currentVersionId.value = volumeVersions.value[0]?.version || null
          if (currentVersionId.value) {
            await doLoadVersion(currentVersionId.value)
          } else {
            volumes.value = []
            isVersionFinalized.value = false
            selectedVolumeNumber.value = null
          }
        } else {
          const remaining = volumes.value
            .filter((v) => v.volume_number !== vol.volume_number)
            .map((v) => ({ ...v }))
          await persistVolumes(remaining)
          showSuccess('删除成功')
          selectedVolumeNumber.value = null
          await doLoadVersion(currentVersionId.value)
        }
      } catch {
        // 统一提示
      } finally {
        saving.value = false
      }
    },
  })
}

// ---- AI 聊天（流式，JSON 补丁模式） ----

/** 从文本中提取最后 N 行 */
function getLastNLines(text, n) {
  const lines = text.split('\n')
  return lines.slice(-n).join('\n')
}

async function handleSend(message) {
  if (isStreaming.value) return
  if (!currentVersionId.value) {
    showWarning('请先生成或选择一个卷版本')
    return
  }
  if (isVersionFinalized.value) {
    showWarning('该版本已锁定，无法修改')
    return
  }
  if (!selectedVolume.value) {
    showWarning('请先选择需要调整的卷')
    return
  }
  if (selectedVolume.value.is_locked) {
    showWarning('该卷已锁定，无法修改')
    return
  }
  const text = (message || '').trim()
  if (!text) return

  const history = messages.value.map((m) => ({ role: m.role, content: m.content })).slice(0, -1)

  const userMsg = { id: Date.now(), role: 'user', content: text }
  const aiMsg = { id: Date.now() + 1, role: 'assistant', content: '' }
  messages.value.push(userMsg)
  messages.value.push(aiMsg)

  isStreaming.value = true
  streamingPreviewText.value = ''
  const targetNumber = selectedVolume.value.volume_number
  let rawBuffer = ''
  let completeEvt = null

  try {
    await sseController.stream(
      `/api/projects/${projectId.value}/volume-versions/${currentVersionId.value}/chat/`,
      {
        body: {
          message: text,
          context_messages: history,
          current_volume_number: targetNumber,
        },
        onEvent: (evt) => {
          if (evt.type === 'complete') {
            completeEvt = evt
          } else if (evt.type === 'error') {
            showError(evt.message || 'AI 处理失败')
          }
        },
      },
      (chunk) => {
        rawBuffer += chunk
        // 实时更新预览：显示最后 3 行
        streamingPreviewText.value = getLastNLines(rawBuffer, 3)
      },
    )

    // 解析 complete 事件中的回复
    if (completeEvt) {
      // 从 rawBuffer 中尝试解析 reply（JSON 格式）
      let reply = ''
      try {
        const parsed = JSON.parse(rawBuffer)
        reply = parsed.reply || ''
      } catch {
        reply = rawBuffer
      }
      aiMsg.content = reply || '调整完成'

      // 用后端返回的最新卷数据刷新
      if (completeEvt.volumes) {
        volumes.value = completeEvt.volumes
        const stillExists = volumes.value.some((v) => v.volume_number === targetNumber)
        selectedVolumeNumber.value = stillExists
          ? targetNumber
          : volumes.value[0]?.volume_number ?? null
      }

      // 获取更新后的卷内容，打开结果弹窗
      const updatedVol = volumes.value.find((v) => v.volume_number === targetNumber)
      chatResultData.value = {
        reply: aiMsg.content,
        volumeNumber: targetNumber,
        volumeTitle: updatedVol?.title || selectedVolume.value?.title || '',
        content: updatedVol?.content || '',
        targetVolume: completeEvt.target_volume || null,
      }
      chatResultModalVisible.value = true
    }

    showSuccess('调整完成')
  } catch (err) {
    if (err.message !== '请求已取消或超时') {
      showError('处理失败，请重试')
      if (!aiMsg.content) {
        messages.value = messages.value.filter((m) => m.id !== aiMsg.id)
      }
    }
  } finally {
    isStreaming.value = false
    streamingPreviewText.value = ''
  }
}

async function handleCopySelected() {
  const text = getSelectedContent()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showSuccess('已复制选中内容')
  } catch {
    showError('复制失败')
  }
  exitSelectionMode()
}

onMounted(() => {
  setPageHeader('卷管理', '依据大纲 AI 生成与调整卷结构')
  loadAll()
})

onBeforeUnmount(() => {
  sseController.abort()
})
</script>

<style lang="scss">
// 覆盖父级布局（unscoped），锁定卷页面为视口高度，内部滚动
.project-layout:has(.volume-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.volume-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.volume-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.volume-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.volume-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// 左：卷列表
.volume-list {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--glass-border);

  .el-button--text {
    color: var(--primary);
    font-weight: 500;

    &:hover {
      color: var(--primary-dark);
    }
  }
}

.list-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
}

.volume-item {
  padding: 10px 12px;
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

  &.locked {
    opacity: 0.75;
  }

  &.failed {
    border: 1px solid rgba(248, 113, 113, 0.3);
  }
}

.volume-item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.volume-item-number {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: rgba(129, 140, 248, 0.15);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.volume-item-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.lock-icon {
  color: var(--text-muted);
  font-size: 13px;
}

.volume-item-meta {
  font-size: 11px;
  color: var(--text-muted);
  padding-left: 30px;
}

// 中：详情
.volume-detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--glass-border);
  flex-wrap: wrap;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.detail-number {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: rgba(129, 140, 248, 0.15);
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.detail-actions {
  display: flex;
  gap: 8px;

  .el-button {
    font-size: 12px;

    &.el-button--danger.is-plain {
      color: var(--el-color-danger);
      border-color: rgba(248, 113, 113, 0.3);

      &:hover {
        background: rgba(248, 113, 113, 0.1);
        border-color: rgba(248, 113, 113, 0.5);
      }
    }
  }
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.detail-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-muted);
  font-size: 14px;
}

// 右：聊天
.volume-chat {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.chat-panel) {
    flex: 1;
    min-height: 0;
    height: auto;
  }
}

// 流式预览
.streaming-preview {
  flex-shrink: 0;
  margin: 0 8px 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.2);
}

.streaming-preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;

  .el-icon {
    color: var(--primary);
    font-size: 14px;
  }
}

.streaming-preview-text {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-secondary);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60px;
  overflow: hidden;
}

// fade 过渡
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--transition-fast);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 聊天结果弹窗
.chat-result-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.chat-result-reply,
.chat-result-content,
.chat-result-target {
  padding: 12px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all var(--transition-fast);
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateX(24px);
}

// 编辑弹窗
.edit-modal-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-track { background: transparent; margin: 4px 0; }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    &:hover { background: rgba(255, 255, 255, 0.35); }
  }
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-height: 0;
}

.form-section {
  padding: 10px 0;

  & + .form-section {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }

  > label {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 500;
    margin-bottom: 8px;
  }

  &.fill-remaining {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;

    .edit-content-textarea {
      flex: 1;
      min-height: 0;

      :deep(.el-textarea) {
        height: 100%;

        .el-textarea__inner {
          height: 100% !important;
          min-height: 0 !important;
        }
      }
    }
  }
}

.form-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 14px;

  .title-bar {
    width: 3px;
    height: 14px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.3);
  }
}

.edit-row {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;

  .edit-field {
    flex: 1;
  }
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 500;
  }
}

.edit-content-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.edit-content-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.edit-content-textarea {
  :deep(.el-textarea__inner) {
    background: rgba(255, 255, 255, 0.03);
    color: var(--text-primary);
    line-height: 1.8;
  }
}

// 底部按钮
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

@media (max-width: 1200px) {
  .volume-chat {
    width: 300px;
  }
}

@media (max-width: 768px) {
  .volume-workspace {
    flex-direction: column;
    padding: 8px;
    gap: 8px;
  }
  .volume-list {
    width: 100%;
    max-height: 240px;
  }
  .volume-chat {
    width: 100%;
    max-height: 420px;
  }
}
</style>
