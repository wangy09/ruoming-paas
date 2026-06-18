import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserPermissions, MenuPermission } from '@/types'

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
    return res.data
  }

  /** 判断是否拥有某权限码 */
  function hasPermission(code: string): boolean {
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
