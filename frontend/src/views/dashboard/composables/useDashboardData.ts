/**
 * Dashboard 数据 Composable
 * 管理统计数据、消息、公告、工作台数据的加载
 */
import { computed, ref } from 'vue'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { dashboardApi } from '@/api/dashboard'
import { messageApi } from '@/api/message'
import { agentApi, kbApi, modelApi } from '@/api/ai'
import { fileApi } from '@/api/file'
import { taskApi } from '@/api/monitor'
import type { AgentInfo, FileInfo, MessageInfo, NoticeInfo } from '@/types'
import type { DashboardType } from './useDashboardPreference'

const authStore = useAuthStore()
const permissionStore = usePermissionStore()

export function useDashboardData() {
  const statsLoading = ref(true)
  const unreadCount = ref(0)
  const messages = ref<MessageInfo[]>([])
  const notices = ref<NoticeInfo[]>([])
  const agentTotal = ref(0)
  const modelTotal = ref(0)
  const kbTotal = ref(0)
  const fileTotal = ref(0)
  const taskTotal = ref(0)
  const recentAgents = ref<AgentInfo[]>([])
  const recentFiles = ref<FileInfo[]>([])

  const baseStats = ref([
    { key: 'users', label: '总用户数', value: '-', icon: 'User', color: '#1677ff', profiles: ['platform', 'tenant'] },
    { key: 'tenants', label: '活跃租户', value: '-', icon: 'OfficeBuilding', color: '#52c41a', profiles: ['platform'] },
    { key: 'calls', label: '今日 AI 调用', value: '-', icon: 'MagicStick', color: '#faad14', profiles: ['platform', 'tenant', 'developer'] },
    { key: 'tokens', label: '今日 Token 消耗', value: '-', icon: 'Coin', color: '#ff4d4f', profiles: ['platform', 'tenant', 'developer'] },
    { key: 'messages', label: '未读消息', value: '0', icon: 'Message', color: '#13c2c2', profiles: ['personal', 'tenant', 'developer'] },
    { key: 'agents', label: 'Agent 数量', value: '0', icon: 'Cpu', color: '#722ed1', profiles: ['developer'] },
  ])

  function canVisit(path: string) {
    return authStore.userInfo?.is_superplatform || permissionStore.hasMenu(path)
  }

  function formatNumber(count: number): string {
    return String(count || 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  }

  function formatToken(count: number): string {
    if (count >= 1000000) {
      return (count / 1000000).toFixed(1) + 'M'
    }
    if (count >= 1000) {
      return (count / 1000).toFixed(1) + 'K'
    }
    return String(count)
  }

  function updateStat(key: string, value: string) {
    const target = baseStats.value.find(item => item.key === key)
    if (target) target.value = value
  }

  function getFulfilled<T>(result: PromiseSettledResult<T>): T | null {
    return result.status === 'fulfilled' ? result.value : null
  }

  const visibleStats = computed(() => {
    return baseStats.value.filter(item => {
      if (!item.profiles?.length) return true
      // 显示所有统计项，不按 profile 过滤（由外部组件控制）
      return true
    }).slice(0, 4)
  })

  async function loadStats() {
    statsLoading.value = true
    try {
      const { data } = await dashboardApi.stats()
      updateStat('users', formatNumber(data.total_users || 0))
      updateStat('tenants', formatNumber(data.active_tenants || 0))
      updateStat('calls', formatNumber(data.today_calls || 0))
      updateStat('tokens', formatToken(data.today_tokens || 0))
    } catch {
      updateStat('users', '0')
      updateStat('tenants', '0')
      updateStat('calls', '0')
      updateStat('tokens', '0')
    } finally {
      statsLoading.value = false
    }
  }

  async function loadWorkbenchData() {
    const results = await Promise.allSettled([
      messageApi.unreadSummary(),
      messageApi.inboxList({ page: 1, page_size: 4 }),
      messageApi.noticeList({ page: 1, page_size: 4, status: 1 }),
      canVisit('/ai/agents') ? agentApi.list({ page: 1, page_size: 4 }) : Promise.resolve(null),
      canVisit('/ai/models') ? modelApi.list({ page: 1, page_size: 1 }) : Promise.resolve(null),
      canVisit('/ai/knowledge') ? kbApi.list({ page: 1, page_size: 1 }) : Promise.resolve(null),
      canVisit('/system/files') ? fileApi.list({ page: 1, page_size: 4 }) : Promise.resolve(null),
      canVisit('/monitor/task') ? taskApi.list({ page: 1, page_size: 1 }) : Promise.resolve(null),
    ])

    const unreadRes = getFulfilled(results[0])
    unreadCount.value = unreadRes?.data?.unread_count || 0
    updateStat('messages', formatNumber(unreadCount.value))

    const inboxRes = getFulfilled(results[1])
    messages.value = inboxRes?.data?.items || []

    const noticeRes = getFulfilled(results[2])
    notices.value = noticeRes?.data?.items || []

    const agentRes = getFulfilled(results[3])
    agentTotal.value = agentRes?.data?.total || 0
    recentAgents.value = agentRes?.data?.items || []
    updateStat('agents', formatNumber(agentTotal.value))

    const modelRes = getFulfilled(results[4])
    modelTotal.value = modelRes?.data?.total || 0

    const kbRes = getFulfilled(results[5])
    kbTotal.value = kbRes?.data?.total || 0

    const fileRes = getFulfilled(results[6])
    fileTotal.value = fileRes?.data?.total || 0
    recentFiles.value = fileRes?.data?.items || []

    const taskRes = getFulfilled(results[7])
    taskTotal.value = taskRes?.data?.total || 0
  }

  async function refreshDashboard() {
    await Promise.all([loadStats(), loadWorkbenchData()])
  }

  function getTodos(profileType: DashboardType) {
    return [
      {
        title: '未读消息',
        desc: unreadCount.value ? '有新消息需要查看' : '暂无新的站内消息',
        value: String(unreadCount.value),
        type: unreadCount.value ? 'danger' as const : 'info' as const,
        color: '#ff4d4f',
        path: '/message/inbox',
      },
      {
        title: profileType === 'developer' ? 'Agent 配置' : '基础配置',
        desc: profileType === 'developer' ? '检查模型和 Agent 是否可用' : '维护系统运行时配置',
        value: profileType === 'developer' ? String(agentTotal.value) : '配置',
        type: 'primary' as const,
        color: '#1677ff',
        path: profileType === 'developer' ? '/ai/agents' : '/system/config',
      },
      {
        title: '文件归档',
        desc: '查看最近上传和归档状态',
        value: String(fileTotal.value),
        type: 'success' as const,
        color: '#52c41a',
        path: '/system/files',
      },
    ]
  }

  function getWorkbenchTitle(profileType: DashboardType) {
    if (profileType === 'developer') return '开发资源'
    if (profileType === 'platform') return '平台运维'
    if (profileType === 'tenant') return '租户资源'
    return '个人概览'
  }

  function getWorkbenchSubtitle(profileType: DashboardType) {
    if (profileType === 'developer') return 'Agent、模型、知识库状态'
    if (profileType === 'platform') return '任务、文件、消息概况'
    return '当前账号可用资源'
  }

  function getWorkbenchItems(profileType: DashboardType) {
    if (profileType === 'developer') {
      return [
        { label: 'Agent', value: formatNumber(agentTotal.value) },
        { label: '模型配置', value: formatNumber(modelTotal.value) },
        { label: '知识库', value: formatNumber(kbTotal.value) },
        { label: '最近 Agent', value: recentAgents.value[0]?.name || '暂无' },
      ]
    }
    return [
      { label: '文件数量', value: formatNumber(fileTotal.value) },
      { label: '计划任务', value: formatNumber(taskTotal.value) },
      { label: '未读消息', value: formatNumber(unreadCount.value) },
      { label: '最近文件', value: recentFiles.value[0]?.original_name || '暂无' },
    ]
  }

  function getWorkbenchActions(profileType: DashboardType) {
    if (profileType === 'developer') {
      return [
        { label: 'Agent 管理', path: '/ai/agents' },
        { label: '模型管理', path: '/ai/models' },
        { label: '知识库', path: '/ai/knowledge' },
      ].filter(item => canVisit(item.path))
    }
    return [
      { label: '消息中心', path: '/message/inbox' },
      { label: '文件中心', path: '/system/files' },
      { label: '配置中心', path: '/system/config' },
    ].filter(item => canVisit(item.path))
  }

  return {
    // 状态
    statsLoading,
    unreadCount,
    messages,
    notices,
    agentTotal,
    modelTotal,
    kbTotal,
    fileTotal,
    taskTotal,
    recentAgents,
    recentFiles,
    baseStats,

    // 计算属性
    visibleStats,

    // 方法
    loadStats,
    loadWorkbenchData,
    refreshDashboard,
    getTodos,
    getWorkbenchTitle,
    getWorkbenchSubtitle,
    getWorkbenchItems,
    getWorkbenchActions,
    formatNumber,
    formatToken,
  }
}
