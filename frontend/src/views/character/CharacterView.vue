<template>
  <div class="character-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="ai" @click="checkVisible = true">
        AI 校验
      </AppButton>
      <AppButton variant="accent" @click="openCreate">
        创建角色
      </AppButton>
    </Teleport>
    <!-- 筛选栏 -->
    <div class="char-filter">
      <el-input
        v-model="searchText"
        class="filter-search"
        placeholder="搜索角色名..."
        clearable
        :prefix-icon="Search"
      />
      <el-select v-model="roleFilter" class="filter-select" placeholder="角色定位">
        <el-option label="全部定位" value="" />
        <el-option
          v-for="r in ROLE_FILTERS"
          :key="r"
          :label="`${r} (${roleCounts[r] || 0})`"
          :value="r"
        />
      </el-select>
      <el-select v-model="factionFilter" class="filter-select" placeholder="势力/阵营">
        <el-option label="全部势力" value="" />
        <el-option v-for="f in factionOptions" :key="f" :label="f" :value="f" />
      </el-select>
    </div>

    <!-- 角色网格 -->
    <div class="char-grid" v-loading="loading" element-loading-text="加载角色列表...">
      <div
        v-for="c in activeFiltered"
        :key="c.id"
        class="char-card glass-surface"
        @click="openEdit(c.id)"
      >
        <div class="char-card-top">
          <div class="char-avatar">{{ (c.name || '?').charAt(0) }}</div>
          <div class="char-info">
            <h4 class="char-name">{{ c.name }}</h4>
            <div class="char-tags">
              <el-tag size="small" type="primary" effect="dark" round>{{ c.role_type || '配角' }}</el-tag>
              <el-tag
                v-for="f in factionsOf(c)"
                :key="f"
                size="small"
                type="warning"
                effect="plain"
                round
              >
                {{ f }}
              </el-tag>
              <el-tag
                v-if="c.source && c.source !== 'manual'"
                size="small"
                :type="sourceTagType(c.source)"
                effect="plain"
                round
              >
                {{ sourceLabel(c.source) }}
              </el-tag>
            </div>
          </div>
        </div>
        <p v-if="c.tagline" class="char-tagline">{{ c.tagline }}</p>
      </div>
    </div>

    <EmptyState
      v-if="!loading && !characters.length"
      icon="Avatar"
      text="暂无角色，点击右上角「创建角色」按钮开始添加"
    />
    <EmptyState
      v-else-if="!loading && !filteredCharacters.length"
      icon="Search"
      text="没有找到匹配的角色，尝试调整搜索或筛选条件"
    />

    <!-- 已删除角色 -->
    <div v-if="deletedFiltered.length" class="deleted-section">
      <div class="deleted-header">
        <el-icon><Delete /></el-icon>
        <span>已删除角色</span>
        <span class="deleted-count">{{ deletedFiltered.length }}</span>
      </div>
      <div class="char-grid">
        <div v-for="c in deletedFiltered" :key="c.id" class="char-card char-card-deleted glass-surface">
          <div class="char-card-top">
            <div class="char-avatar">{{ (c.name || '?').charAt(0) }}</div>
            <div class="char-info">
              <h4 class="char-name">{{ c.name }}</h4>
              <div class="char-tags">
                <el-tag size="small" type="info" effect="plain" round>已删除</el-tag>
              </div>
            </div>
          </div>
          <AppButton variant="default" size="small" plain class="restore-btn" @click="restoreCharacter(c)">
            <el-icon><RefreshLeft /></el-icon>
            恢复
          </AppButton>
        </div>
      </div>
    </div>

    <!-- 创建角色弹窗 -->
    <AppModal v-model:visible="createVisible" title="创建角色" width="800px" height="70vh">
      <div class="edit-modal-container">
        <!-- Tab 栏固定在顶部 -->
        <el-tabs v-model="createTab" class="char-tabs-fixed">
          <el-tab-pane label="手动创建" name="manual" />
          <el-tab-pane label="AI 生成" name="ai" />
          <el-tab-pane label="批量生成" name="batch" />
        </el-tabs>
        
        <!-- 内容区可滚动 -->
        <div class="tab-content-scroll">
          <!-- 手动创建 -->
          <div v-if="createTab === 'manual'" class="tab-pane-content">
            <CharacterFormFields :form="manualForm" tab="all" :genre="projectGenre" />
            <div class="editor-section">
              <div class="editor-section-title"><span class="title-bar"></span>人际关系</div>
              <RelationshipEditor
                v-model="manualRels"
                :characters="createRelCharacters"
                :relationship-types="relTypes"
              />
            </div>
          </div>

          <!-- AI 生成 -->
          <div v-else-if="createTab === 'ai'" class="tab-pane-content">
            <div v-if="!aiGenerated" class="ai-desc-block">
              <p class="ai-desc-hint">描述你想要的角色：题材、身份、性格、与其他角色的关系等，AI 将生成完整设定</p>
              <el-input
                v-model="aiRequirement"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 20 }"
                maxlength="2000"
                show-word-limit
                placeholder="例如：一个表面玩世不恭、实则心思缜密的魔教少主，与主角是宿敌却又数次暗中相助..."
              />
            </div>
            <template v-else>
              <CharacterFormFields :form="aiForm" tab="all" :genre="projectGenre" />
              <div class="editor-section">
                <div class="editor-section-title"><span class="title-bar"></span>人际关系</div>
                <RelationshipEditor
                  v-model="aiRels"
                  :characters="createRelCharacters"
                  :relationship-types="relTypes"
                />
              </div>
            </template>
          </div>

          <!-- 批量生成 -->
          <div v-else-if="createTab === 'batch'" class="tab-pane-content">
            <div v-if="!batchList.length" class="ai-desc-block">
              <p class="ai-desc-hint">描述一组角色的需求，AI 将批量生成多个互相关联的角色</p>
              <el-input
                v-model="batchRequirement"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 20 }"
                maxlength="2000"
                show-word-limit
                placeholder="例如：生成一个修真宗门的核心人物群像，包括掌门、几位长老、核心弟子，彼此间有师承、竞争与隐秘矛盾..."
              />
            </div>
            <div v-else class="batch-list">
              <div v-for="(char, idx) in batchList" :key="idx" class="batch-card" :class="{ 'is-unchecked': !char.selected }">
                <el-checkbox v-model="char.selected" class="batch-checkbox" />
                <div class="batch-content">
                  <div class="batch-header">
                    <span class="batch-name">{{ char.name || '未命名' }}</span>
                    <el-tag size="small" type="primary" effect="dark" round>{{ normalizeRoleType(char.role_type) }}</el-tag>
                    <span v-if="char.age !== null && char.age !== '' && char.age !== undefined" class="batch-meta">年龄：{{ char.age }}</span>
                    <span v-if="char.identity" class="batch-meta">身份：{{ char.identity }}</span>
                    <span v-if="char.faction" class="batch-meta">势力：{{ char.faction }}</span>
                  </div>
                  <div v-if="char.content" class="batch-desc">
                    <strong>内容</strong>{{ truncate(char.content, 150) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-content create-footer">
          <div class="footer-right">
            <AppButton @click="createVisible = false" class="footer-btn">取消</AppButton>
            <template v-if="createTab === 'manual'">
              <AppButton variant="ai" :loading="polishing" :disabled="!manualForm.name.trim()" @click="polishManual" class="footer-btn">
                <el-icon><MagicStick /></el-icon> AI 润色
              </AppButton>
              <AppButton variant="accent" :loading="saving" :disabled="!manualForm.name.trim()" @click="saveManual" class="footer-btn">
                保存角色
              </AppButton>
            </template>
            <template v-else-if="createTab === 'ai'">
              <AppButton
                v-if="aiGenerated"
                :loading="generating"
                @click="generateSingle"
                class="footer-btn"
              >
                <el-icon><RefreshLeft /></el-icon> 重新生成
              </AppButton>
              <AppButton
                v-else
                variant="accent"
                :loading="generating"
                :disabled="!aiRequirement.trim()"
                @click="generateSingle"
                class="footer-btn"
              >
                <el-icon><MagicStick /></el-icon> AI 生成
              </AppButton>
              <AppButton v-if="aiGenerated" variant="accent" :loading="saving" @click="saveAi" class="footer-btn">
                保存角色
              </AppButton>
            </template>
            <template v-else>
              <AppButton
                v-if="batchList.length"
                :loading="generating"
                @click="generateBatch"
                class="footer-btn"
              >
                <el-icon><RefreshLeft /></el-icon> 重新生成
              </AppButton>
              <AppButton
                v-else
                variant="accent"
                :loading="generating"
                :disabled="!batchRequirement.trim()"
                @click="generateBatch"
                class="footer-btn"
              >
                <el-icon><MagicStick /></el-icon> 批量生成
              </AppButton>
              <div v-if="batchProgress.active" class="batch-progress">
                <el-progress
                  :percentage="Math.round((batchProgress.done / batchProgress.total) * 100)"
                  :status="batchProgress.done >= batchProgress.total ? 'success' : undefined"
                  :stroke-width="6"
                />
                <span class="batch-progress-text">{{ batchProgress.done }} / {{ batchProgress.total }}</span>
              </div>
              <AppButton
                v-if="batchList.length"
                variant="accent"
                :loading="saving"
                :disabled="!batchSelectedCount || batchProgress.active"
                @click="saveBatch"
                class="footer-btn"
              >
                批量保存{{ batchSelectedCount ? `（${batchSelectedCount}）` : '' }}
              </AppButton>
            </template>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- 编辑角色弹窗 -->
    <AppModal v-model:visible="editVisible" title="编辑角色" width="800px" height="70vh">
      <div class="edit-modal-container" v-loading="editLoading" element-loading-text="加载角色详情...">
        <!-- Tab 栏固定在顶部 -->
        <el-tabs v-model="editTab" class="char-tabs-fixed">
          <el-tab-pane label="基础信息" name="basic" />
          <el-tab-pane label="角色内容" name="content" />
          <el-tab-pane label="关系网络" name="relations" />
          <el-tab-pane label="关系图谱" name="graph" />
          <el-tab-pane label="角色轨迹" name="trajectory" />
          <Teleport defer to=".char-tabs-fixed .el-tabs__nav-wrap">
            <AppButton
              size="small"
              class="timeline-link-btn"
              @click="router.push({ name: 'Timeline', query: { view: 'graph', graph_view: 'character', character_id: editId } })"
            >
              <el-icon><DataLine /></el-icon> 查看人物时间线
            </AppButton>
          </Teleport>
        </el-tabs>
        
        <!-- 内容区 -->
        <div class="tab-content-scroll" :class="{ 'no-scroll': editTab === 'content' || editTab === 'graph' }">
          <div v-if="editTab === 'basic'" class="tab-pane-content">
            <CharacterFormFields :form="editForm" tab="basic" :genre="projectGenre" />
          </div>
          <div v-else-if="editTab === 'content'" class="tab-pane-content content-tab">
            <CharacterFormFields :form="editForm" tab="content" :genre="projectGenre" />
          </div>
          <div v-else-if="editTab === 'relations'" class="tab-pane-content">
            <RelationshipEditor
              v-model="editRels"
              :characters="editRelCharacters"
              :relationship-types="relTypes"
            />
          </div>
          <div v-else-if="editTab === 'graph'" class="tab-pane-content">
            <CharacterGraphModal
              :project-id="projectId"
              :character-id="editId"
              :character-name="editForm.name"
            />
          </div>
          <div v-else-if="editTab === 'trajectory'" class="tab-pane-content">
            <CharacterTrajectoryPanel
              ref="trajectoryPanelRef"
              :project-id="projectId"
              :character-id="editId"
              @edit="openTrajectoryEdit"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-content">
          <AppButton variant="danger" plain @click="removeCharacter" class="footer-btn">
            <el-icon><Delete /></el-icon> 删除
          </AppButton>
          <div class="footer-right">
            <AppButton @click="editVisible = false" class="footer-btn">取消</AppButton>
            <AppButton variant="ai" :loading="polishing" :disabled="!editForm.name.trim()" @click="polishEdit" class="footer-btn">
              <el-icon><MagicStick /></el-icon> AI 润色
            </AppButton>
            <AppButton variant="accent" :loading="saving" :disabled="!editForm.name.trim()" @click="saveEdit" class="footer-btn">
              保存修改
            </AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- AI 检测/优化弹窗 -->
    <CharacterCheckModal
      v-model:visible="checkVisible"
      :project-id="projectId"
      @saved="loadCharacters"
    />

    <!-- 编辑轨迹弹窗（独立二级弹窗） -->
    <AppModal v-model:visible="trajEditVisible" title="编辑轨迹" width="600px" height="auto">
      <el-form :model="trajEditForm" label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="trajEditForm.title" placeholder="如：创业初期" />
        </el-form-item>
        <el-form-item label="时间范围">
          <div class="traj-time-range">
            <el-input v-model="trajEditForm.start_time" placeholder="起始时间，如：2024年1月" />
            <span class="traj-time-separator">~</span>
            <el-input v-model="trajEditForm.end_time" placeholder="结束时间，如：2024年6月" />
          </div>
        </el-form-item>
        <el-form-item label="涉及章节">
          <el-input v-model="trajChapterIdsInput" placeholder="多个章节用逗号分隔，如：1,2,3" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="trajEditForm.details.description" type="textarea" :rows="3" placeholder="详细描述..." />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="trajEditForm.details.location" placeholder="如：北京" />
        </el-form-item>
        <el-form-item label="情感状态">
          <el-input v-model="trajEditForm.details.emotional_state" placeholder="如：焦虑" />
        </el-form-item>
        <el-form-item label="实力等级">
          <el-input v-model="trajEditForm.details.power_level" placeholder="如：初级" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="modal-footer-content">
          <AppButton variant="ai" :loading="trajChecking" @click="checkTrajectory" class="footer-btn">
            <el-icon><MagicStick /></el-icon> AI 检测
          </AppButton>
          <div class="footer-right">
            <AppButton @click="trajEditVisible = false" class="footer-btn">取消</AppButton>
            <AppButton variant="accent" :loading="trajSaving" :disabled="!trajEditForm.title.trim()" @click="saveTrajectory" class="footer-btn">
              保存
            </AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- AI检测结果弹窗（三级弹窗） -->
    <el-dialog
      v-model="trajCheckVisible"
      title="AI 检测结果"
      width="480px"
      :close-on-click-modal="false"
      class="traj-check-dialog"
    >
      <div v-loading="trajChecking" class="traj-check-content">
        <template v-if="trajCheckResult">
          <div v-if="trajCheckResult.issues && trajCheckResult.issues.length > 0" class="traj-issues">
            <div class="traj-issues-header">
              <el-icon><WarningFilled /></el-icon>
              <span>发现 {{ trajCheckResult.issues.length }} 个问题</span>
            </div>
            <div v-for="(issue, idx) in trajCheckResult.issues" :key="idx" class="traj-issue-item">
              <div class="traj-issue-desc">{{ issue.description }}</div>
              <div v-if="issue.suggestion" class="traj-issue-suggestion">
                <span class="suggestion-label">建议：</span>{{ issue.suggestion }}
              </div>
              <AppButton v-if="issue.fix" size="small" variant="accent" class="traj-fix-btn" @click="applyFix(issue)">
                修复
              </AppButton>
            </div>
          </div>
          <div v-else class="traj-check-pass">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>轨迹数据完整，未发现问题</span>
          </div>
        </template>
      </div>
      <template #footer>
        <AppButton @click="trajCheckVisible = false">关闭</AppButton>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, inject, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, MagicStick, Delete, RefreshLeft, WarningFilled, CircleCheckFilled, DataLine } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import CharacterFormFields from './components/CharacterFormFields.vue'
import RelationshipEditor from './components/RelationshipEditor.vue'
// import ExperienceEditor from './components/ExperienceEditor.vue' // 已废弃：经历整合到 content 字段中
import CharacterCheckModal from './components/CharacterCheckModal.vue'
import CharacterGraphModal from './components/CharacterGraphModal.vue'
import CharacterTrajectoryPanel from './components/CharacterTrajectoryPanel.vue'
import { useProjectId } from '@/composables/useProjectId'
import { useProjectStore } from '@/stores/project'
import { characterApi } from '@/api/character'
import { truncate } from '@/utils/format'
import { showSuccess, showError } from '@/utils/notify'
import { sourceLabel, sourceTagType } from './characterUtils'
import { useCharacterForm } from './useCharacterForm'

const { projectId } = useProjectId()
const projectStore = useProjectStore()
const setPageHeader = inject('setPageHeader')
const projectGenre = computed(() => projectStore.currentProject?.genre || 'general')

const {
  relTypes,
  loading, characters, activeChars, loadCharacters, loadRelTypes,
  createVisible, createTab, saving, generating, polishing,
  manualForm, manualRels, aiForm, aiRels, aiGenerated, aiRequirement,
  batchRequirement, batchList, batchSelectedCount, batchProgress, createRelCharacters,
  openCreate, generateSingle, generateBatch, saveManual, saveAi, saveBatch, polishManual,
  editVisible, editLoading, editTab, editId, editForm, editRels,
  editRelCharacters, checkVisible,
  openEdit, saveEdit, polishEdit, removeCharacter, restoreCharacter,
} = useCharacterForm(projectId)

const ROLE_FILTERS = ['主角', '反派', '配角', '路人']

// ---- 列表筛选 ----
const searchText = ref('')
const roleFilter = ref('')
const factionFilter = ref('')

const filteredCharacters = computed(() => {
  const search = searchText.value.toLowerCase().trim()
  return characters.value.filter((c) => {
    const matchName = !search || (c.name || '').toLowerCase().includes(search)
    const matchRole = !roleFilter.value || c.role_type === roleFilter.value
    let matchFaction = true
    if (factionFilter.value) {
      const fs = (c.faction || '').split(',').map((f) => f.trim())
      matchFaction = fs.includes(factionFilter.value)
    }
    return matchName && matchRole && matchFaction
  })
})

const activeFiltered = computed(() => filteredCharacters.value.filter((c) => !c.is_deleted))
const deletedFiltered = computed(() => filteredCharacters.value.filter((c) => c.is_deleted))

const roleCounts = computed(() => {
  const counts = {}
  activeChars.value.forEach((c) => {
    const r = c.role_type || '配角'
    counts[r] = (counts[r] || 0) + 1
  })
  return counts
})

const factionOptions = computed(() => {
  const counts = {}
  activeChars.value.forEach((c) => {
    ;(c.faction || '').split(',').forEach((f) => {
      const t = f.trim()
      if (t) counts[t] = (counts[t] || 0) + 1
    })
  })
  return Object.keys(counts).sort()
})

function factionsOf(c) {
  return (c.faction || '').split(',').map((f) => f.trim()).filter(Boolean)
}

// ---- 轨迹编辑（独立二级弹窗） ----
const trajectoryPanelRef = ref(null)
const trajEditVisible = ref(false)
const trajSaving = ref(false)
const trajChecking = ref(false)
const trajCheckVisible = ref(false)
const trajCheckResult = ref(null)
const trajEditForm = reactive({
  id: null,
  title: '',
  start_time: '',
  end_time: '',
  chapter_ids: [],
  details: {
    description: '',
    location: '',
    emotional_state: '',
    power_level: '',
    key_events: [],
    tags: [],
  },
})

const trajChapterIdsInput = computed({
  get: () => trajEditForm.chapter_ids.join(','),
  set: (val) => {
    trajEditForm.chapter_ids = val.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  },
})

function openTrajectoryEdit(t) {
  trajEditForm.id = t.id
  trajEditForm.title = t.title
  trajEditForm.start_time = t.start_time || ''
  trajEditForm.end_time = t.end_time || ''
  trajEditForm.chapter_ids = t.chapter_ids || []
  trajEditForm.details = { ...t.details }
  trajEditVisible.value = true
}

async function saveTrajectory() {
  if (!trajEditForm.title.trim()) {
    showError('请输入轨迹标题')
    return
  }

  trajSaving.value = true
  try {
    const data = {
      title: trajEditForm.title,
      start_time: trajEditForm.start_time,
      end_time: trajEditForm.end_time,
      chapter_ids: trajEditForm.chapter_ids,
      details: trajEditForm.details,
    }

    await characterApi.updateTrajectory(projectId.value, editId.value, trajEditForm.id, data)
    showSuccess('轨迹已更新')

    trajEditVisible.value = false
    trajectoryPanelRef.value?.refresh()
  } catch (error) {
    showError('保存失败')
  } finally {
    trajSaving.value = false
  }
}

async function checkTrajectory() {
  trajChecking.value = true
  trajCheckResult.value = null
  trajCheckVisible.value = true

  try {
    // 模拟AI检测逻辑，检查轨迹数据完整性
    const issues = []

    if (!trajEditForm.title.trim()) {
      issues.push({
        field: 'title',
        description: '轨迹标题为空',
        suggestion: '请填写轨迹标题，如"创业初期"、"拜师学艺"等',
        fix: { title: '未命名轨迹' },
      })
    }

    if (!trajEditForm.start_time && !trajEditForm.end_time) {
      issues.push({
        field: 'time',
        description: '未设置时间范围',
        suggestion: '建议填写故事内时间，便于时间线梳理',
        fix: null,
      })
    }

    if (!trajEditForm.details.description) {
      issues.push({
        field: 'description',
        description: '轨迹描述为空',
        suggestion: '建议添加简要描述，记录角色在此阶段的关键变化',
        fix: { 'details.description': '待补充' },
      })
    }

    if (!trajEditForm.details.location) {
      issues.push({
        field: 'location',
        description: '未记录地点信息',
        suggestion: '建议记录角色所在位置，便于空间关系分析',
        fix: null,
      })
    }

    if (!trajEditForm.details.emotional_state) {
      issues.push({
        field: 'emotional_state',
        description: '未记录情感状态',
        suggestion: '建议记录角色情感变化，增强人物塑造',
        fix: null,
      })
    }

    // 模拟网络延迟
    await new Promise(resolve => setTimeout(resolve, 800))

    trajCheckResult.value = { issues }
  } catch (error) {
    showError('检测失败')
    trajCheckVisible.value = false
  } finally {
    trajChecking.value = false
  }
}

function applyFix(issue) {
  if (!issue.fix) return

  Object.entries(issue.fix).forEach(([key, value]) => {
    if (key.includes('.')) {
      const [parent, child] = key.split('.')
      if (trajEditForm[parent]) {
        trajEditForm[parent][child] = value
      }
    } else {
      trajEditForm[key] = value
    }
  })

  showSuccess('已自动修复')
  // 重新检测
  checkTrajectory()
}

// ---- Header 右侧：操作按钮 ----

onMounted(() => {
  setPageHeader('角色管理', 'AI 生成、润色、检测与优化角色设定')
  loadCharacters()
  loadRelTypes()
  
  // 将筛选栏移动到页面头部中间
  nextTick(() => {
    const filter = document.querySelector('.character-view .char-filter')
    const center = document.querySelector('#page-header-center')
    if (filter && center) {
      center.appendChild(filter)
    }
  })
})

onBeforeUnmount(() => {
  // 将筛选栏移回原位
  const filter = document.querySelector('#page-header-center .char-filter')
  const charView = document.querySelector('.character-view')
  if (filter && charView) {
    charView.insertBefore(filter, charView.firstChild)
  }
})
</script>

<style lang="scss" scoped>
.character-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  height: 100%;
}

