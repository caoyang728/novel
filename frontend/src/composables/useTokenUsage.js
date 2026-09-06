/**
 * Token 用量 composable
 */
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function useTokenUsage() {
  const authStore = useAuthStore()
  const loading = ref(false)

  async function fetchTodayUsage() {
    loading.value = true
    try {
      await authStore.fetchTodayUsage()
    } finally {
      loading.value = false
    }
  }

  return {
    todayUsage: authStore.todayTokenUsage,
    loading,
    fetchTodayUsage,
  }
}
