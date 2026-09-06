/**
 * 从路由获取 projectId
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

export function useProjectId() {
  const route = useRoute()

  const projectId = computed(() => route.params.projectId)

  return { projectId }
}