// 筛选栏
.char-filter {
  display: flex;
  gap: 12px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  align-items: center;
}

.filter-search {
  width: 200px;
}

.filter-select {
  width: 140px;
}

// 角色网格
.char-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.char-card {
  padding: 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 10px;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--primary);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
  }
}

.char-card-top {
  display: flex;
  gap: 12px;
  align-items: center;
}

.char-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), #818cf8);
}

.char-info {
  min-width: 0;
  flex: 1;
}

.char-name {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.char-tagline {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.char-card-deleted {
  opacity: 0.6;
  cursor: default;

  &:hover {
    transform: none;
    border-color: var(--glass-border);
    box-shadow: none;
  }

  .char-avatar {
    background: linear-gradient(135deg, #6b7280, #9ca3af);
  }
}

.restore-btn {
  align-self: flex-start;
}

// 已删除分区
.deleted-section {
  margin-top: 8px;
}

.deleted-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;

  .deleted-count {
    background: rgba(156, 163, 175, 0.15);
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 12px;
  }
}

// 编辑弹窗容器
.edit-modal-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

// 固定 Tab 栏
.char-tabs-fixed {
  flex-shrink: 0;
  margin-bottom: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 0;
  
  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }
  
  :deep(.el-tabs__nav-wrap) {
    padding: 0;
    overflow: visible !important;
    
    &::after {
      display: none;
    }
  }
  
  :deep(.el-tabs__nav-scroll) {
    overflow: visible !important;
  }
  
  :deep(.el-tabs__item) {
    padding: 14px 20px !important;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.25s ease;
    border-radius: 0;
    margin: 0 1px;
    
    &:hover {
      color: var(--primary);
      background: rgba(129, 140, 248, 0.08);
    }
    
    &.is-active {
      color: var(--primary);
      font-weight: 600;
      background: rgba(129, 140, 248, 0.15);
    }
  }
  
  :deep(.el-tabs__active-bar) {
    height: 3px;
    border-radius: 2px 2px 0 0;
    background: linear-gradient(90deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.4);
  }
}

// tabs 导航栏右侧的「查看人物时间线」按钮
:deep(.timeline-link-btn) {
  position: absolute;
  right: 12px;
  top: 50%;
  margin-top: -12px;
  z-index: 1;
}

// 可滚动内容区
.tab-content-scroll {
  flex: 1;
  padding: 16px 12px;
  background: rgba(255, 255, 255, 0.01);
  border-radius: 0 0 8px 8px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  
  &.no-scroll {
    overflow-y: hidden;
  }
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
    margin: 4px 0;
  }
  
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    
    &:hover {
      background: rgba(255, 255, 255, 0.35);
    }
  }
}

