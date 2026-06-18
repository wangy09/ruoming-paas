import { get, post, put } from '@/utils/request'
import type { ApiResponse, PageData, TenantInfo } from '@/types'

export const tenantApi = {
  list: (params?: { page?: number; page_size?: number; status?: string; keyword?: string }) =>
    get<ApiResponse<PageData<TenantInfo>>>('/api/v1/tenants', params),

  get: (id: number) =>
    get<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}`),

  create: (data: Partial<TenantInfo>) =>
    post<ApiResponse<TenantInfo>>('/api/v1/tenants', data),

  update: (id: number, data: Partial<TenantInfo>) =>
    put<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}`, data),

  approve: (id: number) =>
    post<ApiResponse>(`/api/v1/tenants/${id}/approve`),

  disable: (id: number, reason?: string) =>
    post<ApiResponse>(`/api/v1/tenants/${id}/disable`, { reason }),

  usage: (id: number) =>
    get<ApiResponse<{ api_calls: number; ai_tokens: number; storage_mb: number }>>(
      `/api/v1/tenants/${id}/usage`,
    ),
}
