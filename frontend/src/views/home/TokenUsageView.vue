<template>
  <div class="token-usage-view">
    <div class="usage-content">
      <!-- 时间范围筛选 -->
      <div class="range-filter">
        <AppButton
          v-for="r in ranges"
          :key="r.value"
          :variant="activeRange === r.value ? 'accent' : 'default'"
          size="small"
          @click="switchRange(r.value)"
        >{{ r.label }}</AppButton>
      </div>

      <!-- 统计卡片 -->
      <div class="stat-cards">
        <div class="stat-card stat-card--input">
          <div class="stat-value">{{ formatTokenCount(currentUsage.input_tokens) }}</div>
          <div class="stat-label">输入 Token</div>
        </div>
        <div class="stat-card stat-card--output">
          <div class="stat-value">{{ formatTokenCount(currentUsage.output_tokens) }}</div>
          <div class="stat-label">输出 Token</div>
        </div>
        <div class="stat-card stat-card--hit">
          <div class="stat-value">{{ isEstimated ? '-' : formatTokenCount(currentUsage.input_cache_hit_tokens) }}</div>
          <div class="stat-label">输入缓存命中</div>
        </div>
        <div class="stat-card stat-card--miss">
          <div class="stat-value">{{ isEstimated ? '-' : formatTokenCount(currentUsage.input_cache_miss_tokens) }}</div>
          <div class="stat-label">输入缓存未命中</div>
        </div>
        <div class="stat-card stat-card--cost">
          <div class="stat-value">{{ currentUsage.cost > 0 ? '¥' + currentUsage.cost.toFixed(4) : '-' }}</div>
          <div class="stat-label">预估费用</div>
        </div>
      </div>

      <!-- Tab 标签页 -->
      <div class="tab-bar">
        <button
          :class="['tab-item', { active: activeTab === 'detail' }]"
          @click="activeTab = 'detail'"
        >
          <el-icon><List /></el-icon>
          <span>详细记录</span>
        </button>
        <button
          :class="['tab-item', { active: activeTab === 'project' }]"
          @click="activeTab = 'project'"
        >
          <el-icon><Collection /></el-icon>
          <span>按项目统计</span>
        </button>
      </div>

      <!-- 详细记录面板 -->
      <div v-show="activeTab === 'detail'" class="tab-panel glass-panel">
        <!-- 筛选栏 -->
        <div class="filter-bar">
          <el-select
            v-model="filterProject"
            placeholder="筛选项目"
            clearable
            size="small"
            style="width: 180px"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p"
              :label="p"
              :value="p"
            />
          </el-select>
          <el-select
            v-model="filterTaskType"
            placeholder="筛选任务类型"
            clearable
            size="small"
            style="width: 180px"
          >
            <el-option
              v-for="t in taskTypeOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
          <span class="filter-count">共 {{ filteredLogs.length }} 条</span>
        </div>

        <!-- 表格 -->
        <div class="table-wrapper">
          <el-table
            v-loading="loading"
            :data="pagedLogs"
            stripe
            style="width: 100%"
            :header-cell-style="{ background: 'transparent', color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--glass-border)' }"
          >
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="project" label="项目" min-width="120">
              <template #default="{ row }">
                {{ row.project || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="task_type" label="任务类型" width="140">
              <template #default="{ row }">
                {{ getTaskTypeText(row.task_type) }}
              </template>
            </el-table-column>
            <el-table-column label="输入" width="100" align="right">
              <template #default="{ row }">
                {{ formatTokenCount(row.input_tokens) }}
              </template>
            </el-table-column>
            <el-table-column label="输出" width="100" align="right">
              <template #default="{ row }">
                {{ formatTokenCount(row.output_tokens) }}
              </template>
            </el-table-column>
            <el-table-column label="缓存命中" width="110" align="right">
              <template #default="{ row }">
                <template v-if="isLogEstimated(row)">
                  <span class="token-estimated">预估</span>
                </template>
                <template v-else>
                  {{ formatTokenCount(row.input_cache_hit_tokens) }}
                </template>
              </template>
            </el-table-column>
            <el-table-column label="缓存未命中" width="110" align="right">
              <template #default="{ row }">
                <template v-if="isLogEstimated(row)">
                  <span class="token-estimated">预估</span>
                </template>
                <template v-else>
                  {{ formatTokenCount(row.input_cache_miss_tokens) }}
                </template>
              </template>
            </el-table-column>
            <el-table-column label="费用" width="100" align="right">
              <template #default="{ row }">
                {{ row.cost > 0 ? '¥' + Number(row.cost).toFixed(4) : '-' }}
              </template>
            </el-table-column>
            <template #empty>
              <span v-if="isRangeEmpty">{{ { today: '今日', week: '本周', month: '本月', all: '暂' }[activeRange] }}暂无数据</span>
              <span v-else>暂无匹配数据</span>
            </template>
          </el-table>
        </div>

        <!-- 分页 -->
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="filteredLogs.length"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            size="small"
            background
          />
        </div>
      </div>

      <!-- 按项目统计面板 -->
      <div v-show="activeTab === 'project'" class="tab-panel glass-panel">
        <div class="project-panel-scroll">
          <div v-if="filteredProjectStats.length === 0 && !loading" class="empty-state">
            <p>暂无数据</p>
          </div>
          <div v-else class="project-stats-list">
            <div v-for="stat in filteredProjectStats" :key="stat.project_id" class="project-stat-card">
              <div class="project-stat-header">
                <span class="project-stat-title">{{ stat.project_title || '-' }}</span>
                <span class="project-stat-badge">{{ formatTokenCount(stat.total_tokens) }} tokens · {{ stat.cost > 0 ? '¥' + stat.cost.toFixed(4) : '-' }}</span>
              </div>
              <div class="project-stat-progress">
                <div class="project-stat-progress-bar" :style="{ width: getProjectPercent(stat) + '%' }"></div>
              </div>
              <div class="project-stat-detail">
                <span>输入: {{ formatTokenCount(stat.input_tokens) }}</span>
                <span>输出: {{ formatTokenCount(stat.output_tokens) }}</span>
                <span>命中: {{ isProjectEstimated(stat) ? '预估' : formatTokenCount(stat.input_cache_hit_tokens) }}</span>
                <span>未命中: {{ isProjectEstimated(stat) ? '预估' : formatTokenCount(stat.input_cache_miss_tokens) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { tokenUsageApi } from '@/api/tokenUsage'
import { formatTokenCount } from '@/utils/format'
import AppButton from '@/components/common/AppButton.vue'
import { List, Collection } from '@element-plus/icons-vue'

const ranges = [
  { value: 'today', label: '今日' },
  { value: 'week', label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'all', label: '全部' },
]

const loading = ref(false)
const activeRange = ref('today')
const activeTab = ref('detail')
const statsData = ref(null)
const logs = ref([])
const projectStats = ref([])

// 筛选和分页
const filterProject = ref('')
const filterTaskType = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

const currentUsage = computed(() => {
  if (!statsData.value) return {}
  return statsData.value[activeRange.value] || statsData.value.all || {}
})

const isEstimated = computed(() => {
  const u = currentUsage.value
  return (u.input_cache_hit_tokens || 0) === 0 && (u.input_cache_miss_tokens || 0) === 0
})

const isRangeEmpty = computed(() => {
  const u = currentUsage.value
  return !u.total_tokens && !u.count
})

// 检查日志是否在当前时间范围内
function isLogInRange(log) {
  if (activeRange.value === 'all') return true
  if (!log.created_at) return false

  const logDate = new Date(log.created_at.replace(' ', 'T'))
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  if (activeRange.value === 'today') {
    return logDate >= today
  }
  if (activeRange.value === 'week') {
    const weekAgo = new Date(today)
    weekAgo.setDate(weekAgo.getDate() - 7)
    return logDate >= weekAgo
  }
  if (activeRange.value === 'month') {
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    return logDate >= monthStart
  }
  return true
}

// 按时间范围筛选的日志
const logsByRange = computed(() => {
  return logs.value.filter(isLogInRange)
})

// 按时间范围计算的项目统计
const filteredProjectStats = computed(() => {
  const statsMap = {}
  for (const log of logsByRange.value) {
    if (!log.project || log.project === '-') continue
    if (!statsMap[log.project]) {
      statsMap[log.project] = {
        project_title: log.project,
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
        input_cache_hit_tokens: 0,
        input_cache_miss_tokens: 0,
        cost: 0,
      }
    }
    const stat = statsMap[log.project]
    stat.input_tokens += log.input_tokens || 0
    stat.output_tokens += log.output_tokens || 0
    stat.total_tokens += log.total_tokens || 0
    stat.input_cache_hit_tokens += log.input_cache_hit_tokens || 0
    stat.input_cache_miss_tokens += log.input_cache_miss_tokens || 0
    stat.cost += parseFloat(log.cost || 0)
  }
  return Object.values(statsMap).sort((a, b) => b.total_tokens - a.total_tokens)
})

// 项目选项
const projectOptions = computed(() => {
  const set = new Set(logsByRange.value.map(l => l.project).filter(Boolean))
  return Array.from(set).sort()
})

// 任务类型选项
const taskTypeOptions = computed(() => {
  const set = new Set(logsByRange.value.map(l => l.task_type).filter(Boolean))
  return Array.from(set).sort().map(t => ({ value: t, label: getTaskTypeText(t) }))
})

// 筛选后的日志（先按时间范围，再按项目/任务类型）
const filteredLogs = computed(() => {
  let result = logsByRange.value
  if (filterProject.value) {
    result = result.filter(l => l.project === filterProject.value)
  }
  if (filterTaskType.value) {
    result = result.filter(l => l.task_type === filterTaskType.value)
  }
  return result
})

// 分页后的日志
const pagedLogs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredLogs.value.slice(start, start + pageSize.value)
})

// 筛选变化时重置页码
watch([filterProject, filterTaskType], () => {
  currentPage.value = 1
})

// 时间范围变化时重置页码和筛选
watch(activeRange, () => {
  currentPage.value = 1
  filterProject.value = ''
  filterTaskType.value = ''
})

function isLogEstimated(row) {
  return (row.input_cache_hit_tokens || 0) === 0 && (row.input_cache_miss_tokens || 0) === 0
}

function isProjectEstimated(stat) {
  return (stat.input_cache_hit_tokens || 0) === 0 && (stat.input_cache_miss_tokens || 0) === 0
}

function getProjectPercent(stat) {
  if (!filteredProjectStats.value.length) return 0
  const max = filteredProjectStats.value[0].total_tokens || 1
  return Math.min((stat.total_tokens / max) * 100, 100)
}

function switchRange(range) {
  activeRange.value = range
}

async function loadData() {
  loading.value = true
  try {
    const data = await tokenUsageApi.getStats()
    const usage = data.usage || data
    statsData.value = usage
    logs.value = usage.logs || []
    projectStats.value = usage.project_stats || []
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function getTaskTypeText(taskType) {
  const texts = {
    'outline': '大纲-大纲生成',
    'volume_analysis': '卷-大纲分析',
    'volume_generate': '卷-批量生成',
    'volume_optimize': '卷-批量优化',
    'volume_chat': '卷-聊天',
    'volume_chat_merge': '卷-跨卷合并',
    'volume_single_optimize': '卷-单卷优化',
    'volume_single_generate': '卷-单卷生成',
    'chapter_outline': '章节-概要生成',
    'chapter_content': '章节-内容生成',
    'chapter_verify': '章节-校验',
    'chapter_verify_fix': '章节-校验修复',
    'chapter_split': '章节-拆分',
    'chapter_chat': '章节-对话写作',
    'character_generate': '角色-角色生成',
    'character_polish': '角色-角色润色',
    'character_check': '角色-角色检测',
    'character_optimize': '角色-角色优化',
    'timeline_generate': '时间线-生成',
    'timeline_chat': '时间线-聊天',
    'timeline_single_optimize': '时间线-单项优化',
    'timeline_generate_fields': '时间线-字段生成',
    'timeline_merge': '时间线-合并',
    'timeline_check': '时间线-一致性检查',
    'timeline_check_optimize': '时间线-一致性修复',
    'worldview_deepen': '世界观-宏观缺口检测',
    'worldview_deepen_integrate': '世界观-缺口检测整合',
    'worldview_consistency': '世界观-宏观一致性检查',
    'worldview_consistency_fix': '世界观-宏观一致性修复',
    'faction_design': '世界观-阵营生成',
    'location_design': '世界观-地点生成',
    'relation_generate': '世界观-关系生成',
    'worldview_foundation': '世界观-世界基础生成',
    'worldview_power': '世界观-力量体系生成',
    'worldview_races': '世界观-种族族群生成',
    'worldview_society': '世界观-组织势力生成',
    'worldview_culture': '世界观-文化习俗生成',
    'worldview_history': '世界观-重要事件生成',
    'worldview_special': '世界观-特殊规则生成',
    'worldview_setting': '世界观-基础设定生成',
    'worldview_init_question': '世界观-引导问题',
    'worldview_chat': '世界观-聊天',
    'project_title_suggest_json': '项目-书名建议',
    'project_description_suggest': '项目-简介建议',
    'project_info_generate': '项目-信息生成',
    'project_title_suggest': '项目-书名建议',
    'project_title_rewrite': '项目-书名改写',
    'project_description_optimize': '项目-简介优化',
    'project_enhance_description': '项目-描述完善',
    'note_polish': '随手记-AI整理',
    'character_state_extract': '角色-状态提取',
    'chapter_outline_adjust': '章节-概要调整',
    'chapter_batch_content': '章节-批量内容生成',
    'chapter_batch_fix': '章节-批量修复',
    'chapter_scoring': '章节-评分',
    'reader_review': '章节-读者审阅',
    'other': '其他任务',
  }
  return texts[taskType] || taskType
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.token-usage-view {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.usage-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ==================== 时间范围筛选 ==================== */
.range-filter {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ==================== 统计卡片 ==================== */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  flex-shrink: 0;
}

.stat-card {
  background: var(--glass-bg-1);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 16px;
  text-align: center;
  backdrop-filter: blur(var(--glass-blur));
  transition: all var(--transition-normal);

  &:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
    box-shadow: var(--glass-shadow);
  }

  .stat-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .stat-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }
}

.stat-card--hit,
.stat-card--output {
  border-color: rgba(129, 140, 248, 0.25);
  background: rgba(99, 102, 241, 0.06);

  .stat-value {
    color: var(--primary);
  }
}

.stat-card--miss {
  border-color: rgba(248, 113, 113, 0.25);
  background: rgba(239, 68, 68, 0.05);

  .stat-value {
    color: var(--danger);
  }
}

.stat-card--cost {
  border-color: rgba(251, 191, 36, 0.25);
  background: rgba(245, 158, 11, 0.05);

  .stat-value {
    color: var(--warning);
  }
}

/* ==================== Tab 标签页 ==================== */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--glass-border);
  padding-bottom: 0;
  flex-shrink: 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  transition: all var(--transition-fast);

  &:hover {
    color: var(--primary);
    background: rgba(99, 102, 241, 0.08);
  }

  &.active {
    color: var(--primary);
    background: rgba(99, 102, 241, 0.12);
    font-weight: 600;
  }

  .el-icon {
    font-size: 16px;
  }
}

/* ==================== Tab 面板 ==================== */
.tab-panel {
  flex: 1;
  min-height: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ==================== 筛选栏 ==================== */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
}

.filter-count {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

/* ==================== 表格容器 ==================== */
.table-wrapper {
  flex: 1;
  min-height: 0;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }
  }
}

/* ==================== 分页栏 ==================== */
.pagination-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid var(--glass-border);
  margin-top: 12px;
}

/* ==================== 预估标记 ==================== */
.token-estimated {
  display: inline-block;
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(107, 114, 128, 0.2);
  border-radius: 3px;
  padding: 0 6px;
  vertical-align: middle;
}

/* ==================== 项目统计面板 ==================== */
.project-panel-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }
  }
}

.project-stats-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.project-stat-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 16px;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(99, 102, 241, 0.06);
    border-color: rgba(129, 140, 248, 0.25);
  }
}

.project-stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.project-stat-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.project-stat-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(129, 140, 248, 0.2);
  border-radius: var(--radius-xs);
  padding: 2px 10px;
}

.project-stat-progress {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

.project-stat-progress-bar {
  height: 100%;
  background: var(--primary-gradient);
  border-radius: 3px;
  transition: width var(--transition-normal);
}

.project-stat-detail {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
}

/* ==================== 空状态 ==================== */
.empty-state {
  text-align: center;
  padding: 48px 0;
  color: var(--text-muted);
}

/* ==================== 响应式 ==================== */
@media (max-width: 1200px) {
  .stat-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .filter-bar {
    flex-wrap: wrap;
  }

  .project-stat-detail {
    flex-wrap: wrap;
    gap: 4px 12px;
  }
}
</style>
