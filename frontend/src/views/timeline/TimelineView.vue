<template>
  <div class="timeline-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="ai" @click="runCheck">
        一致性检查
      </AppButton>
      <AppButton variant="success" @click="openAddModal">
        新增事件
      </AppButton>
    </Teleport>
    <div class="timeline-panel glass-panel" v-loading="loading">
      <!-- 时间线事件流 -->
      <div class="timeline-scroll">
        <EmptyState
          v-if="filteredEvents.length === 0"
          icon="Clock"
          :text="searchQuery || timeFilter ? '没有找到匹配的事件' : '暂无时间线事件，点击右上角「新增事件」或「AI 生成时间线」'"
        />
        <div v-else class="timeline-track">
          <div v-for="group in groupedEvents" :key="group.label" class="year-group">
            <div class="year-marker">
              <span class="year-dot"></span>
              <span class="year-label">{{ group.label }}</span>
              <span class="year-count">{{ group.items.length }}</span>
            </div>
            <div class="year-events">
              <div
                v-for="ev in group.items"
                :key="ev.id"
                class="event-card glass-surface"
                @click="openEditModal(ev)"
              >
                <div class="event-card-head">
                  <span class="event-title text-ellipsis">{{ ev.title }}</span>
                  <el-tag size="small" effect="plain" class="event-time-tag">{{ formatTimeLabel(ev) }}</el-tag>
                </div>
                <div v-if="ev.description" class="event-desc">{{ ev.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增 / 编辑事件弹窗 -->
    <AppModal v-model:visible="editVisible" :title="editForm.id ? '编辑事件' : '新增事件'" width="680px" height="65vh" min-height="65vh">
      <div class="edit-modal-container">
        <!-- 弹窗头部装饰 -->
        <div class="edit-header-banner">
          <div class="edit-header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          </div>
          <div class="edit-header-text">
            <span class="edit-header-label">{{ editForm.id ? '修改事件详情' : '创建新的时间线事件' }}</span>
            <span class="edit-header-hint">填写以下信息，标记故事中的重要节点</span>
          </div>
        </div>
        <el-form label-position="top" class="edit-form">
          <!-- 基本信息 -->
          <div class="form-section">
            <div class="form-section-title"><span class="title-bar"></span>基本信息</div>
            <el-form-item label="事件标题" required>
              <el-input v-model="editForm.title" placeholder="例：玄武门之变、三顾茅庐" maxlength="100" />
            </el-form-item>
            <el-form-item label="纪元单位">
              <el-input v-model="editForm.era_unit" placeholder="如：公元、洪武、贞观" maxlength="20" />
            </el-form-item>
          </div>
          <!-- 时间范围 -->
          <div class="form-section">
            <div class="form-section-title"><span class="title-bar"></span>时间范围</div>
            <div class="time-range-card">
              <div class="time-point">
                <span class="time-point-label">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
                  开始
                </span>
                <div class="time-inputs">
                  <el-input-number v-model="editForm.start_year" :controls="false" :min="-9999" :max="9999" class="time-input" />
                  <span class="time-unit">年</span>
                  <el-input-number v-model="editForm.start_month" :controls="false" :min="0" :max="12" class="time-input" />
                  <span class="time-unit">月</span>
                </div>
              </div>
              <div class="time-separator">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M13 5l7 7-7 7"/></svg>
              </div>
              <div class="time-point">
                <span class="time-point-label">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12l7 7 7-7"/></svg>
                  结束
                </span>
                <div class="time-inputs">
                  <el-input-number v-model="editForm.end_year" :controls="false" :min="-9999" :max="9999" class="time-input" />
                  <span class="time-unit">年</span>
                  <el-input-number v-model="editForm.end_month" :controls="false" :min="0" :max="12" class="time-input" />
                  <span class="time-unit">月</span>
                </div>
              </div>
            </div>
          </div>
          <!-- 事件描述 -->
          <div class="form-section">
            <div class="form-section-title"><span class="title-bar"></span>事件描述</div>
            <el-input
              v-model="editForm.description"
              type="textarea"
              :autosize="{ minRows: 4, maxRows: 12 }"
              resize="vertical"
              placeholder="描述该时间段内发生的关键事件、人物关系、情节转折..."
              maxlength="5000"
              show-word-limit
            />
          </div>
        </el-form>
      </div>
      <template #footer>
        <div class="edit-footer">
          <div class="footer-left">
            <AppButton v-if="!editForm.id" variant="ai" :loading="aiBusy" @click="aiGenerateFields">
              <el-icon><MagicStick /></el-icon> AI 生成字段
            </AppButton>
            <template v-else>
              <AppButton variant="danger" :icon="Delete" @click="confirmDeleteEvent">删除</AppButton>
              <AppButton :icon="Connection" @click="openMergeModal">合并</AppButton>
              <AppButton :icon="Scissor" @click="openSplitModal">拆分</AppButton>
              <AppButton variant="ai" :loading="aiBusy" @click="aiOptimizeEvent">
                <el-icon><MagicStick /></el-icon> AI 优化
              </AppButton>
            </template>
          </div>
          <div class="footer-right">
            <AppButton @click="editVisible = false">取消</AppButton>
            <AppButton variant="accent" :loading="saving" @click="saveEvent">保存事件</AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- AI 生成时间线弹窗 -->
    <AppModal v-model:visible="genVisible" title="AI 生成时间线" width="560px">
      <p class="modal-tip">将基于世界观设定生成完整时间线，生成结果可在预览弹窗中逐项编辑、保存。可在下方补充额外要求。</p>
      <el-input
        v-model="genPrompt"
        type="textarea"
        :rows="5"
        resize="none"
        placeholder="补充要求（可选），如：重点描写王朝更迭、跨度约三百年..."
      />
      <template #footer>
        <AppButton @click="genVisible = false">取消</AppButton>
        <AppButton variant="accent" :loading="generating" @click="runGenerate">开始生成</AppButton>
      </template>
    </AppModal>

    <!-- 合并事件弹窗 -->
    <AppModal v-model:visible="mergeVisible" title="合并事件" width="600px">
      <p class="modal-tip">选择至少 2 个事件，AI 将把它们合并为一个事件。</p>
      <div class="merge-list">
        <label v-for="ev in events" :key="ev.id" class="merge-item glass-surface">
          <el-checkbox v-model="mergeSelected[ev.id]" />
          <span class="merge-title text-ellipsis">{{ ev.title }}</span>
          <span class="merge-time">{{ formatTimeLabel(ev) }}</span>
        </label>
      </div>
      <template #footer>
        <AppButton @click="mergeVisible = false">取消</AppButton>
        <AppButton variant="accent" :loading="merging" @click="runMerge">确认合并</AppButton>
      </template>
    </AppModal>

    <!-- 拆分事件弹窗 -->
    <AppModal v-model:visible="splitVisible" title="拆分事件" width="520px">
      <div class="split-current">
        <strong>{{ splitForm.eventTitle }}</strong>
        <span class="merge-time">时间范围：{{ splitForm.timeLabel }}</span>
      </div>
      <el-form label-position="top">
        <el-form-item label="纪元单位">
          <el-input v-model="splitForm.eraUnit" placeholder="如：公元、洪武" maxlength="20" />
        </el-form-item>
        <el-form-item label="拆分点（格式：年:月, 年:月）">
          <el-input v-model="splitForm.points" placeholder="如：10:3, 15:6 或 10, 15" />
        </el-form-item>
      </el-form>
      <template #footer>
        <AppButton @click="splitVisible = false">取消</AppButton>
        <AppButton variant="accent" :loading="splitting" @click="runSplit">确认拆分</AppButton>
      </template>
    </AppModal>

    <!-- 生成 / 优化结果预览弹窗 -->
    <AppModal
      v-model:visible="previewVisible"
      title="时间线预览"
      width="86%"
      height="86vh"
      :close-on-click-modal="false"
    >
      <div class="preview-layout" v-loading="generating" element-loading-text="AI 生成中，请稍候...">
        <aside class="preview-list">
          <div v-if="previewItems.length === 0" class="preview-empty">等待生成...</div>
          <div
            v-for="(item, idx) in previewItems"
            :key="idx"
            class="preview-item"
            :class="{ active: idx === previewSelected, deleted: item._operation === 'delete' }"
            @click="previewSelected = idx"
          >
            <div class="preview-item-time">{{ formatTimeLabel(item) }}</div>
            <div class="preview-item-title text-ellipsis">{{ item.title || '未命名事件' }}</div>
            <div class="preview-item-badges">
              <el-tag v-if="item._operation === 'add'" size="small" type="success">新增</el-tag>
              <el-tag v-else-if="item._operation === 'modify'" size="small" type="warning">修改</el-tag>
              <el-tag v-else-if="item._operation === 'delete'" size="small" type="danger">删除</el-tag>
              <el-tag v-if="savedIndexes.includes(idx)" size="small" type="info">已保存</el-tag>
            </div>
          </div>
        </aside>

        <section class="preview-content">
          <div class="preview-toolbar">
            <AppButton
              size="small"
              :icon="previewEditing ? View : Edit"
              :disabled="currentPreview?._operation === 'delete'"
              @click="previewEditing = !previewEditing"
            >
              {{ previewEditing ? '预览模式' : '编辑模式' }}
            </AppButton>
          </div>

          <div v-if="currentPreview" class="preview-panels">
            <!-- 删除操作：仅展示原文 -->
            <div v-if="currentPreview._operation === 'delete'" class="preview-panel">
              <div class="panel-label">原文（此事件将被删除）</div>
              <div class="panel-card danger">
                <div class="panel-title">{{ originalOf(currentPreview)?.title || currentPreview.title }}</div>
                <div class="panel-time">
                  {{ originalOf(currentPreview) ? formatTimeLabel(originalOf(currentPreview)) : formatTimeLabel(currentPreview) }}
                </div>
                <div class="panel-text">
                  {{ originalOf(currentPreview)?.description || currentPreview.completeContent || '---' }}
                </div>
              </div>
            </div>

            <template v-else>
              <div class="preview-panel">
                <div class="panel-label">原文</div>
                <div v-if="originalOf(currentPreview)" class="panel-card">
                  <div class="panel-title">{{ originalOf(currentPreview).title }}</div>
                  <div class="panel-time">{{ formatTimeLabel(originalOf(currentPreview)) }}</div>
                  <div class="panel-text">{{ originalOf(currentPreview).description || '---' }}</div>
                </div>
                <div v-else class="panel-card empty">
                  <el-icon :size="28"><Plus /></el-icon>
                  <span>无原文（新增事件）</span>
                </div>
              </div>

              <div class="preview-panel">
                <div class="panel-label">修改后</div>
                <div v-if="previewEditing" class="panel-edit">
                  <el-input v-model="currentPreview.title" size="small" placeholder="事件标题" class="edit-title" />
                  <div class="edit-time-grid">
                    <el-input v-model="currentPreview.era_unit" size="small" placeholder="纪元单位" />
                    <el-input-number v-model="currentPreview.start_year" :controls="false" :min="-9999" :max="9999" size="small" placeholder="开始年" class="full-width" />
                    <el-input-number v-model="currentPreview.start_month" :controls="false" :min="0" :max="12" size="small" placeholder="开始月" class="full-width" />
                    <el-input-number v-model="currentPreview.end_year" :controls="false" :min="-9999" :max="9999" size="small" placeholder="结束年" class="full-width" />
                    <el-input-number v-model="currentPreview.end_month" :controls="false" :min="0" :max="12" size="small" placeholder="结束月" class="full-width" />
                  </div>
                  <el-input
                    v-model="currentPreview.completeContent"
                    type="textarea"
                    :rows="10"
                    resize="none"
                    placeholder="事件描述..."
                  />
                  <div class="edit-actions">
                    <AppButton size="small" variant="ai" :icon="MagicStick" :loading="aiBusy" @click="aiOptimizePreviewItem">
                      AI 优化
                    </AppButton>
                    <AppButton size="small" variant="success" :loading="saving" @click="savePreviewItem(previewSelected)">
                      保存此项
                    </AppButton>
                  </div>
                </div>
                <div v-else class="panel-card">
                  <div class="panel-title">{{ currentPreview.title }}</div>
                  <div class="panel-time">{{ formatTimeLabel(currentPreview) }}</div>
                  <div class="panel-text">{{ currentPreview.completeContent || currentPreview.description || '---' }}</div>
                </div>
              </div>
            </template>
          </div>

          <div v-else class="preview-empty-panel">
            <el-icon :size="32"><Clock /></el-icon>
            <span>请选择左侧事件查看详情</span>
          </div>
        </section>
      </div>
      <template #footer>
        <AppButton @click="previewVisible = false">关闭</AppButton>
        <AppButton variant="success" :loading="savingAll" :disabled="generating || previewItems.length === 0" @click="saveAllPreview">
          全部保存
        </AppButton>
      </template>
    </AppModal>

    <!-- 一致性检查结果弹窗 -->
    <AppModal v-model:visible="checkVisible" title="时间线一致性检查" width="760px" height="80vh">
      <div v-loading="checking" element-loading-text="AI 检查中，请稍候..." class="check-body">
        <div v-if="!checking && issues.length === 0" class="check-pass">
          <el-icon :size="44" color="var(--success)"><CircleCheckFilled /></el-icon>
          <p>{{ passMessage || '时间线整体合理，未发现问题。' }}</p>
        </div>
        <div v-else-if="!checking" class="issue-list">
          <div v-for="(issue, idx) in issues" :key="idx" class="issue-card glass-surface">
            <div class="issue-head">
              <el-tag :type="issueTagType(issue.type)" effect="dark">{{ issueLabel(issue.type) }}</el-tag>
            </div>
            <div class="issue-events">
              <div v-for="(evt, ei) in issue.eventData" :key="ei" class="issue-event">
                <div class="issue-event-title text-ellipsis">{{ evt.title }}</div>
                <div v-if="evt.time" class="issue-event-time">{{ evt.time }}</div>
                <div class="issue-event-desc">{{ evt.desc || '---' }}</div>
              </div>
            </div>
            <div class="issue-reason">原因：{{ issue.description }}</div>
            <el-input
              v-model="issue.solution"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="输入解决方案（留空则 AI 自行判断）..."
            />
          </div>
        </div>
      </div>
      <template #footer>
        <AppButton @click="checkVisible = false">关闭</AppButton>
        <AppButton
          v-if="issues.length > 0"
          variant="ai"
          :icon="MagicStick"
          :loading="optimizing"
          @click="runCheckOptimize"
        >
          AI 一键优化
        </AppButton>
      </template>
    </AppModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import {
  /* Search, */ Plus, Edit, View, Delete, MagicStick, Connection, Scissor,
  CircleCheckFilled, /* WarningFilled, */ Clock,
} from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import { timelineApi, timelineUrls } from '@/api/timeline'
import { createSseController, streamRequest } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import { extractJsonFromString } from '@/utils/json'
import { escapeHtml } from '@/utils/format'

const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')
const pageHeaderRightRef = inject('pageHeaderRightRef')
const pageHeaderCenterRef = inject('pageHeaderCenterRef')

// ===== 流式 ITEM 标记解析（════ITEM_START/END════ 包裹 JSON） =====
const ITEM_START = '════ITEM_START════'
const ITEM_END = '════ITEM_END════'

function createItemParser(onItem) {
  let buffer = ''
  let inItem = false
  let itemBuffer = ''

  function feed(chunk) {
    buffer += chunk
    for (;;) {
      if (!inItem) {
        const startIdx = buffer.indexOf(ITEM_START)
        if (startIdx === -1) {
          // 保留尾部，防止标记跨 chunk 截断
          if (buffer.length > ITEM_START.length + 10) {
            buffer = buffer.slice(-(ITEM_START.length + 10))
          }
          break
        }
        inItem = true
        buffer = buffer.slice(startIdx + ITEM_START.length)
      } else {
        const endIdx = buffer.indexOf(ITEM_END)
        if (endIdx === -1) {
          itemBuffer += buffer
          buffer = ''
          break
        }
        itemBuffer += buffer.slice(0, endIdx)
        buffer = buffer.slice(endIdx + ITEM_END.length)
        inItem = false
        const jsonStr = itemBuffer
        itemBuffer = ''
        const parsed = extractJsonFromString(jsonStr.trim())
        if (parsed) onItem(parsed)
      }
    }
  }

  return { feed }
}

function extractItems(text) {
  const items = []
  createItemParser((p) => items.push(p)).feed(text || '')
  return items
}

// ===== 基础状态 =====
const loading = ref(false)
const events = ref([])
const worldviewInfo = ref(null)
const searchQuery = ref('')
const timeFilter = ref('')

async function loadEvents() {
  loading.value = true
  try {
    const data = await timelineApi.getEvents(projectId.value)
    const list = data.events || data || []
    events.value = [...list].sort(
      (a, b) =>
        (a.start_year || 0) - (b.start_year || 0) ||
        (a.start_month || 0) - (b.start_month || 0) ||
        (a.end_year || 0) - (b.end_year || 0) ||
        (a.end_month || 0) - (b.end_month || 0),
    )
    worldviewInfo.value = data.worldview_info || null
    refreshHeader()
  } catch {
    // request.js 已统一提示
  } finally {
    loading.value = false
  }
}

// ===== 时间工具 =====
function extractTimeYear(event) {
  const era = event.era_unit || ''
  const year = event.start_year
  if (year === 0 || year === undefined || year === null) {
    return era ? `${era}元年` : '元年'
  }
  if (year < 0) {
    return era ? `${era}前${Math.abs(year)}年` : `前${Math.abs(year)}年`
  }
  return era ? `${era}${year}年` : `${year}年`
}

function formatTimePoint(eraUnit, year, month) {
  if (!year && !month && year !== 0) return ''
  let result = eraUnit || ''
  if (year === 0) {
    result += '元年'
  } else if (year !== undefined && year !== null) {
    if (year < 0 && eraUnit) {
      result += `前${Math.abs(year)}年`
    } else {
      result += `${year}年`
    }
  }
  if (month && month !== 0) result += `${month}月`
  return result
}

function formatTimeFromFields(event) {
  const start = formatTimePoint(event.era_unit, event.start_year, event.start_month)
  const end = formatTimePoint(event.era_unit, event.end_year, event.end_month)
  if (start && end) return `${start} - ${end}`
  return start || end || ''
}

function formatTimeLabel(event) {
  if (!event) return ''
  if (event.time_range) return event.time_range
  return formatTimeFromFields(event)
}

// ===== 筛选与分组 =====
const yearOptions = computed(() => {
  const yearMap = new Map()
  events.value.forEach((e) => {
    const label = extractTimeYear(e)
    if (!yearMap.has(label) || (e.start_year || 0) < yearMap.get(label)) {
      yearMap.set(label, e.start_year || 0)
    }
  })
  return [...yearMap.entries()]
    .sort((a, b) => a[1] - b[1])
    .map(([label]) => label)
})

const filteredEvents = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const tf = timeFilter.value
  return events.value.filter((e) => {
    if (tf && extractTimeYear(e) !== tf) return false
    if (q) {
      const timeRange =
        `${e.era_unit || ''}${e.start_year}${e.start_month}${e.end_year}${e.end_month}`.toLowerCase()
      const title = (e.title || '').toLowerCase()
      const desc = (e.description || '').toLowerCase()
      if (!timeRange.includes(q) && !title.includes(q) && !desc.includes(q)) return false
    }
    return true
  })
})

