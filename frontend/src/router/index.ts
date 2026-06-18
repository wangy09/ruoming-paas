import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/** 静态基础路由（无需权限）*/
export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '404', hidden: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '工作台', icon: 'Odometer', affix: true },
      },
    ],
  },
]

/** 动态路由（需权限，从后端菜单构建）*/
export const asyncRoutes: RouteRecordRaw[] = [
  // 系统管理
  {
    path: '/system',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: { title: '系统管理', icon: 'Setting' },
    children: [
      {
        path: 'users',
        name: 'SystemUser',
        component: () => import('@/views/system/user/index.vue'),
        meta: { title: '用户管理', icon: 'User', permCode: 'system:user:list' },
      },
      {
        path: 'roles',
        name: 'SystemRole',
        component: () => import('@/views/system/role/index.vue'),
        meta: { title: '角色管理', icon: 'UserFilled', permCode: 'system:role:list' },
      },
      {
        path: 'permissions',
        name: 'SystemPermission',
        component: () => import('@/views/system/permission/index.vue'),
        meta: { title: '权限管理', icon: 'Lock', permCode: 'system:permission:list' },
      },
      {
        path: 'tenants',
        name: 'SystemTenant',
        component: () => import('@/views/system/tenant/index.vue'),
        meta: { title: '租户管理', icon: 'OfficeBuilding', permCode: 'system:tenant:list' },
      },
    ],
  },
  // AI 管理
  {
    path: '/ai',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: { title: 'AI 管理', icon: 'MagicStick' },
    children: [
      {
        path: 'models',
        name: 'AiModels',
        component: () => import('@/views/ai/model/index.vue'),
        meta: { title: '模型管理', icon: 'Cpu', permCode: 'ai:model:list' },
      },
      {
        path: 'agents',
        name: 'AiAgents',
        component: () => import('@/views/ai/agent/index.vue'),
        meta: { title: 'Agent 管理', icon: 'Robot', permCode: 'ai:agent:list' },
      },
      {
        path: 'knowledge',
        name: 'AiKnowledge',
        component: () => import('@/views/ai/knowledge/index.vue'),
        meta: { title: '知识库', icon: 'Collection', permCode: 'ai:kb:list' },
      },
      {
        path: 'conversations',
        name: 'AiConversations',
        component: () => import('@/views/ai/conversation/index.vue'),
        meta: { title: '对话历史', icon: 'ChatDotRound', permCode: 'ai:conversation:list' },
      },
      {
        path: 'prompts',
        name: 'AiPrompts',
        component: () => import('@/views/ai/prompt/index.vue'),
        meta: { title: 'Prompt 模板', icon: 'Document', permCode: 'ai:prompt:list' },
      },
    ],
  },
  // 审计日志
  {
    path: '/audit',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: { title: '审计日志', icon: 'Notebook' },
    children: [
      {
        path: 'logs',
        name: 'AuditLogs',
        component: () => import('@/views/audit/logs/index.vue'),
        meta: { title: '操作日志', icon: 'List', permCode: 'audit:log:list' },
      },
      {
        path: 'login-logs',
        name: 'AuditLoginLogs',
        component: () => import('@/views/audit/login/index.vue'),
        meta: { title: '登录日志', icon: 'Key', permCode: 'audit:login:list' },
      },
    ],
  },
  // 404 兜底
  { path: '/:pathMatch(.*)*', redirect: '/404', meta: { hidden: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes: constantRoutes,
  scrollBehavior: () => ({ top: 0 }),
})

export default router
