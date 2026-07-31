import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useDark, useToggle } from '@vueuse/core'
import { configApi } from '@/api/config'
import { systemApi } from '@/api/system'
import type { ConfigInfo } from '@/types'

const DEFAULT_APP_TITLE = '若茗PaaS'
const DEFAULT_LOGIN_SUBTITLE = '企业级 AI 应用开发底座'
const DEFAULT_LOGO_URL = '/logo.svg'
const DEFAULT_PRIMARY_COLOR = '#1677ff'

const PUBLIC_CONFIG_KEYS = [
  'site.title',
  'site.login_subtitle',
  'site.logo_url',
  'ui.primary_color',
  'ai.assistant.enabled',
  'ai.assistant.welcome',
  'ai.assistant.agent_id',
]

type PublicConfigMap = Partial<Record<string, string>>
export interface VisitedView {
  path: string
  title: string
  name?: string
  affix?: boolean
}

interface LayoutSettings {
  showTabsBar: boolean
  showBreadcrumb: boolean
  fixedHeader: boolean
}

interface VisualSettings {
  grayMode: boolean
  colorWeakMode: boolean
}

const DEFAULT_LAYOUT_SETTINGS: LayoutSettings = {
  showTabsBar: true,
  showBreadcrumb: true,
  fixedHeader: true,
}

const DEFAULT_VISUAL_SETTINGS: VisualSettings = {
  grayMode: false,
  colorWeakMode: false,
}

function loadVisitedViews(): VisitedView[] {
  try {
    const data = localStorage.getItem('visited_views')
    if (data) return JSON.parse(data)
  } catch {
    // ignore
  }
  return []
}

function loadLayoutSettings(): LayoutSettings {
  try {
    const data = localStorage.getItem('layout_settings')
    if (data) return { ...DEFAULT_LAYOUT_SETTINGS, ...JSON.parse(data) }
  } catch {
    // ignore
  }
  return { ...DEFAULT_LAYOUT_SETTINGS }
}

function loadVisualSettings(): VisualSettings {
  try {
    const data = localStorage.getItem('visual_settings')
    if (data) return { ...DEFAULT_VISUAL_SETTINGS, ...JSON.parse(data) }
  } catch {
    // ignore
  }
  return { ...DEFAULT_VISUAL_SETTINGS }
}

function loadCachedViews(): string[] {
  try {
    const data = localStorage.getItem('cached_views')
    if (data) return JSON.parse(data)
  } catch {
    // ignore
  }
  return []
}

function normalizePublicConfigs(data: Record<string, string> | ConfigInfo[] | undefined): PublicConfigMap {
  if (!data) return {}
  if (Array.isArray(data)) {
    return data.reduce<PublicConfigMap>((map, item) => {
      map[item.config_key] = item.display_val || item.config_val || item.default_value || ''
      return map
    }, {})
  }
  return data
}

function normalizeHexColor(color: string): string | null {
  const value = color.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(value)) return value
  if (/^#[0-9a-fA-F]{3}$/.test(value)) {
    return `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`
  }
  return null
}