const groupedEvents = computed(() => {
  const groups = new Map()
  filteredEvents.value.forEach((e) => {
    const label = extractTimeYear(e)
    if (!groups.has(label)) {
      groups.set(label, { label, minYear: e.start_year || 0, items: [] })
    }
    const g = groups.get(label)
    g.items.push(e)
    if ((e.start_year || 0) < g.minYear) g.minYear = e.start_year || 0
  })
  return [...groups.values()].sort((a, b) => a.minYear - b.minYear)
})

// ===== 新增 / 编辑事件 =====
const editVisible = ref(false)
const saving = ref(false)
const aiBusy = ref(false)
const editForm = reactive({
  id: null,
  title: '',
  era_unit: '',
  start_year: 0,
  start_month: 0,
  end_year: 0,
  end_month: 0,
  description: '',
})

function resetEditForm() {
  editForm.id = null
  editForm.title = ''
  editForm.era_unit = ''
  editForm.start_year = 0
  editForm.start_month = 0
  editForm.end_year = 0
  editForm.end_month = 0
  editForm.description = ''
}

function openAddModal() {
  resetEditForm()
  editVisible.value = true
}

function openEditModal(ev) {
  editForm.id = ev.id
  editForm.title = ev.title || ''
  editForm.era_unit = ev.era_unit || ''
  editForm.start_year = ev.start_year || 0
  editForm.start_month = ev.start_month || 0
  editForm.end_year = ev.end_year || 0
  editForm.end_month = ev.end_month || 0
  editForm.description = ev.description || ''
  editVisible.value = true
}

