<template>
  <div class="main-layout">
    <!-- 左侧图标轨道 -->
    <aside class="icon-rail glass-surface">
      <div class="rail-top">
        <router-link to="/" class="rail-logo" title="书架">
          <el-icon :size="24"><HomeFilled /></el-icon>
        </router-link>
        <router-link to="/" class="rail-item" :class="{ active: isActive('Bookshelf') }" title="书架">
          <el-icon :size="20"><Reading /></el-icon>
        </router-link>
        <router-link to="/token-usage" class="rail-item" :class="{ active: isActive('TokenUsage') }" title="Token 统计">
          <el-icon :size="20"><DataLine /></el-icon>
        </router-link>
        <router-link to="/llm-config" class="rail-item" :class="{ active: isActive('LlmConfig') }" title="LLM 配置">
          <el-icon :size="20"><Setting /></el-icon>
        </router-link>
      </div>

      <div class="rail-bottom">
        <el-dropdown trigger="click" placement="right-start" @visible-change="onAvatarDropdownChange">
          <div class="rail-user" title="用户菜单">
            <el-icon :size="20"><UserFilled /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <span class="user-name">{{ authStore.username }}</span>
              </el-dropdown-item>
              <el-dropdown-item v-if="authStore.todayUsage" disabled>
                <span class="token-info">今日 Token: {{ formatTokenCount(authStore.todayUsage.total_tokens) }}</span>
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶栏 -->
      <header class="top-bar glass-surface">
        <div class="top-bar-left">
          <h2 class="top-bar-title">{{ pageTitle }}</h2>
          <p v-if="pageSubtitle" class="top-bar-subtitle">{{ pageSubtitle }}</p>
        </div>
        <div class="top-bar-right">
          <component :is="uiStore.headerActions" v-if="uiStore.headerActions" />
          <slot name="header-actions" />
        </div>
      </header>

      <!-- 页面内容 -->
      <div class="page-content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  HomeFilled, Reading, DataLine, Setting,
  UserFilled, SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { formatTokenCount } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUiStore()

const pageTitle = computed(() => route.meta.title || 'Novel Agent')
const pageSubtitle = computed(() => route.meta.subtitle || '')

function isActive(name) {
  return route.name === name
}

async function handleLogout() {
  await authStore.logout()
}

// 点击头像展开下拉时，触发获取今日 Token 用量
function onAvatarDropdownChange(visible) {
  if (visible) {
    authStore.fetchTodayUsage()
  }
}

// 进入主框架时加载用户信息
onMounted(() => {
  authStore.fetchUser()
})
</script>

<style lang="scss" scoped>
.main-layout {
  display: flex;
  min-height: 100vh;
}

// 图标轨道
.icon-rail {
  width: 64px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  border-radius: 0;
  border-left: none;
  border-top: none;
  border-bottom: none;
}

.rail-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.rail-logo {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--primary);
  margin-bottom: 12px;
  transition: all var(--transition-fast);

  &:hover {
    background: rgba(129, 140, 248, 0.15);
  }
}

.rail-item {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
  text-decoration: none;

  &:hover {
    color: var(--text-primary);
    background: rgba(255, 255, 255, 0.06);
  }

  &.active {
    color: var(--primary);
    background: rgba(129, 140, 248, 0.12);
  }
}

.rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.rail-user {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  background: rgba(255, 255, 255, 0.06);

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-primary);
  }
}

.user-name {
  font-weight: 600;
}

.token-info {
  font-size: 12px;
  color: var(--text-muted);
}

// 主内容区
.main-content {
  flex: 1;
  margin-left: 64px;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

// 顶栏
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  position: sticky;
  top: 0;
  z-index: 50;
  border-radius: 0;
  border-left: none;
  border-top: none;
  border-right: none;
  flex-shrink: 0;
}

.top-bar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.top-bar-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin: 2px 0 0;
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

// 页面内容
.page-content {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

// 响应式
@media (max-width: 768px) {
  .icon-rail {
    width: 100%;
    height: 56px;
    flex-direction: row;
    position: fixed;
    top: auto;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 0 12px;
    border-radius: 0;
    border-bottom: none;
    border-left: none;
    border-right: none;
    border-top: 1px solid var(--glass-border);
  }

  .rail-top {
    flex-direction: row;
    gap: 4px;
  }

  .rail-logo {
    margin-bottom: 0;
    margin-right: 8px;
  }

  .rail-bottom {
    margin-left: auto;
  }

  .main-content {
    margin-left: 0;
    margin-bottom: 56px;
  }

  .page-content {
    padding: 16px;
  }
}
</style>
