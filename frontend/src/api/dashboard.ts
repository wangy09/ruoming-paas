import { del, get, put } from '@/utils/request'
import type { ApiResponse } from '@/types'

export interface DashboardStats {
  total_users: number
  active_tenants: number
  today_calls: number
  today_tokens: number
}

export type DashboardTemplateType = 'auto' | 'platform' | 'tenant' | 'developer' | 'personal'

export interface DashboardQuickEntry {
  title: string
  path: string
  icon?: string | null
  color?: string | null
  desc?: string | null
}

export interface DashboardPreferences {
  template_type: DashboardTemplateType
  widgets: Record<string, boolean>
  quick_entries: DashboardQuickEntry[]
}

export interface DashboardPreferencesResult {
  preferences: DashboardPreferences
  source: 'user' | 'default'
}

export const dashboardApi = {
  stats: () => get<ApiResponse<DashboardStats>>('/api/v1/dashboard/stats'),

  preferences: () =>
    get<ApiResponse<DashboardPreferencesResult>>('/api/v1/dashboard/preferences'),

  updatePreferences: (data: DashboardPreferences) =>
    put<ApiResponse<DashboardPreferencesResult>>('/api/v1/dashboard/preferences', data),

  resetPreferences: () =>
    del<ApiResponse<DashboardPreferencesResult>>('/api/v1/dashboard/preferences'),
}
