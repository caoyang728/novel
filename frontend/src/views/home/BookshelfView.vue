<template>
  <div class="bookshelf-view">
    <!-- 书架容器 -->
    <div v-loading="loading" class="bookshelf-container">
      <div v-if="projects.length === 0 && !loading" class="empty-wrapper">
        <EmptyState icon="FolderOpened" text="还没有项目，点击上方按钮创建一个吧" />
      </div>
      <!-- 每层书架 -->
      <div v-for="(shelf, index) in shelves" :key="index" class="shelf-row">
        <div class="shelf-books">
          <ProjectCard
            v-for="project in shelf"
            :key="project.id"
            :project="project"
            @click="goToProject(project)"
            @edit="openEditModal(project)"
            @delete="handleDelete(project)"
          />
        </div>
        <!-- 书架底板 -->
        <div class="shelf-base"></div>
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <ProjectFormModal
      v-model:visible="formModalVisible"
      :project="editingProject"
      :submitting="formSubmitting"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { Plus, FolderOpened } from '@element-plus/icons-vue'
import { useProjectStore } from '@/stores/project'
import { useUiStore } from '@/stores/ui'
import { showSuccess, showError } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import ProjectCard from '@/components/project/ProjectCard.vue'
import ProjectFormModal from '@/components/project/ProjectFormModal.vue'

const router = useRouter()
const projectStore = useProjectStore()
const uiStore = useUiStore()

// 设置顶栏右侧按钮
uiStore.setHeaderActions(h(AppButton, {
  variant: 'accent',
  onClick: openCreateModal,
}, () => [h(Plus), ' 创建项目']))

onUnmounted(() => {
  uiStore.clearHeaderActions()
})

const loading = ref(false)
const formModalVisible = ref(false)
const formSubmitting = ref(false)
const editingProject = ref(null)
const BOOKS_PER_SHELF = 5

const { projects } = storeToRefs(projectStore)

// 将项目按每行数量分组
const shelves = computed(() => {
  const result = []
  for (let i = 0; i < projects.value.length; i += BOOKS_PER_SHELF) {
    result.push(projects.value.slice(i, i + BOOKS_PER_SHELF))
  }
  return result
})

async function loadProjects() {
  loading.value = true
  try {
    await projectStore.fetchProjects()
  } catch (err) {
    showError('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

function goToProject(project) {
  router.push(`/projects/${project.id}`)
}

function openCreateModal() {
  editingProject.value = null
  formModalVisible.value = true
}

function openEditModal(project) {
  editingProject.value = project
  formModalVisible.value = true
}

async function handleFormSubmit(formData) {
  formSubmitting.value = true
  try {
    if (formData.isEdit && editingProject.value) {
      await projectStore.updateProject(editingProject.value.id, {
        title: formData.title,
        description: formData.description,
        min_words_per_chapter: formData.min_words_per_chapter,
      })
      showSuccess('项目已更新')
    } else {
      await projectStore.createProject({
        title: formData.title,
        description: formData.description,
      })
      showSuccess('项目已创建')
    }
    formModalVisible.value = false
  } catch (err) {
    showError(err.message || '操作失败')
  } finally {
    formSubmitting.value = false
  }
}

function handleDelete(project) {
  showConfirmModal({
    title: '删除项目',
    message: `确定要删除项目 "${project.title}" 吗？此操作不可撤销。`,
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      try {
        await projectStore.deleteProject(project.id)
        showSuccess('项目已删除')
        close()
      } catch (err) {
        showError('删除失败')
      }
    },
  })
}

onMounted(() => {
  loadProjects()
})
</script>

<style lang="scss" scoped>
.bookshelf-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bookshelf-container {
  position: relative;
  background: linear-gradient(180deg, 
    rgba(15, 23, 42, 0.2) 0%,
    rgba(30, 41, 59, 0.15) 100%
  );
  border-radius: var(--radius-lg);
  padding: 20px 0;
  border: 1px solid rgba(255, 255, 255, 0.05);
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  
  &::-webkit-scrollbar {
    width: 8px;
  }
  
  &::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 4px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    
    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }
  }
}

.shelf-row {
  margin-bottom: 20px;
  padding: 0 20px;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.shelf-books {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 15px 10px 0 10px;
  flex-wrap: wrap;
}

.shelf-base {
  height: 14px;
  background: linear-gradient(180deg, 
    rgba(139, 119, 101, 0.7) 0%,
    rgba(101, 85, 70, 0.85) 20%,
    rgba(78, 67, 55, 0.9) 50%,
    rgba(60, 52, 43, 0.95) 80%,
    rgba(45, 38, 32, 0.98) 100%
  );
  border-radius: 0 0 6px 6px;
  box-shadow: 
    0 6px 16px rgba(0, 0, 0, 0.5),
    0 2px 4px rgba(0, 0, 0, 0.3),
    inset 0 2px 3px rgba(255, 255, 255, 0.12),
    inset 0 -3px 6px rgba(0, 0, 0, 0.4);
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 5%;
    right: 5%;
    height: 2px;
    background: linear-gradient(90deg, 
      transparent 0%, 
      rgba(255, 255, 255, 0.12) 15%, 
      rgba(255, 255, 255, 0.18) 50%, 
      rgba(255, 255, 255, 0.12) 85%, 
      transparent 100%
    );
  }
  
  &::after {
    content: '';
    position: absolute;
    bottom: 2px;
    left: 8%;
    right: 8%;
    height: 1px;
    background: linear-gradient(90deg, 
      transparent 0%, 
      rgba(0, 0, 0, 0.2) 20%, 
      rgba(0, 0, 0, 0.3) 50%, 
      rgba(0, 0, 0, 0.2) 80%, 
      transparent 100%
    );
  }
}

.empty-wrapper {
  padding: 60px 0;
  text-align: center;
}
</style>
