<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-form inline class="search-form" @submit.prevent="fetchList" style="flex: 1;">
          <el-form-item label="关键词">
            <el-input v-model="query.keyword" placeholder="用户名 / 邮箱" clearable style="width:200px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
              <el-option label="启用" :value="1" />
              <el-option label="禁用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
            <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="toolbar-actions">
          <el-button :icon="Refresh" v-permission="'system:user:sync'" @click="openSyncDialog">
            同步用户
          </el-button>
          <el-button type="primary" :icon="Plus" v-permission="'system:user:create'" @click="openDialog()">
            新增用户
          </el-button>
        </div>
      </div>

      <el-divider />

      <!-- 表格 -->
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column label="头像" width="72" align="center">
          <template #default="{ row: r }">
            <el-avatar :size="36" :src="(r as UserListItem).avatar || undefined">
              {{ getAvatarText(r as UserListItem) }}
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="nickname" label="用户昵称" min-width="120" show-overflow-tooltip />
        <el-table-column label="来源" min-width="130" align="center">
          <template #default="{ row: r }">
            <el-tooltip
              v-if="(r as UserListItem).source_provider"
              :content="getSourceProviderTooltip(r as UserListItem)"
              placement="top"
            >
              <el-tag :type="getSourceProviderTagType((r as UserListItem).source_provider)" size="small">
                {{ getSourceProviderLabel((r as UserListItem).source_provider) }}
              </el-tag>
            </el-tooltip>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="部门" min-width="120">
          <template #default="{ row: r }">
            {{ (r as UserListItem).dept_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row: r }">
            <el-tag
              v-for="role in (r as UserListItem).roles"
              :key="role.id"
              size="small"
              type="info"
              class="mr-1"
            >
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row: r }">
            <el-switch
              :model-value="(r as UserListItem).status === 1"
              :loading="switchLoadingId === (r as UserListItem).id"
              @change="toggleActive(r as UserListItem)"
            />
          </template>
        </el-table-column>
        <el-table-column label="超管" width="70" align="center">
          <template #default="{ row: r }">
            <el-tag v-if="(r as UserListItem).is_superplatform" type="danger" size="small">超管</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row: r }">{{ formatDate((r as UserListItem).created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right" align="center">
          <template #default="{ row: r }">
            <el-button
              link type="primary"
              v-permission="'system:user:update'"
              @click="openDialog(r as UserListItem)"
            >编辑</el-button>
            <el-button
              v-if="!(r as UserListItem).is_superplatform"
              link type="warning"
              v-permission="'system:user:update'"
              @click="openRoleDialog(r as UserListItem)"
            >角色</el-button>
            <el-button
              link type="warning"
              v-permission="'system:user:reset-password'"
              @click="handleResetPwd(r as UserListItem)"
            >重置密码</el-button>
            <el-button
              v-if="!(r as UserListItem).is_superplatform"
              link type="danger"
              v-permission="'system:user:delete'"
              @click="handleDelete(r as UserListItem)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        class="mt-4"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @change="fetchList"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <FormDialog
      v-model:visible="dialogVisible"
      v-model:model-value="editRow"
      :dept-options="deptOptions"
      @submit="handleFormSubmit"
    />

    <!-- 分配角色对话框 -->
    <RoleDialog
      v-model:visible="roleDialogVisible"
      v-model:model-value="editRow"
      :all-roles="allRoles"
      @submit="handleRoleSubmit"
    />

    <!-- 通讯录同步对话框 -->
    <SyncDialog
      v-model:visible="syncDialogVisible"
      :sync-form="syncForm"
      :connection-options="connectionOptions"
      :sync-check-result="syncCheckResult"
      :sync-preview-result="syncPreviewResult"
      :sync-logs="syncLogs"
      :connection-loading="connectionLoading"
      :strategy-loading="strategyLoading"
      :strategy-saving="strategySaving"
      :sync-task-creating="syncTaskCreating"
      :checking="checking"
      :previewing="previewing"
      :syncing="syncing"
      :sync-busy="syncBusy"
      @provider-change="handleSyncProviderChange"
      @connection-change="handleSyncConnectionChange"
      @clear-results="clearSyncResults"
      @save-strategy="handleSaveSyncStrategy"
      @reload-strategy="handleReloadSyncStrategy"
      @create-task="handleCreateContactSyncTask"
      @check="handleCheckSyncContacts"
      @preview="handlePreviewSyncContacts"
      @sync="handleSyncContacts"
      @open-log-detail="openSyncLogDetail"
    />

    <!-- 同步日志详情对话框 -->
    <SyncLogDetailDialog
      v-model:visible="syncLogDetailVisible"
      :current-sync-log="currentSyncLog"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api/user'
