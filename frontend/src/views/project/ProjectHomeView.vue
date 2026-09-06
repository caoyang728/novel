<template>
  <div class="project-home-view">
    <div class="module-grid">
      <router-link
        v-for="item in modules"
        :key="item.name"
        :to="item.to"
        class="module-card glass-panel-hover"
      >
        <el-icon :size="32" class="module-icon"><component :is="item.icon" /></el-icon>
        <h3 class="module-name">{{ item.label }}</h3>
        <p class="module-desc">{{ item.desc }}</p>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { inject, onMounted } from 'vue'
import {
  Document, Notebook, Reading, Collection,
  User, Calendar, EditPen, Share,
} from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useProjectId } from '@/composables/useProjectId'

const projectStore = useProjectStore()
const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')

onMounted(() => {
  setPageHeader(projectStore.projectTitle, '项目概览')
})

const modules = [
  { name: 'Worldview', label: '世界观', icon: Collection, to: { name: 'Worldview' }, desc: '世界观设定' },
  { name: 'Character', label: '人物清单', icon: User, to: { name: 'Character' }, desc: '角色管理' },
  { name: 'Graph', label: '知识图谱', icon: Share, to: { name: 'Graph' }, desc: '关系图谱' },
  { name: 'Timeline', label: '故事时间线', icon: Calendar, to: { name: 'Timeline' }, desc: '故事时间线' },
  { name: 'Outline', label: '大纲', icon: Document, to: { name: 'Outline' }, desc: '构建和管理故事大纲' },
  { name: 'Volume', label: '卷管理', icon: Notebook, to: { name: 'Volume' }, desc: '管理卷结构' },
  { name: 'Chapter', label: '章节管理', icon: Reading, to: { name: 'Chapter' }, desc: '章节生成与管理' },
  { name: 'Note', label: '随手记', icon: EditPen, to: { name: 'Note' }, desc: '随手记' },
]
</script>

<style lang="scss" scoped>
.project-home-view { width: 100%; }

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.module-card {
  padding: 24px;
  text-align: center;
  text-decoration: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.module-icon {
  color: var(--primary);
  margin-bottom: 4px;
}

.module-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.module-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}
</style>
