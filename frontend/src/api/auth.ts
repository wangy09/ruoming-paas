import { post, get } from '@/utils/request'
import type { ApiResponse, LoginRequest, LoginResponse, UserInfo, UserPermissions } from '@/types'

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
}
