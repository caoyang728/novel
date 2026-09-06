<template>
  <div class="chapter-view">
    <Teleport defer to="#header-right-teleport">
      <el-select v-model="currentVersionId" size="small" style="width: 140px" @change="onVersionChange">
        <el-option
          v-for="v in volumeVersions"
          :key="v.id"
          :label="`v${v.version_number} (${v.volume_count}卷)${v.is_finalized ? ' ✓' : ''}`"
          :value="v.id"
        />
      </el-select>
      <el-select v-model="currentVolumeId" size="small" style="width: 140px" :disabled="!currentVersionId" @change="onVolumeChange">
        <el-option
          v-for="vol in volumes"
          :key="vol.id"
          :label="`第${vol.volume_number}卷: ${vol.title}`"
          :value="vol.id"
        />
      </el-select>
      <AppButton
        variant="success"
        :disabled="!currentVolumeId || generating"
        @click="generateChapters"
      >
        <el-icon><Star /></el-icon> AI 生成章节
      </AppButton>
      <AppButton
        variant="ai"
        :disabled="!currentVolumeId || allChapters.length === 0 || generating"
        @click="openBatchCheck"
      >
        <el-icon><CircleCheck /></el-icon> AI 校验
      </AppButton>
      <AppButton
        variant="warning"
        @click="goReaderReview"
      >
        <el-icon><Reading /></el-icon> 读者审阅
      </AppButton>
    </Teleport>
    <div
      class="chapter-workspace"
      v-loading="generating || statusLoading"
      :element-loading-text="genStatus"
    >
      <!-- 左：章节列表 -->
      <aside class="chapter-list-panel glass-surface">
        <div class="list-header">
          <span class="list-title">
            章节列表
            <el-tag size="small" round effect="dark">{{ allChapters.length }}章</el-tag>
          </span>
          <el-select v-model="statusFilter" size="small" class="filter-select">
            <el-option label="全部" value="" />
            <el-option label="已生成概述" value="summary" />
            <el-option label="草稿" value="draft" />
            <el-option label="生成失败" value="failed" />
            <el-option label="已锁定" value="locked" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
            <el-option label="已删除" value="deleted" />
          </el-select>
        </div>
        <div class="chapter-list" v-loading="listLoading">
          <EmptyState
            v-if="filteredChapters.length === 0"
            icon="Document"
            :text="allChapters.length === 0 ? '暂无章节，请选择卷后点击 AI 生成章节' : '无匹配的章节'"
          />
          <div
            v-for="chap in filteredChapters"
            :key="chap.id"
            class="chapter-item"
            :class="{ active: chap.id === currentChapterId, deleted: chap.state === 'deleted' }"
            @click="selectChapter(chap.id)"
          >
            <div class="chapter-top">
              <span class="chapter-number">第{{ chap.chapter_number }}章</span>
              <el-tag size="small" :type="badgeType(chap)" effect="dark">{{ badgeText(chap) }}</el-tag>
            </div>
            <div class="chapter-title text-ellipsis">{{ chap.title || '未命名章节' }}</div>
            <div class="chapter-meta">
              <span>{{ chap.word_count || 0 }}字</span>
              <span v-if="chap.updated_at">{{ formatTime(chap.updated_at) }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中：编辑器 -->
      <section class="editor-panel glass-panel">
        <EmptyState
          v-if="!currentChapter"
          icon="EditPen"
          text="选择一个章节开始创作，或点击「AI 生成章节」创建新内容"
        />
        <template v-else>
          <div class="editor-header">
            <div class="editor-title-area">
              <template v-if="!titleEditing">
                <span class="current-chapter-label">
                  第{{ currentChapter.chapter_number }}章: {{ form.title || '未命名章节' }}
                </span>
                <el-icon
                  v-if="!isDeleted && !isPublished"
                  class="title-edit-icon"
                  title="编辑标题"
                  @click="startEditTitle"
                >
                  <EditPen />
                </el-icon>
              </template>
              <template v-else>
                <el-input
                  v-model="titleDraft"
                  size="small"
                  class="title-inline-input"
                  placeholder="输入章节标题"
                  @keyup.enter="finishEditTitle"
                  @keyup.esc="cancelEditTitle"
                />
                <AppButton size="small" variant="accent" @click="finishEditTitle">
                  <el-icon><Check /></el-icon>
                </AppButton>
              </template>
            </div>
            <div class="editor-toolbar">
              <AppButton v-if="showVerify" size="small" :disabled="!hasContent" @click="verifyChapter">
                <el-icon><CircleCheck /></el-icon> 校验
              </AppButton>
              <AppButton v-if="showSplit" size="small" :disabled="splitDisabled" @click="splitChapter">
                <el-icon><Scissor /></el-icon> 拆分
              </AppButton>
              <AppButton v-if="isDirty" size="small" variant="accent" :loading="isSaving" @click="saveChapter">
                <el-icon><Download /></el-icon> 保存
              </AppButton>
              <AppButton v-if="isDirty" size="small" @click="cancelEdit">取消</AppButton>
              <AppButton v-if="showPublish" size="small" variant="success" @click="publishChapter">
                <el-icon><Promotion /></el-icon> 发布
              </AppButton>
              <AppButton v-if="showLock" size="small" :variant="isLocked ? 'warning' : 'default'" @click="toggleLock">
                <el-icon><Unlock v-if="isLocked" /><Lock v-else /></el-icon>
                {{ isLocked ? '解锁' : '锁定' }}
              </AppButton>
              <AppButton v-if="showDelete" size="small" variant="danger" :disabled="isLocked" @click="softDeleteChapter">
                <el-icon><Delete /></el-icon> 删除
              </AppButton>
              <span v-if="isPublished" class="published-tip">
                <el-icon><Lock /></el-icon> 已发布的章节不再支持修改
              </span>
            </div>
          </div>

          <div class="editor-body">
            <div class="editor-form">
              <div class="content-tabs">
                <button
                  class="content-tab"
                  :class="{ active: editorTab === 'content' }"
                  @click="switchTab('content')"
                >
                  章节内容
                </button>
                <button
                  class="content-tab"
                  :class="{ active: editorTab === 'summary' }"
                  @click="switchTab('summary')"
                >
                  章节概述
                </button>
              </div>

              <!-- 内容 tab -->
              <div v-show="editorTab === 'content'" class="content-wrapper" v-loading="detailLoading">
                <div v-if="showEmptyContent" class="empty-content">
                  <el-icon :size="36" class="empty-icon"><Document /></el-icon>
                  <p>暂无章节内容</p>
                  <template v-if="isDeleted">
                    <div class="empty-actions">
                      <AppButton variant="success" @click="restoreChapter">
                        <el-icon><RefreshLeft /></el-icon> 恢复
                      </AppButton>
                      <AppButton variant="danger" @click="showHardDeleteModal">
                        <el-icon><Delete /></el-icon> 彻底删除
                      </AppButton>
                    </div>
                  </template>
                  <AppButton v-else variant="accent" size="large" :loading="generating" @click="generateSingleContent">
                    <el-icon><MagicStick /></el-icon> AI 生成
                  </AppButton>
                </div>
                <textarea
                  v-else
                  v-model="form.content"
                  class="editor-textarea"
                  :readonly="isDeleted || isPublished"
                  placeholder="开始创作..."
                  @input="markDirty"
                ></textarea>
              </div>

              <!-- 概述 tab -->
              <textarea
                v-show="editorTab === 'summary'"
                v-model="form.summary"
                class="editor-textarea summary-textarea"
                :readonly="isDeleted || isPublished"
                placeholder="输入章节概述..."
                @input="markDirty"
              ></textarea>
            </div>

            <!-- AI 对话面板 -->
            <div v-show="editorTab === 'content'" class="ai-chat-panel">
              <ChatPanel
                title="AI 写作助手"
                :messages="chatMessages"
                :is-streaming="chatStreaming"
                :input-placeholder="chatDisabled ? '当前状态下 AI 助手不可用' : '输入指令让 AI 帮你写作... (Enter发送, Shift+Enter换行)'"
                @send="sendAiMessage"
                @stop="stopChat"
                @clear="chatMessages = []"
              >
                <template v-if="!chatDisabled" #quick-prompts>
                  <div class="quick-prompts">
                    <button
                      v-for="q in quickPrompts"
                      :key="q"
                      class="quick-prompt"
                      :disabled="chatStreaming"
                      @click="sendAiMessage(q)"
                    >
                      {{ q }}
                    </button>
                  </div>
                </template>
              </ChatPanel>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- 校验结果弹窗 -->
    <AppModal
      v-model:visible="verifyVisible"
      title="章节校验结果"
      width="660px"
      height="80vh"
    >
      <div v-loading="verifyLoading" element-loading-text="校验中..." class="verify-body">
        <div v-if="!verifyLoading && verifyIssues.length === 0" class="check-empty">
          <el-icon :size="40" class="check-empty-icon"><CircleCheckFilled /></el-icon>
          <p>校验完成，未发现问题</p>
        </div>
        <template v-else>
          <p class="check-intro">AI 已完成章节校验，以下是发现的问题：</p>
          <div class="check-issues">
            <div v-for="(issue, idx) in verifyIssues" :key="idx" class="check-issue glass-surface">
              <div class="check-issue-head">
                <el-checkbox v-model="issue.checked" />
                <el-tag size="small" effect="dark">{{ VERIFY_TYPE_LABELS[issue.type] || issue.type || '其他问题' }}</el-tag>
              </div>
              <div class="check-issue-row">
                <span class="row-label">问题</span>
                <span class="row-text">{{ issue.description }}</span>
              </div>
              <div v-if="issue.suggestion" class="check-issue-row">
                <span class="row-label">建议</span>
                <span class="row-text suggestion">{{ issue.suggestion }}</span>
              </div>
              <el-input
                v-model="issue.userComment"
                type="textarea"
                :rows="2"
                class="check-issue-input"
                placeholder="输入修改意见（选填，留空则按 AI 建议修复）..."
              />
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <AppButton @click="verifyVisible = false">关闭</AppButton>
        <AppButton
          v-if="verifyIssues.length > 0"
          variant="ai"
          :loading="generating"
          @click="fixVerifyIssues"
        >
          <el-icon><MagicStick /></el-icon> AI修复选中的问题
        </AppButton>
      </template>
    </AppModal>

    <!-- 拆分章节弹窗 -->
    <AppModal v-model:visible="splitVisible" title="拆分章节" width="520px" height="auto">
      <div class="split-options">
        <div class="split-group">
          <label class="split-label">拆分模式</label>
          <el-radio-group v-model="splitMode" class="split-radios">
            <el-radio value="by_word_count">按字数拆分</el-radio>
            <el-radio value="by_plot">按剧情拆分</el-radio>
          </el-radio-group>
          <div class="split-desc">
            {{ splitMode === 'by_word_count'
              ? '保留约前3000-3200字，剩余内容成为新章节'
              : splitMode === 'by_plot'
                ? '根据剧情自然断点拆分章节'
                : '请选择拆分模式' }}
          </div>
        </div>
        <div class="split-group">
          <label class="split-label">内容处理</label>
          <el-radio-group v-model="splitHandling" class="split-radios">
            <el-radio value="insert_next">插入下一章</el-radio>
            <el-radio value="create_new">新建一章</el-radio>
          </el-radio-group>
          <div class="split-desc">
            {{ splitHandling === 'insert_next'
              ? '将拆分内容插入下一章开头（如无下一章则新建）'
              : splitHandling === 'create_new'
                ? '拆分内容作为新章节，自动调整序号'
                : '请选择内容处理方式' }}
          </div>
        </div>
      </div>
      <template #footer>
        <AppButton @click="splitVisible = false">取消</AppButton>
        <AppButton variant="accent" :disabled="!splitMode || !splitHandling" @click="executeSplit">
          确认拆分
        </AppButton>
      </template>
    </AppModal>

    <!-- 彻底删除确认弹窗 -->
    <AppModal v-model:visible="hardDeleteVisible" title="彻底删除章节" width="480px" height="auto">
      <div class="hard-delete-body">
        <p class="hard-delete-warn">
          本次删除将彻底删除，且无法恢复。请输入章节名「{{ hardDeleteConfirmText }}」确认删除：
        </p>
        <el-input v-model="hardDeleteInput" placeholder="请输入章节名确认删除" />
      </div>
      <template #footer>
        <AppButton @click="hardDeleteVisible = false">取消</AppButton>
        <AppButton
          variant="danger"
          :disabled="hardDeleteInput !== hardDeleteConfirmText || !hardDeleteConfirmText"
          @click="executeHardDelete"
        >
          彻底删除
        </AppButton>
      </template>
    </AppModal>

    <!-- 相邻已删除章节警告 -->
    <AppModal v-model:visible="warningVisible" title="提示" width="480px" height="auto">
      <div class="warning-body">
        <p v-for="(msg, i) in warningMessages" :key="i" class="warning-msg">{{ msg }}</p>
      </div>
      <template #footer>
        <AppButton @click="warningVisible = false">取消</AppButton>
        <AppButton @click="onWarningRestore">去恢复</AppButton>
        <AppButton variant="accent" @click="onWarningConfirm">确认</AppButton>
      </template>
    </AppModal>

    <!-- AI 校验范围选择 -->
    <AppModal v-model:visible="batchRangeVisible" title="AI校验 - 选择范围" width="560px" height="auto">
      <div class="batch-range-body">
        <p class="batch-range-tip">
          每10章为一个批次，前后各扩展3章作为上下文参考（前3章只读，后3章可修改）。
        </p>
        <div class="batch-range-form">
          <div class="batch-range-row">
            <label>起始章节</label>
            <el-select v-model="batchStart" placeholder="请选择" size="small">
              <el-option
                v-for="cn in chapterNumbers"
                :key="'s' + cn"
                :label="`第${cn}章`"
                :value="cn"
              />
            </el-select>
          </div>
          <div class="batch-range-row">
            <label>结束章节</label>
            <el-select v-model="batchEnd" placeholder="请选择" size="small">
              <el-option
                v-for="cn in chapterNumbers"
                :key="'e' + cn"
                :label="`第${cn}章`"
                :value="cn"
              />
            </el-select>
          </div>
        </div>
        <div v-if="rangePreview.length" class="batch-range-preview">
          <div class="preview-title">校验范围预览</div>
          <div class="preview-legend">
            <span class="legend-item"><span class="legend-dot before"></span> 上下文（只读）</span>
            <span class="legend-item"><span class="legend-dot main"></span> 主要校验（可修改）</span>
            <span class="legend-item"><span class="legend-dot after"></span> 上下文（可修改）</span>
          </div>
          <div class="preview-chips">
            <span
              v-for="chip in rangePreview"
              :key="chip.cn"
              class="batch-chip"
              :class="[chip.cls, { missing: !chip.exists }]"
              :title="`第${chip.cn}章 ${chip.exists ? '' : '(不存在)'}`"
            >
              {{ chip.cn }}
            </span>
          </div>
        </div>
      </div>
      <template #footer>
        <AppButton @click="batchRangeVisible = false">取消</AppButton>
        <AppButton variant="accent" :disabled="!rangeValid" @click="startBatchCheck">
          <el-icon><Search /></el-icon> 开始校验
        </AppButton>
      </template>
    </AppModal>

    <!-- AI 校验结果 -->
    <AppModal
      v-model:visible="batchResultVisible"
      title="AI校验结果"
      width="820px"
      height="82vh"
    >
      <div v-loading="batchChecking" element-loading-text="校验中..." class="batch-result-body">
        <template v-if="!batchChecking">
          <div v-if="batchIssues.length === 0" class="check-empty">
            <el-icon :size="40" class="check-empty-icon"><CircleCheckFilled /></el-icon>
            <p>校验完成，未发现问题</p>
          </div>
          <template v-else>
            <div v-if="batchOverall" class="batch-overall">{{ batchOverall }}</div>
            <div class="check-summary">
              <div class="summary-item">共 <span>{{ batchIssues.length }}</span> 个问题</div>
              <div v-if="severityCount.high" class="summary-item high">严重 <span>{{ severityCount.high }}</span></div>
              <div v-if="severityCount.medium" class="summary-item medium">中等 <span>{{ severityCount.medium }}</span></div>
              <div v-if="severityCount.low" class="summary-item low">轻微 <span>{{ severityCount.low }}</span></div>
            </div>
            <div class="check-issues">
              <div v-for="(issue, idx) in batchIssues" :key="idx" class="check-issue glass-surface">
                <div class="check-issue-head">
                  <el-checkbox v-model="issue.checked" />
                  <el-tag size="small" type="primary" effect="dark">
                    第{{ issue.chapter_number || (issue.chapters ? issue.chapters.join(',') : '?') }}章
                  </el-tag>
                  <el-tag v-if="issue.chapters" size="small" type="warning" effect="plain">跨章</el-tag>
                  <el-tag size="small" effect="dark">{{ BATCH_TYPE_LABELS[issue.type] || issue.type }}</el-tag>
                  <el-tag size="small" :type="severityType(issue.severity)" effect="plain">
                    {{ severityLabel(issue.severity) }}
                  </el-tag>
                </div>
                <div class="check-issue-row">
                  <span class="row-label">问题</span>
                  <span class="row-text">{{ issue.description }}</span>
                </div>
                <div v-if="issue.original_text" class="check-issue-row">
                  <span class="row-label">原文</span>
                  <span class="row-text original">{{ issue.original_text }}</span>
                </div>
                <div v-if="issue.suggestion" class="check-issue-row">
                  <span class="row-label">建议</span>
                  <span class="row-text suggestion">{{ issue.suggestion }}</span>
                </div>
                <el-input
                  v-model="issue.userComment"
                  type="textarea"
                  :rows="2"
                  class="check-issue-input"
                  placeholder="输入修改意见（选填，留空则按AI建议修复）..."
                />
              </div>
            </div>
          </template>
        </template>
      </div>
      <template #footer>
        <AppButton @click="batchResultVisible = false">关闭</AppButton>
        <AppButton
          v-if="batchIssues.length > 0"
          variant="ai"
          :loading="generating"
          @click="fixBatchIssues"
        >
          <el-icon><MagicStick /></el-icon> AI修复选中的问题
        </AppButton>
      </template>
    </AppModal>

    <!-- AI 修改对比弹窗 -->
    <ChapterCompareModal
      v-model:visible="compareVisible"
      :modifications="compare.modifications"
      :streaming="compare.streaming"
      :streaming-text="compare.streamingText"
      :streaming-original="compare.streamingOriginal"
      :chat-messages="compare.chatMessages"
      :chat-sending="compare.chatSending"
      :chat-disabled="compare.chatDisabled"
      :saving="compare.saving"
      @save="saveCompareChanges"
      @cancel="cancelCompareChanges"
      @send="sendCompareChat"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  MagicStick, /* DataAnalysis, */ Reading, EditPen, Check, CircleCheck, CircleCheckFilled,
  Scissor, Download, Promotion, Unlock, Lock, Delete, RefreshLeft, Document, Search, Star,
} from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import ChapterCompareModal from './components/ChapterCompareModal.vue'
import { chapterApi, chapterUrls } from '@/api/chapter'
import { volumeApi } from '@/api/volume'
import { api } from '@/api/request'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import { extractJsonFromString } from '@/utils/json'

