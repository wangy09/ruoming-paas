/**
 * Dashboard 偏好设置 Composable
 * 管理首页模板、组件显示、常用入口等用户偏好
 */
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { formatDate } from '@/utils/format'
import { dashboardApi } from '@/api/dashboard'
import type { DashboardPreferences, DashboardQuickEntry, DashboardTemplateType } from '@/api/dashboard'
import type { MenuPermission, NoticeInfo } from '@/types'

const authStore = useAuthStore()
const permissionStore = usePermissionStore()

export type DashboardType = 'platform' | 'tenant' | 'developer' | 'personal'
export type DashboardWidgetKey = 'stats' | 'quick_entries' | 'todos' | 'messages' | 'notices' | 'workbench'

export interface DashboardProfile {
  type: DashboardType
  label: string
  title: string
  description: string
  color: string
}

export interface QuickEntry {
  title: string
  desc: string
  path: string
  icon: string
  color: string
  menu?: string
  profiles?: DashboardType[]
}

export interface MenuOption {
  title: string
  path: string
  icon: string
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

export interface TodoItem {
  title: string
  desc: string
  value: string
  type: TagType
  color: string
  path: string
}

const defaultWidgets: Record<DashboardWidgetKey, boolean> = {
  stats: true,
  quick_entries: true,
  todos: true,
  messages: true,
  notices: true,
  workbench: true,
}

const quickEntryColors = ['#1677ff', '#722ed1', '#13c2c2', '#faad14', '#ff4d4f', '#52c41a']

export function useDashboardPreference() {
  const preferenceDialogVisible = ref(false)
  const preferenceSaving = ref(false)
  const preferenceSource = ref<'user' | 'default'>('default')

  const preferenceForm = reactive<DashboardPreferences>({
    template_type: 'auto',
    widgets: { ...defaultWidgets },
    quick_entries: [],
  })

  const templateOptions: Array<{ label: string; value: DashboardTemplateType }> = [
    { label: '自动', value: 'auto' },
    { label: '平台', value: 'platform' },
    { label: '租户', value: 'tenant' },
    { label: '开发者', value: 'developer' },
    { label: '个人', value: 'personal' },
  ]

  const widgetOptions: Array<{ key: DashboardWidgetKey; label: string; desc: string }> = [
    { key: 'stats', label: '统计指标', desc: '用户、租户、AI 调用等核心指标' },
    { key: 'quick_entries', label: '常用入口', desc: '按权限展示快捷入口' },
    { key: 'todos', label: '今日关注', desc: '未读消息、配置和文件归档提醒' },
    { key: 'messages', label: '我的消息', desc: '最近收到的站内消息' },
    { key: 'notices', label: '平台公告', desc: '最新公告列表' },
    { key: 'workbench', label: '资源概览', desc: '开发、运维或个人资源统计' },
  ]

  const greeting = computed(() => {
    const h = new Date().getHours()
    if (h < 6) return '凌晨好'
    if (h < 12) return '上午好'
    if (h < 18) return '下午好'
    return '晚上好'
  })

  const displayName = computed(() => authStore.userInfo?.nickname || authStore.userInfo?.username || '用户')
  const avatarText = computed(() => displayName.value.charAt(0).toUpperCase())
  const roleLabels = computed(() => (authStore.userInfo?.roles || []).map(role => role.name).slice(0, 3))
  const roleCodes = computed(() => (authStore.userInfo?.roles || []).map(role => role.code.toLowerCase()))

  const roleDashboardType = computed<DashboardType | null>(() => {
    const matched = (authStore.userInfo?.roles || [])
      .map(role => role.dashboard_template)
      .find((template): template is DashboardType =>
        template === 'platform' || template === 'tenant' || template === 'developer' || template === 'personal',
      )
    return matched || null
  })

  const tenantLabel = computed(() => {
    if (authStore.userInfo?.is_superplatform) return '平台级'
    return authStore.userInfo?.tenant_code ? `租户：${authStore.userInfo.tenant_code}` : '当前租户'
  })

  const inferredDashboardType = computed<DashboardType>(() => {
    if (roleDashboardType.value) {
      return roleDashboardType.value
    }
    if (authStore.userInfo?.is_superplatform) {
      return 'platform'
    }
    if (roleCodes.value.some(code => /developer|dev|code|ai|agent/.test(code))) {
      return 'developer'
    }
    if (roleCodes.value.some(code => /admin|manager|tenant/.test(code))) {
      return 'tenant'
    }
    return 'personal'
  })

  const resolvedDashboardType = computed<DashboardType>(() => {
    return preferenceForm.template_type === 'auto' ? inferredDashboardType.value : preferenceForm.template_type
  })

  const dashboardProfile = computed<DashboardProfile>(() => {
    if (resolvedDashboardType.value === 'platform') {
      return {
        type: 'platform',
        label: '平台管理员首页',
        title: '平台运营总览',
        description: '聚合用户服务、消息公告、AI 能力和常用入口，帮助快速了解平台使用情况与待处理事项。',
        color: '#1677ff',
      }
    }
    if (resolvedDashboardType.value === 'developer') {
      return {
        type: 'developer',
        label: '开发者首页',
        title: '开发工作台',
        description: '聚合 Agent、知识库、代码生成、文件和配置入口，服务日常开发与调试。',
        color: '#722ed1',
      }
    }
    if (resolvedDashboardType.value === 'tenant') {
      return {
        type: 'tenant',
        label: '租户管理员首页',
        title: '租户管理工作台',
        description: '关注本租户用户、权限、消息、文件和 AI 资源使用情况。',
        color: '#13c2c2',
      }
    }
    return {
      type: 'personal',
      label: '个人首页',
      title: '个人效率工作台',
      description: '集中查看消息、公告、常用功能和个人可访问的业务入口。',
      color: '#2f7d70',
    }
  })

  function canVisit(path: string) {
    return authStore.userInfo?.is_superplatform || permissionStore.hasMenu(path)
  }

  function isWidgetVisible(key: DashboardWidgetKey) {
    return preferenceForm.widgets[key] !== false
  }

  function normalizePreferences(preferences?: Partial<DashboardPreferences>): DashboardPreferences {
    return {
      template_type: preferences?.template_type || 'auto',
      widgets: {
        ...defaultWidgets,
        ...(preferences?.widgets || {}),
      },
      quick_entries: normalizeQuickEntries(preferences?.quick_entries || []),
    }
  }

  function applyPreferences(preferences: DashboardPreferences, source: 'user' | 'default') {
    const normalized = normalizePreferences(preferences)
    preferenceForm.template_type = normalized.template_type
    preferenceForm.widgets = normalized.widgets
    preferenceForm.quick_entries = normalized.quick_entries
    preferenceSource.value = source
  }

  function flattenMenuOptions(menus: MenuPermission[] = []): MenuOption[] {
    const result: MenuOption[] = []
    const seen = new Set<string>()

    const walk = (items: MenuPermission[]) => {
      for (const menu of items) {
        if (menu.path && menu.path !== '/' && !menu.isExternal && !seen.has(menu.path) && canVisit(menu.path)) {
          seen.add(menu.path)
          result.push({
            title: menu.title,
            path: menu.path,
            icon: menu.icon || 'Menu',
          })
        }
        if (menu.children?.length) {
          walk(menu.children)
        }
      }
    }

    walk(menus)
    return result
  }

  function createQuickEntryFromMenu(path: string, index: number): DashboardQuickEntry | null {
    const option = availableMenuOptions.value.find(item => item.path === path)
    if (!option) return null
    return {
      title: option.title,
      path: option.path,
      icon: option.icon,
      color: quickEntryColors[index % quickEntryColors.length],
      desc: '我的常用入口',
    }
  }

  function normalizeQuickEntries(entries: DashboardQuickEntry[]): DashboardQuickEntry[] {
    const seen = new Set<string>()
    const result: DashboardQuickEntry[] = []
    for (const entry of entries) {
      if (!entry?.path || seen.has(entry.path)) continue
      seen.add(entry.path)
      const index = result.length
      const option = availableMenuOptions.value.find(item => item.path === entry.path)
      result.push({
        title: entry.title || option?.title || entry.path,
        path: entry.path,
        icon: entry.icon || option?.icon || 'Menu',
        color: entry.color || quickEntryColors[index % quickEntryColors.length],
        desc: entry.desc || '我的常用入口',
      })
      if (result.length >= 12) break
    }
    return result
  }

  function normalizeQuickEntry(entry: DashboardQuickEntry, index: number): QuickEntry {
    return {
      title: entry.title,
      desc: entry.desc || '我的常用入口',
      path: entry.path,
      icon: entry.icon || 'Menu',
      color: entry.color || quickEntryColors[index % quickEntryColors.length],
    }
  }

  const availableMenuOptions = computed<MenuOption[]>(() => flattenMenuOptions(permissionStore.menuTree))

  const selectedQuickEntryPaths = computed<string[]>({
    get: () => preferenceForm.quick_entries.map(item => item.path),
    set: paths => {
      const oldMap = new Map(preferenceForm.quick_entries.map(item => [item.path, item]))
      preferenceForm.quick_entries = paths
        .map((path, index) => oldMap.get(path) || createQuickEntryFromMenu(path, index))
        .filter((item): item is DashboardQuickEntry => Boolean(item))
        .slice(0, 12)
    },
  })

  const customQuickEntries = computed<QuickEntry[]>(() => {
    return preferenceForm.quick_entries
      .map((entry, index) => normalizeQuickEntry(entry, index))
      .filter(entry => canVisit(entry.path))
  })

  const quickEntries: QuickEntry[] = [
    { title: '用户管理', desc: '维护账号、角色和状态', path: '/system/users', icon: 'User', color: '#1677ff', menu: '/system/users', profiles: ['platform', 'tenant'] },
    { title: '角色授权', desc: '配置菜单、按钮和数据范围', path: '/system/role-permission', icon: 'Lock', color: '#722ed1', menu: '/system/role-permission', profiles: ['platform', 'tenant'] },
    { title: '配置中心', desc: '管理运行时业务配置', path: '/system/config', icon: 'Setting', color: '#13c2c2', menu: '/system/config', profiles: ['platform', 'tenant', 'developer'] },
    { title: '消息中心', desc: '公告与站内消息', path: '/message/inbox', icon: 'Message', color: '#faad14', menu: '/message/inbox' },
    { title: 'Agent 管理', desc: '创建和维护智能体', path: '/ai/agents', icon: 'Cpu', color: '#ff4d4f', menu: '/ai/agents', profiles: ['platform', 'tenant', 'developer'] },
    { title: '知识库', desc: '管理文档和向量索引', path: '/ai/knowledge', icon: 'Collection', color: '#52c41a', menu: '/ai/knowledge', profiles: ['developer'] },
    { title: '代码生成器', desc: '生成基础业务模块', path: '/dev/codegen', icon: 'DocumentAdd', color: '#1677ff', menu: '/dev/codegen', profiles: ['developer'] },
    { title: '文件中心', desc: '上传、预览、归档附件', path: '/system/files', icon: 'Folder', color: '#13c2c2', menu: '/system/files' },
    { title: '计划任务', desc: '查看任务和执行日志', path: '/monitor/task', icon: 'Timer', color: '#722ed1', menu: '/monitor/task', profiles: ['platform', 'developer'] },
    { title: '服务监控', desc: '查看服务资源状态', path: '/monitor/server', icon: 'Monitor', color: '#52c41a', menu: '/monitor/server', profiles: ['platform'] },
  ]

  const availableQuickEntries = computed(() => {
    const profile = dashboardProfile.value.type
    const recommended = quickEntries
      .filter(item => !item.profiles || item.profiles.includes(profile))
      .filter(item => canVisit(item.menu || item.path))
    const merged = [...customQuickEntries.value, ...recommended]
    const seen = new Set<string>()
    return merged
      .filter(item => {
        if (seen.has(item.path)) return false
        seen.add(item.path)
        return true
      })
      .slice(0, 8)
  })

  function moveQuickEntry(index: number, delta: number) {
    const targetIndex = index + delta
    if (targetIndex < 0 || targetIndex >= preferenceForm.quick_entries.length) return
    const next = [...preferenceForm.quick_entries]
    const [item] = next.splice(index, 1)
    next.splice(targetIndex, 0, item)
    preferenceForm.quick_entries = next
  }

  function removeQuickEntry(index: number) {
    preferenceForm.quick_entries = preferenceForm.quick_entries.filter((_, i) => i !== index)
  }

  async function loadPreferences() {
    try {
      const { data } = await dashboardApi.preferences()
      applyPreferences(data.preferences, data.source)
    } catch {
      applyPreferences(normalizePreferences(), 'default')
    }
  }

  function openPreferenceDialog() {
    preferenceDialogVisible.value = true
  }

  async function savePreferences() {
    preferenceSaving.value = true
    try {
      const { data } = await dashboardApi.updatePreferences(normalizePreferences(preferenceForm))
      applyPreferences(data.preferences, data.source)
      preferenceDialogVisible.value = false
      ElMessage.success('首页偏好已保存')
    } finally {
      preferenceSaving.value = false
    }
  }

  async function resetPreferences() {
    preferenceSaving.value = true
    try {
      const { data } = await dashboardApi.resetPreferences()
      applyPreferences(data.preferences, data.source)
      ElMessage.success('已恢复默认首页')
    } finally {
      preferenceSaving.value = false
    }
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

  function formatDateTime(value?: string | null): string {
    if (!value) return '-'
    return formatDate(new Date(value))
  }

  function noticeTargetLabel(type: NoticeInfo['target_type']) {
    const map: Record<NoticeInfo['target_type'], string> = {
      all: '全平台',
      dept: '部门',
      user: '用户',
    }
    return map[type] || '公告'
  }

  return {
    // 状态
    preferenceDialogVisible,
    preferenceSaving,
    preferenceSource,
    preferenceForm,
    templateOptions,
    widgetOptions,

    // 计算属性
    greeting,
    displayName,
    avatarText,
    roleLabels,
    tenantLabel,
    dashboardProfile,
    availableMenuOptions,
    selectedQuickEntryPaths,
    availableQuickEntries,

    // 方法
    canVisit,
    isWidgetVisible,
    moveQuickEntry,
    removeQuickEntry,
    loadPreferences,
    openPreferenceDialog,
    savePreferences,
    resetPreferences,
    normalizePreferences,
    applyPreferences,
    formatNumber,
    formatToken,
    formatDateTime,
    noticeTargetLabel,
  }
}
