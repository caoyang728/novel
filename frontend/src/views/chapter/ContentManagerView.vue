<template>
  <div class="reader-review-view">
    <div class="page-actions">
      <el-select
        v-model="currentVersionId"
        class="hd-select"
        placeholder="卷版本"
        :disabled="reviewing"
        @change="onVersionChange"
      >
        <el-option
          v-for="v in volumeVersions"
          :key="v.id"
          :label="`版本 v${v.version_number}${v.is_finalized ? '（已定稿）' : ''}`"
          :value="v.id"
        />
      </el-select>
      <el-select
        v-model="currentVolumeId"
        class="hd-select"
        placeholder="选择卷"
        :disabled="!currentVersionId || reviewing"
        @change="onVolumeChange"
      >
        <el-option
          v-for="vol in volumes"
          :key="vol.id"
          :label="`第${vol.volume_number}卷 ${vol.title || ''}`"
          :value="vol.id"
        />
      </el-select>
      <AppButton v-if="!reviewing" variant="accent" :disabled="!currentVolumeId" @click="startReview">
        <el-icon><Reading /></el-icon>
        <span>开始审阅</span>
      </AppButton>
      <AppButton v-else variant="danger" @click="stopReview">
        <el-icon><VideoPause /></el-icon>
        <span>停止审阅</span>
      </AppButton>
    </div>

    <div class="review-content">
      <!-- 审阅进度 -->
      <div v-if="reviewing" class="progress-panel glass-surface" v-loading="true" element-loading-text="AI 正在以读者视角阅读章节...">
        <div class="progress-info">
          <span class="progress-batch">{{ progress.message || '准备中...' }}</span>
          <span class="progress-range" v-if="progress.chapters">{{ progress.chapters }}</span>
        </div>
        <el-progress
          :percentage="progressPercentage"
          :stroke-width="10"
          :duration="1"
          striped
          striped-flow
          status="success"
        />
        <p class="progress-tip">每批约 10 章（相邻批次重叠 3 章以保证衔接判断准确），请耐心等待</p>
      </div>

      <!-- 空状态 -->
      <EmptyState
        v-if="!reviewing && reviews.length === 0"
        icon="Reading"
        text="选择卷后点击「开始审阅」，AI 将以读者视角逐批评估章节质量并给出评分与修改建议"
      />

      <!-- 批次结果列表 -->
      <div v-if="reviews.length > 0" class="review-list">
        <div v-for="r in reviews" :key="r.batch" class="review-card glass-panel">
          <!-- 失败批次 -->
          <template v-if="r.error">
            <div class="batch-header">
              <div class="batch-id">
                <span class="batch-title">第 {{ r.batch }} 批</span>
                <el-tag type="danger" effect="dark">审阅失败</el-tag>
              </div>
            </div>
            <p class="batch-error">
              <el-icon><WarningFilled /></el-icon>
              {{ r.error }}
            </p>
          </template>

          <!-- 成功批次 -->
          <template v-else>
            <div class="batch-header">
              <div class="batch-id">
                <span class="batch-title">第 {{ r.batch }} 批审阅</span>
                <el-tag type="primary" effect="dark" v-if="r.chapter_range">
                  第 {{ r.chapter_range[0] }} - {{ r.chapter_range[1] }} 章
                </el-tag>
              </div>
              <div class="batch-score" :class="scoreClass(r.batch_overall_score)">
                <span class="score-num">{{ formatScore(r.batch_overall_score) }}</span>
                <span class="score-label">批次综合评分</span>
              </div>
            </div>

            <p v-if="r.batch_overall_comment" class="batch-comment">{{ r.batch_overall_comment }}</p>

            <!-- 逐章审阅 -->
            <div class="chapter-reviews">
              <div
                v-for="ch in r.chapter_reviews || []"
                :key="`${r.batch}-${ch.chapter_number}`"
                class="chapter-review glass-surface"
              >
                <div class="ch-header">
                  <span class="ch-title">第 {{ ch.chapter_number }} 章</span>
                  <span class="ch-score" :class="scoreClass(ch.score)">
                    <i class="score-star">★</i>{{ formatScore(ch.score) }}
                  </span>
                </div>

                <!-- 亮点 -->
                <div v-if="ch.strengths && ch.strengths.length" class="review-section">
                  <div class="section-label label-success">
                    <el-icon><CircleCheck /></el-icon>
                    <span>亮点（{{ ch.strengths.length }}）</span>
                  </div>
                  <ul class="strength-list">
                    <li v-for="(s, i) in ch.strengths" :key="i" class="strength-item">{{ s }}</li>
                  </ul>
                </div>

                <!-- 问题 -->
                <div v-if="ch.issues && ch.issues.length" class="review-section">
                  <div class="section-label label-warning">
                    <el-icon><Warning /></el-icon>
                    <span>待改进（{{ ch.issues.length }}）</span>
                  </div>
                  <div class="issue-list">
                    <div v-for="(iss, i) in ch.issues" :key="i" class="issue-card">
                      <div class="issue-tags">
                        <el-tag size="small" effect="plain">{{ issueTypeLabel(iss.type) }}</el-tag>
                        <el-tag size="small" :type="severityType(iss.severity)" effect="light">
                          {{ severityLabel(iss.severity) }}
                        </el-tag>
                      </div>
                      <p class="issue-desc">{{ iss.description }}</p>
                      <p v-if="iss.suggestion" class="issue-sugg">
                        <span class="sugg-label">修改建议：</span>{{ iss.suggestion }}
                      </p>
                    </div>
                  </div>
                </div>

                <div
                  v-if="(!ch.strengths || !ch.strengths.length) && (!ch.issues || !ch.issues.length)"
                  class="ch-clean"
                >
                  <el-icon><CircleCheck /></el-icon>
                  <span>本章未发现显著问题</span>
                </div>
              </div>
            </div>

            <!-- 跨章节问题 -->
            <div v-if="r.cross_chapter_issues && r.cross_chapter_issues.length" class="cross-section">
              <div class="section-label label-danger">
                <el-icon><Connection /></el-icon>
                <span>跨章节问题（{{ r.cross_chapter_issues.length }}）</span>
              </div>
              <div class="issue-list">
                <div v-for="(ci, i) in r.cross_chapter_issues" :key="i" class="issue-card issue-cross">
                  <div class="issue-tags">
                    <el-tag
                      v-for="(cn, j) in ci.chapters || []"
                      :key="j"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      第 {{ cn }} 章
                    </el-tag>
                    <el-tag size="small" type="danger" effect="light">{{ crossTypeLabel(ci.type) }}</el-tag>
                  </div>
                  <p class="issue-desc">{{ ci.description }}</p>
                  <p v-if="ci.suggestion" class="issue-sugg">
                    <span class="sugg-label">修改建议：</span>{{ ci.suggestion }}
                  </p>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 完成汇总 -->
      <div v-if="finished && reviews.length > 0" class="finish-bar glass-surface">
        <el-icon class="finish-icon"><CircleCheckFilled /></el-icon>
        <span>
          审阅完成：共 {{ reviews.length }} 个批次
          <template v-if="failBatches > 0">，<em class="fail-count">{{ failBatches }} 批失败</em></template>
        </span>
        <el-button text type="primary" @click="scrollToTop">回到顶部</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, inject } from 'vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import { volumeApi } from '@/api/volume'
