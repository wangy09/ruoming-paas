import { post, get, put } from '@/utils/request'
import type { ApiResponse, LoginRequest, LoginResponse, UserInfo, UserPermissions } from '@/types'

export interface PasswordUpdate {
  old_password: string
  new_password: string
}

export interface CaptchaResponse {
  key: string
  image: string
}

export const authApi = {
  login: (data: LoginRequest) =>
    post<ApiResponse<LoginResponse>>('/api/v1/auth/login', data),

  logout: (refreshToken?: string) =>
    post<ApiResponse>('/api/v1/auth/logout', { refresh_token: refreshToken }),

  refresh: (refreshToken: string) =>
    post<ApiResponse<{ access_token: string; refresh_token: string }>>(
      '/api/v1/auth/refresh',
      { refresh_token: refreshToken },
    ),

  me: () => get<ApiResponse<UserInfo>>('/api/v1/auth/me'),

  myPermissions: () => get<ApiResponse<UserPermissions>>('/api/v1/my/permissions'),

  // 修改当前用户密码
  updatePassword: (data: PasswordUpdate) =>
    put<ApiResponse>('/api/v1/auth/me/password', data),

  // 获取验证码
  getCaptcha: () => get<ApiResponse<CaptchaResponse>>('/api/v1/auth/captcha'),
}
