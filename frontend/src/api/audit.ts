import { del, get } from '@/utils/request'
import type { ApiResponse, PageData, LoginLog, AuditLog } from '@/types'

export const auditApi = {
  /**
   * 获取登录日志列表
   * @param params 查询参数
   */
  loginLogs: (params: {
    page?: number
    page_size?: number
    username?: string
    status?: number
  }) => get<ApiResponse<PageData<LoginLog>>>('/api/v1/audit/login-logs', params),

  /**
   * 获取操作日志列表
   * @param params 查询参数
   */
  logs: (params: {
    page?: number
    page_size?: number
    username?: string
    action?: string
    resource_type?: string
    status?: number
    start_time?: string
    end_time?: string
  }) => get<ApiResponse<PageData<AuditLog>>>('/api/v1/audit/logs', params),

  /**
   * 清除操作日志
   * @param params 清除参数
   */
  clearLogs: (params: {
    start_time?: string
    end_time?: string
  }) => del<ApiResponse<{ deleted_count: number }>>('/api/v1/audit/logs', { params }),
}