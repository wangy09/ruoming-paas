import { del, get, post, put } from '@/utils/request'
import type { ApiResponse, ConfigHistoryInfo, ConfigInfo, ConfigPayload, ConfigScope, PageData } from '@/types'

export const configApi = {
  list: (params: {
    scope?: ConfigScope
    app_key?: string
    category?: string
    keyword?: string
    is_public?: boolean
    is_encrypted?: boolean
    status?: 0 | 1 | number
  }) => get<ApiResponse<ConfigInfo[] | PageData<ConfigInfo>>>('/api/v1/config-center', params),

  create: (data: ConfigPayload) =>
    post<ApiResponse<ConfigInfo>>('/api/v1/config-center', data),

  update: (id: number, data: Partial<ConfigPayload>) =>
    put<ApiResponse<ConfigInfo>>(`/api/v1/config-center/${id}`, data),

  remove: (id: number) =>
    del<ApiResponse>(`/api/v1/config-center/${id}`),

  history: (params: {
    config_key?: string
    page?: number
    page_size?: number
  }) => get<ApiResponse<PageData<ConfigHistoryInfo>>>('/api/v1/config-center/history', params),

  publicConfigs: (params: {
    keys?: string[]
    category?: string
    app_key?: string
  }) => {
    const search = new URLSearchParams()
    params.keys?.forEach(key => search.append('keys', key))
    if (params.category) search.set('category', params.category)
    if (params.app_key) search.set('app_key', params.app_key)
    const query = search.toString()
    return get<ApiResponse<Record<string, string> | ConfigInfo[]>>(
      `/api/v1/config-center/public${query ? `?${query}` : ''}`,
    )
  },
}
