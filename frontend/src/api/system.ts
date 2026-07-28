import { get, post, put, del } from '@/utils/request'
import type { ApiResponse, PageData } from '@/types'

export interface DeptInfo {
  id: number
  parent_id: number
  name: string
  ancestors: string | null
  level: number
  sort: number
  leader: string | null
  phone: string | null
  email: string | null
  status: number
  tenant_id: number | null
  children?: DeptInfo[]
  remark: string | null
}

export interface DeptCreate {
  parent_id?: number
  name: string
  sort?: number
  leader?: string
  phone?: string
  email?: string
  status?: number
  remark?: string
}

export interface DemoModeInfo {
  demo_mode: boolean
}

export const systemApi = {
  // 演示模式
  demoMode: () =>
    get<ApiResponse<DemoModeInfo>>('/api/v1/system/demo-mode'),

  // 部门管理
  deptTree: () =>
    get<ApiResponse<DeptInfo[]>>('/api/v1/depts/tree'),

  deptOptions: () =>
    get<ApiResponse<DeptInfo[]>>('/api/v1/depts/options'),

  deptDetail: (id: number) =>
    get<ApiResponse<DeptInfo>>(`/api/v1/depts/${id}`),

  deptCreate: (data: DeptCreate) =>
    post<ApiResponse<DeptInfo>>('/api/v1/depts', data),

  deptUpdate: (id: number, data: Partial<DeptCreate>) =>
    put<ApiResponse<DeptInfo>>(`/api/v1/depts/${id}`, data),

  deptDelete: (id: number) =>
    del<ApiResponse>(`/api/v1/depts/${id}`),
}
