/**
 * 路由导航守卫
 * 流程：未登录 → 跳登录页；已登录 + 未加载权限 → 加载权限 + 动态注册路由 → 继续
 */
import type { Router } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { useAppStore } from '@/store/app'
import { ElMessage } from 'element-plus'

const WHITE_LIST = ['/login', '/404', '/403']

export function setupRouterGuard(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    const authStore = useAuthStore()
    const permStore = usePermissionStore()
    const appStore = useAppStore()

    await appStore.loadPublicConfig()

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

    // 加载权限（会动态注册路由）
    if (!permStore.loaded) {
      try {
        await permStore.loadPermissions()
        // 动态路由注册后，检查并补全恢复的标签页信息
        appStore.visitedViews.forEach((view: { path: string; title?: string; name?: string; affix?: boolean }) => {
          const resolved = router.resolve(view.path)
          if (resolved.matched.length && resolved.meta.title && !view.title) {
            view.title = resolved.meta.title as string
          }
          if (typeof resolved.name === 'string' && !view.name) {
            view.name = resolved.name
          }
          if (resolved.meta.affix && view.affix === undefined) {
            view.affix = Boolean(resolved.meta.affix)
          }
        })
        localStorage.setItem('visited_views', JSON.stringify(appStore.visitedViews))
        // 需要重新导航到目标路由
        const targetRoute = router.resolve(to.path)
        if (targetRoute.matched.length) {
          return next({ ...to, replace: true })
        }
      } catch (error) {
        console.error('加载权限失败:', error)
        ElMessage.error('加载权限失败')
        authStore.clear()
        return next('/login')
      }
    }

    // 添加标签页
    if (to.meta.title && !to.meta.hidden) {
      appStore.addVisitedView({
        path: to.path,
        title: to.meta.title as string,
        name: typeof to.name === 'string' ? to.name : undefined,
        affix: Boolean(to.meta.affix),
      })
      appStore.addCachedView(typeof to.name === 'string' ? to.name : undefined)
    }

    // 检查路由是否存在
    const targetRoute = router.resolve(to.path)
    if (!targetRoute.matched.length) {
      return next({ path: '/404' })
    }

    next()
  })

  router.afterEach(() => {
    // NProgress.done() 已在 request.ts 响应拦截器处理
  })
}

export function resetRouter() {
  // 重置权限存储
  const permStore = usePermissionStore()
  permStore.reset()
}