import { integrationApi } from '@/api/integration'
import { taskApi } from '@/api/monitor'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { formatDate } from '@/utils/format'
import type {
  ContactSyncCheckResult,
  ContactSyncLogItem,
  ContactSyncPreviewResult,
  ContactSyncRequest,
  ContactSyncResult,
  ContactSyncStrategy,
  IntegrationConnection,
  UserListItem,
  RoleInfo,
  DeptInfo,
} from '@/types'
import FormDialog from './components/FormDialog.vue'
import RoleDialog from './components/RoleDialog.vue'
import SyncDialog from './components/SyncDialog.vue'
import SyncLogDetailDialog from './components/SyncLogDetailDialog.vue'

// ── 列表 ──────────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<UserListItem[]>([])
const total = ref(0)
const switchLoadingId = ref<number | null>(null)

type SourceTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'
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
const router = useRouter()

interface SourceProviderMeta {
  label: string
  tagType: SourceTagType
}

const SOURCE_PROVIDER_MAP: Record<string, SourceProviderMeta> = {
  feishu: { label: '飞书', tagType: 'primary' },
  dingtalk: { label: '钉钉', tagType: 'warning' },
  wecom: { label: '企业微信', tagType: 'success' },
  custom: { label: '自定义', tagType: 'info' },
}

function getSourceProviderMeta(provider?: string | null): SourceProviderMeta {
  const providerCode = provider?.trim()
  if (!providerCode) {
    return { label: '-', tagType: 'info' }
  }
  return SOURCE_PROVIDER_MAP[providerCode] || { label: providerCode, tagType: 'info' }
}

function getSourceProviderLabel(provider?: string | null) {
  return getSourceProviderMeta(provider).label
}

function getSourceProviderTagType(provider?: string | null) {
  return getSourceProviderMeta(provider).tagType
}

function getSourceProviderTooltip(row: UserListItem) {
  const providerLabel = getSourceProviderLabel(row.source_provider)
  const details = [
    `来源：${providerLabel}`,
    row.source_connection_name ? `连接：${row.source_connection_name}` : '',
    row.source_external_id ? `外部ID：${row.source_external_id}` : '',
  ].filter(Boolean)
  return details.join('；')
}

function getAvatarText(row: UserListItem) {
  const displayName = row.nickname || row.username || ''
  return displayName.trim().slice(0, 1).toUpperCase() || '用'
}

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as number | undefined,
})

