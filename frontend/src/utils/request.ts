/**
 * Axios 封装
 * - 请求拦截：自动注入 Bearer Token + X-Tenant-Code
 * - 响应拦截：统一错误提示 + 401 Token 刷新队列
 */
import axios, { type AxiosInstance, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { useErrorLogStore } from '@/store/errorLog'
import { tokenStorage } from './token'

/** 将错误信息推入错误日志 store（懒加载避免 pinia 初始化顺序问题） */
function pushErrorLog(params: {
  status: number
  code?: number
  method: string
  url: string
  message: string
  traceId?: string
  responseSnippet?: string
}) {
  try {
    const store = useErrorLogStore()
    store.addLog(params)
  } catch {
    // store 未初始化时静默忽略
  }
}

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

    const token = tokenStorage.getAccessToken()
    const tenantCode = tokenStorage.getTenantCode()

    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    if (tenantCode) {
      config.headers['X-Tenant-Code'] = tenantCode
    }

    const method = (config.method || 'get').toLowerCase()
    if (method !== 'get' && method !== 'head' && method !== 'options') {
      const csrfToken = getCsrfTokenFromCookie()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }

    return config
  },
  (error) => {
    NProgress.done()
    return Promise.reject(error)
  },
)

function getCsrfTokenFromCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

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

    // 二进制响应（文件下载）直接返回 response，不解析 JSON
    const responseType = response.config.responseType
    if (responseType === 'blob' || responseType === 'arraybuffer') {
      return response
    }

    const res = response.data

    // 业务错误码处理（后端统一返回 200 HTTP + code 字段）
    if (res.code !== undefined && res.code !== 200 && res.code !== 201) {
      const msg = res.message || '请求失败'
      ElMessage.error(msg)
      pushErrorLog({
        status: 200,
        code: res.code,
        method: (response.config.method || 'GET').toUpperCase(),
        url: response.config.url || '',
        message: msg,
        traceId: res.trace_id,
        responseSnippet: JSON.stringify(res).slice(0, 300),
      })
      return Promise.reject(new Error(msg))
    }

    return res
  },
  async (error) => {
    NProgress.done()
    const { response, config } = error

    if (!response) {
      const msg = '网络连接失败，请检查网络'
      ElMessage.error(msg)
      pushErrorLog({
        status: 0,
        method: (config?.method || 'GET').toUpperCase(),
        url: config?.url || '',
        message: msg,
      })
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

      const refreshToken = tokenStorage.getRefreshToken()
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
          tokenStorage.setAccessToken(access_token)
          if (newRefreshToken) tokenStorage.setRefreshToken(newRefreshToken)
          onRefreshed(access_token)
          // 重试原请求
          return request(config)
        } catch {
          tokenStorage.clearAll()
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

    let errMsg = ''
    if (response.status === 403) {
      errMsg = '无操作权限'
      ElMessage.error(errMsg)
    } else if (response.status === 429) {
      const retryAfter = response.headers['retry-after']
      const backendMsg = response.data?.message || '请求过于频繁，请稍后重试'
      if (retryAfter) {
        errMsg = `${backendMsg}（建议 ${retryAfter} 秒后重试）`
      } else {
        errMsg = backendMsg
      }
      ElMessage.warning(errMsg)
    } else if (response.status >= 500) {
      errMsg = response.data?.message || '服务器异常，请稍后重试'
      ElMessage.error(errMsg)
    } else if (response.data?.message) {
      errMsg = response.data.message
      ElMessage.error(errMsg)
    }

    if (errMsg) {
      pushErrorLog({
        status: response.status,
        code: response.data?.code,
        method: (config?.method || 'GET').toUpperCase(),
        url: config?.url || '',
        message: errMsg,
        traceId: response.data?.trace_id,
        responseSnippet: JSON.stringify(response.data || {}).slice(0, 300),
      })
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
    tokenStorage.clearAll()
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
