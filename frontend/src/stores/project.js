import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/request'

export const useProjectStore = defineStore('project', () => {
  // ---- State ----
  const currentProject = ref(null)
  const projects = ref([])
  const loading = ref(false)

  // ---- Getters ----
  const projectId = computed(() => currentProject.value?.id || null)
  const projectTitle = computed(() => currentProject.value?.title || '')

  // ---- Actions ----
  async function fetchProjects() {
    loading.value = true
    try {
      const data = await api.get('/api/projects/')
      const list = Array.isArray(data) ? data : data.results || data.projects || []
      projects.value = list.map((p) => ({ ...p, id: p.id || p.pk }))
      return projects.value
    } catch (err) {
      console.error('Failed to fetch projects:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id) {
    try {
      const data = await api.get(`/api/projects/${id}/`)
      const project = data.project || data
      currentProject.value = { ...project, id: project.id || project.pk }
      return currentProject.value
    } catch (err) {
      console.error('Failed to fetch project:', err)
      currentProject.value = null
      throw err
    }
  }

  async function createProject(projectData) {
    const data = await api.post('/api/projects/create/', projectData)
    const project = data.project || data
    const normalized = { ...project, id: project.id || project.pk }
    projects.value.unshift(normalized)
    return normalized
  }

  async function updateProject(id, projectData) {
    await api.put(`/api/projects/${id}/`, projectData)
    // PUT 返回 { success: true }，需要重新获取详情
    const updated = await fetchProject(id)
    const idx = projects.value.findIndex((p) => p.id === id)
    if (idx !== -1) projects.value[idx] = updated
    return updated
  }

  async function deleteProject(id) {
    await api.del(`/api/projects/${id}/`)
    projects.value = projects.value.filter((p) => p.id !== id)
    if (currentProject.value?.id === id) currentProject.value = null
  }

  function setCurrentProject(project) {
    currentProject.value = project
  }

  function clearCurrentProject() {
    currentProject.value = null
  }

  return {
    // State
    currentProject,
    projects,
    loading,
    // Getters
    projectId,
    projectTitle,
    // Actions
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    deleteProject,
    setCurrentProject,
    clearCurrentProject,
  }
})