function buildEventPayload() {
  return {
    title: editForm.title.trim(),
    era_unit: editForm.era_unit.trim(),
    start_year: Number(editForm.start_year) || 0,
    start_month: Number(editForm.start_month) || 0,
    end_year: Number(editForm.end_year) || 0,
    end_month: Number(editForm.end_month) || 0,
    description: editForm.description.trim(),
    is_active: true,
  }
}

async function saveEvent() {
  if (!editForm.title.trim()) {
    showError('请输入事件标题')
    return
  }
  saving.value = true
  try {
    const payload = buildEventPayload()
    const res = editForm.id
      ? await timelineApi.updateEvent(projectId.value, editForm.id, payload)
      : await timelineApi.createEvent(projectId.value, payload)
    if (res.success || res.id) {
      showSuccess(editForm.id ? '更新成功' : '创建成功')
      editVisible.value = false
      loadEvents()
    } else {
      showError(res.message || '保存失败')
    }
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

function confirmDeleteEvent() {
  const id = editForm.id
  if (!id) return
  showConfirmModal({
    title: '确认删除',
    message: '确定要删除这个时间线事件吗？此操作不可撤销。',
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      try {
        await timelineApi.deleteEvent(projectId.value, id)
        close()
        editVisible.value = false
        showSuccess('删除成功')
        loadEvents()
      } catch {
        // 统一提示
      }
    },
  })
}

// ===== 相邻事件上下文 =====
function extractEventContext(e) {
  return {
    title: e.title || '',
    era_unit: e.era_unit || '',
    start_year: e.start_year || 0,
    start_month: e.start_month || 0,
    end_year: e.end_year || 0,
    end_month: e.end_month || 0,
    description: e.description || '',
  }
}

function buildAdjacentContext(eventIndex) {
  const list = events.value
  if (eventIndex === -1) {
    return {
      prevItem: list.length ? extractEventContext(list[list.length - 1]) : null,
      nextItem: null,
    }
  }
  return {
    prevItem: eventIndex > 0 ? extractEventContext(list[eventIndex - 1]) : null,
    nextItem: eventIndex < list.length - 1 ? extractEventContext(list[eventIndex + 1]) : null,
  }
}

function applyAiFields(parsed) {
  if (parsed.title) editForm.title = parsed.title
  if (parsed.era_unit !== undefined) editForm.era_unit = parsed.era_unit || ''
  if (parsed.start_year !== undefined) editForm.start_year = Number(parsed.start_year) || 0
  if (parsed.start_month !== undefined) editForm.start_month = Number(parsed.start_month) || 0
  if (parsed.end_year !== undefined) editForm.end_year = Number(parsed.end_year) || 0
  if (parsed.end_month !== undefined) editForm.end_month = Number(parsed.end_month) || 0
  if (parsed.content) editForm.description = parsed.content
}

// AI 生成字段（新增模式）
async function aiGenerateFields() {
  const description = editForm.description.trim()
  if (!description) {
    showError('请先输入事件描述')
    return
  }
  aiBusy.value = true
  const { prevItem, nextItem } = buildAdjacentContext(-1)
  try {
    const raw = await sseController.stream(timelineUrls.generateFields(projectId.value), {
      body: { description, prev_item: prevItem, next_item: nextItem },
    })
    const parsed = extractJsonFromString(raw.trim())
    if (parsed) {
      applyAiFields(parsed)
      showSuccess('AI 生成完成')
    } else {
      showError('AI 返回内容解析失败，未返回有效 JSON')
    }
  } catch (err) {
    showError('AI 生成失败：' + err.message)
  } finally {
    aiBusy.value = false
  }
}

// AI 优化事件（编辑模式）
async function aiOptimizeEvent() {
  if (!editForm.id) {
    showError('请先选择一个时间线事件')
    return
  }
  aiBusy.value = true
  const idx = events.value.findIndex((e) => e.id === editForm.id)
  const { prevItem, nextItem } = buildAdjacentContext(idx)
  try {
    const raw = await sseController.stream(timelineUrls.optimizeSingle(projectId.value), {
      body: {
        title: editForm.title.trim(),
        era_unit: editForm.era_unit.trim(),
        start_year: Number(editForm.start_year) || 0,
        start_month: Number(editForm.start_month) || 0,
        end_year: Number(editForm.end_year) || 0,
        end_month: Number(editForm.end_month) || 0,
        content: editForm.description.trim(),
        prev_item: prevItem,
        next_item: nextItem,
      },
    })
    const parsed = extractJsonFromString(raw.trim())
    if (parsed) {
      applyAiFields(parsed)
      showSuccess('AI 优化完成')
    } else {
      showError('AI 返回内容解析失败，未返回有效 JSON')
    }
  } catch (err) {
    showError('AI 优化失败：' + err.message)
  } finally {
    aiBusy.value = false
  }
}

// ===== 合并事件 =====
const mergeVisible = ref(false)
const merging = ref(false)
const mergeSelected = reactive({})

function openMergeModal() {
  Object.keys(mergeSelected).forEach((k) => delete mergeSelected[k])
  events.value.forEach((e) => {
    mergeSelected[e.id] = e.id === editForm.id
  })
  mergeVisible.value = true
}

async function runMerge() {
  const ids = events.value.filter((e) => mergeSelected[e.id]).map((e) => e.id)
  if (ids.length < 2) {
    showError('请至少选择 2 个事件进行合并')
    return
  }
  merging.value = true
  try {
    const res = await timelineApi.merge(projectId.value, { event_ids: ids })
    if (res.success) {
      showSuccess('合并成功')
      mergeVisible.value = false
      editVisible.value = false
      loadEvents()
    } else {
      showError(res.message || '合并失败')
    }
  } catch {
    // 统一提示
  } finally {
    merging.value = false
  }
}

// ===== 拆分事件 =====
const splitVisible = ref(false)
const splitting = ref(false)
const splitForm = reactive({ eventId: null, eventTitle: '', timeLabel: '', eraUnit: '', points: '' })

function openSplitModal() {
  if (!editForm.id) {
    showError('请先选择一个时间线事件')
    return
  }
  const ev = events.value.find((e) => e.id === editForm.id)
  splitForm.eventId = editForm.id
  splitForm.eventTitle = editForm.title
  splitForm.timeLabel = ev ? formatTimeLabel(ev) : ''
  splitForm.eraUnit = editForm.era_unit || ''
  splitForm.points = ''
  splitVisible.value = true
}

async function runSplit() {
  const pointsInput = splitForm.points.trim()
  if (!pointsInput) {
    showError('请输入拆分点')
    return
  }
  const splitPoints = pointsInput
    .split(',')
    .map((p) => {
      const parts = p.trim().split(':')
      const year = parseInt(parts[0], 10) || 0
      const month = parts.length > 1 ? parseInt(parts[1], 10) || 0 : 0
      return { year, month }
    })
    .filter((p) => p.year !== 0 || p.month !== 0)

  if (splitPoints.length === 0) {
    showError('拆分点不能为空')
    return
  }

  splitting.value = true
  try {
    const res = await timelineApi.split(projectId.value, {
      event_id: splitForm.eventId,
      era_unit: splitForm.eraUnit.trim(),
      split_points: splitPoints,
    })
    if (res.success) {
      showSuccess('拆分成功')
      splitVisible.value = false
      editVisible.value = false
      loadEvents()
    } else {
      showError(res.message || '拆分失败')
    }
  } catch {
    // 统一提示
  } finally {
    splitting.value = false
  }
}

// ===== AI 批量生成 =====
const genVisible = ref(false)
const genPrompt = ref('')
const generating = ref(false)

function openGenModal() {
  genPrompt.value = ''
  genVisible.value = true
}

async function runGenerate() {
  const extra = genPrompt.value.trim()
  genVisible.value = false

  // 初始化预览弹窗
  generating.value = true
  previewItems.value = []
  previewSelected.value = 0
  previewEditing.value = false
  savedIndexes.value = []
  previewDeletedIds.value = []
  previewOriginal.value = [...events.value]
  previewVisible.value = true

  const existing = events.value
  const parser = createItemParser((parsed) => {
    const matched = existing.find(
      (item) =>
        (item.title && parsed.title && item.title === parsed.title) ||
        (item.era_unit === parsed.era_unit &&
          item.start_year === parsed.start_year &&
          item.start_month === parsed.start_month &&
          item.end_year === parsed.end_year &&
          item.end_month === parsed.end_month),
    )
    previewItems.value.push({
      ...parsed,
      id: matched ? matched.id : null,
      completeContent: parsed.content || '',
      description: parsed.content || '',
    })
  })

  try {
    await sseController.stream(timelineUrls.generate(projectId.value), {
      body: {
        messages: [{ role: 'user', content: `根据世界观生成完整时间线。${extra}` }],
        extra_prompt: extra,
      },
    }, (chunk) => parser.feed(chunk))

    if (previewItems.value.length === 0) {
      showError('未生成任何时间线事件')
      previewVisible.value = false
    } else {
      showSuccess('生成完成')
    }
  } catch (err) {
    if (previewItems.value.length === 0) previewVisible.value = false
    showError('生成失败：' + err.message)
  } finally {
    generating.value = false
  }
}

// ===== 预览弹窗（生成 / 优化结果） =====
const previewVisible = ref(false)
const previewItems = ref([])
const previewSelected = ref(0)
const previewEditing = ref(false)
const savedIndexes = ref([])
const previewDeletedIds = ref([])
const previewOriginal = ref([])
const savingAll = ref(false)

const currentPreview = computed(() => previewItems.value[previewSelected.value] || null)

function originalOf(item) {
  if (!item || item._operation === 'add') return null
  return (
    previewOriginal.value.find(
      (ot) =>
        (item.id && ot.id === item.id) ||
        ot.title === item.title ||
        (item._originalTitle && ot.title === item._originalTitle),
    ) || null
  )
}

function previewItemPayload(item) {
  return {
    title: item.title,
    era_unit: item.era_unit || '',
    start_year: Number(item.start_year) || 0,
    start_month: Number(item.start_month) || 0,
    end_year: Number(item.end_year) || 0,
    end_month: Number(item.end_month) || 0,
    description: item.completeContent || item.description || '',
    is_active: item.is_active !== false,
  }
}

async function savePreviewItem(index) {
  const item = previewItems.value[index]
  if (!item || item._operation === 'delete') return
  saving.value = true
  try {
    const payload = previewItemPayload(item)
    const res = item.id
      ? await timelineApi.updateEvent(projectId.value, item.id, payload)
      : await timelineApi.createEvent(projectId.value, payload)
    if (res.success || res.id) {
      if (res.id) item.id = res.id
      if (!savedIndexes.value.includes(index)) savedIndexes.value.push(index)
      showSuccess(res.message || '保存成功')
      loadEvents()
    } else {
      showError(res.message || '保存失败')
    }
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

async function saveAllPreview() {
  savingAll.value = true
  try {
    const toSave = previewItems.value
      .map((item, index) => ({ item, index }))
      .filter(({ item, index }) => item._operation !== 'delete' && !savedIndexes.value.includes(index))

    const CONCURRENCY = 5
    let successCount = 0
    for (let batchStart = 0; batchStart < toSave.length; batchStart += CONCURRENCY) {
      const batch = toSave.slice(batchStart, batchStart + CONCURRENCY)
      const results = await Promise.allSettled(
        batch.map(async ({ item, index }) => {
          const payload = previewItemPayload(item)
          const res = item.id
            ? await timelineApi.updateEvent(projectId.value, item.id, payload)
            : await timelineApi.createEvent(projectId.value, payload)
          if (res.success || res.id) {
            if (res.id) item.id = res.id
            savedIndexes.value.push(index)
            return true
          }
          return false
        }),
      )
      results.forEach((r) => {
        if (r.status === 'fulfilled' && r.value) successCount++
      })
    }

    // 并发删除标记为 delete 的事件
    await Promise.allSettled(
      previewDeletedIds.value.map((id) =>
        timelineApi.deleteEvent(projectId.value, id).catch((e) => console.error('删除事件失败:', id, e)),
      ),
    )
    previewDeletedIds.value = []

    const saveableCount = previewItems.value.filter((i) => i._operation !== 'delete').length
    const savedCount = new Set(savedIndexes.value).size
    if (savedCount >= saveableCount) {
      showSuccess('全部保存成功')
    } else {
      showWarning(`保存完成：${successCount} 项成功，共 ${saveableCount} 项`)
    }
    previewVisible.value = false
    loadEvents()
  } catch (err) {
    showError('保存失败：' + err.message)
  } finally {
    savingAll.value = false
  }
}

function previewCtx(item) {
  return {
    title: item.title || '',
    era_unit: item.era_unit || '',
    start_year: Number(item.start_year) || 0,
    start_month: Number(item.start_month) || 0,
    end_year: Number(item.end_year) || 0,
    end_month: Number(item.end_month) || 0,
    description: item.completeContent || item.description || '',
  }
}

// 预览弹窗中的 AI 优化单项
async function aiOptimizePreviewItem() {
  const idx = previewSelected.value
  const item = previewItems.value[idx]
  if (!item) return
  aiBusy.value = true
  const prevItem = idx > 0 ? previewCtx(previewItems.value[idx - 1]) : null
  const nextItem = idx < previewItems.value.length - 1 ? previewCtx(previewItems.value[idx + 1]) : null
  try {
    const raw = await sseController.stream(timelineUrls.optimizeSingle(projectId.value), {
      body: {
        title: item.title || '',
        era_unit: item.era_unit || '',
        start_year: Number(item.start_year) || 0,
        start_month: Number(item.start_month) || 0,
        end_year: Number(item.end_year) || 0,
        end_month: Number(item.end_month) || 0,
        content: item.completeContent || '',
        prev_item: prevItem,
        next_item: nextItem,
      },
    })
    const parsed = extractJsonFromString(raw.trim())
    if (parsed) {
      if (parsed.title) item.title = parsed.title
      if (parsed.era_unit !== undefined) item.era_unit = parsed.era_unit || ''
      if (parsed.start_year !== undefined) item.start_year = Number(parsed.start_year) || 0
      if (parsed.start_month !== undefined) item.start_month = Number(parsed.start_month) || 0
      if (parsed.end_year !== undefined) item.end_year = Number(parsed.end_year) || 0
      if (parsed.end_month !== undefined) item.end_month = Number(parsed.end_month) || 0
      if (parsed.content) {
        item.completeContent = parsed.content
        item.description = parsed.content
      }
      showSuccess('AI 优化完成')
    } else {
      showError('AI 返回内容解析失败')
    }
  } catch (err) {
    showError('AI 优化失败：' + err.message)
  } finally {
    aiBusy.value = false
  }
}

// ===== 一致性检查 =====
const checkVisible = ref(false)
const checking = ref(false)
const optimizing = ref(false)
const issues = ref([])
const passMessage = ref('')

const TYPE_LABELS = {
  duplicate: '重复事件',
  conflict: '时间冲突',
  contradiction: '逻辑矛盾',
  unreasonable: '时间不合理',
}
const TYPE_TAG_TYPES = {
  duplicate: 'warning',
  conflict: 'danger',
  contradiction: 'danger',
  unreasonable: 'info',
}

function issueLabel(type) {
  return TYPE_LABELS[type] || type
}

function issueTagType(type) {
  return TYPE_TAG_TYPES[type] || 'info'
}

async function runCheck() {
  checking.value = true
  checkVisible.value = true
  issues.value = []
  passMessage.value = ''
  try {
    const raw = await sseController.stream(timelineUrls.check(projectId.value), { body: {} })
    const parsedItems = extractItems(raw)

    const passItem = parsedItems.find((i) => i.type === 'pass')
    if (passItem) {
      passMessage.value = passItem.description || '时间线整体合理，未发现问题。'
      return
    }

    // 按事件 ID 对去重
    const seenPairs = new Set()
    const deduped = []
    parsedItems.forEach((issue) => {
      const evts = issue.events || []
      const key = evts
        .map((e) => (typeof e === 'object' ? e.id : e))
        .sort()
        .join('|||')
      if (seenPairs.has(key)) return
      seenPairs.add(key)
      deduped.push(issue)
    })

    issues.value = deduped.map((issue) => {
      const evts = issue.events || []
      const eventData = evts
        .map((evtInfo) => {
          const isObj = evtInfo && typeof evtInfo === 'object'
          const id = isObj ? evtInfo.id : null
          const title = isObj ? evtInfo.title : evtInfo
          const data = id
            ? events.value.find((e) => e.id == id)
            : events.value.find((e) => e.title === title)
          return {
            id: data?.id ?? id,
            title: data?.title || title || '',
            time: data ? formatTimeLabel(data) : '',
            desc: data?.description || '',
          }
        })
        .filter((e) => e.title)
      return {
        type: issue.type,
        description: issue.description || issueLabel(issue.type),
        solution: '',
        eventData,
      }
    })

    if (issues.value.length === 0) {
      passMessage.value = '时间线整体合理，未发现问题。'
    }
  } catch (err) {
    checkVisible.value = false
    showError('AI 检查失败：' + err.message)
  } finally {
    checking.value = false
  }
}

// 增量变更合并（check/optimize 返回 add/modify/delete 操作）
function mergeIncrementalChanges(baseEvents, changes) {
  const result = []
  const deletedIds = []

  for (const change of changes) {
    if (change.operation === 'add') {
      const existingMatch = baseEvents.find(
        (t) => (t.title || '').trim() === (change.title || '').trim(),
      )
      if (existingMatch) continue
      result.push({
        ...change,
        id: null,
        completeContent: change.content || '',
        description: change.content || '',
        _operation: 'add',
      })
    } else if (change.operation === 'modify') {
      const matchTitle = (change.match_title || '').trim()
      const original = baseEvents.find((t) => (t.title || '').trim() === matchTitle)
      if (original) {
        const hasTimeChange =
          change.start_year !== undefined ||
          change.start_month !== undefined ||
          change.end_year !== undefined ||
          change.end_month !== undefined ||
          change.era_unit !== undefined
        const merged = {
          ...original,
          title: change.title || original.title,
          era_unit: change.era_unit !== undefined ? change.era_unit : original.era_unit,
          start_year: change.start_year !== undefined ? change.start_year : original.start_year,
          start_month: change.start_month !== undefined ? change.start_month : original.start_month,
          end_year: change.end_year !== undefined ? change.end_year : original.end_year,
          end_month: change.end_month !== undefined ? change.end_month : original.end_month,
          completeContent: change.content || original.description || '',
          description: change.content || original.description || '',
          _operation: 'modify',
          _originalTitle: matchTitle,
        }
        if (hasTimeChange) delete merged.time_range
        result.push(merged)
      } else {
        result.push({
          ...change,
          id: null,
          completeContent: change.content || '',
          description: change.content || '',
          _operation: 'add',
        })
      }
    } else if (change.operation === 'delete') {
      const matchTitle = (change.match_title || '').trim()
      const original = baseEvents.find((t) => (t.title || '').trim() === matchTitle)
      if (original) {
        if (original.id) deletedIds.push(original.id)
        result.push({
          ...original,
          completeContent: original.description || '',
          description: original.description || '',
          _operation: 'delete',
          _originalTitle: matchTitle,
        })
      }
    }
  }

  return { result, deletedIds }
}

async function runCheckOptimize() {
  optimizing.value = true
  try {
    const typeLabels = {
      duplicate: '重复事件',
      conflict: '时间冲突',
      contradiction: '逻辑矛盾',
      unreasonable: '时间范围不合理',
      order: '时间顺序错误',
    }

    // 按事件分组，合并同一事件的原因
    const eventMap = new Map()
    issues.value.forEach((issue) => {
      const reason = `[${typeLabels[issue.type] || issue.type}] ${issue.description || ''}`
      issue.eventData.forEach((evt) => {
        const key = evt.id ? `id:${evt.id}` : `title:${evt.title}`
        if (!eventMap.has(key)) {
          eventMap.set(key, { id: evt.id || '', title: evt.title, reasons: [] })
        }
        const entry = eventMap.get(key)
        if (!entry.reasons.includes(reason)) entry.reasons.push(reason)
      })
    })

    const eventList = [...eventMap.values()].filter((e) => e.title)
    if (eventList.length === 0) {
      showError('未找到有效的事件信息')
      return
    }

    const userSolution = issues.value
      .map((i) => i.solution)
      .filter((s) => s && s.trim())
      .join('\n')

    const raw = await streamRequest(timelineUrls.checkOptimize(projectId.value), {
      body: {
        events: eventList.map((e) => ({ id: e.id || '', title: e.title, reasons: e.reasons })),
        user_solution: userSolution,
      },
    })

    const allChanges = []
    extractItems(raw).forEach((parsed) => {
      const numOrUndef = (v) => (v !== undefined && v !== null ? Number(v) || 0 : undefined)
      const baseChange = {
        match_title: parsed.match_title,
        title: parsed.title,
        era_unit: parsed.era_unit,
        start_year: numOrUndef(parsed.start_year),
        start_month: numOrUndef(parsed.start_month),
        end_year: numOrUndef(parsed.end_year),
        end_month: numOrUndef(parsed.end_month),
        content: parsed.description,
      }
      if (parsed.merge_with) {
        allChanges.push({ operation: 'modify', ...baseChange })
        allChanges.push({ operation: 'delete', match_title: parsed.merge_with })
      } else if (parsed.match_title) {
        allChanges.push({ operation: 'modify', ...baseChange })
      }
    })

    if (allChanges.length === 0) {
      showError('未生成任何调整方案，请补充解决方案后重试')
      return
    }

    previewOriginal.value = [...events.value]
    const { result, deletedIds } = mergeIncrementalChanges(events.value, allChanges)
    previewItems.value = result
    previewDeletedIds.value = deletedIds
    previewSelected.value = 0
    previewEditing.value = false
    savedIndexes.value = []

    const modifyCount = allChanges.filter((c) => c.operation === 'modify').length
    const deleteCount = allChanges.filter((c) => c.operation === 'delete').length
    const parts = []
    if (modifyCount) parts.push(`修改 ${modifyCount} 个`)
    if (deleteCount) parts.push(`删除 ${deleteCount} 个`)

    checkVisible.value = false
    previewVisible.value = true
    showSuccess(`已生成方案：${parts.join('，')}事件`)
  } catch (err) {
    showError('AI 优化失败：' + err.message)
  } finally {
    optimizing.value = false
  }
}

// ===== Header 注入 =====
function refreshHeader() {
  // 筛选栏注入 header 中间
  const buildFilterBar = (years) => {
    const yearOpts = (years || []).map(y => `<option value="${escapeHtmlAttr(y)}">${escapeHtml(y)}</option>`).join('')
    const searchVal = searchQuery.value ? `value="${escapeHtmlAttr(searchQuery.value)}"` : ''
    const timeVal = timeFilter.value
    return `
      <div class="tl-filter-bar">
        <div class="tl-search-box">
          <i class="fas fa-search"></i>
          <input type="text" id="tl-search-input" placeholder="搜索事件标题 / 描述 / 时间..." ${searchVal} />
        </div>
        <select id="tl-time-select">
          <option value="">全部时间</option>
          ${yearOpts}
        </select>
      </div>
    `
  }
  pageHeaderCenterRef.value = buildFilterBar(yearOptions.value)

  // 绑定事件 & 恢复选中状态
  setTimeout(() => {
    const searchInput = document.getElementById('tl-search-input')
    const timeSelect = document.getElementById('tl-time-select')
    if (searchInput) searchInput.addEventListener('input', window.__tlFilterSearch)
    if (timeSelect) {
      timeSelect.addEventListener('change', window.__tlFilterTime)
      if (timeFilter.value) timeSelect.value = timeFilter.value
    }
  }, 0)
}
function escapeHtmlAttr(s) { return String(s).replace(/"/g, '&quot;').replace(/</g, '&lt;') }
window.__tlFilterSearch = (e) => { searchQuery.value = e.target.value }
window.__tlFilterTime = (e) => { timeFilter.value = e.target.value }

onMounted(() => {
  setPageHeader('时间线', '故事时间线管理与 AI 一致性审查')
  refreshHeader()
  loadEvents()
})

onBeforeUnmount(() => {
  sseController.abort()
  pageHeaderRightRef.value = ''
  pageHeaderCenterRef.value = ''
  delete window.__tlFilterSearch
  delete window.__tlFilterTime
})
</script>

<style lang="scss">
.project-layout:has(.timeline-view) {
  height: 100vh;
  overflow: hidden;
}
.project-layout:has(.timeline-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}
.project-layout:has(.timeline-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}

// ===== Header 筛选栏（注入到 project-topbar，需 unscoped） =====
.tl-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.tl-search-box {
  position: relative;
  width: 220px;
  flex-shrink: 0;

  i {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 11px;
    pointer-events: none;
  }

  input {
    width: 100%;
    height: 32px;
    padding: 0 10px 0 28px;
    border: 1px solid rgba(91, 106, 122, 0.4);
    border-radius: 8px;
    font-size: 12px;
    background: rgba(30, 41, 59, 0.5);
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;

    &:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.15);
    }

    &::placeholder {
      color: var(--text-muted);
    }
  }
}

.tl-filter-bar select {
  height: 32px;
  padding: 0 26px 0 10px;
  border: 1px solid rgba(91, 106, 122, 0.4);
  border-radius: 8px;
  font-size: 12px;
  background: rgba(30, 41, 59, 0.5);
  color: var(--text-secondary);
  cursor: pointer;
  outline: none;
  flex-shrink: 0;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%239ca3af' d='M1.5 3.5l3.5 3.5 3.5-3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.15);
  }

  option {
    background: var(--surface, #1f2937);
    color: var(--text-primary, #f9fafb);
  }
}
</style>

<style lang="scss" scoped>
.timeline-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  height: 100%;
}

// 主面板
.timeline-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.timeline-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

// 时间线轨道
.timeline-track {
  position: relative;
  padding-left: 26px;

  &::before {
    content: '';
    position: absolute;
    left: 8px;
    top: 10px;
    bottom: 10px;
    width: 2px;
    background: linear-gradient(180deg, var(--primary), rgba(129, 140, 248, 0.05));
    border-radius: 2px;
    opacity: 0.5;
  }
}

.year-group {
  margin-bottom: 26px;

  &:last-child {
    margin-bottom: 0;
  }
}

.year-marker {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  margin-left: -26px;
  padding: 6px 0 6px 3px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.98) 60%, rgba(15, 23, 42, 0));

  .year-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--primary);
    box-shadow: 0 0 0 4px rgba(129, 140, 248, 0.18);
    margin-left: 3px;
    flex-shrink: 0;
  }

  .year-label {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.5px;
  }

  .year-count {
    font-size: 11px;
    font-weight: 600;
    color: var(--primary);
    background: rgba(129, 140, 248, 0.15);
    padding: 1px 7px;
    border-radius: 10px;
    line-height: 1.5;
  }
}

