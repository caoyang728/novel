<template>
  <div class="graph-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="accent" @click="doRebuild">
        重建图谱
      </AppButton>
    </Teleport>
    <div v-loading="loading" class="graph-body">
      <!-- 空状态 -->
      <EmptyState
        v-if="!loading && (!nodes.length)"
        icon="Share"
        text="暂无图谱数据，重建图谱将从角色数据生成关系网络"
      >
        <AppButton variant="accent" :loading="rebuilding" @click="doRebuild">
          <el-icon><Refresh /></el-icon> 重建图谱
        </AppButton>
      </EmptyState>

      <template v-else>
        <!-- 筛选面板 -->
        <aside class="graph-filters glass-surface">
          <div class="filter-section">
            <div class="filter-title">节点类型</div>
            <label v-for="t in nodeTypeFilters" :key="t.value" class="filter-item">
              <el-checkbox v-model="t.checked" @change="applyFilters" />
              <span class="filter-dot" :style="{ background: t.color }" />
              {{ t.label }}
              <span class="filter-count">({{ t.count }})</span>
            </label>
          </div>
          <div class="filter-section">
            <div class="filter-title">关系类型</div>
            <label v-for="t in edgeTypeFilters" :key="t.value" class="filter-item">
              <el-checkbox v-model="t.checked" @change="applyFilters" />
              <span class="filter-dot" :style="{ background: edgeColor(t.value) }" />
              {{ t.value }}
              <span class="filter-count">({{ t.count }})</span>
            </label>
          </div>
        </aside>

        <!-- 画布 -->
        <div class="graph-canvas-wrap">
          <GraphCanvas
            ref="canvasRef"
            :nodes="nodes"
            :edges="edges"
            @node-click="onNodeClick"
            @blank-click="detail = null"
          />
        </div>

        <!-- 节点详情面板 -->
        <transition name="slide-panel">
          <aside v-if="detail" class="node-detail glass-surface">
            <div class="detail-header">
              <div>
                <div class="detail-name">{{ detail.node.label }}</div>
                <el-tag :type="detail.node.ntype === 'character' ? 'primary' : 'danger'" size="small">
                  {{ detail.node.ntype === 'character' ? '角色' : '势力' }}
                </el-tag>
              </div>
              <AppButton text size="small" @click="closeDetail">
                <el-icon><Close /></el-icon>
              </AppButton>
            </div>

            <div v-if="detail.node.desc" class="detail-desc">{{ detail.node.desc }}</div>

            <div v-if="propRows.length" class="detail-props">
              <div v-for="row in propRows" :key="row.key" class="prop-row">
                <span class="prop-key">{{ row.label }}:</span>
                <span class="prop-val">{{ row.value }}</span>
              </div>
            </div>

            <div v-if="detail.neighbors.length" class="detail-relations">
              <div class="relations-title">关系 ({{ detail.neighbors.length }})</div>
              <div
                v-for="(rel, idx) in detail.neighbors"
                :key="idx"
                class="rel-item"
                @click="jumpToNeighbor(rel)"
              >
                <span class="rel-arrow">{{ rel.direction === 'out' ? '→' : '←' }}</span>
                <el-tag size="small" effect="plain" :style="{ color: edgeColor(rel.edgeType), borderColor: edgeColor(rel.edgeType) }">
                  {{ rel.edgeType }}
                </el-tag>
                <span class="rel-name">{{ rel.node.label }}</span>
              </div>
            </div>

            <div class="detail-footer">
              <AppButton variant="accent" size="small" @click="focusNeighborhood">聚焦关系网络</AppButton>
            </div>
          </aside>
        </transition>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, inject, watch } from 'vue'
import { /* Search, */ Refresh, Close } from '@element-plus/icons-vue'
import GraphCanvas from '@/components/graph/GraphCanvas.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import { graphApi } from '@/api/graph'
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'

const setPageHeader = inject('setPageHeader')

const { projectId } = useProjectId()

const loading = ref(false)
const rebuilding = ref(false)
const searchQuery = ref('')

const nodes = ref([])
const edges = ref([])
const stats = ref(null)
const detail = ref(null)
const canvasRef = ref(null)

const nodeTypeFilters = ref([])
const edgeTypeFilters = ref([])

const EDGE_COLORS = {
  '朋友': '#22c55e', '恋人': '#ec4899', '配偶': '#f43f5e',
  '父母': '#f59e0b', '子女': '#f59e0b', '兄弟姐妹': '#eab308',
  '师父': '#a855f7', '徒弟': '#c084fc', '敌人': '#ef4444',
  '对手': '#f97316', '导师': '#8b5cf6', '门生': '#a78bfa',
  '盟友': '#06b6d4', '亲属': '#fbbf24', '君主': '#7c3aed',
  '臣子': '#8b5cf6', '其他': '#6b7280', '所属': '#475569',
}
const NODE_TYPE_META = {
  character: { label: '角色', color: '#818cf8' },
  faction: { label: '势力', color: '#f87171' },
}

const PROP_LABELS = { role_type: '定位', gender: '性别', age: '年龄', identity: '身份', faction: '势力' }

