<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 搜索栏 -->
      <el-form inline class="search-form" @submit.prevent="fetchList">
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" placeholder="用户名 / 邮箱" clearable style="width:200px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.is_active" placeholder="全部" clearable style="width:120px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <!-- 工具栏 -->
      <div class="table-toolbar">
        <div class="flex gap-2">
          <el-button type="primary" :icon="Plus" v-permission="'system:user:create'" @click="openDialog()">
            新增用户
          </el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="nickname" label="昵称" min-width="120" show-overflow-tooltip />
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
              v-model="row.is_active"
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
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link type="primary"
              v-permission="'system:user:update'"
              @click="openDialog(row)"
            >编辑</el-button>
            <el-button
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
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="显示名称" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api/user'
import { permissionApi } from '@/api/permission'
import { formatDate } from '@/utils/format'
import type { UserListItem, RoleInfo } from '@/types'

// ── 列表 ──────────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<UserListItem[]>([])
const total = ref(0)
const switchLoadingId = ref<number | null>(null)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  is_active: undefined as boolean | undefined,
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
  query.is_active = undefined
  query.page = 1
  fetchList()
}

async function toggleActive(row: UserListItem) {
  switchLoadingId.value = row.id
  try {
    await userApi.update(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch {
    row.is_active = !row.is_active
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
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await userApi.update(editId.value, { nickname: form.nickname, email: form.email, phone: form.phone })
      ElMessage.success('更新成功')
    } else {
      await userApi.create(form)
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
  selectedRoleIds.value = row.roles.map(r => r.id)
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

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.table-toolbar { margin-bottom: 12px; }
.mt-4 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }
.ml-2 { margin-left: 8px; }
.role-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
}
</style>
