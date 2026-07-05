import { get, post, put, del } from '@/utils/request'
import type {
  ApiResponse,
  ContactSyncRequest,
  ContactSyncResult,
  PageData,
  UserCreate,
  UserListItem,
  UserUpdate,
} from '@/types'

export const userApi = {
  list: (params: {
    page?: number
    page_size?: number
    keyword?: string
    is_active?: boolean
  }) => get<ApiResponse<PageData<UserListItem>>>('/api/v1/users', params),

  get: (id: number) =>
    get<ApiResponse<UserListItem>>(`/api/v1/users/${id}`),

  create: (data: UserCreate) =>
    post<ApiResponse<UserListItem>>('/api/v1/users', data),

  syncContacts: (data: ContactSyncRequest) =>
    post<ApiResponse<ContactSyncResult>>('/api/v1/users/sync', data),

  update: (id: number, data: UserUpdate) =>
    put<ApiResponse<UserListItem>>(`/api/v1/users/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/users/${id}`),

  resetPassword: (id: number, newPassword: string) =>
    post<ApiResponse>(`/api/v1/users/${id}/reset-password`, { new_password: newPassword }),

  assignRoles: (id: number, roleIds: number[]) =>
    post<ApiResponse>(`/api/v1/users/${id}/roles`, { role_ids: roleIds }),
}