.year-events {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-card {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover {
    transform: translateX(4px);
    border-color: rgba(129, 140, 248, 0.4);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  }
}

.event-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.event-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.event-time-tag {
  flex-shrink: 0;
}

.event-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

// 弹窗通用
.modal-tip {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.6;
}

.full-width {
  width: 100%;
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

// 弹窗头部装饰
.edit-header-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(167, 139, 250, 0.06));
  border: 1px solid rgba(129, 140, 248, 0.15);
}

.edit-header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--primary), #a78bfa);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.3);
}

.edit-header-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.edit-header-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}

.edit-header-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}

.edit-form {
  display: flex;
  flex-direction: column;
}

.form-section {
  padding: 18px 0;
  & + .form-section {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
}

.form-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 16px;
  letter-spacing: 0.3px;

  .title-bar {
    width: 3px;
    height: 14px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.3);
  }
}

// 时间范围卡片
.time-range-card {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  padding: 16px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.time-point {
  flex: 1;
  min-width: 0;
}

.time-point-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.time-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}

.time-input {
  flex: 1;
  min-width: 0;
}

.time-unit {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.time-separator {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(129, 140, 248, 0.1);
  color: var(--primary);
  margin-bottom: 2px;
}

.edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 10px;
  flex-wrap: wrap;
}

