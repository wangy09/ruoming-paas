<template>
  <div class="page-container">
    <section class="hero-card" :style="{ '--hero-accent': dashboardProfile.color }">
      <div class="hero-main">
        <el-avatar :size="64" class="hero-avatar">
          {{ avatarText }}
        </el-avatar>
        <div class="hero-copy">
          <div class="hero-kicker">{{ greeting }}，{{ displayName }}</div>
          <h2 class="hero-title">{{ dashboardProfile.title }}</h2>
          <p class="hero-desc">{{ dashboardProfile.description }}</p>
          <div class="hero-tags">
            <el-tag effect="dark" round>{{ dashboardProfile.label }}</el-tag>
            <el-tag v-if="tenantLabel" effect="plain" round>{{ tenantLabel }}</el-tag>
            <el-tag v-for="role in roleLabels" :key="role" effect="plain" round>{{ role }}</el-tag>
          </div>
        </div>
      </div>
      <div class="hero-side">
        <div class="time-card">
          <div class="time-label">当前时间</div>
          <div class="time-value">{{ currentTime }}</div>
        </div>
        <div class="hero-actions">
          <el-button type="primary" plain @click="refreshDashboard">
            刷新首页
          </el-button>
          <el-button plain @click="openPreferenceDialog">
            首页设置
          </el-button>
        </div>
      </div>
    </section>

    <el-row v-if="isWidgetVisible('stats')" :gutter="16" class="section-row">
      <el-col v-for="stat in visibleStats" :key="stat.label" :xs="12" :sm="6">
        <div class="stat-card" :style="{ '--accent': stat.color }">
          <div class="stat-icon">
            <el-icon :size="26">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">
              <span v-if="!statsLoading">{{ stat.value }}</span>
              <el-skeleton-item v-else variant="text" style="width: 64px" />
            </div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row v-if="isWidgetVisible('quick_entries') || isWidgetVisible('todos')" :gutter="16" class="section-row">
      <el-col v-if="isWidgetVisible('quick_entries')" :xs="24" :lg="isWidgetVisible('todos') ? 16 : 24">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">常用入口</span>
              <span class="card-subtitle">我的常用入口优先展示，并按权限过滤</span>
            </div>
            <el-button link type="primary" @click="openPreferenceDialog">管理入口</el-button>
          </div>
          <div class="quick-grid">
            <button
              v-for="entry in availableQuickEntries"
              :key="entry.path"
              class="quick-entry"
              :style="{ '--entry-color': entry.color }"
              @click="router.push(entry.path)"
            >
              <span class="quick-icon">
                <el-icon><component :is="entry.icon" /></el-icon>
              </span>
              <span class="quick-title">{{ entry.title }}</span>
              <span class="quick-desc">{{ entry.desc }}</span>
            </button>
          </div>
          <el-empty v-if="!availableQuickEntries.length" description="暂无可用快捷入口" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('todos')" :xs="24" :lg="isWidgetVisible('quick_entries') ? 8 : 24">
        <div class="page-card todo-card">
          <div class="card-header">
            <div>
              <span class="card-title">今日关注</span>
              <span class="card-subtitle">优先处理消息和基础配置</span>
            </div>
          </div>
          <div class="todo-list">
            <div v-for="todo in todos" :key="todo.title" class="todo-item" @click="router.push(todo.path)">
              <div class="todo-dot" :style="{ backgroundColor: todo.color }" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-desc">{{ todo.desc }}</div>
              </div>
              <el-tag size="small" :type="todo.type">{{ todo.value }}</el-tag>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row
      v-if="isWidgetVisible('messages') || isWidgetVisible('notices') || isWidgetVisible('workbench')"
      :gutter="16"
      class="section-row"
    >
      <el-col v-if="isWidgetVisible('messages')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">我的消息</span>
              <span class="card-subtitle">最近收到的站内消息</span>
            </div>
            <el-button link type="primary" @click="router.push('/message/inbox')">查看全部</el-button>
          </div>
          <div v-if="messages.length" class="list-panel">
            <div v-for="msg in messages" :key="msg.id" class="list-item">
              <div class="list-title">
                <span class="text-ellipsis">{{ msg.title }}</span>
                <el-tag v-if="!msg.is_read" size="small" type="danger">未读</el-tag>
              </div>
              <div class="list-meta">{{ formatDateTime(msg.created_at) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无消息" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('notices')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">平台公告</span>
              <span class="card-subtitle">已发布的最新公告</span>
            </div>
            <el-button link type="primary" @click="router.push('/message/notices')">查看公告</el-button>
          </div>
          <div v-if="notices.length" class="list-panel">
            <div v-for="notice in notices" :key="notice.id" class="list-item">
              <div class="list-title">
                <span class="text-ellipsis">{{ notice.title }}</span>
                <el-tag size="small" effect="plain">{{ noticeTargetLabel(notice.target_type) }}</el-tag>
              </div>
              <div class="list-meta">{{ formatDateTime(notice.published_at || notice.created_at) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无公告" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('workbench')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">{{ workbenchTitle }}</span>
              <span class="card-subtitle">{{ workbenchSubtitle }}</span>
            </div>
          </div>
          <div class="workbench-list">
            <div v-for="item in workbenchItems" :key="item.label" class="workbench-item">
              <span class="workbench-label">{{ item.label }}</span>
              <span class="workbench-value">{{ item.value }}</span>
            </div>
          </div>
          <div class="workbench-footer">
            <el-button
              v-for="action in workbenchActions"
              :key="action.path"
              size="small"
              @click="router.push(action.path)"
            >
              {{ action.label }}
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-dialog
      v-model="preferenceDialogVisible"
      title="首页设置"
      width="720px"
      append-to-body
    >
      <div class="preference-panel">
        <div class="preference-section">
          <div class="preference-title">首页模板</div>
          <div class="preference-tip">
            自动模式会优先使用角色默认首页，再按当前用户身份兜底判断；手动选择后只影响当前账号。
            当前来源：{{ preferenceSource === 'user' ? '个人偏好' : '系统默认' }}
          </div>
          <el-radio-group v-model="preferenceForm.template_type" class="template-radio-group">
            <el-radio-button v-for="item in templateOptions" :key="item.value" :label="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </div>

        <div class="preference-section">
          <div class="preference-title">组件显示</div>
          <div class="widget-options">
            <el-checkbox
              v-for="widget in widgetOptions"
              :key="widget.key"
              v-model="preferenceForm.widgets[widget.key]"
            >
              <span class="widget-label">{{ widget.label }}</span>
              <span class="widget-desc">{{ widget.desc }}</span>
            </el-checkbox>
          </div>
        </div>

        <div class="preference-section">
          <div class="preference-title">我的常用入口</div>
          <div class="preference-tip">
            只能从当前账号有权限访问的菜单中选择，首页会优先展示这些入口。
          </div>
          <el-select
            v-model="selectedQuickEntryPaths"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择要加入首页的菜单"
            class="quick-entry-select"
          >
            <el-option
              v-for="item in availableMenuOptions"
              :key="item.path"
              :label="item.title"
              :value="item.path"
            >
              <span class="menu-option-title">{{ item.title }}</span>
              <span class="menu-option-path">{{ item.path }}</span>
            </el-option>
          </el-select>

          <div v-if="preferenceForm.quick_entries.length" class="quick-entry-config-list">
            <div v-for="(entry, index) in preferenceForm.quick_entries" :key="entry.path" class="quick-entry-config-item">
              <div class="quick-entry-config-main">
                <el-icon><component :is="entry.icon || 'Menu'" /></el-icon>
                <div>
                  <div class="quick-entry-config-title">{{ entry.title }}</div>
                  <div class="quick-entry-config-path">{{ entry.path }}</div>
                </div>
              </div>
              <div class="quick-entry-config-actions">
                <el-button link :disabled="index === 0" @click="moveQuickEntry(index, -1)">上移</el-button>
                <el-button link :disabled="index === preferenceForm.quick_entries.length - 1" @click="moveQuickEntry(index, 1)">下移</el-button>
                <el-button link type="danger" @click="removeQuickEntry(index)">移除</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="还没有自定义常用入口" :image-size="72" />
        </div>
      </div>
      <template #footer>
        <el-button @click="resetPreferences">恢复默认</el-button>
        <el-button @click="preferenceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="preferenceSaving" @click="savePreferences">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { formatDate } from '@/utils/format'
import { dashboardApi } from '@/api/dashboard'
import type { DashboardPreferences, DashboardQuickEntry, DashboardTemplateType } from '@/api/dashboard'
import { messageApi } from '@/api/message'
import { agentApi, kbApi, modelApi } from '@/api/ai'
import { fileApi } from '@/api/file'
import { taskApi } from '@/api/monitor'
import type { AgentInfo, FileInfo, MenuPermission, MessageInfo, NoticeInfo } from '@/types'

const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const router = useRouter()

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
const preferenceDialogVisible = ref(false)
const preferenceSaving = ref(false)
const preferenceSource = ref<'user' | 'default'>('default')

const currentTime = ref(formatDate(new Date()))
let timer: number | undefined

type DashboardType = 'platform' | 'tenant' | 'developer' | 'personal'
type DashboardWidgetKey = 'stats' | 'quick_entries' | 'todos' | 'messages' | 'notices' | 'workbench'

interface DashboardProfile {
  type: DashboardType
  label: string
  title: string
  description: string
  color: string
}

interface QuickEntry {
  title: string
  desc: string
  path: string
  icon: string
  color: string
  menu?: string
  profiles?: DashboardType[]
}

interface MenuOption {
  title: string
  path: string
  icon: string
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

interface TodoItem {
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

const baseStats = ref([
  { key: 'users', label: '总用户数', value: '-', icon: 'User', color: '#1677ff', profiles: ['platform', 'tenant'] },
  { key: 'tenants', label: '活跃租户', value: '-', icon: 'OfficeBuilding', color: '#52c41a', profiles: ['platform'] },
  { key: 'calls', label: '今日 AI 调用', value: '-', icon: 'MagicStick', color: '#faad14', profiles: ['platform', 'tenant', 'developer'] },
  { key: 'tokens', label: '今日 Token 消耗', value: '-', icon: 'Coin', color: '#ff4d4f', profiles: ['platform', 'tenant', 'developer'] },
  { key: 'messages', label: '未读消息', value: '0', icon: 'Message', color: '#13c2c2', profiles: ['personal', 'tenant', 'developer'] },
  { key: 'agents', label: 'Agent 数量', value: '0', icon: 'Cpu', color: '#722ed1', profiles: ['developer'] },
])

const visibleStats = computed(() => {
  const profile = dashboardProfile.value.type
  return baseStats.value.filter(item => item.profiles.includes(profile)).slice(0, 4)
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

const quickEntryColors = ['#1677ff', '#722ed1', '#13c2c2', '#faad14', '#ff4d4f', '#52c41a']

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

const todos = computed<TodoItem[]>(() => [
  {
    title: '未读消息',
    desc: unreadCount.value ? '有新消息需要查看' : '暂无新的站内消息',
    value: String(unreadCount.value),
    type: unreadCount.value ? 'danger' : 'info',
    color: '#ff4d4f',
    path: '/message/inbox',
  },
  {
    title: dashboardProfile.value.type === 'developer' ? 'Agent 配置' : '基础配置',
    desc: dashboardProfile.value.type === 'developer' ? '检查模型和 Agent 是否可用' : '维护系统运行时配置',
    value: dashboardProfile.value.type === 'developer' ? String(agentTotal.value) : '配置',
    type: 'primary',
    color: '#1677ff',
    path: dashboardProfile.value.type === 'developer' ? '/ai/agents' : '/system/config',
  },
  {
    title: '文件归档',
    desc: '查看最近上传和归档状态',
    value: String(fileTotal.value),
    type: 'success',
    color: '#52c41a',
    path: '/system/files',
  },
])

const workbenchTitle = computed(() => {
  if (dashboardProfile.value.type === 'developer') return '开发资源'
  if (dashboardProfile.value.type === 'platform') return '平台运维'
  if (dashboardProfile.value.type === 'tenant') return '租户资源'
  return '个人概览'
})

const workbenchSubtitle = computed(() => {
  if (dashboardProfile.value.type === 'developer') return 'Agent、模型、知识库状态'
  if (dashboardProfile.value.type === 'platform') return '任务、文件、消息概况'
  return '当前账号可用资源'
})

const workbenchItems = computed(() => {
  if (dashboardProfile.value.type === 'developer') {
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
})

const workbenchActions = computed(() => {
  if (dashboardProfile.value.type === 'developer') {
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

// 格式化 Token 数量
function formatToken(count: number): string {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'K'
  }
  return String(count)
}

function formatNumber(count: number): string {
  return String(count || 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
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

function updateStat(key: string, value: string) {
  const target = baseStats.value.find(item => item.key === key)
  if (target) target.value = value
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

function getFulfilled<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === 'fulfilled' ? result.value : null
}

async function refreshDashboard() {
  await Promise.all([loadStats(), loadWorkbenchData()])
}

onMounted(() => {
  void loadPreferences()
  void refreshDashboard()
  timer = window.setInterval(() => {
    currentTime.value = formatDate(new Date())
  }, 60000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.section-row { margin-top: 16px; }

.hero-card {
  position: relative;
  overflow: hidden;
  min-height: 188px;
  border-radius: 16px;
  padding: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  color: #fff;
  background:
    radial-gradient(circle at 88% 16%, rgba(255, 255, 255, 0.2), transparent 26%),
    linear-gradient(135deg, color-mix(in srgb, var(--hero-accent) 82%, #0f172a), color-mix(in srgb, var(--hero-accent) 48%, #0f172a));
  box-shadow: 0 16px 42px color-mix(in srgb, var(--hero-accent) 16%, transparent);

  &::after {
    content: '';
    position: absolute;
    right: -70px;
    bottom: -90px;
    width: 260px;
    height: 260px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.12);
  }
}

.hero-main {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}

.hero-avatar {
  background: rgba(255, 255, 255, 0.26);
  color: #fff;
  font-size: 26px;
  font-weight: 700;
  border: 1px solid rgba(255, 255, 255, 0.34);
}

.hero-kicker {
  font-size: 14px;
  opacity: 0.86;
}

.hero-title {
  margin: 8px 0 8px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.hero-desc {
  max-width: 680px;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  opacity: 0.9;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.hero-side {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  min-width: 210px;
}

.hero-actions {
  display: flex;
  gap: 8px;
}

.time-card {
  width: 210px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
}

.time-label {
  font-size: 12px;
  opacity: 0.78;
}

.time-value {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 600;
}

.stat-card {
  height: 104px;
  background: var(--app-bg-card);
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  border-left: 4px solid var(--accent);

  .stat-icon {
    width: 50px;
    height: 50px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    flex-shrink: 0;
  }

  .stat-value { font-size: 24px; font-weight: 700; color: var(--app-text-primary); }
  .stat-label { font-size: 12px; color: var(--app-text-secondary); margin-top: 4px; }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .card-title {
    display: block;
    font-size: 15px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  .card-subtitle {
    display: block;
    margin-top: 4px;
    color: var(--app-text-secondary);
    font-size: 12px;
  }
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.quick-entry {
  min-height: 118px;
  padding: 16px;
  border: 1px solid var(--app-border-color);
  border-radius: 14px;
  background: var(--app-bg-card);
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s;

  &:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--entry-color) 42%, var(--app-border-color));
    box-shadow: 0 12px 28px color-mix(in srgb, var(--entry-color) 12%, transparent);
  }
}

.quick-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--entry-color);
  background: color-mix(in srgb, var(--entry-color) 12%, transparent);
}

.quick-title {
  display: block;
  margin-top: 12px;
  color: var(--app-text-primary);
  font-weight: 600;
}

.quick-desc {
  display: block;
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.todo-card {
  height: 100%;
}

.todo-list,
.list-panel,
.workbench-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 0;
  border-bottom: 1px solid var(--app-border-color);
  cursor: pointer;

  &:last-child {
    border-bottom: none;
  }
}

.todo-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  color: var(--app-text-primary);
  font-weight: 600;
}

.todo-desc {
  margin-top: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.list-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--app-border-color);

  &:last-child {
    border-bottom: none;
  }
}

.list-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--app-text-primary);
  font-weight: 500;
}

.list-meta {
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--app-bg-page);
}

.workbench-label {
  color: var(--app-text-secondary);
}

.workbench-value {
  max-width: 150px;
  overflow: hidden;
  color: var(--app-text-primary);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.preference-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.preference-section {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--app-border-color);

  &:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
}

.preference-title {
  color: var(--app-text-primary);
  font-weight: 600;
}

.preference-tip {
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.template-radio-group {
  margin-top: 14px;
}

.widget-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;

  :deep(.el-checkbox) {
    height: auto;
    align-items: flex-start;
    margin-right: 0;
    padding: 12px;
    border: 1px solid var(--app-border-color);
    border-radius: 10px;
  }
}

.widget-label {
  display: block;
  color: var(--app-text-primary);
  font-weight: 500;
}

.widget-desc {
  display: block;
  margin-top: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.quick-entry-select {
  width: 100%;
  margin-top: 14px;
}

.menu-option-title {
  font-weight: 500;
}

.menu-option-path {
  float: right;
  margin-left: 16px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.quick-entry-config-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.quick-entry-config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  background: var(--app-bg-page);
}

.quick-entry-config-main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
  color: var(--app-text-primary);
}

.quick-entry-config-title {
  font-weight: 500;
}

.quick-entry-config-path {
  margin-top: 3px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.quick-entry-config-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 6px;
}

@media (max-width: 1280px) {
  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .hero-card,
  .hero-main {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-side,
  .time-card {
    width: 100%;
    min-width: 0;
    align-items: stretch;
  }

  .quick-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions,
  .widget-options {
    flex-direction: column;
    grid-template-columns: 1fr;
  }

  .quick-entry-config-item,
  .quick-entry-config-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
