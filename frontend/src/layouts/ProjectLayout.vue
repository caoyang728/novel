<template>
  <div class="project-layout">
    <!-- 顶部导航栏 -->
    <header class="project-topbar glass-surface">
      <el-button text size="small" class="back-btn" @click="goBack">
        <el-icon><Back /></el-icon>
        <span class="back-text">返回</span>
      </el-button>
      <el-divider direction="vertical" />
      <div class="page-header">
        <div class="page-header-left">
          <h1 class="page-title">{{ pageHeader.title }}</h1>
          <p v-if="pageHeader.subtitle" class="page-subtitle">{{ pageHeader.subtitle }}</p>
        </div>
        <div id="page-header-center" class="page-header-center"></div>
        <div class="page-header-right">
          <div id="header-right-teleport" class="header-right-content"></div>
          <div v-if="pageHeader.rightHtml" v-html="pageHeader.rightHtml"></div>
        </div>
      </div>
    </header>

    <!-- 页面内容 -->
    <main class="project-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { reactive, ref, provide, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useProjectId } from '@/composables/useProjectId'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const { projectId } = useProjectId()

// 页面头部信息（供子页面注入）
const pageHeader = reactive({
  title: '',
  subtitle: '',
  rightHtml: '',
})

provide('setPageHeader', (title, subtitle, rightHtml) => {
  pageHeader.title = title
  pageHeader.subtitle = subtitle || ''
  pageHeader.rightHtml = rightHtml || ''
})

// 提供 header 右侧内容 ref，支持子组件通过 ref 注入 HTML（向后兼容）
const pageHeaderRightRef = ref('')
provide('pageHeaderRightRef', pageHeaderRightRef)

// 提供 header 中间内容 ref
const pageHeaderCenterRef = ref('')
provide('pageHeaderCenterRef', pageHeaderCenterRef)

watch(pageHeaderRightRef, (val) => {
  pageHeader.rightHtml = val || ''
})

watch(pageHeaderCenterRef, (val) => {
  const el = document.getElementById('page-header-center')
  if (el) el.innerHTML = val || ''
})

function goBack() {
  if (route.name === 'ProjectHome') {
    router.push('/')
  } else {
    router.push({ name: 'ProjectHome' })
  }
}

// 加载项目信息
async function loadProject() {
  if (projectId.value) {
    try {
      await projectStore.fetchProject(projectId.value)
    } catch {
      router.push('/')
    }
  }
}

// 加载项目列表（用于项目切换器）
async function loadProjects() {
  if (projectStore.projects.length === 0) {
    try {
      await projectStore.fetchProjects()
    } catch {
      // ignore
    }
  }
}

onMounted(() => {
  loadProject()
  loadProjects()
})

watch(projectId, () => {
  loadProject()
})
</script>

<style lang="scss" scoped>
.project-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

// 顶部导航栏
.project-topbar {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 50;
  border-radius: 0;
  border-left: none;
  border-top: none;
  border-right: none;
  gap: 12px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid transparent;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
    border-color: var(--border-light);
    transform: translateX(-2px);
  }

  &:active {
    background: var(--surface-active);
    transform: translateX(-1px);
  }

  .el-icon {
    font-size: 16px;
    transition: transform 0.2s ease;
  }

  &:hover .el-icon {
    transform: translateX(-2px);
  }
}

.back-text {
  margin-left: 2px;
}

.page-header {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-md);
}

.page-header-left {
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 6px;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-header-center {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.page-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.header-right-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

// 页面内容
.project-content {
  flex: 1;
  padding: 24px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

// 响应式
@media (max-width: 768px) {
  .project-topbar {
    padding: 0 12px;
    height: 52px;
    gap: 8px;
  }

  .back-text {
    display: none;
  }

  .page-header-center {
    display: none;
  }

  .page-title {
    font-size: 16px;
  }

  .project-content {
    padding: 16px;
  }
}
</style>
