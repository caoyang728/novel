import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 布局组件
const AuthLayout = () => import('@/layouts/AuthLayout.vue')
const MainLayout = () => import('@/layouts/MainLayout.vue')
const ProjectLayout = () => import('@/layouts/ProjectLayout.vue')

// 页面组件
const LoginView = () => import('@/views/auth/LoginView.vue')
const RegisterView = () => import('@/views/auth/RegisterView.vue')
const ResetPasswordView = () => import('@/views/auth/ResetPasswordView.vue')
const BookshelfView = () => import('@/views/home/BookshelfView.vue')
const TokenUsageView = () => import('@/views/home/TokenUsageView.vue')
const LlmConfigView = () => import('@/views/home/LlmConfigView.vue')
const ProjectHomeView = () => import('@/views/project/ProjectHomeView.vue')
const OutlineView = () => import('@/views/outline/OutlineView.vue')
const VolumeView = () => import('@/views/volume/VolumeView.vue')
const ChapterView = () => import('@/views/chapter/ChapterView.vue')
const ContentManagerView = () => import('@/views/chapter/ContentManagerView.vue')
const WorldviewView = () => import('@/views/worldview/WorldviewView.vue')
const WorldviewChatView = () => import('@/views/worldview/WorldviewChatView.vue')
const CharacterView = () => import('@/views/character/CharacterView.vue')
const TimelineView = () => import('@/views/timeline/TimelineView.vue')
const NoteView = () => import('@/views/note/NoteView.vue')
const GraphView = () => import('@/views/graph/GraphView.vue')

const routes = [
  // 认证页面（AuthLayout 布局；父路径 /auth 仅作布局载体，子路由用绝对路径，URL 仍为 /login 等）
  {
    path: '/auth',
    component: AuthLayout,
    redirect: '/login',
    children: [
      {
        path: '/login',
        name: 'Login',
        component: LoginView,
        meta: { title: '登录', guest: true },
      },
      {
        path: '/register',
        name: 'Register',
        component: RegisterView,
        meta: { title: '注册', guest: true },
      },
      {
        path: '/reset-password',
        name: 'ResetPassword',
        component: ResetPasswordView,
        meta: { title: '重置密码', guest: true },
      },
    ],
  },
  // 全局页面（需要认证）
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Bookshelf',
        component: BookshelfView,
        meta: { title: '书架', subtitle: '管理您的小说项目' },
      },
      {
        path: 'token-usage',
        name: 'TokenUsage',
        component: TokenUsageView,
        meta: { title: 'Token 统计', subtitle: '查看您的 Token 使用情况和缓存命中统计' },
      },
      {
        path: 'llm-config',
        name: 'LlmConfig',
        component: LlmConfigView,
        meta: { title: 'LLM 配置', subtitle: '管理模型服务商与各场景使用的模型' },
      },
    ],
  },
  // 项目内页面
  {
    path: '/projects/:projectId(\\d+)',
    component: ProjectLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'ProjectHome',
        component: ProjectHomeView,
        meta: { title: '项目主页' },
      },
      {
        path: 'outline',
        name: 'Outline',
        component: OutlineView,
        meta: { title: '大纲' },
      },
      {
        path: 'volume',
        name: 'Volume',
        component: VolumeView,
        meta: { title: '卷' },
      },
      {
        path: 'chapter',
        name: 'Chapter',
        component: ChapterView,
        meta: { title: '章节' },
      },
      {
        path: 'content',
        name: 'Content',
        component: ContentManagerView,
        meta: { title: '内容管理' },
      },
      {
        path: 'worldview',
        name: 'Worldview',
        component: WorldviewView,
        meta: { title: '世界观' },
      },
      {
        path: 'worldview/chat',
        name: 'WorldviewChat',
        component: WorldviewChatView,
        meta: { title: '世界观聊天' },
      },
      {
        path: 'character',
        name: 'Character',
        component: CharacterView,
        meta: { title: '角色' },
      },
      {
        path: 'timeline',
        name: 'Timeline',
        component: TimelineView,
        meta: { title: '时间线' },
      },
      {
        path: 'note',
        name: 'Note',
        component: NoteView,
        meta: { title: '随手记' },
      },
      {
        path: 'graph',
        name: 'Graph',
        component: GraphView,
        meta: { title: '图谱' },
      },
    ],
  },
  // 404 回退
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 设置页面标题
  const baseTitle = 'Novel Agent'
  document.title = to.meta.title ? `${to.meta.title} - ${baseTitle}` : baseTitle

  // 已登录用户访问登录页 → 重定向书架
  if (to.meta.guest && authStore.isAuthenticated) {
    return next({ name: 'Bookshelf' })
  }

  // 需要认证的页面
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  next()
})

export default router