const router = useRouter()
const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')
const pid = computed(() => projectId.value)

// ========== 常量 ==========
const VERIFY_TYPE_LABELS = {
  continuity: '连贯性问题',
  logic: '逻辑问题',
  character: '人物设定问题',
  plot: '情节问题',
  consistency: '一致性问题',
}
const BATCH_TYPE_LABELS = {
  continuity: '衔接性',
  logic: '逻辑性',
  character: '角色一致性',
  plot: '情节合理性',
  language: '语言质量',
  dialogue: '对话质量',
  word_count: '字数合规',
}
const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 }
const ITEM_START = '════ITEM_START════'
const ITEM_END = '════ITEM_END════'

const quickPrompts = [
  '继续写下去，保持风格一致',
  '补充更多细节描写',
  '增加人物对话',
  '加强情感描写',
  '过渡到下一场景',
]

// ========== 卷版本 / 卷 ==========
const volumeVersions = ref([])
const currentVersionId = ref('')
const volumes = ref([])
const currentVolumeId = ref('')

// ========== 章节列表 / 编辑器 ==========
const allChapters = ref([])
const listLoading = ref(true)
const detailLoading = ref(false)
const currentChapterId = ref(null)
const statusFilter = ref('')
const editorTab = ref('content')
const form = reactive({ title: '', content: '', summary: '' })
const isDirty = ref(false)
const isSaving = ref(false)
let snapshot = { title: '', content: '', summary: '' }
const titleEditing = ref(false)
const titleDraft = ref('')