const propRows = computed(() => {
  if (!detail.value?.node?.props) return []
  return Object.keys(PROP_LABELS)
    .filter((k) => detail.value.node.props[k] !== undefined && detail.value.node.props[k] !== null && detail.value.node.props[k] !== '')
    .map((k) => ({ key: k, label: PROP_LABELS[k], value: detail.value.node.props[k] }))
})

function edgeColor(type) {
  return EDGE_COLORS[type] || '#6b7280'
}

// ---- Header 搜索 ----
const searchInput = ref(null)

async function loadData() {
  loading.value = true
  try {
    const res = await graphApi.getData(projectId.value)
    if (!res?.success) {
      showError(res?.error || '加载失败')
      return
    }
    const data = res.data
    nodes.value = data.nodes || []
    edges.value = data.edges || []
    stats.value = data.stats || null

    if (data.stats?.nodes_by_type) {
      nodeTypeFilters.value = Object.keys(data.stats.nodes_by_type).map((t) => ({
        value: t,
        label: NODE_TYPE_META[t]?.label || t,
        color: NODE_TYPE_META[t]?.color || '#6b7280',
        count: data.stats.nodes_by_type[t],
        checked: true,
      }))
    }
    if (data.stats?.edges_by_type) {
      edgeTypeFilters.value = Object.keys(data.stats.edges_by_type).map((t) => ({
        value: t,
        count: data.stats.edges_by_type[t],
        checked: true,
      }))
    }
  } catch (err) {
    showError('加载失败: ' + err.message)
  } finally {
    loading.value = false
  }
}

function onNodeClick({ node, neighbors }) {
  detail.value = { node, neighbors }
}

function closeDetail() {
  detail.value = null
  canvasRef.value?.clearHighlight()
}

function jumpToNeighbor(rel) {
  const result = canvasRef.value?.highlightByCyId(rel.cyId)
  if (result) detail.value = result
}

function focusNeighborhood() {
  if (detail.value) {
    canvasRef.value?.focusNeighborhood('n' + detail.value.node.dbId)
  }
}

let searchTimer = null
function onSearch() {
  clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  searchTimer = setTimeout(() => {
    canvasRef.value?.searchMatch(q)
  }, 200)
}

function onSearchClear() {
  canvasRef.value?.clearHighlight()
}

function applyFilters() {
  const nodeTypes = nodeTypeFilters.value.filter((f) => f.checked).map((f) => f.value)
  const edgeTypes = edgeTypeFilters.value.filter((f) => f.checked).map((f) => f.value)
  canvasRef.value?.applyFilters(nodeTypes, edgeTypes)
}

function doRebuild() {
  showConfirmModal({
    title: '重建图谱',
    message: '确定要重建图谱吗？这将从所有角色数据重新生成图谱。',
    confirmText: '重建',
    onConfirm: (close) => {
      rebuilding.value = true
      graphApi.rebuild(projectId.value)
        .then((r) => {
          if (r?.success) {
            showSuccess('图谱重建成功')
            close()
            setTimeout(loadData, 1000)
          } else {
            showError(r?.error || '重建失败')
          }
        })
        .catch((err) => showError('重建失败: ' + err.message))
        .finally(() => {
          rebuilding.value = false
        })
    },
  })
}

// ---- 监听状态变化 ----
watch(rebuilding, () => {})

onMounted(() => {
  setPageHeader('关系图谱', '角色与势力关系可视化')
  loadData()
})

onBeforeUnmount(() => {
  // 清理
})
</script>

<style lang="scss">
.project-layout:has(.graph-view) {
  height: 100vh;
  overflow: hidden;
}
.project-layout:has(.graph-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}
.project-layout:has(.graph-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.graph-view {
  display: flex;
  flex-direction: column;
  height: 100%;

}

.stats-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);

  .stat-item b {
    color: var(--text-primary);
    margin-left: 2px;
  }
}

.graph-body {
  position: relative;
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

.graph-filters {
  width: 260px;
  flex-shrink: 0;
  padding: 14px;
  overflow-y: auto;
}

.filter-section {
  margin-bottom: 18px;
}

.filter-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 17px;
  color: var(--text-regular);
  padding: 5px 6px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;

  &:hover {
    background: rgba(99, 102, 241, 0.08);
  }
}

.filter-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.filter-count {
  color: var(--text-muted);
  font-size: 13px;
  margin-left: auto;
}

.graph-canvas-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.node-detail {
  width: 280px;
  flex-shrink: 0;
  padding: 16px;
  overflow-y: auto;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.detail-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.detail-props {
  margin-bottom: 12px;
}

.prop-row {
  display: flex;
  gap: 6px;
  font-size: 13px;
  padding: 3px 0;

  .prop-key {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .prop-val {
    color: var(--text-regular);
  }
}

.relations-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.rel-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: background var(--transition-fast);

  &:hover {
    background: rgba(255, 255, 255, 0.05);
  }
}

.rel-arrow {
  color: var(--text-muted);
}

.rel-name {
  color: var(--text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-footer {
  margin-top: 12px;
  border-top: 1px solid var(--glass-border);
  padding-top: 8px;

  .el-button {
    width: 100%;
  }
}

.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all 0.25s ease;
}
.slide-panel-enter-from,
.slide-panel-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 768px) {
  .graph-filters {
    display: none;
  }
}
</style>