import { chapterUrls } from '@/api/chapter'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError, showWarning } from '@/utils/notify'

const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')

// ========== 卷版本 / 卷 ==========
const volumeVersions = ref([])
const currentVersionId = ref('')
const volumes = ref([])
const currentVolumeId = ref('')

// ========== 审阅状态 ==========
const reviewing = ref(false)
const finished = ref(false)
const progress = reactive({ current: 0, total: 0, chapters: '', message: '' })
const reviews = ref([])
let abortController = null

const progressPercentage = computed(() => {
  if (!progress.total) return reviewing.value ? 5 : 0
  return Math.min(100, Math.round((progress.current / progress.total) * 100))
})

const failBatches = computed(() => reviews.value.filter((r) => r.error).length)

// ========== 标签映射 ==========
const ISSUE_TYPE_LABELS = {
  pace: '叙事节奏',
  continuity: '情节衔接',
  character: '角色一致',
  expression: '表达问题',
  readability: '可读性',
}

const CROSS_TYPE_LABELS = {
  continuity: '情节衔接',
  character: '角色一致',
  pace: '叙事节奏',
}

function issueTypeLabel(type) {
  return ISSUE_TYPE_LABELS[type] || type || '其他'
}

function crossTypeLabel(type) {
  return CROSS_TYPE_LABELS[type] || type || '跨章问题'
}