function hexToRgba(hex: string, alpha: number): string {
  const normalized = normalizeHexColor(hex) || DEFAULT_PRIMARY_COLOR
  const r = parseInt(normalized.slice(1, 3), 16)
  const g = parseInt(normalized.slice(3, 5), 16)
  const b = parseInt(normalized.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export const useAppStore = defineStore('app', () => {
  const isDark = useDark()
  const toggleDark = useToggle(isDark)

  const sidebarCollapsed = ref(false)
  const contentMaximized = ref(false)
  const browserFullscreen = ref(false)
  const layoutSettings = ref<LayoutSettings>(loadLayoutSettings())
  const visualSettings = ref<VisualSettings>(loadVisualSettings())
  const primaryColor = ref(localStorage.getItem('primary_color') || DEFAULT_PRIMARY_COLOR)
  const appTitle = ref(DEFAULT_APP_TITLE)
  const loginSubtitle = ref(DEFAULT_LOGIN_SUBTITLE)
  const logoUrl = ref(DEFAULT_LOGO_URL)
  const publicConfigLoaded = ref(false)
  let publicConfigPromise: Promise<void> | null = null

  const cachedViews = ref<string[]>(loadCachedViews())
  const visitedViews = ref<VisitedView[]>(loadVisitedViews())

  const locale = ref<'zh-CN' | 'en-US'>('zh-CN')

  const isDemoMode = ref(false)
  const aiAssistantEnabled = ref(true)
  const aiAssistantWelcome = ref('你好！我是 AI 助手，可以帮您导航页面、回答问题。')
  const aiAssistantAgentId = ref<number | null>(null)

  async function loadDemoMode() {
    try {
      const res = await systemApi.demoMode()
      isDemoMode.value = res.data?.demo_mode || false
    } catch {
      isDemoMode.value = false
    }
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function saveVisitedViews() {
    localStorage.setItem('visited_views', JSON.stringify(visitedViews.value))
  }

  function saveCachedViews() {
    localStorage.setItem('cached_views', JSON.stringify(cachedViews.value))
  }

  function saveLayoutSettings() {
    localStorage.setItem('layout_settings', JSON.stringify(layoutSettings.value))
  }

  function saveVisualSettings() {
    localStorage.setItem('visual_settings', JSON.stringify(visualSettings.value))
  }

  function applyVisualSettings() {
    const root = document.documentElement
    root.classList.toggle('gray-mode', visualSettings.value.grayMode)
    root.classList.toggle('color-weak-mode', visualSettings.value.colorWeakMode)
  }

  function addVisitedView(view: VisitedView) {
    if (visitedViews.value.some(v => v.path === view.path)) return
    visitedViews.value.push(view)
    saveVisitedViews()
  }

  function addCachedView(name?: string) {
    if (!name || cachedViews.value.includes(name)) return
    cachedViews.value.push(name)
    saveCachedViews()
  }

  function removeVisitedView(path: string) {
    const target = visitedViews.value.find(v => v.path === path)
    visitedViews.value = visitedViews.value.filter(v => v.path !== path)
    saveVisitedViews()
    if (target?.name) removeCachedView(target.name)
  }

  function closeOtherViews(path: string) {
    visitedViews.value = visitedViews.value.filter(v => v.path === path || v.affix)
    saveVisitedViews()
    syncCachedViewsWithVisitedViews()
  }

  function closeAllViews() {
    visitedViews.value = visitedViews.value.filter(v => v.affix)
    saveVisitedViews()
    syncCachedViewsWithVisitedViews()
  }

  function closeLeftViews(path: string) {
    const currentIdx = visitedViews.value.findIndex(v => v.path === path)
    if (currentIdx < 0) return
    visitedViews.value = visitedViews.value.filter((v, index) => index >= currentIdx || v.affix)
    saveVisitedViews()
    syncCachedViewsWithVisitedViews()
  }

  function closeRightViews(path: string) {
    const currentIdx = visitedViews.value.findIndex(v => v.path === path)
    if (currentIdx < 0) return
    visitedViews.value = visitedViews.value.filter((v, index) => index <= currentIdx || v.affix)
    saveVisitedViews()
    syncCachedViewsWithVisitedViews()
  }

  function removeCachedView(name: string) {
    cachedViews.value = cachedViews.value.filter(item => item !== name)
    saveCachedViews()
  }

  function syncCachedViewsWithVisitedViews() {
    const names = new Set(visitedViews.value.map(v => v.name).filter(Boolean))
    cachedViews.value = cachedViews.value.filter(name => names.has(name))
    saveCachedViews()
  }

  function setShowTabsBar(visible: boolean) {
    layoutSettings.value.showTabsBar = visible
    saveLayoutSettings()
  }

  function setShowBreadcrumb(visible: boolean) {
    layoutSettings.value.showBreadcrumb = visible
    saveLayoutSettings()
  }

  function setFixedHeader(fixed: boolean) {
    layoutSettings.value.fixedHeader = fixed
    saveLayoutSettings()
  }

  function resetLayoutSettings() {
    layoutSettings.value = { ...DEFAULT_LAYOUT_SETTINGS }
    saveLayoutSettings()
  }

  function setGrayMode(enabled: boolean) {
    visualSettings.value.grayMode = enabled
    saveVisualSettings()
    applyVisualSettings()
  }

  function setColorWeakMode(enabled: boolean) {
    visualSettings.value.colorWeakMode = enabled
    saveVisualSettings()
    applyVisualSettings()
  }

  function resetVisualSettings() {
    visualSettings.value = { ...DEFAULT_VISUAL_SETTINGS }
    saveVisualSettings()
    applyVisualSettings()
  }

  function setContentMaximized(maximized: boolean) {
    contentMaximized.value = maximized
  }

  function toggleContentMaximized() {
    contentMaximized.value = !contentMaximized.value
  }

  function syncBrowserFullscreen() {
    browserFullscreen.value = Boolean(document.fullscreenElement)
  }

  async function toggleBrowserFullscreen() {
    // 浏览器全屏 API 必须由用户手势触发，失败时交给调用侧提示
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await document.documentElement.requestFullscreen()
    }
    syncBrowserFullscreen()
  }

  function applyPrimaryColor(color: string) {
    const normalized = normalizeHexColor(color) || DEFAULT_PRIMARY_COLOR
    primaryColor.value = normalized
    document.documentElement.style.setProperty('--el-color-primary', normalized)
    document.documentElement.style.setProperty('--el-color-primary-light-3', hexToRgba(normalized, 0.8))
    document.documentElement.style.setProperty('--el-color-primary-light-5', hexToRgba(normalized, 0.6))
    document.documentElement.style.setProperty('--el-color-primary-light-7', hexToRgba(normalized, 0.4))
    document.documentElement.style.setProperty('--el-color-primary-light-8', hexToRgba(normalized, 0.2))
    document.documentElement.style.setProperty('--el-color-primary-light-9', hexToRgba(normalized, 0.1))
    document.documentElement.style.setProperty('--el-color-primary-dark-2', normalized)
  }

  function setPrimaryColor(color: string) {
    applyPrimaryColor(color)
    localStorage.setItem('primary_color', primaryColor.value)
  }

  function clearPageCache() {
    cachedViews.value = []
    saveCachedViews()
  }

  function clearTabs() {
    cachedViews.value = []
    visitedViews.value = []
    saveCachedViews()
    saveVisitedViews()
  }

  function resetPublicConfigCache() {
    publicConfigLoaded.value = false
    publicConfigPromise = null
  }

  function clearPreferenceCache() {
    clearTabs()
    resetLayoutSettings()
    resetVisualSettings()
    localStorage.removeItem('primary_color')
    applyPrimaryColor(DEFAULT_PRIMARY_COLOR)
    resetPublicConfigCache()
  }

  async function loadPublicConfig() {
    if (publicConfigLoaded.value) return
    if (publicConfigPromise) return publicConfigPromise

    publicConfigPromise = configApi.publicConfigs({ keys: PUBLIC_CONFIG_KEYS })
      .then((res) => {
        const configs = normalizePublicConfigs(res.data)
        appTitle.value = configs['site.title'] || DEFAULT_APP_TITLE
        loginSubtitle.value = configs['site.login_subtitle'] || DEFAULT_LOGIN_SUBTITLE
        logoUrl.value = configs['site.logo_url'] || DEFAULT_LOGO_URL
        applyPrimaryColor(configs['ui.primary_color'] || primaryColor.value)
        aiAssistantEnabled.value = configs['ai.assistant.enabled'] !== 'false'
        aiAssistantWelcome.value = configs['ai.assistant.welcome'] || aiAssistantWelcome.value
        const agentId = configs['ai.assistant.agent_id']
        aiAssistantAgentId.value = agentId ? Number(agentId) : null
        publicConfigLoaded.value = true
      })
      .catch(() => {
        applyPrimaryColor(primaryColor.value)
        publicConfigLoaded.value = true
      })
      .finally(() => {
        publicConfigPromise = null
      })

    return publicConfigPromise
  }

  applyPrimaryColor(primaryColor.value)
  applyVisualSettings()

  return {
    isDark,
    toggleDark,
    sidebarCollapsed,
    toggleSidebar,
    contentMaximized,
    setContentMaximized,
    toggleContentMaximized,
    browserFullscreen,
    syncBrowserFullscreen,
    toggleBrowserFullscreen,
    layoutSettings,
    setShowTabsBar,
    setShowBreadcrumb,
    setFixedHeader,
    resetLayoutSettings,
    visualSettings,
    setGrayMode,
    setColorWeakMode,
    resetVisualSettings,
    primaryColor,
    setPrimaryColor,
    clearPageCache,
    clearTabs,
    clearPreferenceCache,
    appTitle,
    loginSubtitle,
    logoUrl,
    publicConfigLoaded,
    loadPublicConfig,
    cachedViews,
    visitedViews,
    addVisitedView,
    addCachedView,
    removeVisitedView,
    closeOtherViews,
    closeAllViews,
    closeLeftViews,
    closeRightViews,
    locale,
    isDemoMode,
    loadDemoMode,
    aiAssistantEnabled,
    aiAssistantWelcome,
    aiAssistantAgentId,
  }
})