async function fetchList() {
  loading.value = true
  try {
    const res = await userApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.status = undefined
  query.page = 1
  fetchList()
}

async function toggleActive(row: UserListItem) {
  const newStatus = row.status === 1 ? 0 : 1
  switchLoadingId.value = row.id
  try {
    await userApi.update(row.id, { status: newStatus })
    row.status = newStatus
    ElMessage.success(`用户已${newStatus === 1 ? '启用' : '禁用'}`)
  } catch {
    // 失败时不更新状态
  } finally {
    switchLoadingId.value = null
  }
}

async function handleDelete(row: UserListItem) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

async function handleResetPwd(row: UserListItem) {
  const newPwd = 'ruoming@2024'
  await ElMessageBox.confirm(`重置用户「${row.username}」密码为 ${newPwd}？`, '确认', { type: 'warning' })
  await userApi.resetPassword(row.id, newPwd)
  ElMessage.success('密码已重置')
}

// ── 部门选项 ──────────────────────────────────────────────────────────────────
const deptOptions = ref<DeptInfo[]>([])

async function fetchDeptOptions() {
  try {
    const res = await systemApi.deptOptions()
    deptOptions.value = res.data
  } catch {
    deptOptions.value = []
  }
}

// ── 新增/编辑 ─────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const editRow = ref<UserListItem | null>(null)

function openDialog(row?: UserListItem) {
  editRow.value = row ?? null
  dialogVisible.value = true
}

async function handleFormSubmit(form: Record<string, unknown>) {
  if (editRow.value?.id) {
    await userApi.update(editRow.value.id, { nickname: form.nickname, email: form.email, phone: form.phone, dept_id: form.dept_id })
    ElMessage.success('更新成功')
  } else {
    await userApi.create(form as any)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

// ── 分配角色 ──────────────────────────────────────────────────────────────────
const roleDialogVisible = ref(false)
const allRoles = ref<RoleInfo[]>([])

async function openRoleDialog(row: UserListItem) {
  editRow.value = row
  if (!allRoles.value.length) {
    const res = await permissionApi.roleList({ page_size: 200 })
    allRoles.value = res.data.items
  }
  roleDialogVisible.value = true
}

async function handleRoleSubmit(userId: number, roleIds: number[]) {
  await userApi.assignRoles(userId, roleIds)
  ElMessage.success('角色分配成功')
  roleDialogVisible.value = false
  fetchList()
}

// ── 外部通讯录同步 ────────────────────────────────────────────────────────────
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

const syncForm = reactive({
  provider: 'wecom' as 'feishu' | 'wecom' | 'dingtalk',
  connection_id: undefined as number | undefined,
  ...DEFAULT_SYNC_STRATEGY,
})

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
    connectionOptions.value = (res.data || []).filter(item => item.capabilities.includes('contact_sync'))
    if (!connectionOptions.value.some(item => item.id === syncForm.connection_id)) {
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

async function handleReloadSyncStrategy() {
  await loadSelectedContactSyncStrategy(true)
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
  const connection = connectionOptions.value.find(item => item.id === syncForm.connection_id)
  const taskName = `${connection?.name || getSourceProviderLabel(syncForm.provider)} 通讯录每日同步`

  syncTaskCreating.value = true
  try {
    const existingTasks = await taskApi.list({
      page: 1,
      page_size: 200,
      func_name: CONTACT_SYNC_TASK_FUNC,
    })
    const existingTask = (existingTasks.data.items as ScheduledTaskItem[] | undefined)?.find(
      item => Number(item.kwargs?.connection_id) === syncForm.connection_id
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
      `将在系统“计划任务”中新增一条停用记录「${taskName}」，任务会复用当前连接保存的默认策略。创建后可在计划任务中修改周期、启停和查看执行日志。`,
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
      const confirmed = await confirmOrCancel(checkResult.summary || '同步自检存在警告，仍要继续同步？', '自检警告')
      if (!confirmed) {
        return
      }
    }
    const confirmed = await confirmOrCancel(`同步会创建或更新${getSyncContentLabel()}，确认开始？`, '确认同步')
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
    fetchDeptOptions()
    fetchList()
  } finally {
    syncing.value = false
  }
}

async function confirmOrCancel(message: string, title: string) {
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

function normalizeSyncStrategy(strategy: Partial<ContactSyncStrategy> | null | undefined): ContactSyncStrategy {
  const usernameStrategy = Array.isArray(strategy?.username_strategy)
    ? strategy.username_strategy.filter(isUsernameStrategy)
    : []
  const nicknameStrategy = Array.isArray(strategy?.nickname_strategy)
    ? strategy.nickname_strategy.filter(isNicknameStrategy)
    : []
  const emailUpdateMode = normalizeFieldUpdateMode(
    strategy?.email_update_mode,
    strategy?.overwrite_email,
    DEFAULT_SYNC_STRATEGY.email_update_mode
  )
  const phoneUpdateMode = normalizeFieldUpdateMode(
    strategy?.phone_update_mode,
    strategy?.overwrite_phone,
    DEFAULT_SYNC_STRATEGY.phone_update_mode
  )
  const departmentUpdateMode = normalizeFieldUpdateMode(
    strategy?.department_update_mode,
    strategy?.overwrite_department,
    DEFAULT_SYNC_STRATEGY.department_update_mode
  )

  return {
    sync_departments: typeof strategy?.sync_departments === 'boolean' ? strategy.sync_departments : DEFAULT_SYNC_STRATEGY.sync_departments,
    sync_users: typeof strategy?.sync_users === 'boolean' ? strategy.sync_users : DEFAULT_SYNC_STRATEGY.sync_users,
    sync_avatar: typeof strategy?.sync_avatar === 'boolean' ? strategy.sync_avatar : DEFAULT_SYNC_STRATEGY.sync_avatar,
    disable_missing_users: typeof strategy?.disable_missing_users === 'boolean' ? strategy.disable_missing_users : DEFAULT_SYNC_STRATEGY.disable_missing_users,
    username_strategy: usernameStrategy.length ? usernameStrategy : [...DEFAULT_SYNC_STRATEGY.username_strategy],
    nickname_strategy: nicknameStrategy.length ? nicknameStrategy : [...DEFAULT_SYNC_STRATEGY.nickname_strategy],
    overwrite_email: emailUpdateMode === 'always',
    overwrite_phone: phoneUpdateMode === 'always',
    overwrite_department: departmentUpdateMode === 'always',
    email_update_mode: emailUpdateMode,
    phone_update_mode: phoneUpdateMode,
    department_update_mode: departmentUpdateMode,
  }
}

function applySyncStrategy(strategy: ContactSyncStrategy) {
  syncForm.sync_departments = strategy.sync_departments
  syncForm.sync_users = strategy.sync_users
  syncForm.sync_avatar = strategy.sync_avatar
  syncForm.disable_missing_users = strategy.disable_missing_users
  syncForm.username_strategy = [...strategy.username_strategy] as UsernameStrategy[]
  syncForm.nickname_strategy = [...strategy.nickname_strategy] as NicknameStrategy[]
  syncForm.overwrite_email = strategy.overwrite_email
  syncForm.overwrite_phone = strategy.overwrite_phone
  syncForm.overwrite_department = strategy.overwrite_department
  syncForm.email_update_mode = strategy.email_update_mode
  syncForm.phone_update_mode = strategy.phone_update_mode
  syncForm.department_update_mode = strategy.department_update_mode
}

function isUsernameStrategy(value: unknown): value is UsernameStrategy {
  return usernameStrategyOptions.some(item => item.value === value)
}

function isNicknameStrategy(value: unknown): value is NicknameStrategy {
  return nicknameStrategyOptions.some(item => item.value === value)
}

function isFieldUpdateMode(value: unknown): value is FieldUpdateMode {
  return fieldUpdateModeOptions.some(item => item.value === value)
}

function normalizeFieldUpdateMode(
  mode: unknown,
  legacyOverwrite: unknown,
  defaultMode: FieldUpdateMode
): FieldUpdateMode {
  if (isFieldUpdateMode(mode)) {
    return mode
  }
  if (typeof legacyOverwrite === 'boolean') {
    return legacyOverwrite ? 'always' : 'never'
  }
  return defaultMode
}

function pickDefaultSyncConnection() {
  return connectionOptions.value.find((item: IntegrationConnection) => item.is_default) || connectionOptions.value[0]
}

function getSyncContentLabel() {
  const items = [
    syncForm.sync_departments ? '部门' : '',
    syncForm.sync_users ? '用户资料' : '',
    syncForm.sync_avatar ? '头像' : '',
  ].filter(Boolean)
  return items.length ? items.join('、') : '选中的内容'
}

async function fetchSyncLogs() {
  syncLogLoading.value = true
  try {
    const res = await userApi.contactSyncLogs({
      provider: syncForm.provider,
      limit: 5,
    })
    syncLogs.value = res.data || []
  } finally {
    syncLogLoading.value = false
  }
}

function openSyncLogDetail(row: ContactSyncLogItem) {
  currentSyncLog.value = row
  syncLogDetailVisible.value = true
}

onMounted(() => {
  fetchList()
  fetchDeptOptions()
})
</script>

<style lang="scss" scoped>
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mt-4 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }
.text-muted { color: var(--el-text-color-secondary); }
</style>