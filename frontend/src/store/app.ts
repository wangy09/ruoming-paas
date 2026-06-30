import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useDark, useToggle } from '@vueuse/core'
import { configApi } from '@/api/config'
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
]

type PublicConfigMap = Partial<Record<string, string>>

function loadVisitedViews(): Array<{ path: string; title: string; name?: string; affix?: boolean }> {
  try {
    const data = localStorage.getItem('visited_views')
    if (data) return JSON.parse(data)
  } catch {
    // ignore
  }
  return []
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

export const useAppStore = defineStore('app', () => {
  const isDark = useDark()
  const toggleDark = useToggle(isDark)

  const sidebarCollapsed = ref(false)
  const primaryColor = ref(localStorage.getItem('primary_color') || DEFAULT_PRIMARY_COLOR)
  const appTitle = ref(DEFAULT_APP_TITLE)
  const loginSubtitle = ref(DEFAULT_LOGIN_SUBTITLE)
  const logoUrl = ref(DEFAULT_LOGO_URL)
  const publicConfigLoaded = ref(false)
  let publicConfigPromise: Promise<void> | null = null

  const cachedViews = ref<string[]>(loadCachedViews())
  const visitedViews = ref<Array<{ path: string; title: string; name?: string; affix?: boolean }>>(loadVisitedViews())

  const locale = ref<'zh-CN' | 'en-US'>('zh-CN')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function addVisitedView(view: { path: string; title: string; name?: string }) {
    if (visitedViews.value.some(v => v.path === view.path)) return
    visitedViews.value.push(view)
    localStorage.setItem('visited_views', JSON.stringify(visitedViews.value))
  }

  function removeVisitedView(path: string) {
    visitedViews.value = visitedViews.value.filter(v => v.path !== path)
    localStorage.setItem('visited_views', JSON.stringify(visitedViews.value))
  }

  function closeOtherViews(path: string) {
    visitedViews.value = visitedViews.value.filter(v => v.path === path || v.affix)
    localStorage.setItem('visited_views', JSON.stringify(visitedViews.value))
  }

  function closeAllViews() {
    visitedViews.value = visitedViews.value.filter(v => v.affix)
    localStorage.setItem('visited_views', JSON.stringify(visitedViews.value))
  }

  function applyPrimaryColor(color: string) {
    primaryColor.value = color
    document.documentElement.style.setProperty('--el-color-primary', color)
  }

  function setPrimaryColor(color: string) {
    applyPrimaryColor(color)
    localStorage.setItem('primary_color', color)
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

  return {
    isDark,
    toggleDark,
    sidebarCollapsed,
    toggleSidebar,
    primaryColor,
    setPrimaryColor,
    appTitle,
    loginSubtitle,
    logoUrl,
    publicConfigLoaded,
    loadPublicConfig,
    cachedViews,
    visitedViews,
    addVisitedView,
    removeVisitedView,
    closeOtherViews,
    closeAllViews,
    locale,
  }
})
