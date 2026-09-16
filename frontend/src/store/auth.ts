import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import { tokenStorage } from '@/utils/token'
import { useAppStore } from '@/store/app'
import { usePermissionStore } from '@/store/permission'
import type { UserInfo, LoginRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(tokenStorage.getAccessToken())
  const refreshTokenVal = ref(tokenStorage.getRefreshToken())
  const tenantCode = ref(tokenStorage.getTenantCode())
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!accessToken.value)
  const isSuperplatform = computed(() => userInfo.value?.is_superplatform ?? false)

  /** 登录 */
  async function login(data: LoginRequest) {
    const res = await authApi.login(data)
    const payload = res.data

    accessToken.value = payload.access_token
    refreshTokenVal.value = payload.refresh_token
    userInfo.value = {
      id: payload.user_id,
      username: payload.username,
      nickname: payload.nickname,
      is_superplatform: payload.is_superplatform,
      tenant_id: payload.tenant_id,
    }

    const tc = data.tenant_code || payload.tenant_code || ''
    tenantCode.value = tc

    tokenStorage.setAccessToken(payload.access_token)
    tokenStorage.setRefreshToken(payload.refresh_token)
    tokenStorage.setTenantCode(tc)

    return payload
  }

  /** 刷新 Token */
  async function refreshToken() {
    if (!refreshTokenVal.value) throw new Error('no refresh token')
    const res = await authApi.refresh(refreshTokenVal.value)
    const { access_token, refresh_token } = res.data
    accessToken.value = access_token
    if (refresh_token) {
      refreshTokenVal.value = refresh_token
      tokenStorage.setRefreshToken(refresh_token)
    }
    tokenStorage.setAccessToken(access_token)
  }

  /** 获取当前用户信息 */
  async function fetchMe() {
    const res = await authApi.me()
    userInfo.value = res.data
    return res.data
  }

  /** 登出 */
  async function logout() {
    try {
      await authApi.logout(refreshTokenVal.value)
    } catch {
      // ignore
    }
    clear()
  }

  function clear() {
    accessToken.value = ''
    refreshTokenVal.value = ''
    tenantCode.value = ''
    userInfo.value = null
    tokenStorage.clearAll()

    // 清空上一个用户残留的标签页（内存状态 + 本地缓存）
    const appStore = useAppStore()
    appStore.clearTabs()

    // 重置权限加载状态，下次登录时重新请求当前用户的权限和菜单
    const permStore = usePermissionStore()
    permStore.reset()
  }

  return {
    accessToken,
    tenantCode,
    userInfo,
    isLoggedIn,
    isSuperplatform,
    login,
    refreshToken,
    fetchMe,
    logout,
    clear,
  }
})