.footer-left,
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

// 弹窗内表单控件增强
:deep(.app-glass-dialog) {
  .el-form-item {
    margin-bottom: 18px;
    &:last-child { margin-bottom: 0; }
  }

  .el-form-item__label {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.2px;
    margin-bottom: 6px;
  }

  .el-input__wrapper {
    border-radius: 8px;
    transition: all 0.25s ease;
    &:hover {
      box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.35) inset;
    }
  }

  .el-input__wrapper.is-focus {
    box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px rgba(99, 102, 241, 0.12);
  }

  .el-textarea__inner {
    border-radius: 10px;
    padding: 14px 16px;
    transition: all 0.25s ease;
    &:focus {
      box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 3px rgba(99, 102, 241, 0.12);
    }
  }

  .el-input-number .el-input__wrapper {
    padding-left: 10px;
    padding-right: 10px;
  }

  .el-input__count-inner {
    font-size: 11px;
    color: var(--text-muted);
  }
}

// 合并弹窗
.merge-list {
  max-height: 52vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 4px;
}

.merge-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);

  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  .merge-title {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
    min-width: 0;
  }

  .merge-time {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }
}

// 拆分弹窗
.split-current {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: rgba(129, 140, 248, 0.08);
  border: 1px solid rgba(129, 140, 248, 0.2);
  margin-bottom: 16px;
  font-size: 13px;

  .merge-time {
    font-size: 12px;
    color: var(--text-muted);
  }
}

