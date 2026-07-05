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
          <template #default="{ row }">
            <el-avatar :size="36" :src="row.avatar || undefined">
              {{ getAvatarText(row) }}
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="nickname" label="用户昵称" min-width="120" show-overflow-tooltip />
        <el-table-column label="来源" min-width="130" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.source_provider"
              :content="getSourceProviderTooltip(row)"
              placement="top"
            >
              <el-tag :type="getSourceProviderTagType(row.source_provider)" size="small">
                {{ getSourceProviderLabel(row.source_provider) }}
              </el-tag>
            </el-tooltip>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="部门" min-width="120">
          <template #default="{ row }">
            {{ row.dept_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="role in row.roles"
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
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 1"
              :loading="switchLoadingId === row.id"
              @change="toggleActive(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="超管" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_superplatform" type="danger" size="small">超管</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link type="primary"
              v-permission="'system:user:update'"
              @click="openDialog(row)"
            >编辑</el-button>
            <el-button
              v-if="!row.is_superplatform"
              link type="warning"
              v-permission="'system:user:update'"
              @click="openRoleDialog(row)"
            >角色</el-button>
            <el-button
              link type="warning"
              v-permission="'system:user:reset-password'"
              @click="handleResetPwd(row)"
            >重置密码</el-button>
            <el-button
              v-if="!row.is_superplatform"
              link type="danger"
              v-permission="'system:user:delete'"
              @click="handleDelete(row)"
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
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑用户' : '新增用户'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editId" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="用户姓名" prop="nickname">
          <el-input v-model="form.nickname" placeholder="用户真实姓名或显示名称" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="form.dept_id"
            :data="deptOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            check-strictly
            placeholder="请选择部门（可选）"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="email@example.com" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="!editId" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色对话框 -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="480px" destroy-on-close>
      <el-checkbox-group v-model="selectedRoleIds">
        <div v-for="role in allRoles" :key="role.id" class="role-item">
          <el-checkbox :label="role.id" :value="role.id">
            <div>
              <span class="font-bold">{{ role.name }}</span>
              <span class="text-gray text-sm ml-2">{{ role.code }}</span>
            </div>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAssignRoles">确定</el-button>
      </template>
    </el-dialog>

    <!-- 通讯录同步对话框 -->
    <el-dialog v-model="syncDialogVisible" title="同步外部通讯录" width="520px" destroy-on-close>
      <el-alert
        title="第一版会同步部门、用户基础信息和头像 URL；默认不会禁用外部通讯录中缺失的本地用户。"
        type="info"
        show-icon
        :closable="false"
        class="mb-4"
      />
      <el-form label-width="110px">
        <el-form-item label="同步来源">
          <el-select v-model="syncForm.provider" style="width: 100%" @change="handleSyncProviderChange">
            <el-option label="飞书" value="feishu" />
            <el-option label="企业微信" value="wecom" />
            <el-option label="钉钉" value="dingtalk" />
          </el-select>
        </el-form-item>
        <el-form-item label="集成连接">
          <el-select
            v-model="syncForm.connection_id"
            filterable
            placeholder="请选择已启用通讯录同步的连接"
            style="width: 100%"
            :loading="connectionLoading"
          >
            <el-option
              v-for="item in connectionOptions"
              :key="item.id"
              :label="syncConnectionLabel(item)"
              :value="item.id"
            />
          </el-select>
          <div class="form-tip">
            同步会使用选中的连接凭证。飞书通讯录同步需要该连接已保存 App ID 和 App Secret。
          </div>
        </el-form-item>
        <el-form-item label="同步内容">
          <el-checkbox v-model="syncForm.sync_departments">部门</el-checkbox>
          <el-checkbox v-model="syncForm.sync_users">用户</el-checkbox>
          <el-checkbox v-model="syncForm.sync_avatar">头像</el-checkbox>
        </el-form-item>
        <el-form-item label="缺失用户">
          <el-switch
            v-model="syncForm.disable_missing_users"
            active-text="自动禁用"
            inactive-text="保持不变"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="syncDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="syncing" @click="handleSyncContacts">开始同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api/user'
import { integrationApi } from '@/api/integration'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { formatDate } from '@/utils/format'
import type { IntegrationConnection, UserListItem, RoleInfo, DeptInfo } from '@/types'

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

  // 后端暂未返回连接名或外部 ID 时，至少展示来源名称
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
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  password: '',
  dept_id: undefined as number | undefined,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }, { min: 6, message: '至少6位' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

function openDialog(row?: UserListItem) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    username: row?.username ?? '',
    nickname: row?.nickname ?? '',
    email: row?.email ?? '',
    phone: row?.phone ?? '',
    password: '',
    dept_id: (row as any)?.dept_id,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await userApi.update(editId.value, { nickname: form.nickname, email: form.email, phone: form.phone, dept_id: form.dept_id })
      ElMessage.success('更新成功')
    } else {
      await userApi.create(form as any)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

// ── 分配角色 ──────────────────────────────────────────────────────────────────
const roleDialogVisible = ref(false)
const allRoles = ref<RoleInfo[]>([])
const selectedRoleIds = ref<number[]>([])
const currentUserId = ref<number>(0)

async function openRoleDialog(row: UserListItem) {
  currentUserId.value = row.id
  selectedRoleIds.value = (row.roles || []).map((r: { id: number }) => r.id)
  if (!allRoles.value.length) {
    const res = await permissionApi.roleList({ page_size: 200 })
    allRoles.value = res.data.items
  }
  roleDialogVisible.value = true
}

async function handleAssignRoles() {
  submitting.value = true
  try {
    await userApi.assignRoles(currentUserId.value, selectedRoleIds.value)
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

// ── 外部通讯录同步 ────────────────────────────────────────────────────────────
const syncDialogVisible = ref(false)
const syncing = ref(false)
const connectionLoading = ref(false)
const connectionOptions = ref<IntegrationConnection[]>([])

const syncForm = reactive({
  provider: 'wecom' as 'feishu' | 'wecom' | 'dingtalk',
  connection_id: undefined as number | undefined,
  sync_departments: true,
  sync_users: true,
  sync_avatar: true,
  disable_missing_users: false,
})

async function openSyncDialog() {
  syncDialogVisible.value = true
  await fetchConnectionOptions()
}

async function handleSyncProviderChange() {
  syncForm.connection_id = undefined
  await fetchConnectionOptions()
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
  } finally {
    connectionLoading.value = false
  }
}

async function handleSyncContacts() {
  if (!syncForm.connection_id) {
    ElMessage.warning('请选择已启用通讯录同步的集成连接')
    return
  }
  if (!syncForm.sync_departments && !syncForm.sync_users) {
    ElMessage.warning('请至少选择一个同步内容')
    return
  }
  await ElMessageBox.confirm('同步会创建或更新部门、用户资料和头像，确认开始？', '确认同步', {
    type: 'warning',
  })
  syncing.value = true
  try {
    const res = await userApi.syncContacts({
      ...syncForm,
      connection_id: syncForm.connection_id,
    })
    const data = res.data
    ElMessage.success(
      `同步完成：部门新增 ${data.departments_created}、更新 ${data.departments_updated}；用户新增 ${data.users_created}、更新 ${data.users_updated}`
    )
    if (data.errors?.length) {
      ElMessage.warning(`同步完成但有 ${data.errors.length} 条提示，请查看接口返回详情`)
    }
    syncDialogVisible.value = false
    fetchDeptOptions()
    fetchList()
  } finally {
    syncing.value = false
  }
}

function pickDefaultSyncConnection() {
  return connectionOptions.value.find(item => item.is_default) || connectionOptions.value[0]
}

function syncConnectionLabel(item: IntegrationConnection) {
  return `${item.name}${item.is_default ? '（默认）' : ''}${item.secret_configured ? '' : '（未保存密钥）'}`
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
.mb-4 { margin-bottom: 16px; }
.mr-1 { margin-right: 4px; }
.ml-2 { margin-left: 8px; }
.text-muted { color: var(--el-text-color-secondary); }
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}
.role-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
}
</style>
