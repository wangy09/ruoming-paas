import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useDark, useToggle } from '@vueuse/core'

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

export const useAppStore = defineStore('app', () => {
  const isDark = useDark()
  const toggleDark = useToggle(isDark)

  const sidebarCollapsed = ref(false)
  const primaryColor = ref(localStorage.getItem('primary_color') || '#1677ff')

  const cachedViews = ref<string[]>(loadCachedViews())
  const visitedViews = ref<Array<{ path: string; title: string; name?: string; affix?: boolean }>>(loadVisitedViews())

  const locale = ref<'zh-CN' | 'en-US'>('zh-CN')

  const appTitle = computed(() => import.meta.env.VITE_APP_TITLE || '若茗PaaS')

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

  function setPrimaryColor(color: string) {
    primaryColor.value = color
    localStorage.setItem('primary_color', color)
    document.documentElement.style.setProperty('--el-color-primary', color)
  }

  return {
    isDark,
    toggleDark,
    sidebarCollapsed,
    toggleSidebar,
    primaryColor,
    setPrimaryColor,
    cachedViews,
    visitedViews,
    addVisitedView,
    removeVisitedView,
    closeOtherViews,
    closeAllViews,
    locale,
    appTitle,
  }
})
