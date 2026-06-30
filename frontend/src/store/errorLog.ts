/**
 * 接口错误日志 Store
 * 记录所有接口报错，支持在前端页面查看和清空
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ErrorLogItem {
  id: string
  time: string
  /** HTTP 状态码，业务错误时为 200 */
  status: number
  /** 业务错误码（后端 code 字段） */
  code?: number
  method: string
  url: string
  message: string
  /** 后端返回的 trace_id，用于服务端日志联查 */
  traceId?: string
  /** 响应数据快照（截断） */
  responseSnippet?: string
}

const MAX_LOGS = 200

export const useErrorLogStore = defineStore('errorLog', () => {
  const logs = ref<ErrorLogItem[]>([])

  const unreadCount = ref(0)

  const hasErrors = computed(() => logs.value.length > 0)

  function addLog(item: Omit<ErrorLogItem, 'id' | 'time'>) {
    const log: ErrorLogItem = {
      ...item,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      time: new Date().toLocaleString('zh-CN', { hour12: false }),
    }
    logs.value.unshift(log)
    // 超出上限时丢弃最老的
    if (logs.value.length > MAX_LOGS) {
      logs.value = logs.value.slice(0, MAX_LOGS)
    }
    unreadCount.value += 1
  }

  function clearLogs() {
    logs.value = []
    unreadCount.value = 0
  }

  function markRead() {
    unreadCount.value = 0
  }

  return { logs, unreadCount, hasErrors, addLog, clearLogs, markRead }
})