function severityLabel(severity) {
  return { high: '严重', medium: '中等', low: '轻微' }[severity] || severity || '中等'
}

function severityType(severity) {
  return { high: 'danger', medium: 'warning', low: 'info' }[severity] || 'info'
}

function formatScore(score) {
  const n = Number(score)
  return Number.isFinite(n) ? n.toFixed(1) : '--'
}

function scoreClass(score) {
  const n = Number(score)
  if (!Number.isFinite(n)) return 'score-fair'
  if (n >= 9) return 'score-excellent'
  if (n >= 7) return 'score-good'
  if (n >= 5) return 'score-fair'
  return 'score-poor'
}

// ========== 加载卷版本 / 卷 ==========
async function loadVolumeVersions() {
  try {
    const data = await volumeApi.getVersions(projectId.value)
    if (data && data.success) {
      volumeVersions.value = data.versions || []
      const finalized = volumeVersions.value.find((v) => v.is_finalized)
      const target = finalized || volumeVersions.value[0]
      if (target) {
        currentVersionId.value = target.id
        await loadVolumes(target.id)
      }
    }
  } catch (e) {
    console.error('加载卷版本失败:', e)
  }
}

async function loadVolumes(versionId) {
  if (!versionId) return
  try {
    const data = await volumeApi.getVersion(projectId.value, versionId)
    if (data && data.success) {
      volumes.value = data.volumes || []
      const first = volumes.value[0]
      if (first && !currentVolumeId.value) {
        currentVolumeId.value = first.id
      }
    }
  } catch (e) {
    console.error('加载卷列表失败:', e)
  }
}

function resetResults() {
  reviews.value = []
  finished.value = false
  progress.current = 0
  progress.total = 0
  progress.chapters = ''
  progress.message = ''
}

async function onVersionChange() {
  currentVolumeId.value = ''
  volumes.value = []
  resetResults()
  if (currentVersionId.value) await loadVolumes(currentVersionId.value)
}

function onVolumeChange() {
  resetResults()
}

// ========== 审阅 ==========
async function startReview() {
  if (!currentVolumeId.value) {
    showWarning('请先选择要审阅的卷')
    return
  }
  resetResults()
  reviewing.value = true
  abortController = new AbortController()

  try {
    await streamRequestRaw(
      chapterUrls.readerReview(projectId.value),
      {
        body: { volume_id: Number(currentVolumeId.value) },
        signal: abortController.signal,
        onEvent: (evt) => {
          if (evt.type === 'progress') {
            progress.current = evt.current || 0
            progress.total = evt.total || 0
            progress.chapters = evt.chapters || ''
            progress.message = evt.message || ''
          } else if (evt.type === 'review') {
            if (evt.error) {
              reviews.value.push({ batch: evt.batch, error: evt.error })
            } else if (evt.review) {
              reviews.value.push(evt.review)
            }
          } else if (evt.type === 'complete') {
            finished.value = true
            const failCount = reviews.value.filter((r) => r.error).length
            if (failCount > 0) {
              showWarning(`审阅完成，${failCount} 个批次失败`)
            } else {
              showSuccess('读者审阅完成')
            }
          }
        },
      },
    )
  } catch (err) {
    if (err && err.message && err.message.includes('取消')) {
      // 用户主动停止，不提示错误
      finished.value = reviews.value.length > 0
    } else {
      showError('审阅失败：' + (err.message || '未知错误'))
    }
  } finally {
    reviewing.value = false
    abortController = null
  }
}

