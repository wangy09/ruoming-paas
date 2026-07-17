import { get, post, put, del } from '@/utils/request'
import type { ApiResponse, PageData, TenantInfo } from '@/types'

export interface TenantApproveRequest {
  status: number
  remark?: string
}

export interface TenantQuotaUpdate {
  max_users?: number
  max_storage_gb?: number
  max_api_calls_day?: number
  max_ai_tokens_day?: number
  max_concurrent?: number
}

export const tenantApi = {
  list: (params?: { page?: number; page_size?: number; status?: number; keyword?: string; plan?: string }) =>
    get<ApiResponse<PageData<TenantInfo>>>('/api/v1/tenants', params),

  get: (id: number) =>
    get<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}`),

  create: (data: { name: string; code: string; plan?: string; contact_email?: string; contact_phone?: string; remark?: string; admin_username: string; admin_password: string; admin_email?: string }) =>
    post<ApiResponse<TenantInfo>>('/api/v1/tenants', data),

  update: (id: number, data: Partial<TenantInfo>) =>
    put<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}`, data),

  updateQuota: (id: number, data: TenantQuotaUpdate) =>
    put<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}/quota`, data),

  approve: (id: number, data: TenantApproveRequest) =>
    post<ApiResponse<TenantInfo>>(`/api/v1/tenants/${id}/approve`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/tenants/${id}`),

  usage: (id: number) =>
    get<ApiResponse<{ api_calls: number; ai_tokens: number; storage_bytes: number }>>(
      `/api/v1/tenants/${id}/usage`,
    ),
}
