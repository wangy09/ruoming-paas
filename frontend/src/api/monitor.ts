import request from '@/utils/request'

// ── 服务监控 ──────────────────────────────────────────────────

export const monitorApi = {
  /** 系统基础信息（一次性） */
  serverInfo: () => request.get('/api/v1/monitor/server/info'),

  /** 实时性能指标（CPU / 内存 / 磁盘） */
  serverMetrics: () => request.get('/api/v1/monitor/server/metrics'),

  /** 网络流量统计 */
  serverNetwork: (iface?: string) =>
    request.get('/api/v1/monitor/server/network', { params: iface ? { iface } : {} }),
}

// ── 计划任务 ──────────────────────────────────────────────────

export const taskApi = {
  /** 获取可用 Celery Task 下拉列表 */
  getFunctions: () => request.get('/api/v1/monitor/tasks/functions'),

  /** 任务列表 */
  list: (params: { page?: number; page_size?: number; name?: string; func_name?: string; status?: number }) =>
    request.get('/api/v1/monitor/tasks', { params }),

  /** 创建任务 */
  create: (data: Record<string, unknown>) => request.post('/api/v1/monitor/tasks', data),

  /** 编辑任务 */
  update: (id: number, data: Record<string, unknown>) => request.put(`/api/v1/monitor/tasks/${id}`, data),

  /** 删除任务 */
  remove: (id: number) => request.delete(`/api/v1/monitor/tasks/${id}`),

  /** 启用任务 */
  enable: (id: number) => request.post(`/api/v1/monitor/tasks/${id}/enable`),

  /** 停用任务 */
  disable: (id: number) => request.post(`/api/v1/monitor/tasks/${id}/disable`),

  /** 立即执行 */
  runNow: (id: number) => request.post(`/api/v1/monitor/tasks/${id}/run`),

  /** 某任务执行日志 */
  logs: (taskId: number, params: { page?: number; page_size?: number; status?: string }) =>
    request.get(`/api/v1/monitor/tasks/${taskId}/logs`, { params }),

  /** 所有任务执行日志 */
  allLogs: (params: { page?: number; page_size?: number; status?: string }) =>
    request.get('/api/v1/monitor/tasks/logs/all', { params }),

  /** 清空日志 */
  clearLogs: (params: { task_id?: number; before_date?: string }) =>
    request.delete('/api/v1/monitor/tasks/logs', { params }),
}
