import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '@/api/user'
import { integrationApi } from '@/api/integration'
import { taskApi } from '@/api/monitor'
import type {
  ContactSyncCheckResult,
  ContactSyncLogItem,
  ContactSyncPreviewResult,
  ContactSyncRequest,
  ContactSyncResult,
  ContactSyncStrategy,
  IntegrationConnection,
} from '@/types'

type UsernameStrategy = 'email_prefix' | 'phone' | 'name' | 'external_id'
type NicknameStrategy = 'name' | 'nickname' | 'username'
type FieldUpdateMode = 'never' | 'if_empty' | 'always'

interface ScheduledTaskItem {
  id: number
  name: string
  func_name: string
  kwargs?: Record<string, unknown> | null
}

const CONTACT_SYNC_TASK_FUNC = 'app.modules.integration.tasks.sync_contact_connection'

const DEFAULT_SYNC_STRATEGY: ContactSyncStrategy = {
  sync_departments: true,
  sync_users: true,
  sync_avatar: true,
  disable_missing_users: false,
  username_strategy: ['email_prefix', 'phone', 'name', 'external_id'],
  nickname_strategy: ['name', 'nickname'],
  overwrite_email: true,
  overwrite_phone: false,
  overwrite_department: true,
  email_update_mode: 'always',
  phone_update_mode: 'never',
  department_update_mode: 'always',
}

