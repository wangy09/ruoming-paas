import { get } from '@/utils/request'
import type { ApiResponse } from '@/types'

export interface DashboardStats {
  total_users: number
  active_tenants: number
  today_calls: number
  today_tokens: number
}

export const dashboardApi = {
  stats: () => get<ApiResponse<DashboardStats>>('/api/v1/dashboard/stats'),
}
