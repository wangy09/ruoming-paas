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
import { ref, reactive, onMounted, h } from 'vue'
import { ElMessage, ElMessageBox, ElButton } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api/user'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { formatDate } from '@/utils/format'
import type {
  UserListItem,
  RoleInfo,
  DeptInfo,
  UserFormData,
  UserUpdate,
  UserCreate,
} from '@/types'
import FormDialog from './components/FormDialog.vue'
import RoleDialog from './components/RoleDialog.vue'
import SyncDialog from './components/SyncDialog.vue'
import SyncLogDetailDialog from './components/SyncLogDetailDialog.vue'
import { useContactSync } from './composables/useContactSync'

// ── 列表 ──────────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<UserListItem[]>([])
const total = ref(0)
const switchLoadingId = ref<number | null>(null)

type SourceTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

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

function generateRandomPassword(length = 16): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%^&*'
  const array = new Uint32Array(length)
  crypto.getRandomValues(array)
  return Array.from(array, (n) => chars[n % chars.length]).join('')
}

async function handleResetPwd(row: UserListItem) {
  const newPwd = generateRandomPassword(16)
  await ElMessageBox.confirm(
    `即将重置用户「${row.username}」的密码，新密码将在重置后展示，请妥善保管。`,
    '确认重置密码',
    { type: 'warning' },
  )
  await userApi.resetPassword(row.id, newPwd)
  await ElMessageBox({
    title: '密码已重置',
    message: () =>
      h('div', { style: 'line-height: 1.8' }, [
        h('p', null, `用户「${row.username}」密码已重置：`),
        h(
          'div',
          { style: 'display: flex; align-items: center; gap: 8px; margin: 12px 0' },
          [
            h('code', { style: 'font-size: 16px; font-weight: 600; padding: 4px 12px; background: var(--el-fill-color-light); border-radius: 4px' }, newPwd),
            h(
              ElButton,
              {
                size: 'small',
                type: 'primary',
                plain: true,
                onClick: async () => {
                  await navigator.clipboard.writeText(newPwd)
                  ElMessage.success('密码已复制到剪贴板')
                },
              },
              () => '复制密码',
            ),
          ],
        ),
        h('p', { style: 'color: var(--el-text-color-secondary); font-size: 13px' }, '请将此密码安全地告知用户，并要求其首次登录后立即修改。'),
      ]),
    confirmButtonText: '我已保存',
    showCancelButton: false,
    closeOnClickModal: false,
  })
  fetchList()
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

async function handleFormSubmit(form: UserFormData) {
  if (editRow.value?.id) {
    const payload: UserUpdate = {
      nickname: form.nickname || undefined,
      email: form.email || undefined,
      phone: form.phone || undefined,
      dept_id: form.dept_id,
    }
    await userApi.update(editRow.value.id, payload)
    ElMessage.success('更新成功')
  } else {
    const payload: UserCreate = {
      username: form.username,
      password: form.password,
      nickname: form.nickname || undefined,
      email: form.email || undefined,
      phone: form.phone || undefined,
      dept_id: form.dept_id,
    }
    await userApi.create(payload)
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
const {
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
} = useContactSync()

setCallbacks(fetchList, fetchDeptOptions)

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