export function useContactSync() {
  const router = useRouter()

  const syncDialogVisible = ref(false)
  const syncing = ref(false)
  const checking = ref(false)
  const previewing = ref(false)
  const connectionLoading = ref(false)
  const strategyLoading = ref(false)
  const strategySaving = ref(false)
  const syncTaskCreating = ref(false)
  const connectionOptions = ref<IntegrationConnection[]>([])
  const syncCheckResult = ref<ContactSyncCheckResult | null>(null)
  const syncPreviewResult = ref<ContactSyncPreviewResult | null>(null)
  const syncLogLoading = ref(false)
  const syncLogs = ref<ContactSyncLogItem[]>([])
  const syncLogDetailVisible = ref(false)
  const currentSyncLog = ref<ContactSyncLogItem | null>(null)
  const syncBusy = computed(() => checking.value || previewing.value || syncing.value)

  const usernameStrategyOptions: Array<{ label: string; value: UsernameStrategy }> = [
    { label: '邮箱前缀', value: 'email_prefix' },
    { label: '手机号', value: 'phone' },
    { label: '姓名', value: 'name' },
    { label: '外部ID', value: 'external_id' },
  ]
  const nicknameStrategyOptions: Array<{ label: string; value: NicknameStrategy }> = [
    { label: '姓名', value: 'name' },
    { label: '昵称', value: 'nickname' },
    { label: '用户名', value: 'username' },
  ]
  const fieldUpdateModeOptions: Array<{ label: string; value: FieldUpdateMode }> = [
    { label: '不更新', value: 'never' },
    { label: '仅本地为空时填充', value: 'if_empty' },
    { label: '外部有值时覆盖', value: 'always' },
  ]

  const syncForm = reactive({
    provider: 'wecom' as 'feishu' | 'wecom' | 'dingtalk',
    connection_id: undefined as number | undefined,
    ...DEFAULT_SYNC_STRATEGY,
  })

  let fetchListCallback: (() => Promise<void>) | null = null
  let fetchDeptOptionsCallback: (() => Promise<void>) | null = null

  function setCallbacks(fetchList: () => Promise<void>, fetchDeptOptions: () => Promise<void>) {
    fetchListCallback = fetchList
    fetchDeptOptionsCallback = fetchDeptOptions
  }

  function applySyncStrategy(strategy: ContactSyncStrategy | null | undefined) {
    const s = normalizeSyncStrategy(strategy)
    syncForm.sync_departments = s.sync_departments
    syncForm.sync_users = s.sync_users
    syncForm.sync_avatar = s.sync_avatar
    syncForm.disable_missing_users = s.disable_missing_users
    syncForm.username_strategy = [...s.username_strategy]
    syncForm.nickname_strategy = [...s.nickname_strategy]
    syncForm.email_update_mode = s.email_update_mode
    syncForm.phone_update_mode = s.phone_update_mode
    syncForm.department_update_mode = s.department_update_mode
  }

  function normalizeSyncStrategy(s: ContactSyncStrategy | null | undefined): ContactSyncStrategy {
    if (!s) return { ...DEFAULT_SYNC_STRATEGY }
    const username_strategy = Array.isArray(s.username_strategy) && s.username_strategy.length
      ? [...s.username_strategy]
      : [...DEFAULT_SYNC_STRATEGY.username_strategy]
    const nickname_strategy = Array.isArray(s.nickname_strategy) && s.nickname_strategy.length
      ? [...s.nickname_strategy]
      : [...DEFAULT_SYNC_STRATEGY.nickname_strategy]
    return {
      sync_departments: s.sync_departments ?? DEFAULT_SYNC_STRATEGY.sync_departments,
      sync_users: s.sync_users ?? DEFAULT_SYNC_STRATEGY.sync_users,
      sync_avatar: s.sync_avatar ?? DEFAULT_SYNC_STRATEGY.sync_avatar,
      disable_missing_users: s.disable_missing_users ?? DEFAULT_SYNC_STRATEGY.disable_missing_users,
      username_strategy,
      nickname_strategy,
      email_update_mode: s.email_update_mode ?? DEFAULT_SYNC_STRATEGY.email_update_mode,
      phone_update_mode: s.phone_update_mode ?? DEFAULT_SYNC_STRATEGY.phone_update_mode,
      department_update_mode: s.department_update_mode ?? DEFAULT_SYNC_STRATEGY.department_update_mode,
    }
  }

  function pickDefaultSyncConnection() {
    return connectionOptions.value.find((c) => c.is_default) || connectionOptions.value[0]
  }

  function getSourceProviderLabel(provider: string): string {
    const labels: Record<string, string> = {
      feishu: '飞书',
      dingtalk: '钉钉',
      wecom: '企业微信',
    }
    return labels[provider] || provider
  }

  function getSyncContentLabel(): string {
    const parts: string[] = []
    if (syncForm.sync_departments) parts.push('部门')
    if (syncForm.sync_users) parts.push('用户')
    return parts.join('和')
  }

  function clearSyncResults() {
    syncCheckResult.value = null
    syncPreviewResult.value = null
  }

  async function fetchConnectionOptions() {
    connectionLoading.value = true
    try {
      const res = await integrationApi.connections({
        provider: syncForm.provider,
        enabled: true,
      })
      connectionOptions.value = (res.data || []).filter((item) =>
        item.capabilities.includes('contact_sync')
      )
      if (!connectionOptions.value.some((item) => item.id === syncForm.connection_id)) {
        syncForm.connection_id = pickDefaultSyncConnection()?.id
      }
      await loadSelectedContactSyncStrategy()
    } finally {
      connectionLoading.value = false
    }
  }

  async function loadSelectedContactSyncStrategy(showMessage = false) {
    if (!syncForm.connection_id) {
      applySyncStrategy(DEFAULT_SYNC_STRATEGY)
      return
    }
    strategyLoading.value = true
    try {
      const res = await integrationApi.contactSyncStrategy(syncForm.connection_id)
      applySyncStrategy(normalizeSyncStrategy(res.data))
      clearSyncResults()
      if (showMessage) {
        ElMessage.success('已恢复连接默认策略')
      }
    } finally {
      strategyLoading.value = false
    }
  }

  async function fetchSyncLogs() {
    syncLogLoading.value = true
    try {
      const res = await integrationApi.contactSyncLogs({ limit: 20 })
      syncLogs.value = res.data || []
    } finally {
      syncLogLoading.value = false
    }
  }

  function openSyncLogDetail(log: ContactSyncLogItem) {
    currentSyncLog.value = log
    syncLogDetailVisible.value = true
  }

  async function openSyncDialog() {
    clearSyncResults()
    syncDialogVisible.value = true
    await Promise.all([fetchConnectionOptions(), fetchSyncLogs()])
  }

  async function handleSyncProviderChange() {
    syncForm.connection_id = undefined
    applySyncStrategy(DEFAULT_SYNC_STRATEGY)
    clearSyncResults()
    await Promise.all([fetchConnectionOptions(), fetchSyncLogs()])
  }

  async function handleSyncConnectionChange() {
    clearSyncResults()
    await loadSelectedContactSyncStrategy()
  }

  async function handleReloadSyncStrategy() {
    await loadSelectedContactSyncStrategy(true)
  }

  function buildSyncStrategy(): ContactSyncStrategy | null {
    if (!syncForm.sync_departments && !syncForm.sync_users) {
      ElMessage.warning('请至少选择一个同步内容')
      return null
    }
    if (syncForm.sync_users && !syncForm.username_strategy.length) {
      ElMessage.warning('请至少选择一个用户名优先级')
      return null
    }
    if (syncForm.sync_users && !syncForm.nickname_strategy.length) {
      ElMessage.warning('请至少选择一个昵称优先级')
      return null
    }
    return {
      sync_departments: syncForm.sync_departments,
      sync_users: syncForm.sync_users,
      sync_avatar: syncForm.sync_avatar,
      disable_missing_users: syncForm.disable_missing_users,
      username_strategy: [...syncForm.username_strategy],
      nickname_strategy: [...syncForm.nickname_strategy],
      overwrite_email: syncForm.email_update_mode === 'always',
      overwrite_phone: syncForm.phone_update_mode === 'always',
      overwrite_department: syncForm.department_update_mode === 'always',
      email_update_mode: syncForm.email_update_mode,
      phone_update_mode: syncForm.phone_update_mode,
      department_update_mode: syncForm.department_update_mode,
    }
  }

  function buildSyncPayload(): ContactSyncRequest | null {
    if (!syncForm.connection_id) {
      ElMessage.warning('请选择已启用通讯录同步的集成连接')
      return null
    }
    const strategy = buildSyncStrategy()
    if (!strategy) {
      return null
    }
    return {
      provider: syncForm.provider,
      connection_id: syncForm.connection_id,
      ...strategy,
    }
  }

  async function runSyncCheck(payload: ContactSyncRequest, showMessage = true) {
    checking.value = true
    try {
      const res = await userApi.checkSyncContacts(payload)
      syncCheckResult.value = res.data
      if (showMessage) {
        ElMessage.success('自检完成')
      }
      return res.data
    } finally {
      checking.value = false
    }
  }

  async function confirmOrCancel(message: string, title: string): Promise<boolean> {
    try {
      await ElMessageBox.confirm(message, title, {
        type: 'warning',
      })
      return true
    } catch (error) {
      if (error === 'cancel' || error === 'close') {
        return false
      }
      throw error
    }
  }

  async function handleCheckSyncContacts() {
    if (syncBusy.value) {
      return
    }
    const payload = buildSyncPayload()
    if (!payload) {
      return
    }
    await runSyncCheck(payload)
  }

  async function handlePreviewSyncContacts() {
    const payload = buildSyncPayload()
    if (!payload) {
      return
    }
    previewing.value = true
    try {
      const res = await userApi.previewSyncContacts(payload)
      syncPreviewResult.value = res.data
      fetchSyncLogs()
      ElMessage.success('预览完成')
    } finally {
      previewing.value = false
    }
  }

  async function handleSaveSyncStrategy() {
    if (!syncForm.connection_id) {
      ElMessage.warning('请先选择集成连接')
      return
    }
    const strategy = buildSyncStrategy()
    if (!strategy) {
      return
    }
    strategySaving.value = true
    try {
      const res = await integrationApi.saveContactSyncStrategy(syncForm.connection_id, strategy)
      applySyncStrategy(normalizeSyncStrategy(res.data))
      clearSyncResults()
      ElMessage.success('默认策略已保存')
    } finally {
      strategySaving.value = false
    }
  }

  async function handleCreateContactSyncTask() {
    if (!syncForm.connection_id) {
      ElMessage.warning('请先选择集成连接')
      return
    }
    const strategy = buildSyncStrategy()
    if (!strategy) {
      return
    }
    const connection = connectionOptions.value.find((item) => item.id === syncForm.connection_id)
    const taskName = `${connection?.name || getSourceProviderLabel(syncForm.provider)} 通讯录每日同步`

    syncTaskCreating.value = true
    try {
      const existingTasks = await taskApi.list({
        page: 1,
        page_size: 200,
        func_name: CONTACT_SYNC_TASK_FUNC,
      })
      const existingTask = (existingTasks.data.items as ScheduledTaskItem[] | undefined)?.find(
        (item) => Number(item.kwargs?.connection_id) === syncForm.connection_id
      )
      if (existingTask) {
        try {
          await ElMessageBox.confirm(
            `当前连接已存在通讯录同步计划任务「${existingTask.name}」，是否前往系统计划任务中管理？`,
            '计划任务已存在',
            {
              confirmButtonText: '去计划任务',
              cancelButtonText: '留在当前页',
              type: 'warning',
            }
          )
          await router.push('/monitor/task')
        } catch {
          // 用户选择留在当前页
        }
        return
      }

      await ElMessageBox.confirm(
        `将在系统"计划任务"中新增一条停用记录「${taskName}」，任务会复用当前连接保存的默认策略。创建后可在计划任务中修改周期、启停和查看执行日志。`,
        '创建通讯录同步计划任务',
        {
          confirmButtonText: '创建计划任务',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      await integrationApi.saveContactSyncStrategy(syncForm.connection_id, strategy)
      await taskApi.create({
        name: taskName,
        task_type: 'interval',
        func_name: CONTACT_SYNC_TASK_FUNC,
        interval_seconds: 86400,
        is_once: false,
        status: 0,
        args: [],
        kwargs: {
          connection_id: syncForm.connection_id,
        },
        remark: '外部通讯录每日自动同步任务。任务由用户同步弹框创建，可在系统计划任务中统一启停、调整周期和查看执行日志。',
      })
      try {
        await ElMessageBox.confirm(
          '已在系统计划任务中创建停用记录。是否现在前往计划任务页面确认周期并启用？',
          '创建成功',
          {
            confirmButtonText: '去计划任务',
            cancelButtonText: '稍后再说',
            type: 'success',
          }
        )
        await router.push('/monitor/task')
      } catch {
        ElMessage.success('已在系统计划任务中创建停用记录，请到计划任务确认后启用')
      }
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error('创建计划任务失败')
      }
    } finally {
      syncTaskCreating.value = false
    }
  }

  async function handleSyncContacts() {
    if (syncBusy.value) {
      return
    }
    const payload = buildSyncPayload()
    if (!payload) {
      return
    }
    syncing.value = true
    try {
      const checkResult = await runSyncCheck(payload, false)
      if (checkResult.status === 'failed') {
        ElMessage.error(checkResult.summary || '同步自检失败，请修复后再开始同步')
        return
      }
      if (checkResult.status === 'warning') {
        const confirmed = await confirmOrCancel(
          checkResult.summary || '同步自检存在警告，仍要继续同步？',
          '自检警告'
        )
        if (!confirmed) {
          return
        }
      }
      const confirmed = await confirmOrCancel(
        `同步会创建或更新${getSyncContentLabel()}，确认开始？`,
        '确认同步'
      )
      if (!confirmed) {
        return
      }
      const res = await userApi.syncContacts(payload)
      const data = res.data
      ElMessage.success(
        `同步完成：部门新增 ${data.departments_created}、更新 ${data.departments_updated}；用户新增 ${data.users_created}、更新 ${data.users_updated}`
      )
      if (data.errors?.length) {
        ElMessage.warning(`同步完成但有 ${data.errors.length} 条提示，请查看接口返回详情`)
      }
      fetchSyncLogs()
      syncDialogVisible.value = false
      await fetchDeptOptionsCallback?.()
      await fetchListCallback?.()
    } finally {
      syncing.value = false
    }
  }

  return {
    // state
    syncDialogVisible,
    syncing,
    checking,
    previewing,
    connectionLoading,
    strategyLoading,
    strategySaving,
    syncTaskCreating,
    connectionOptions,
    syncCheckResult,
    syncPreviewResult,
    syncLogLoading,
    syncLogs,
    syncLogDetailVisible,
    currentSyncLog,
    syncBusy,
    syncForm,
    usernameStrategyOptions,
    nicknameStrategyOptions,
    fieldUpdateModeOptions,
    DEFAULT_SYNC_STRATEGY,
    // methods
    setCallbacks,
    openSyncDialog,
    handleSyncProviderChange,
    handleSyncConnectionChange,
    handleReloadSyncStrategy,
    handleSaveSyncStrategy,
    handleCreateContactSyncTask,
    handleCheckSyncContacts,
    handlePreviewSyncContacts,
    handleSyncContacts,
    openSyncLogDetail,
    clearSyncResults,
  }
}