.tab-pane-content {
  animation: fadeIn 0.25s ease;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  
  &.content-tab {
    height: 100%;
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

// 底部按钮栏（基础样式已定义在 index.scss）
.modal-footer-content.create-footer {
  justify-content: flex-end;
}

.footer-btn {
  height: 36px;
  padding: 0 20px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  transition: all 0.25s ease;
  
  &:hover {
    transform: translateY(-1px);
  }
  
  &:active {
    transform: scale(0.97) translateY(0);
  }
}

.editor-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.editor-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 16px;

  .title-bar {
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.3);
  }
}

.ai-desc-block {
  padding: 8px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.el-textarea) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  :deep(.el-textarea__inner) {
    flex: 1;
    resize: none;
  }
}

.ai-desc-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 10px;
  line-height: 1.6;
}

// 批量生成
.batch-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.batch-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
}

.batch-progress-text {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.batch-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border);
  background: rgba(255, 255, 255, 0.03);
  transition: opacity var(--transition-fast);

  &.is-unchecked {
    opacity: 0.5;
  }
}

.batch-checkbox {
  margin-top: 4px;
}

.batch-content {
  flex: 1;
  min-width: 0;
}

.batch-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.batch-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.batch-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.batch-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-top: 4px;

  strong {
    color: var(--primary);
    margin-right: 6px;
    font-weight: 600;
  }
}

@media (max-width: 768px) {
  .page-header-center {
    display: none;
  }
}

// 轨迹编辑弹窗样式
.traj-time-range {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;

  .el-input {
    flex: 1;
  }
}

.traj-time-separator {
  color: var(--text-muted);
  font-size: 14px;
  flex-shrink: 0;
}

// AI检测结果弹窗样式
.traj-check-dialog {
  :deep(.el-dialog) {
    background: var(--surface-dark);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
  }
}

.traj-check-content {
  min-height: 120px;
}

.traj-issues {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.traj-issues-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #fbbf24;

  .el-icon {
    font-size: 18px;
  }
}

.traj-issue-item {
  position: relative;
  padding: 12px 14px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 8px;
}

.traj-issue-desc {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 6px;
  padding-right: 60px;
}

.traj-issue-suggestion {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;

  .suggestion-label {
    color: var(--primary);
    font-weight: 500;
  }
}

.traj-fix-btn {
  position: absolute;
  top: 12px;
  right: 12px;
}

.traj-check-pass {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px 0;
  color: #34d399;
  font-size: 14px;

  .el-icon {
    font-size: 40px;
  }
}
</style>