const generating = ref(false)
const genStatus = ref('')
const statusLoading = ref(false)
const contentLoading = ref(false)
let typewriterVersion = 0

// ========== AI 对话 ==========
const chatMessages = ref([])
const chatStreaming = ref(false)
let chatHistory = []
let chatAbort = null

// ========== 对比弹窗会话 ==========
const compareVisible = ref(false)
const compare = reactive({
  modifications: {},
  currentChapterNumber: null,
  chatMessages: [],
  chatSending: false,
  streaming: false,
  streamingText: '',
  streamingOriginal: '',
  chatDisabled: false,
  saving: false,
})

// ========== 校验弹窗 ==========
const verifyVisible = ref(false)
const verifyLoading = ref(false)
const verifyIssues = ref([])

// ========== 拆分弹窗 ==========
const splitVisible = ref(false)
const splitMode = ref('')
const splitHandling = ref('')

// ========== 彻底删除 ==========
const hardDeleteVisible = ref(false)
const hardDeleteInput = ref('')

// ========== 相邻删除警告 ==========
const warningVisible = ref(false)
const warningMessages = ref([])
let warningOnConfirm = null
let warningOnRestore = null

// ========== 批量校验 ==========
const batchRangeVisible = ref(false)
const batchStart = ref('')
const batchEnd = ref('')
const batchResultVisible = ref(false)
const batchChecking = ref(false)
const batchIssues = ref([])
const batchOverall = ref('')

// ========== 计算属性 ==========
const currentChapter = computed(() =>
  allChapters.value.find((c) => c.id === currentChapterId.value) || null,
)

const filteredChapters = computed(() => {
  const f = statusFilter.value
  if (f === 'locked') return allChapters.value.filter((c) => c.state === 'locked')
  if (f === 'deleted') return allChapters.value.filter((c) => c.state === 'deleted')
  if (f) {
    return allChapters.value.filter(
      (c) => c.status === f && c.state !== 'locked' && c.state !== 'deleted',
    )
  }
  return allChapters.value
})

const isDeleted = computed(() => currentChapter.value?.state === 'deleted')
const isLocked = computed(() => currentChapter.value?.state === 'locked')
const isPublished = computed(() => currentChapter.value?.status === 'published')
const hasContent = computed(() => !!form.content)
const chatDisabled = computed(
  () => editorTab.value === 'summary' || isLocked.value || isDeleted.value || isPublished.value,
)
const showEmptyContent = computed(
  () =>
    editorTab.value === 'content' &&
    !!currentChapter.value &&
    !contentLoading.value &&
    (isDeleted.value || !form.content),
)
const showVerify = computed(
  () => !!currentChapter.value && !isDeleted.value && !isPublished.value && !isLocked.value,
)
const showSplit = showVerify
const splitDisabled = computed(
  () => editorTab.value === 'summary' || (currentChapter.value?.word_count || 0) < 3000,
)
const showPublish = computed(() => isLocked.value && !isPublished.value)
const showLock = computed(
  () => !!currentChapter.value && !isDeleted.value && !isPublished.value,
)
const showDelete = showLock

const hardDeleteConfirmText = computed(() => currentChapter.value?.title || '')

const chapterNumbers = computed(() =>
  allChapters.value.map((c) => c.chapter_number).sort((a, b) => a - b),
)

const rangePreview = computed(() => {
  const s = Number(batchStart.value)
  const e = Number(batchEnd.value)
  if (!s || !e || s > e) return []
  const nums = chapterNumbers.value
  if (nums.length === 0) return []
  const min = nums[0]
  const max = nums[nums.length - 1]
  const ctxStart = Math.max(min, s - 3)
  const ctxEnd = Math.min(max, e + 3)
  const chips = []
  for (let cn = ctxStart; cn <= ctxEnd; cn++) {
    let cls = 'main'
    if (cn < s) cls = 'before'
    else if (cn > e) cls = 'after'
    chips.push({ cn, cls, exists: nums.includes(cn) })
  }
  return chips
})