// 预览弹窗
.preview-layout {
  display: flex;
  gap: 14px;
  min-height: 480px;
  height: 70vh;
}

.preview-list {
  width: 240px;
  flex-shrink: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

.preview-empty,
.preview-empty-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  color: var(--text-muted);
  font-size: 13px;
  padding: 32px;
  text-align: center;
}

.preview-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  &.active {
    background: rgba(129, 140, 248, 0.12);
    border-color: rgba(129, 140, 248, 0.35);
  }

  &.deleted {
    opacity: 0.55;
  }
}

.preview-item-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 3px;
}

.preview-item-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.preview-item-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.preview-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.preview-toolbar {
  margin-bottom: 10px;
}

.preview-panels {
  flex: 1;
  display: flex;
  gap: 14px;
  min-height: 0;
}

.preview-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.panel-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.panel-card {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);

  &.danger {
    border-color: rgba(239, 68, 68, 0.4);
    background: rgba(239, 68, 68, 0.06);
  }

  &.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 13px;
  }
}

.panel-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.panel-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.panel-text {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

.panel-edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;

  .edit-title {
    font-weight: 600;
  }
}

.edit-time-grid {
  display: grid;
  grid-template-columns: 1.4fr repeat(4, 1fr);
  gap: 8px;
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

// 检查弹窗
.check-body {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
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

.check-pass {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 56px 24px;
  text-align: center;

  p {
    color: var(--text-regular);
    font-size: 14px;
    margin: 0;
  }
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.issue-card {
  padding: 16px;
  border-radius: var(--radius-md);
}

.issue-head {
  margin-bottom: 10px;
}

.issue-events {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
}

.issue-event {
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
}

.issue-event-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.issue-event-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.issue-event-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.issue-reason {
  font-size: 12.5px;
  color: var(--text-regular);
  line-height: 1.6;
  margin-bottom: 10px;
}

@media (max-width: 900px) {
  .preview-layout {
    flex-direction: column;
    height: auto;
  }
  .preview-list {
    width: 100%;
    max-height: 200px;
  }
  .preview-panels {
    flex-direction: column;
  }
  .time-range-card {
    flex-direction: column;
    gap: 12px;
  }
  .time-separator {
    transform: rotate(90deg);
  }
  .edit-time-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