function stopReview() {
  if (abortController) abortController.abort()
}

function scrollToTop() {
  const el = document.querySelector('.reader-review-view')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  setPageHeader('读者审阅', 'AI 以真实读者视角逐批审阅章节，评估阅读流畅度、节奏、情节连贯与角色一致性')
  loadVolumeVersions()
})

onBeforeUnmount(() => {
  sseController.abort()
  if (abortController) {
    abortController.abort()
    abortController = null
  }
})
</script>

<style lang="scss" scoped>
.page-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.reader-review-view {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hd-select {
  width: 180px;
}

.review-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

// ========== 进度面板 ==========
.progress-panel {
  padding: 24px 28px;
  border-radius: var(--radius-md);
  min-height: 140px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 14px;
}

.progress-info {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.progress-batch {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.progress-range {
  font-size: 13px;
  color: var(--primary);
  font-weight: 600;
  background: rgba(99, 102, 241, 0.12);
  padding: 2px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.progress-tip {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

// ========== 批次卡片 ==========
.review-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-card {
  padding: 24px 28px;
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.batch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.batch-id {
  display: flex;
  align-items: center;
  gap: 12px;
}

.batch-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.batch-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 22px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--glass-border);
  min-width: 96px;
}

.score-num {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
}

.score-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.score-excellent .score-num,
.score-excellent {
  color: var(--success);
}
.score-good .score-num {
  color: var(--primary);
}
.score-fair .score-num {
  color: var(--warning);
}
.score-poor .score-num {
  color: var(--danger);
}

.batch-comment {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-regular, var(--text-secondary));
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.06);
  border-left: 3px solid var(--primary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.batch-error {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--danger);
  font-size: 14px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-sm);
}

// ========== 逐章审阅 ==========
.chapter-reviews {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
}

.chapter-review {
  padding: 16px 18px;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ch-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.ch-score {
  font-size: 18px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.score-star {
  font-size: 13px;
  font-style: normal;
}

.review-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

.label-success {
  color: var(--success);
}

.label-warning {
  color: var(--warning);
}

.label-danger {
  color: var(--danger);
}

.strength-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.strength-item {
  position: relative;
  padding: 8px 12px 8px 24px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  background: rgba(34, 197, 94, 0.06);
  border-radius: var(--radius-sm);

  &::before {
    content: '+';
    position: absolute;
    left: 10px;
    top: 8px;
    color: var(--success);
    font-weight: 700;
  }
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.issue-card {
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-cross {
  background: rgba(239, 68, 68, 0.05);
  border-color: rgba(239, 68, 68, 0.25);
}

.issue-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.issue-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
}

.issue-sugg {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.sugg-label {
  color: var(--primary);
  font-weight: 600;
}

.ch-clean {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--success);
  opacity: 0.8;
}

.cross-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
  border-top: 1px dashed var(--glass-border);
}

// ========== 完成汇总 ==========
.finish-bar {
  position: sticky;
  bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 22px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  align-self: center;
  backdrop-filter: blur(16px);
}

.finish-icon {
  color: var(--success);
  font-size: 18px;
}

.fail-count {
  color: var(--danger);
  font-style: normal;
}

@media (max-width: 1200px) {
  .chapter-reviews {
    grid-template-columns: 1fr;
  }
}
</style>