const rangeValid = computed(() => {
  const s = Number(batchStart.value)
  const e = Number(batchEnd.value)
  return !!s && !!e && s <= e
})

const severityCount = computed(() => ({
  high: batchIssues.value.filter((i) => i.severity === 'high').length,
  medium: batchIssues.value.filter((i) => i.severity === 'medium').length,
  low: batchIssues.value.filter((i) => i.severity === 'low').length,
}))

// ========== 工具 ==========
function badgeType(chap) {
  if (chap.state === 'deleted') return 'danger'
  if (chap.state === 'locked') return 'warning'
  switch (chap.status) {
    case 'published': return 'success'
    case 'summary': return 'info'
    case 'failed': return 'danger'
    case 'archived': return 'info'
    default: return 'primary'
  }
}

function badgeText(chap) {
  if (chap.state === 'deleted') return '已删除'
  if (chap.state === 'locked') return '已锁定'
  switch (chap.status) {
    case 'published': return '已发布'
    case 'summary': return '已生成概述'
    case 'failed': return '生成失败'
    case 'archived': return '已归档'
    default: return '草稿'
  }
}

function severityLabel(sev) {
  return sev === 'high' ? '严重' : sev === 'medium' ? '中等' : '轻微'
}

function severityType(sev) {
  return sev === 'high' ? 'danger' : sev === 'medium' ? 'warning' : 'info'
}

function formatTime(s) {
  try {
    return new Date(s).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function sortChapters() {
  allChapters.value.sort((a, b) => a.chapter_number - b.chapter_number)
}

function updateLocalChapter(id, fields) {
  const idx = allChapters.value.findIndex((c) => c.id === id)
  if (idx >= 0) {
    allChapters.value[idx] = { ...allChapters.value[idx], ...fields }
  }
}

function parseItems(text) {
  const items = []
  let searchIdx = 0
  for (;;) {
    const s = text.indexOf(ITEM_START, searchIdx)
    if (s === -1) break
    const e = text.indexOf(ITEM_END, s)
    if (e === -1) break
    const jsonStr = text.substring(s + ITEM_START.length, e).trim()
    const parsed = extractJsonFromString(jsonStr)
    if (parsed) items.push(parsed)
    searchIdx = e + ITEM_END.length
  }
  return items
}

function checkUnsaved(msg) {
  if (!isDirty.value) return Promise.resolve(true)
  return new Promise((resolve) => {
    showConfirmModal({
      title: '未保存的修改',
      message: msg || '当前有未保存的修改，操作后将丢失。确定要继续吗？',
      onConfirm: (close) => {
        close()
        isDirty.value = false
        resolve(true)
      },
      onCancel: () => resolve(false),
    })
  })
}

function goReaderReview() {
  router.push({ name: 'Content', params: { projectId: projectId.value } })
}

// ========== 加载 ==========
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
        await loadChapters(first.id)
      }
    }
  } catch (e) {
    console.error('加载卷列表失败:', e)
  }
}

async function loadChapters(volumeId) {
  if (!volumeId) return false
  listLoading.value = true
  try {
    const data = await chapterApi.loadByVolume(projectId.value, volumeId)
    if (data && data.success) {
      allChapters.value = data.chapters || []
      sortChapters()
      return true
    } else {
      if (data && data.message) showError(data.message)
      return false
    }
  } catch (e) {
    console.error('加载章节列表失败:', e)
    return false
  } finally {
    listLoading.value = false
  }
}

async function onVersionChange() {
  currentVolumeId.value = ''
  volumes.value = []
  allChapters.value = []
  currentChapterId.value = null
  if (currentVersionId.value) await loadVolumes(currentVersionId.value)
}

async function onVolumeChange() {
  currentChapterId.value = null
  allChapters.value = []
  form.title = ''
  form.content = ''
  form.summary = ''
  chatMessages.value = []
  if (currentVolumeId.value) await loadChapters(currentVolumeId.value)
}

// ========== 章节选择 / 编辑 ==========
function applyChapterToForm(chap) {
  form.title = chap.title || ''
  form.content = chap.content || ''
  form.summary = chap.summary || ''
}

function takeSnapshot() {
  snapshot = { title: form.title, content: form.content, summary: form.summary }
}

function markDirty() {
  if (!isDirty.value) isDirty.value = true
}

async function selectChapter(id) {
  if (isDirty.value && currentChapterId.value && currentChapterId.value !== id) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前章节有未保存的修改，切换后将丢失。确定要切换吗？',
      onConfirm: (close) => {
        close()
        isDirty.value = false
        selectChapter(id)
      },
    })
    return
  }

  const chap = allChapters.value.find((c) => c.id === id)
  if (!chap) return

  currentChapterId.value = id
  titleEditing.value = false
  applyChapterToForm(chap)
  editorTab.value = 'content'
  isDirty.value = false
  takeSnapshot()
  chatMessages.value = []
  chatHistory = []

  if (chap.content === undefined && chap.state !== 'deleted') {
    contentLoading.value = true
    loadChapterDetail(chap)
  }
}

async function loadChapterDetail(chap) {
  detailLoading.value = true
  try {
    const data = await chapterApi.getDetail(projectId.value, chap.id)
    if (data && data.success && data.chapter) {
      chap.content = data.chapter.content || ''
      chap.summary = data.chapter.summary || ''
      if (currentChapterId.value === chap.id) {
        form.content = chap.content
        form.summary = chap.summary
      }
    }
  } catch (e) {
    console.error('加载章节详情失败:', e)
  } finally {
    detailLoading.value = false
    contentLoading.value = false
  }
}

function switchTab(tab) {
  editorTab.value = tab
}

function startEditTitle() {
  titleDraft.value = form.title
  titleEditing.value = true
}

function finishEditTitle() {
  const t = titleDraft.value.trim()
  if (t && t !== form.title) {
    form.title = t
    markDirty()
  }
  titleEditing.value = false
}

function cancelEditTitle() {
  titleEditing.value = false
}

function cancelEdit() {
  if (!isDirty.value) return
  form.title = snapshot.title
  form.content = snapshot.content
  form.summary = snapshot.summary
  isDirty.value = false
}

async function saveChapter() {
  if (!currentChapterId.value || isSaving.value) return
  isSaving.value = true
  try {
    const data = await chapterApi.save(projectId.value, {
      chapter_id: currentChapterId.value,
      title: form.title,
      content: form.content,
      summary: form.summary,
    })
    if (data && data.success) {
      updateLocalChapter(currentChapterId.value, {
        title: form.title,
        content: form.content,
        summary: form.summary,
        word_count: data.chapter.word_count,
        status: data.chapter.status,
      })
      isDirty.value = false
      takeSnapshot()
      showSuccess('保存成功')
    } else {
      showError('保存失败: ' + (data?.message || ''))
    }
  } catch (e) {
    showError('网络错误')
  } finally {
    isSaving.value = false
  }
}

// ========== 打字机 ==========
async function typewriter(text) {
  const version = ++typewriterVersion
  form.content = ''
  if (!text) return
  const totalChars = text.length
  const targetDuration = 2000
  const speed = 5
  const chunkSize = Math.max(1, Math.ceil(totalChars / (targetDuration / speed)))
  for (let i = 0; i < text.length; i += chunkSize) {
    if (typewriterVersion !== version) return
    const end = Math.min(i + chunkSize, text.length)
    form.content = text.substring(0, end)
    await new Promise((r) => setTimeout(r, speed))
  }
  form.content = text
}

