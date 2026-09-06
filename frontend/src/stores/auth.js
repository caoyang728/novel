import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/request'
import { rsaEncrypt } from '@/utils/crypto'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  // ---- State ----
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const todayTokenUsage = ref(null)

  // ---- Getters ----
  const isAuthenticated = computed(() => !!accessToken.value)
  const username = computed(() => user.value?.username || '')
  const todayUsage = computed(() => todayTokenUsage.value)

  // ---- Actions ----
  function setTokens(access, refresh) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    if (refresh) localStorage.setItem('refresh_token', refresh)
  }

  function setUser(userData) {
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  function clearAuth() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    todayTokenUsage.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    localStorage.removeItem('user_fetch_time')
  }

  async function login(username, password) {
    const passwordEncrypted = await rsaEncrypt(password)
    const data = await api.post('/login/', { username, password_encrypted: passwordEncrypted })
    setTokens(data.access, data.refresh)
    if (data.user) setUser(data.user)
    return data
  }

  async function register({ username, password, email }) {
    const passwordEncrypted = await rsaEncrypt(password)
    return await api.post('/register.html', {
      username,
      email,
      password_encrypted: passwordEncrypted,
      password_confirm_encrypted: passwordEncrypted,
    })
  }

  async function logout() {
    clearAuth()
    router.push({ name: 'Login' })
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) {
      throw new Error('No refresh token')
    }
    try {
      const data = await api.post('/api/auth/refresh/', {
        refresh: refreshToken.value,
      })
      setTokens(data.access, data.refresh || refreshToken.value)
      return data.access
    } catch (err) {
      clearAuth()
      router.push({ name: 'Login' })
      throw err
    }
  }

  // 缓存时间：1小时
  const USER_CACHE_TTL = 60 * 60 * 1000

  async function fetchUser() {
    // 检查缓存是否有效
    const lastFetch = localStorage.getItem('user_fetch_time')
    if (lastFetch && Date.now() - parseInt(lastFetch) < USER_CACHE_TTL) {
      return
    }
    try {
      const data = await api.get('/api/auth/user/')
      if (data.user) {
        setUser(data.user)
        localStorage.setItem('user_fetch_time', Date.now().toString())
      }
      return data
    } catch (err) {
      // ignore
    }
  }

  async function fetchTodayUsage() {
    try {
      const data = await api.get('/api/token-usage/today/')
      todayTokenUsage.value = data.usage || data
      return data
    } catch (err) {
      // ignore
    }
  }

  return {
    // State
    accessToken,
    refreshToken,
    user,
    todayTokenUsage,
    // Getters
    isAuthenticated,
    username,
    todayUsage,
    // Actions
    setTokens,
    setUser,
    clearAuth,
    login,
    register,
    logout,
    refreshAccessToken,
    fetchUser,
    fetchTodayUsage,
  }
})
