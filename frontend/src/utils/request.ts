/**
 * Axios 封装
 * - 请求拦截：自动注入 Bearer Token + X-Tenant-Code
 * - 响应拦截：统一错误提示 + 401 Token 刷新队列
 */
import axios, { type AxiosInstance, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: false, speed: 300 })

const request: AxiosInstance = axios.create({
  // baseURL 保持空字符串，请求走相对路径（/api/...），由 Vite 代理转发到后端
  // 不能使用 VITE_API_BASE_URL，那是服务端代理 target，浏览器无法访问容器内部地址
  baseURL: '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── 请求拦截器 ────────────────────────────────────────────────────────────────
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    NProgress.start()

    // 延迟 import，避免循环依赖（store 依赖 request，request 不能静态导入 store）
    const token = localStorage.getItem('access_token')
    const tenantCode = localStorage.getItem('tenant_code')

    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    if (tenantCode) {
      config.headers['X-Tenant-Code'] = tenantCode
    }

    return config
  },
  (error) => {
    NProgress.done()
    return Promise.reject(error)
  },
)

// ── Token 刷新队列 ───────────────────────────────────────────────────────────
let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  pendingRequests.push(cb)
}

function onRefreshed(token: string) {
  pendingRequests.forEach((cb) => cb(token))
  pendingRequests = []
}

// ── 响应拦截器 ────────────────────────────────────────────────────────────────
request.interceptors.response.use(
  (response) => {
    NProgress.done()
    const res = response.data

    // 业务错误码处理（后端统一返回 200 HTTP + code 字段）
    if (res.code !== undefined && res.code !== 200 && res.code !== 201) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }

    return res
  },
  async (error) => {
    NProgress.done()
    const { response, config } = error

    if (!response) {
      ElMessage.error('网络连接失败，请检查网络')
      return Promise.reject(error)
    }

    // 401：尝试刷新 Token
    if (response.status === 401) {
      // 登录接口的 401 不视为过期，而是登录失败
      const isLoginRequest = config.url?.includes('/auth/login')
      if (isLoginRequest) {
        if (response.data?.message) {
          ElMessage.error(response.data.message)
        } else {
          ElMessage.error('登录失败')
        }
        return Promise.reject(error)
      }

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        redirectToLogin()
        return Promise.reject(error)
      }

      if (!isRefreshing) {
        isRefreshing = true
        try {
          const res = await axios.post(
            `/api/v1/auth/refresh`,
            { refresh_token: refreshToken },
          )
          const { access_token, refresh_token: newRefreshToken } = res.data.data
          localStorage.setItem('access_token', access_token)
          if (newRefreshToken) localStorage.setItem('refresh_token', newRefreshToken)
          onRefreshed(access_token)
          // 重试原请求
          return request(config)
        } catch {
          localStorage.clear()
          redirectToLogin()
          return Promise.reject(error)
        } finally {
          isRefreshing = false
        }
      }

      // 排队等待刷新
      return new Promise((resolve) => {
        subscribeTokenRefresh((token: string) => {
          config.headers['Authorization'] = `Bearer ${token}`
          resolve(request(config))
        })
      })
    }

    if (response.status === 403) {
      ElMessage.error('无操作权限')
    } else if (response.status === 429) {
      ElMessage.warning('请求过于频繁，请稍后重试')
    } else if (response.status >= 500) {
      ElMessage.error('服务器异常，请稍后重试')
    } else if (response.data?.message) {
      ElMessage.error(response.data.message)
    }

    return Promise.reject(error)
  },
)

function redirectToLogin() {
  ElMessageBox.alert('登录已过期，请重新登录', '提示', {
    confirmButtonText: '重新登录',
    type: 'warning',
    showClose: false,
  }).then(() => {
    localStorage.clear()
    window.location.href = '/login'
  })
}

// ── 便捷方法 ──────────────────────────────────────────────────────────────────
export const get = <T = unknown>(url: string, params?: unknown, config?: AxiosRequestConfig) =>
  request.get<unknown, T>(url, { params, ...config })

export const post = <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  request.post<unknown, T>(url, data, config)

export const put = <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  request.put<unknown, T>(url, data, config)

export const del = <T = unknown>(url: string, config?: AxiosRequestConfig) =>
  request.delete<unknown, T>(url, config)

export const upload = <T = unknown>(url: string, formData: FormData, config?: AxiosRequestConfig) =>
  request.post<unknown, T>(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...config,
  })

export default request
