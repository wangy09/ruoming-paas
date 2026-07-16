/**
 * 字典 Composable - 简洁版
 * 使用方式：const { dictItems, getLabel, dictLoading } = useDict('system_user_status')
 */
import { ref, computed, watch } from 'vue'
import { dictApi } from '@/api/dict'

// 全局缓存
const globalCache = new Map<string, { items: any[], updatedAt: number }>()
const CACHE_TTL = 5 * 60 * 1000 // 5分钟缓存

// 当前正在加载的字典
const loadingMap = new Map<string, Promise<any>>()

/**
 * 根据字典编码获取字典项（自动缓存）
 */
async function fetchDictItems(code: string): Promise<any[]> {
  // 检查缓存
  const cached = globalCache.get(code)
  if (cached && Date.now() - cached.updatedAt < CACHE_TTL) {
    return cached.items
  }

  // 如果已经在加载中，等待它完成
  if (loadingMap.has(code)) {
    const items = await loadingMap.get(code)!
    return items
  }

  // 发起请求
  const promise = (async () => {
    try {
      const res = await dictApi.getDictByCode(code)
      const items = res.data?.items || []
      globalCache.set(code, { items, updatedAt: Date.now() })
      return items
    } catch (error) {
      console.error(`Failed to load dict: ${code}`, error)
      return []
    } finally {
      loadingMap.delete(code)
    }
  })()

  loadingMap.set(code, promise)
  return promise
}

/**
 * 清除字典缓存
 */
function clearDictCache(code?: string) {
  if (code) {
    globalCache.delete(code)
  } else {
    globalCache.clear()
  }
}

// ============ 简洁 API ============

/**
 * 使用字典项列表（响应式）
 * @param dictCode 字典编码
 * @returns { items, loading, error }
 */
export function useDictItems(dictCode: string) {
  const items = ref<any[]>([])
  const loading = ref(false)
  const error = ref<Error | null>(null)

  async function loadDict() {
    if (!dictCode) return
    loading.value = true
    error.value = null
    try {
      items.value = await fetchDictItems(dictCode)
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  loadDict()

  return {
    items,
    loading,
    error,
    reload: loadDict,
  }
}

/**
 * 根据字典编码和值获取标签
 */
export function useDictLabel(dictCode: string, value: () => any) {
  const label = ref<string>('')
  const { items } = useDictItems(dictCode)

  watch(
    [items, value],
    () => {
      if (!value()) {
        label.value = ''
        return
      }
      const item = items.value.find(i => String(i.value) === String(value()))
      label.value = item?.label || String(value())
    },
    { immediate: true }
  )

  return { label }
}

// ============ 预设的通用字典（无需配置，直接使用）============

/**
 * 通用状态（正常/停用）
 */
export function useCommonStatus() {
  const { items } = useDictItems('system_common_status')

  const options = computed(() => items.value.map(i => ({
    label: i.label,
    value: i.value,
  })))

  const tagType = (value: any): '' | 'success' | 'warning' | 'info' | 'danger' | 'primary' => {
    const map: Record<string, string> = {
      '1': 'success',
      '0': 'danger',
    }
    return (map[String(value)] || 'info') as '' | 'success' | 'warning' | 'info' | 'danger' | 'primary'
  }

  const label = (value: any) => {
    const item = items.value.find(i => String(i.value) === String(value))
    return item?.label || String(value)
  }

  return {
    items,
    options,
    tagType,
    label,
  }
}

/**
 * 用户状态（启用/禁用）
 */
export function useUserStatus() {
  const { items } = useDictItems('system_user_status')

  const options = computed(() => items.value.map(i => ({
    label: i.label,
    value: i.value,
  })))

  const tagType = (value: any) => {
    const map: Record<string, string> = {
      'true': 'success',
      'false': 'danger',
      'True': 'success',
      'False': 'danger',
    }
    return map[String(value)] || 'info'
  }

  const label = (value: any) => {
    const item = items.value.find(i => String(i.value) === String(value))
    return item?.label || String(value)
  }

  return {
    items,
    options,
    tagType,
    label,
  }
}

/**
 * 数据权限范围
 */
export function useDataScope() {
  const { items } = useDictItems('system_data_scope')

  const options = computed(() => items.value.map(i => ({
    label: i.label,
    value: Number(i.value),
  })))

  const label = (value: number) => {
    const item = items.value.find(i => Number(i.value) === value)
    return item?.label || String(value)
  }

  return {
    items,
    options,
    label,
  }
}

/**
 * 租户状态
 */
export function useTenantStatus() {
  const { items } = useDictItems('system_tenant_status')

  const options = computed(() => items.value.map(i => ({
    label: i.label,
    value: i.value,
  })))

  const tagType = (value: any): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
    const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
      'active': 'success',
      'inactive': 'danger',
      'suspended': 'warning',
    }
    return map[String(value)] || 'info'
  }

  const label = (value: any) => {
    const item = items.value.find(i => String(i.value) === String(value))
    return item?.label || String(value)
  }

  return {
    items,
    options,
    tagType,
    label,
  }
}

/**
 * Agent 状态
 */
export function useAgentStatus() {
  const { items } = useDictItems('ai_agent_status')

  const options = computed(() => items.value.map(i => ({
    label: i.label,
    value: i.value,
  })))

  const tagType = (value: any) => {
    const map: Record<string, string> = {
      'draft': 'info',
      'active': 'success',
      'archived': '',
    }
    return map[String(value)] || 'info'
  }

  const label = (value: any) => {
    const item = items.value.find(i => String(i.value) === String(value))
    return item?.label || String(value)
  }

  return {
    items,
    options,
    tagType,
    label,
  }
}

// 导出清除缓存方法
export { clearDictCache }
