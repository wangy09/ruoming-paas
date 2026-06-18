import { get, post, put, del } from '@/utils/request'
import type { ApiResponse, PageData, RoleInfo, RoleCreate, PermissionItem } from '@/types'

export const permissionApi = {
  // 角色
  roleList: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    get<ApiResponse<PageData<RoleInfo>>>('/api/v1/roles', params),

  roleCreate: (data: RoleCreate) =>
    post<ApiResponse<RoleInfo>>('/api/v1/roles', data),

  roleUpdate: (id: number, data: Partial<RoleCreate>) =>
    put<ApiResponse<RoleInfo>>(`/api/v1/roles/${id}`, data),

  roleDelete: (id: number) =>
    del<ApiResponse>(`/api/v1/roles/${id}`),

  assignPermissions: (roleId: number, permissionIds: number[]) =>
    post<ApiResponse>(`/api/v1/roles/${roleId}/permissions`, { permission_ids: permissionIds }),

  // 权限
  permissionTree: () =>
    get<ApiResponse<PermissionItem[]>>('/api/v1/permissions/tree'),

  permissionCreate: (data: Partial<PermissionItem>) =>
    post<ApiResponse<PermissionItem>>('/api/v1/permissions', data),

  permissionDelete: (id: number) =>
    del<ApiResponse>(`/api/v1/permissions/${id}`),
}
