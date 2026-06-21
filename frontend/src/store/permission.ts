import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserPermissions, MenuPermission } from '@/types'
import type { RouteRecordRaw } from 'vue-router'
import router from '@/router'

// 使用 import.meta.glob 预加载所有 views 下的组件
const modules = import.meta.glob('@/views/**/*.vue')

export const usePermissionStore = defineStore('permission', () => {
  const permissions = ref<UserPermissions>({
    codes: [],
    buttons: [],
    menus: [],
    columns: {},
  })
  const loaded = ref(false)

  const menuTree = computed(() => permissions.value.menus)
  const buttonCodes = computed(() => new Set(permissions.value.buttons))
  const permCodes = computed(() => new Set(permissions.value.codes))

  /** 初始化权限（登录后调用）*/
  async function loadPermissions() {
    if (loaded.value) return
    const res = await authApi.myPermissions()
    permissions.value = res.data
    loaded.value = true

    // 动态注册路由
    await generateRoutes(res.data.menus)
    return res.data
  }

  /** 根据后端菜单生成动态路由 */
  async function generateRoutes(menus: MenuPermission[]) {
    const routes = convertMenuToRoutes(menus)

    // 注册到路由实例
    routes.forEach(route => {
      router.addRoute('root', route)
    })
  }

  /** 将菜单项转换为路由配置 */
  function convertMenuToRoutes(menus: MenuPermission[]): RouteRecordRaw[] {
    const routes: RouteRecordRaw[] = []

    for (const menu of menus) {
      if (!menu.path || !menu.isVisible) continue

      const route: RouteRecordRaw = {
        path: menu.path,
        name: menu.path.replace(/\//g, '_').replace(/^_/, ''),
        meta: {
          title: menu.title,
          icon: menu.icon,
          permCode: menu.permissionCode,
          isCache: menu.isCache,
        },
      }

      // 处理组件
      if (menu.component) {
        const componentPath = normalizeComponentPath(menu.component)

        // 如果是布局组件
        if (componentPath.includes('BasicLayout')) {
          route.component = () => import('@/layouts/BasicLayout.vue')
          route.redirect = menu.redirect || undefined

          // 处理子菜单
          if (menu.children?.length) {
            const children = convertMenuToRoutes(menu.children)
            if (children.length) {
              route.children = children
            }
          }
        } else {
          // 使用 import.meta.glob 映射的组件
          const moduleKey = `/src/${componentPath}`
          if (modules[moduleKey]) {
            route.component = modules[moduleKey]
          } else {
            console.warn(`组件未找到: ${moduleKey}`)
          }
        }
      } else if (menu.children?.length) {
        // 没有 component 但有子菜单，递归处理
        route.children = convertMenuToRoutes(menu.children)
      }

      routes.push(route)
    }

    return routes
  }

  /** 转换组件路径为 import.meta.glob 兼容格式 */
  function normalizeComponentPath(component: string): string {
    // 移除 @/ 前缀
    let path = component.replace(/^@\/+/, '')

    // 确保路径以 views/ 开头
    if (!path.startsWith('views/')) {
      path = `views/${path}`
    }

    // 确保路径以 .vue 结尾
    if (!path.endsWith('.vue')) {
      path = `${path}.vue`
    }

    return path
  }

  /** 判断是否拥有某权限码 */
  function hasPermission(code: string): boolean {
    // 超管拥有所有权限
    if (permCodes.value.has('*') || buttonCodes.value.has('*')) {
      return true
    }
    return permCodes.value.has(code) || buttonCodes.value.has(code)
  }

  /** 判断是否有某菜单（支持路径匹配）*/
  function hasMenu(path: string): boolean {
    return checkMenuPath(permissions.value.menus, path)
  }

  function checkMenuPath(menus: MenuPermission[], path: string): boolean {
    for (const menu of menus) {
      if (menu.path === path) return true
      if (menu.children?.length && checkMenuPath(menu.children, path)) return true
    }
    return false
  }

  /** 获取资源可见列 */
  function getVisibleColumns(resourceKey: string): string[] {
    return permissions.value.columns[resourceKey] ?? []
  }

  function reset() {
    permissions.value = { codes: [], buttons: [], menus: [], columns: {} }
    loaded.value = false
  }

  return {
    permissions,
    loaded,
    menuTree,
    loadPermissions,
    hasPermission,
    hasMenu,
    getVisibleColumns,
    reset,
  }
})
