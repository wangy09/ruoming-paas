/**
 * 路由导航守卫
 * 流程：未登录 → 跳登录页；已登录 + 未加载权限 → 加载权限 → 注册动态路由 → 继续
 */
import type { Router } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { useAppStore } from '@/store/app'
import { asyncRoutes } from './index'
import { ElMessage } from 'element-plus'

const WHITE_LIST = ['/login', '/404', '/403']

let dynamicRoutesAdded = false

export function setupRouterGuard(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    const authStore = useAuthStore()
    const permStore = usePermissionStore()
    const appStore = useAppStore()

    // 设置页面标题
    document.title = to.meta.title
      ? `${to.meta.title} - ${appStore.appTitle}`
      : appStore.appTitle

    if (WHITE_LIST.includes(to.path)) {
      return next()
    }

    if (!authStore.isLoggedIn) {
      return next({ path: '/login', query: { redirect: to.fullPath } })
    }

    // 首次加载：获取用户信息 + 权限
    if (!authStore.userInfo) {
      try {
        await authStore.fetchMe()
      } catch {
        authStore.clear()
        return next('/login')
      }
    }

    if (!permStore.loaded) {
      try {
        await permStore.loadPermissions()
      } catch {
        ElMessage.error('加载权限失败')
        authStore.clear()
        return next('/login')
      }
    }

    // 动态注册路由（仅一次）
    if (!dynamicRoutesAdded) {
      const filteredRoutes = filterAsyncRoutes(asyncRoutes, permStore)
      filteredRoutes.forEach(r => router.addRoute(r))
      dynamicRoutesAdded = true
      // 重新导航，确保路由已注册
      return next({ ...to, replace: true })
    }

    // 添加标签页
    if (to.meta.title && !to.meta.hidden) {
      appStore.addVisitedView({ path: to.path, title: to.meta.title as string, name: to.name as string })
    }

    next()
  })

  router.afterEach(() => {
    // NProgress.done() 已在 request.ts 响应拦截器处理
  })
}

/**
 * 根据权限码过滤动态路由
 * 超管 (isSuperplatform) 拥有所有路由
 */
function filterAsyncRoutes(routes: typeof asyncRoutes, permStore: ReturnType<typeof usePermissionStore>) {
  const authStore = useAuthStore()
  if (authStore.isSuperplatform) return routes

  return routes.filter(route => {
    if (route.meta?.permCode && !permStore.hasPermission(route.meta.permCode as string)) {
      return false
    }
    if (route.children) {
      route.children = filterAsyncRoutes(route.children, permStore)
    }
    return true
  })
}

export function resetRouter() {
  dynamicRoutesAdded = false
}
