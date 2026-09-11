<template>
  <div class="trajectory-panel">
    <div v-if="loading" v-loading="true" class="trajectory-loading" />
    <template v-else>
      <div v-if="trajectories.length === 0" class="trajectory-empty">
        <el-icon :size="32"><Clock /></el-icon>
        <p>暂无角色轨迹记录</p>
        <span>章节定稿后将自动记录角色状态变化</span>
      </div>
      <div v-else class="trajectory-timeline">
        <div v-for="(t, idx) in trajectories" :key="t.id" class="traj-item">
          <div v-if="idx < trajectories.length - 1" class="traj-line" />
          <div class="traj-content glass-surface">
            <div class="traj-head">
              <span class="traj-title">{{ t.title }}</span>
              <el-tag size="small" :type="sourceTagType(t.source)" effect="plain" round>
                {{ sourceLabel(t.source) }}
              </el-tag>
              <span v-if="t.start_time" class="traj-time">
                {{ t.start_time }}{{ t.end_time ? ' ~ ' + t.end_time : '' }}
              </span>
            </div>
            <div v-if="t.chapter_ids && t.chapter_ids.length > 0" class="traj-chapters">
              <el-icon><Document /></el-icon>
              涉及章节: {{ t.chapter_ids.join(', ') }}
            </div>
            <div v-if="t.details?.description" class="traj-description">
              {{ t.details.description }}
            </div>
            <div v-if="t.details?.location || t.details?.emotional_state || t.details?.power_level" class="traj-details">
              <span v-if="t.details.location" class="traj-detail">
                <el-icon><Location /></el-icon> {{ t.details.location }}
              </span>
              <span v-if="t.details.power_level" class="traj-detail">
                <el-icon><Histogram /></el-icon> {{ t.details.power_level }}
              </span>
              <span v-if="t.details.emotional_state" class="traj-detail">
                <el-icon><ChatDotRound /></el-icon> {{ t.details.emotional_state }}
              </span>
            </div>
            <div v-if="t.details?.key_events && t.details.key_events.length > 0" class="traj-events">
              <div class="traj-events-label">关键事件：</div>
              <div class="traj-events-text">{{ formatKeyEvents(t.details.key_events) }}</div>
            </div>
            <div class="traj-actions">
              <AppButton size="small" text @click="$emit('edit', t)">
                <el-icon><Edit /></el-icon> 编辑
              </AppButton>
              <AppButton size="small" text variant="danger" @click="deleteTrajectory(t)">
                <el-icon><Delete /></el-icon> 删除
              </AppButton>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Clock, Location, Histogram, ChatDotRound, Document, Edit, Delete } from '@element-plus/icons-vue'
import AppButton from '@/components/common/AppButton.vue'
import { characterApi } from '@/api/character'
import { showSuccess, showError } from '@/utils/notify'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  characterId: { type: [Number, String], required: true },
  characterName: { type: String, default: '' },
})

const emit = defineEmits(['edit'])

const loading = ref(false)
const trajectories = ref([])

const SOURCE_LABELS = {
  chapter: '章节生成',
  manual: '手动记录',
  outline_extract: '大纲提取',
  volume_extract: '卷提取',
}

function sourceLabel(source) {
  return SOURCE_LABELS[source] || source || '未知'
}

function sourceTagType(source) {
  const map = {
    manual: 'info',
    ai_generate: '',
    outline_extract: 'primary',
    volume_extract: 'success',
  }
  return map[source] || 'info'
}

function formatKeyEvents(events) {
  if (Array.isArray(events)) return events.join('；')
  if (typeof events === 'string') return events
  return ''
}

async function deleteTrajectory(t) {
  if (!confirm(`确定删除轨迹"${t.title}"吗？`)) return

  try {
    await characterApi.deleteTrajectory(props.projectId, props.characterId, t.id)
    showSuccess('轨迹已删除')
    await fetchTrajectories()
  } catch (error) {
    showError('删除失败')
  }
}

async function fetchTrajectories() {
  loading.value = true
  try {
    const res = await characterApi.getTrajectories(props.projectId, props.characterId)
    trajectories.value = res?.data?.trajectories || []
  } catch {
    // request.js 已统一提示
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTrajectories()
})

defineExpose({
  refresh: fetchTrajectories,
})
</script>

<style lang="scss" scoped>
.trajectory-panel {
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.trajectory-loading {
  min-height: 200px;
}

.trajectory-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px 24px;
  color: var(--text-muted);
  text-align: center;

  p { margin: 0; font-size: 14px; color: var(--text-secondary); }
  span { font-size: 12px; }
}

.trajectory-timeline {
  display: flex;
  flex-direction: column;
  padding: 12px 0;
}

.traj-item {
  position: relative;
  display: flex;
  gap: 16px;
  margin-bottom: 16px;

  &:last-child { margin-bottom: 0; }
}

.traj-line {
  position: absolute;
  left: 4px;
  top: 26px;
  bottom: -8px;
  width: 2px;
  background: rgba(75, 85, 99, 0.4);
}

.traj-content {
  flex: 1;
  padding: 12px 16px;
  border-radius: var(--radius-md);
}

.traj-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.traj-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.traj-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}

.traj-chapters {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.traj-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

.traj-details {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.traj-detail {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);

  .el-icon { font-size: 12px; }
}

.traj-events {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}

.traj-events-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.traj-events-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.traj-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(75, 85, 99, 0.3);
}
</style>
