const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const TENANT_CODE_KEY = 'tenant_code'

// Access Token 存 sessionStorage（浏览器关闭自动清除，降低 XSS 风险）
// Refresh Token 存 localStorage（跨会话保持，配合 Rotation 机制）

export const tokenStorage = {
  getAccessToken(): string {
    return sessionStorage.getItem(ACCESS_TOKEN_KEY) || ''
  },

  setAccessToken(token: string): void {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, token)
  },

  clearAccessToken(): void {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY)
  },

  getRefreshToken(): string {
    return localStorage.getItem(REFRESH_TOKEN_KEY) || ''
  },

  setRefreshToken(token: string): void {
    localStorage.setItem(REFRESH_TOKEN_KEY, token)
  },

  clearRefreshToken(): void {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },

  getTenantCode(): string {
    return localStorage.getItem(TENANT_CODE_KEY) || ''
  },

  setTenantCode(code: string): void {
    localStorage.setItem(TENANT_CODE_KEY, code)
  },

  clearAll(): void {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(TENANT_CODE_KEY)
  },
}