// ========== AI 批量生成章节 ==========
async function generateChapters() {
  if (!currentVolumeId.value) {
    showWarning('请先选择卷')
    return
  }
  if (!(await checkUnsaved('当前有未保存的修改，生成新章节后将丢失。确定要继续吗？'))) return

  generating.value = true
  genStatus.value = '思考中...'

  if (allChapters.value.length === 0) {
    allChapters.value = []
    currentChapterId.value = null
    form.title = ''
    form.content = ''
    form.summary = ''
  }

  let totalWords = 0
  let completeVolumeId = null

  try {
    await sseController.stream(
      chapterUrls.generate(projectId.value),
      {
        body: { volume_id: Number(currentVolumeId.value) },
        onEvent: (evt) => {
          if (evt.type === 'progress') {
            genStatus.value = evt.message || '生成中...'
          } else if (evt.type === 'outline') {
            const chap = evt.chapter
            chap.id = -(chap.chapter_number)
            chap.status = 'summary'
            chap.word_count = 0
            chap.state = 'normal'
            chap.content = ''
            allChapters.value.push(chap)
            sortChapters()
            currentChapterId.value = chap.id
            applyChapterToForm(chap)
            editorTab.value = 'summary'
            titleEditing.value = false
            const done = allChapters.value.filter(
              (c) => c.status === 'summary' || c.status === 'draft',
            ).length
            genStatus.value = `正在生成章节概述... 第${chap.chapter_number}章（已完成 ${done}/${allChapters.value.length}）`
          } else if (evt.type === 'chapter') {
            const chap = evt.chapter
            const idx = allChapters.value.findIndex(
              (c) => c.chapter_number === chap.chapter_number,
            )
            let target
            if (idx !== -1) {
              target = allChapters.value[idx]
              target.content = chap.content
              target.word_count = chap.word_count
              target.status = 'draft'
            } else {
              chap.id = -(chap.chapter_number)
              chap.state = 'normal'
              allChapters.value.push(chap)
              target = chap
            }
            sortChapters()
            totalWords += chap.word_count || 0
            currentChapterId.value = target.id
            form.title = chap.title || target.title
            form.summary = target.summary || ''
            editorTab.value = 'content'
            titleEditing.value = false
            typewriter(chap.content || '')
            const done = allChapters.value.filter((c) => c.status === 'draft').length
            genStatus.value = `正在生成第${chap.chapter_number}章: ${chap.title || ''}（已完成 ${done}/${allChapters.value.length}）`
          } else if (evt.type === 'chapter_failed') {
            const idx = allChapters.value.findIndex(
              (c) => c.chapter_number === evt.chapter_number,
            )
            if (idx !== -1) allChapters.value[idx].status = 'failed'
          } else if (evt.type === 'complete') {
            completeVolumeId = evt.volume_id
            showSuccess(`章节内容生成完成！共 ${evt.chapters_count} 章，总计 ${totalWords} 字`)
          }
        },
      },
    )

    if (completeVolumeId) {
      const chaptersBefore = [...allChapters.value]
      const loaded = await loadChapters(completeVolumeId)
      if (!loaded && chaptersBefore.length > 0) {
        allChapters.value = chaptersBefore
        sortChapters()
      }
      const last = [...allChapters.value].sort((a, b) => b.chapter_number - a.chapter_number)[0]
      if (last) {
        currentChapterId.value = null
        selectChapter(last.id)
      }
    }
  } catch (e) {
    showError('生成失败: ' + e.message)
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ========== 单章内容生成 ==========
function generateSingleContent() {
  if (!currentChapterId.value) return
  checkAdjacentDeletedAndPrompt(doGenerateSingle, '生成/调整/校验')
}

async function doGenerateSingle() {
  if (!(await checkUnsaved('当前有未保存的修改，生成新内容后将丢失。确定要继续吗？'))) return
  const chap = currentChapter.value
  if (!chap) return
  generating.value = true
  genStatus.value = `正在生成第${chap.chapter_number}章: ${chap.title || ''}`
  let fullContent = ''
  try {
    await sseController.stream(
      chapterUrls.content(projectId.value),
      {
        body: { chapter_id: currentChapterId.value },
        onEvent: (evt) => {
          if (evt.type === 'complete') {
            form.content = fullContent
            updateLocalChapter(currentChapterId.value, {
              content: fullContent,
              word_count: fullContent.length,
              status: 'draft',
            })
            isDirty.value = false
            takeSnapshot()
            showSuccess('内容生成成功')
          }
        },
      },
      (t) => {
        fullContent += t
        form.content = fullContent
      },
    )
  } catch (e) {
    showError('生成失败: ' + e.message)
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ========== 状态操作 ==========
async function changeStatus(action, okMsg, buildFields) {
  if (!currentChapterId.value) return
  statusLoading.value = true
  try {
    const data = await api.post(chapterUrls.status(projectId.value), {
      chapter_id: currentChapterId.value,
      action,
    })
    if (data && data.success) {
      const fields = buildFields ? buildFields(data) : {}
      updateLocalChapter(currentChapterId.value, fields)
      showSuccess(okMsg)
      const id = currentChapterId.value
      currentChapterId.value = null
      await nextTick()
      selectChapter(id)
    } else {
      showError(data?.message || '操作失败')
    }
  } catch (e) {
    showError('网络错误')
  } finally {
    statusLoading.value = false
  }
}

function publishChapter() {
  showConfirmModal({
    title: '发布章节',
    message: '确定要发布此章节吗？发布后将无法编辑。',
    onConfirm: (close) => {
      close()
      changeStatus('publish', '发布成功', () => ({ status: 'published' }))
    },
  })
}

function toggleLock() {
  const action = isLocked.value ? 'unlock' : 'lock'
  changeStatus(
    action,
    action === 'lock' ? '章节已锁定' : '章节已解锁',
    (data) => ({ state: data.state }),
  )
}

function softDeleteChapter() {
  const chap = currentChapter.value
  showConfirmModal({
    title: '删除章节',
    message: `确定要删除"${chap.title}"吗？删除后章节将标记为已删除，您可以随时恢复。`,
    danger: true,
    onConfirm: (close) => {
      close()
      changeStatus('soft_delete', '章节已删除', () => ({ state: 'deleted' }))
    },
  })
}

function restoreChapter() {
  changeStatus('restore', '章节已恢复', (data) => ({
    state: 'normal',
    status: data.status || 'draft',
  }))
}

// ========== 彻底删除 / 重排 ==========
function showHardDeleteModal() {
  hardDeleteInput.value = ''
  hardDeleteVisible.value = true
}

async function executeHardDelete() {
  const chap = currentChapter.value
  if (!chap) return
  hardDeleteVisible.value = false
  statusLoading.value = true
  try {
    const data = await api.post(chapterUrls.hardDelete(projectId.value), {
      chapter_id: chap.id,
      confirm_title: chap.title,
    })
    if (data && data.success) {
      showSuccess('章节已彻底删除')
      allChapters.value = allChapters.value.filter((c) => c.id !== chap.id)
      currentChapterId.value = null
      form.title = ''
      form.content = ''
      form.summary = ''
      showConfirmModal({
        title: '调整章节序号',
        message: '章节已删除，章节序号是否需要整体调整，以免缺少章节？',
        confirmText: '调整序号',
        onConfirm: (close) => {
          close()
          executeReorder()
        },
      })
    } else {
      showError(data?.message || '彻底删除失败')
    }
  } catch (e) {
    showError('网络错误')
  } finally {
    statusLoading.value = false
  }
}

async function executeReorder() {
  if (!currentVolumeId.value) {
    showWarning('缺少卷信息')
    return
  }
  statusLoading.value = true
  try {
    const data = await api.post(chapterUrls.reorder(projectId.value), {
      volume_id: currentVolumeId.value,
    })
    if (data && data.success) {
      showSuccess('章节序号已调整')
      await loadChapters(currentVolumeId.value)
    } else {
      showError(data?.message || '调整序号失败')
    }
  } catch (e) {
    showError('网络错误')
  } finally {
    statusLoading.value = false
  }
}

// ========== 相邻已删除章节警告 ==========
function checkAdjacentDeletedAndPrompt(onContinue, label) {
  const ch = currentChapter.value
  if (!ch) return
  const prev = allChapters.value.find(
    (c) => c.chapter_number === ch.chapter_number - 1 && c.state === 'deleted',
  )
  const next = allChapters.value.find(
    (c) => c.chapter_number === ch.chapter_number + 1 && c.state === 'deleted',
  )
  const msgs = []
  if (prev) msgs.push(`上一章内容已经被删除，将不参与本次${label || '操作'}，是否继续？`)
  if (next) msgs.push(`下一章内容已经被删除，将不参与本次${label || '操作'}，是否继续？`)
  if (msgs.length === 0) {
    onContinue()
    return
  }
  warningMessages.value = msgs
  warningOnConfirm = onContinue
  warningOnRestore = () => {
    const target = prev || next
    if (target) selectChapter(target.id)
  }
  warningVisible.value = true
}

function onWarningConfirm() {
  warningVisible.value = false
  const fn = warningOnConfirm
  warningOnConfirm = null
  if (fn) fn()
}

function onWarningRestore() {
  warningVisible.value = false
  const fn = warningOnRestore
  warningOnRestore = null
  if (fn) fn()
}

// ========== 章节校验 ==========
function verifyChapter() {
  if (!currentChapterId.value) return
  checkAdjacentDeletedAndPrompt(doVerify, '校验')
}

async function doVerify() {
  verifyVisible.value = true
  verifyLoading.value = true
  verifyIssues.value = []
  let fullText = ''
  try {
    await sseController.stream(
      chapterUrls.verify(projectId.value),
      {
        body: { chapter_id: currentChapterId.value },
        onEvent: (evt) => {
          if (evt.type === 'complete') {
            const items = parseItems(fullText)
            verifyIssues.value = items
              .filter((i) => i.type !== 'pass')
              .map((i) => ({ ...i, checked: true, userComment: '' }))
            verifyLoading.value = false
          }
        },
      },
      (t) => {
        fullText += t
      },
    )
  } catch (e) {
    verifyLoading.value = false
    showError('校验失败: ' + e.message)
  }
}

async function fixVerifyIssues() {
  const selected = verifyIssues.value.filter((i) => i.checked)
  if (selected.length === 0) {
    showWarning('请至少选择一个需要修复的问题')
    return
  }
  const issuesText = selected
    .map((item, i) => {
      let t = `问题${i + 1}[${item.type}]: ${item.description}`
      const comment = item.userComment || item.suggestion || ''
      if (comment) t += `\n用户意见: ${comment}`
      return t
    })
    .join('\n\n')

  verifyVisible.value = false
  generating.value = true
  genStatus.value = 'AI修复中...'
  let fullContent = ''
  try {
    await sseController.stream(
      chapterUrls.verifyFix(projectId.value),
      {
        body: { chapter_id: currentChapterId.value, issues_text: issuesText },
        onEvent: (evt) => {
          if (evt.type === 'complete') {
            form.content = fullContent
            updateLocalChapter(currentChapterId.value, {
              content: fullContent,
              word_count: fullContent.length,
              status: 'draft',
            })
            isDirty.value = false
            takeSnapshot()
            showSuccess('AI修复完成')
          }
        },
      },
      (t) => {
        fullContent += t
        form.content = fullContent
      },
    )
  } catch (e) {
    showError('修复失败: ' + e.message)
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ========== 拆分 ==========
function splitChapter() {
  if (!currentChapterId.value) return
  if (editorTab.value === 'summary') {
    showWarning('概述模式下无法拆分')
    return
  }
  checkAdjacentDeletedAndPrompt(openSplitModal, '拆分')
}

function openSplitModal() {
  splitMode.value = ''
  splitHandling.value = ''
  splitVisible.value = true
}

async function executeSplit() {
  if (!splitMode.value || !splitHandling.value) return
  splitVisible.value = false

  const chapter = currentChapter.value
  if (!chapter) return
  const originalContent = chapter.content || ''
  const originalTitle = chapter.title || ''
  const nextChapter =
    splitHandling.value === 'insert_next'
      ? allChapters.value.find(
          (c) => c.chapter_number === chapter.chapter_number + 1 && c.state !== 'deleted',
        )
      : null

  resetCompare()
  compare.chatDisabled = true
  let splitChapters = []
  let modalOpened = false
  let typingBuffer = ''
  generating.value = true
  genStatus.value = '拆分中...'

  try {
    await sseController.stream(
      chapterUrls.split(projectId.value),
      {
        body: { chapter_id: currentChapterId.value, split_mode: splitMode.value },
        onEvent: (evt) => {
          if (evt.type === 'chunk') {
            typingBuffer += evt.content || ''
            if (!modalOpened) {
              modalOpened = true
              generating.value = false
              compare.streaming = true
              compare.streamingOriginal = ''
              compare.streamingText = ''
              compare.chatMessages = [{ role: 'assistant', content: '章节拆分中，请稍候...' }]
              compare.chatDisabled = true
              compareVisible.value = true
            }
            compare.streaming = true
            compare.streamingText = typingBuffer
          } else if (evt.type === 'split_chapter') {
            splitChapters.push(evt)
            const chapNum = evt.chapter_number || splitChapters.length
            const chapTitle = evt.title || ''
            const chapContent = evt.content || ''
            let origContent = ''
            let origTitle = ''
            let chapId = null
            let finalContent = chapContent
            if (chapNum === chapter.chapter_number) {
              origContent = originalContent
              origTitle = originalTitle
              chapId = chapter.id
            } else if (splitHandling.value === 'insert_next' && nextChapter) {
              origContent = nextChapter.content || ''
              origTitle = nextChapter.title || ''
              chapId = nextChapter.id
              finalContent = chapContent + origContent
            }
            compare.modifications[chapNum] = {
              chapter_id: chapId,
              original: { title: origTitle, content: origContent },
              modified: { title: chapTitle, content: finalContent },
            }
            typingBuffer = ''
            compare.currentChapterNumber = chapNum
            compare.streaming = false
            compare.streamingText = ''
          } else if (evt.type === 'complete') {
            compare.streaming = false
            compare.streamingText = ''
            compare.chatDisabled = false
            compare.chatMessages = [
              {
                role: 'assistant',
                content: `章节已拆分为 ${splitChapters.length} 部分，请在对比区查看结果。您可以继续对话进行调整，然后点击保存。`,
              },
            ]
            if (compare.currentChapterNumber == null && splitChapters.length) {
              compare.currentChapterNumber = splitChapters[0].chapter_number || 1
            }
            genStatus.value = ''
          }
        },
      },
    )
  } catch (e) {
    compare.streaming = false
    compare.chatDisabled = false
    showError('拆分失败: ' + e.message)
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ========== AI 对话（主面板） ==========
async function sendAiMessage(message) {
  const text = (message || '').trim()
  if (!text || chatStreaming.value) return
  if (!currentChapterId.value) {
    showWarning('请先选择章节')
    return
  }
  if (editorTab.value === 'summary') {
    showWarning('概述模式下无法使用AI对话')
    return
  }
  if (isLocked.value || isDeleted.value || isPublished.value) {
    showWarning('当前章节状态下 AI 助手不可用')
    return
  }
  if (isDirty.value) {
    showConfirmModal({
      title: '未保存的修改',
      message: '当前有未保存的修改，AI创作后将丢失。确定要继续吗？',
      onConfirm: (close) => {
        close()
        isDirty.value = false
        sendAiMessage(text)
      },
    })
    return
  }

  const chapter = currentChapter.value
  if (!chapter) return
  const originalContent = chapter.content || ''
  const originalTitle = chapter.title || ''

  chatMessages.value.push({ id: Date.now(), role: 'user', content: text })
  chatHistory.push({ role: 'user', content: text })
  const aiMsg = reactive({ id: Date.now() + 1, role: 'assistant', content: '' })
  chatMessages.value.push(aiMsg)
  chatStreaming.value = true

  resetCompare()
  let fullResponse = ''
  let modalOpened = false

  const controller = new AbortController()
  chatAbort = controller

  try {
    await streamRequestRaw(
      chapterUrls.chat(projectId.value),
      {
        body: { chapter_id: currentChapterId.value, message: text, history: chatHistory },
        signal: controller.signal,
        onEvent: (evt) => {
          if (evt.type === 'chunk' && evt.content) {
            fullResponse += evt.content
            aiMsg.content = fullResponse
            if (!modalOpened && fullResponse.length > 10) {
              modalOpened = true
              const cn = chapter.chapter_number
              compare.streaming = true
              compare.streamingOriginal = originalContent
              compare.streamingText = ''
              compare.currentChapterNumber = cn
              compare.chatMessages = chatMessages.value.map((m) => ({
                role: m.role,
                content: m.content,
              }))
              compare.modifications = {
                [cn]: {
                  chapter_id: currentChapterId.value,
                  original: { title: originalTitle, content: originalContent },
                  modified: { title: chapter.title, content: chapter.content || '' },
                },
              }
              compareVisible.value = true
            }
            if (modalOpened) compare.streamingText = fullResponse
          } else if (evt.type === 'complete') {
            const finalResponse = evt.response || fullResponse
            aiMsg.content = finalResponse
            chatHistory.push({ role: 'assistant', content: finalResponse })
            const newContent = evt.content || ''
            const newTitle = evt.title || ''
            const respCn = evt.chapter_number || chapter.chapter_number
            if (newContent || newTitle) {
              compare.modifications[respCn] = {
                chapter_id: evt.chapter_id || currentChapterId.value,
                original: {
                  title: evt.original_title || originalTitle,
                  content: evt.original_content || originalContent,
                },
                modified: {
                  title: newTitle || chapter.title,
                  content: newContent || chapter.content || '',
                },
              }
            }
            compare.streaming = false
            compare.streamingText = ''
            if (modalOpened) {
              compare.currentChapterNumber = respCn
              compare.chatMessages = chatMessages.value.map((m) => ({
                role: m.role,
                content: m.content,
              }))
              showSuccess('AI 创作完成，请在弹窗中查看对比并确认修改')
            } else {
              if (newContent) {
                form.content = newContent
                updateLocalChapter(currentChapterId.value, {
                  content: newContent,
                  word_count: newContent.length,
                })
              }
              if (newTitle) {
                form.title = newTitle
                updateLocalChapter(currentChapterId.value, { title: newTitle })
              }
              showSuccess('AI 创作完成')
            }
          }
        },
      },
    )
  } catch (e) {
    if (e.message !== '请求已取消或超时') {
      aiMsg.content = '抱歉，创作失败：' + (e.message || '未知错误')
      showError('创作失败: ' + e.message)
    }
  } finally {
    chatStreaming.value = false
    compare.streaming = false
    chatAbort = null
  }
}

function stopChat() {
  if (chatAbort) chatAbort.abort()
  chatStreaming.value = false
  compare.streaming = false
}

// ========== 对比弹窗 ==========
function resetCompare() {
  compare.modifications = {}
  compare.currentChapterNumber = null
  compare.chatMessages = []
  compare.chatSending = false
  compare.streaming = false
  compare.streamingText = ''
  compare.streamingOriginal = ''
  compare.chatDisabled = false
  compare.saving = false
}

async function sendCompareChat(text) {
  const message = (text || '').trim()
  if (!message || compare.chatSending) return
  const cn = compare.currentChapterNumber
  if (cn == null) {
    showWarning('请先选择章节')
    return
  }
  const mod = compare.modifications[cn]
  if (!mod) return
  const chapterId = mod.chapter_id || currentChapterId.value

  compare.chatMessages.push({ role: 'user', content: message })
  const aiMsg = reactive({ role: 'assistant', content: '' })
  compare.chatMessages.push(aiMsg)
  compare.chatSending = true
  compare.streaming = true
  compare.streamingOriginal = mod.modified.content || ''
  compare.streamingText = ''

  const history = compare.chatMessages
    .slice(0, -1)
    .map((m) => ({ role: m.role, content: m.content }))

  let fullResponse = ''
  try {
    await sseController.stream(
      chapterUrls.chat(projectId.value),
      {
        body: {
          chapter_id: chapterId,
          message,
          history,
          current_content: mod.modified.content || '',
          current_title: mod.modified.title || '',
        },
        onEvent: (evt) => {
          if (evt.type === 'chunk' && evt.content) {
            fullResponse += evt.content
            aiMsg.content = fullResponse
            compare.streamingText = fullResponse
          } else if (evt.type === 'complete') {
            const finalResponse = evt.response || fullResponse
            aiMsg.content = finalResponse
            const newContent = evt.content || mod.modified.content
            const newTitle = evt.title || mod.modified.title
            const respCn = evt.chapter_number || cn
            if (!compare.modifications[respCn]) {
              compare.modifications[respCn] = {
                chapter_id: evt.chapter_id || chapterId,
                original: {
                  title: evt.original_title || mod.modified.title,
                  content: evt.original_content || mod.modified.content,
                },
                modified: { title: newTitle, content: newContent },
              }
            } else {
              compare.modifications[respCn].modified = {
                title: newTitle,
                content: newContent,
              }
            }
            compare.currentChapterNumber = respCn
            compare.streaming = false
            compare.streamingText = ''
          }
        },
      },
    )
  } catch (e) {
    aiMsg.content = '抱歉，处理失败：' + (e.message || '未知错误')
    compare.streaming = false
    showError(e.message)
  } finally {
    compare.chatSending = false
    compare.streaming = false
  }
}

async function saveCompareChanges() {
  if (compare.saving) return
  const numbers = Object.keys(compare.modifications)
    .map(Number)
    .filter((cn) => {
      const mod = compare.modifications[cn]
      return (
        mod &&
        (mod.original.title !== mod.modified.title ||
          mod.original.content !== mod.modified.content)
      )
    })
  if (numbers.length === 0) {
    showWarning('没有需要保存的修改')
    compareVisible.value = false
    return
  }
  compare.saving = true
  let success = 0
  try {
    for (const cn of numbers) {
      const mod = compare.modifications[cn]
      let data
      if (mod.chapter_id) {
        data = await chapterApi.save(projectId.value, {
          chapter_id: mod.chapter_id,
          title: mod.modified.title,
          content: mod.modified.content,
        })
      } else {
        data = await chapterApi.save(projectId.value, {
          chapter_id: 0,
          volume_id: Number(currentVolumeId.value),
          chapter_number: cn,
          title: mod.modified.title,
          content: mod.modified.content,
        })
      }
      if (data && data.success) {
        success++
      } else {
        showError(`第${cn}章保存失败: ${data?.message || ''}`)
      }
    }
    if (success > 0) {
      showSuccess(`成功保存 ${success} 章修改`)
      compareVisible.value = false
      resetCompare()
      await loadChapters(currentVolumeId.value)
    }
  } catch (e) {
    showError('网络错误')
  } finally {
    compare.saving = false
  }
}

function cancelCompareChanges() {
  if (Object.keys(compare.modifications).length > 0) {
    showConfirmModal({
      title: '取消修改',
      message: '确定要取消所有修改吗？未保存的修改将丢失。',
      danger: true,
      onConfirm: (close) => {
        close()
        compareVisible.value = false
        resetCompare()
      },
    })
    return
  }
  compareVisible.value = false
  resetCompare()
}

// ========== 批量校验 ==========
function openBatchCheck() {
  if (!currentVolumeId.value) {
    showWarning('请先选择卷')
    return
  }
  if (allChapters.value.length === 0) {
    showWarning('当前卷下没有章节')
    return
  }
  batchStart.value = ''
  batchEnd.value = ''
  if (currentChapter.value) {
    const cn = currentChapter.value.chapter_number
    const maxCh = chapterNumbers.value[chapterNumbers.value.length - 1]
    const bs = Math.floor((cn - 1) / 10) * 10 + 1
    batchStart.value = bs
    batchEnd.value = Math.min(bs + 9, maxCh)
  }
  batchRangeVisible.value = true
}

async function startBatchCheck() {
  if (!rangeValid.value) return
  const s = Number(batchStart.value)
  const e = Number(batchEnd.value)
  batchRangeVisible.value = false
  batchResultVisible.value = true
  batchChecking.value = true
  batchIssues.value = []
  batchOverall.value = ''
  try {
    await sseController.stream(
      chapterUrls.batchCheck(projectId.value),
      {
        body: { volume_id: Number(currentVolumeId.value), start_chapter: s, end_chapter: e },
        onEvent: (evt) => {
          if (evt.type === 'check_result') {
            const data = evt.data || {}
            const mainRange = evt.main_range || [s, e]
            const single = data.issues || []
            const cross = data.cross_chapter_issues || []
            const filtered = single.filter(
              (i) =>
                i.chapter_number &&
                i.chapter_number >= mainRange[0] &&
                i.chapter_number <= mainRange[1],
            )
            const merged = [...filtered, ...cross]
            merged.sort(
              (a, b) =>
                (SEVERITY_ORDER[a.severity] ?? 2) - (SEVERITY_ORDER[b.severity] ?? 2),
            )
            batchIssues.value = merged.map((i) => ({ ...i, checked: true, userComment: '' }))
            batchOverall.value = data.overall_assessment || ''
            batchChecking.value = false
          } else if (evt.type === 'complete') {
            batchChecking.value = false
            if (batchIssues.value.length === 0) showSuccess('校验完成，未发现问题')
            else showSuccess('校验完成')
          }
        },
      },
    )
  } catch (err) {
    batchChecking.value = false
    showError('校验失败: ' + err.message)
  }
}

async function fixBatchIssues() {
  const selected = batchIssues.value.filter((i) => i.checked)
  if (selected.length === 0) {
    showWarning('请至少选择一个需要修复的问题')
    return
  }
  const issues = selected.map((i) => ({
    chapter_number: i.chapter_number,
    chapters: i.chapters || null,
    type: i.type,
    severity: i.severity,
    description: i.description,
    suggestion: i.suggestion || '',
    user_comment: i.userComment || i.suggestion || '',
  }))

  batchResultVisible.value = false
  generating.value = true
  genStatus.value = 'AI修复中...'
  try {
    let fixResult = null
    await sseController.stream(
      chapterUrls.batchFix(projectId.value),
      {
        body: { volume_id: Number(currentVolumeId.value), issues },
        onEvent: (evt) => {
          if (evt.type === 'fix_complete') {
            fixResult = evt
          } else if (evt.type === 'complete') {
            if (fixResult && fixResult.compare_data && fixResult.compare_data.length > 0) {
              resetCompare()
              fixResult.compare_data.forEach((item) => {
                compare.modifications[item.chapter_number] = {
                  chapter_id: item.chapter_id,
                  original: { title: item.original_title, content: item.original_content },
                  modified: { title: item.modified_title, content: item.modified_content },
                }
              })
              compare.chatDisabled = false
              compare.streaming = false
              compareVisible.value = true
              showSuccess(`修复完成，共${fixResult.fixed_count}章`)
            } else {
              showWarning('AI未产出修改内容')
            }
          }
        },
      },
    )
  } catch (e) {
    showError('修复失败: ' + e.message)
  } finally {
    generating.value = false
    genStatus.value = ''
  }
}

// ========== 初始化 ==========
onMounted(() => {
  setPageHeader('章节编辑器', 'AI 辅助章节生成、校验与创作')
  loadVolumeVersions()
})

onBeforeUnmount(() => {
  sseController.abort()
  if (chatAbort) {
    chatAbort.abort()
    chatAbort = null
  }
})
</script>

<style lang="scss">
// 覆盖父级布局（unscoped），锁定章节页面为视口高度，内部滚动
.project-layout:has(.chapter-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.chapter-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.chapter-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.chapter-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chapter-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// 左：章节列表
.chapter-list-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;

  .list-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.filter-select {
  width: 110px;
}

.chapter-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.chapter-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  &.active {
    background: rgba(129, 140, 248, 0.16);
    border-color: rgba(129, 140, 248, 0.4);
  }

  &.deleted {
    opacity: 0.55;
  }

  .chapter-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  .chapter-number {
    font-size: 12px;
    font-weight: 600;
    color: var(--primary);
  }

  .chapter-title {
    font-size: 13.5px;
    color: var(--text-primary);
    margin-bottom: 4px;
  }

  .chapter-meta {
    display: flex;
    gap: 10px;
    font-size: 11.5px;
    color: var(--text-muted);
  }
}

// 中：编辑器
.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-md);
  overflow: hidden;
  min-width: 0;
  padding: 0;
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.editor-title-area {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.current-chapter-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-edit-icon {
  cursor: pointer;
  color: var(--primary);
  font-size: 14px;

  &:hover {
    opacity: 0.8;
  }
}

.title-inline-input {
  width: 260px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.published-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: var(--warning);
}

.editor-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.editor-form {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 12px 16px;
}

.content-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.content-tab {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);

  &.active {
    background: rgba(129, 140, 248, 0.18);
    color: var(--primary);
    font-weight: 600;
  }
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
}

.editor-textarea {
  flex: 1;
  width: 100%;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.9;
  resize: none;
  outline: none;
  font-family: inherit;

  &:focus {
    border-color: rgba(129, 140, 248, 0.5);
  }

  &[readonly] {
    opacity: 0.85;
  }
}

.summary-textarea {
  flex: 1;
  margin-top: 0;
}

.empty-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);

  .empty-icon {
    opacity: 0.5;
  }

  p {
    font-size: 14px;
    margin: 0;
  }

  .empty-actions {
    display: flex;
    gap: 10px;
  }
}

.ai-chat-panel {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid var(--glass-border);
  padding: 10px;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.chat-panel) {
    border-radius: var(--radius-md);
  }
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px 4px;
}

.quick-prompt {
  background: rgba(129, 140, 248, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.25);
  color: var(--primary);
  font-size: 11.5px;
  padding: 3px 10px;
  border-radius: 999px;
  cursor: pointer;
  transition: all var(--transition-fast);

  &:hover:not(:disabled) {
    background: rgba(129, 140, 248, 0.25);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// 校验类弹窗
.verify-body,
.batch-result-body {
  min-height: 200px;
}

.check-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--success);

  p {
    color: var(--text-secondary);
    margin: 0;
  }
}

.check-intro {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
}

.check-issues {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.check-issue {
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--glass-border);
}

.check-issue-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.check-issue-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 6px;

  .row-label {
    flex-shrink: 0;
    color: var(--text-muted);
    font-size: 12px;
    padding-top: 1px;
  }

  .row-text {
    color: var(--text-regular);
    word-break: break-word;

    &.suggestion {
      color: var(--primary);
    }

    &.original {
      color: var(--text-muted);
      font-style: italic;
    }
  }
}

.check-issue-input {
  margin-top: 6px;
}

.batch-overall {
  background: rgba(129, 140, 248, 0.1);
  border: 1px solid rgba(129, 140, 248, 0.25);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-regular);
  margin-bottom: 12px;
}

.check-summary {
  display: flex;
  gap: 14px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);

  .summary-item span {
    color: var(--text-primary);
    font-weight: 700;
  }

  .summary-item.high span {
    color: #f87171;
  }

  .summary-item.medium span {
    color: var(--warning);
  }

  .summary-item.low span {
    color: var(--success);
  }
}

// 拆分弹窗
.split-options {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.split-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.split-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.split-radios {
  display: flex;
  gap: 16px;
}

.split-desc {
  font-size: 12.5px;
  color: var(--text-muted);
}

// 彻底删除
.hard-delete-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hard-delete-warn {
  color: #f87171;
  font-weight: 500;
  font-size: 13.5px;
  line-height: 1.7;
  margin: 0;
}

// 警告弹窗
.warning-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warning-msg {
  color: var(--warning);
  font-weight: 500;
  font-size: 13.5px;
  margin: 0;
  line-height: 1.7;
}

// 批量范围
.batch-range-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.batch-range-tip {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.7;
}

.batch-range-form {
  display: flex;
  gap: 16px;
}

.batch-range-row {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 13px;
    color: var(--text-secondary);
  }
}

.batch-range-preview {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 12px;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.preview-legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: var(--text-muted);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;

  &.before {
    background: rgba(148, 163, 184, 0.6);
  }

  &.main {
    background: var(--primary);
  }

  &.after {
    background: rgba(74, 222, 128, 0.7);
  }
}

.preview-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.batch-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 26px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;

  &.before {
    background: rgba(148, 163, 184, 0.15);
    color: var(--text-muted);
  }

  &.main {
    background: rgba(129, 140, 248, 0.25);
    color: var(--primary);
  }

  &.after {
    background: rgba(74, 222, 128, 0.15);
    color: var(--success);
  }

  &.missing {
    opacity: 0.3;
    text-decoration: line-through;
  }
}

// 响应式
@media (max-width: 1200px) {
  .chapter-workspace {
    flex-direction: column;
    gap: 8px;
    padding: 8px;
  }

  .chapter-list-panel {
    width: 100%;
    max-height: 260px;
  }

  .ai-chat-panel {
    width: 100%;
    border-left: none;
    border-top: 1px solid var(--glass-border);
    min-height: 320px;
  }
}
</style>
