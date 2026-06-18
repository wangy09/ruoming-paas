<template>
  <div class="page-container">
    <el-row :gutter="16">
      <!-- 左：角色列表 -->
      <el-col :span="10">
        <div class="page-card h-full">
          <div class="card-header">
            <span class="card-title">角色列表</span>
            <el-button type="primary" :icon="Plus" size="small" v-permission="'system:role:create'" @click="openDialog()">
              新增
            </el-button>
          </div>

          <el-table
            v-loading="loading"
            :data="roles"
            stripe
            highlight-current-row
            @current-change="handleRoleSelect"
          >
            <el-table-column prop="name" label="角色名" min-width="120" />
            <el-table-column prop="code" label="权限码" min-width="140" />
            <el-table-column label="系统" width="60" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_system" type="info" size="small">系统</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <el-button link type="primary" v-permission="'system:role:update'" @click="openDialog(row)">编辑</el-button>
                <el-button
                  link type="danger"
                  v-permission="'system:role:delete'"
                  :disabled="row.is_system"
                  @click="handleDelete(row)"
                >删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <!-- 右：权限树 -->
      <el-col :span="14">
        <div class="page-card h-full">
          <div class="card-header">
            <span class="card-title">
              {{ currentRole ? `「${currentRole.name}」的权限` : '选择角色查看权限' }}
            </span>
            <el-button
              v-if="currentRole"
              type="primary"
              size="small"
              :loading="savingPerm"
              v-permission="'system:role:update'"
              @click="savePermissions"
            >
              保存权限
            </el-button>
          </div>

          <el-empty v-if="!currentRole" description="请选择左侧角色" />

          <el-tree
            v-else
            ref="treeRef"
            v-loading="permLoading"
            :data="permTree"
            :props="{ label: 'name', children: 'children' }"
            show-checkbox
            node-key="id"
            :default-checked-keys="checkedPermIds"
            check-strictly
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <el-tag
                  :type="typeTagMap[data.type] || 'info'"
                  size="small"
                  class="mr-1"
                >{{ data.type }}</el-tag>
                {{ node.label }}
                <span class="text-gray text-sm ml-1">{{ data.code }}</span>
              </span>
            </template>
          </el-tree>
        </div>
      </el-col>
    </el-row>

    <!-- 新增/编辑角色 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑角色' : '新增角色'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="角色名" prop="name">
          <el-input v-model="form.name" placeholder="如：租户管理员" />
        </el-form-item>
        <el-form-item label="权限码" prop="code">
          <el-input v-model="form.code" placeholder="如：tenant_admin" :disabled="!!editId" />
        </el-form-item>
        <el-form-item label="父角色">
          <el-select v-model="form.parent_id" placeholder="可选" clearable style="width:100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="form.data_scope" style="width:100%">
            <el-option label="全部数据" value="all" />
            <el-option label="本部门" value="dept" />
            <el-option label="本部门及子部门" value="dept_tree" />
            <el-option label="仅本人" value="self" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { permissionApi } from '@/api/permission'
import type { RoleInfo, PermissionItem } from '@/types'

const typeTagMap: Record<string, string> = {
  menu: 'primary', button: 'success', column: 'warning', api: 'info', data: 'danger',
}

// ── 角色列表 ──────────────────────────────────────────────────────────────────
const loading = ref(false)
const roles = ref<RoleInfo[]>([])

async function fetchRoles() {
  loading.value = true
  try {
    const res = await permissionApi.roleList({ page_size: 200 })
    roles.value = res.data.items
  } finally {
    loading.value = false
  }
}

async function handleDelete(row: RoleInfo) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」？`, '警告', { type: 'warning' })
  await permissionApi.roleDelete(row.id)
  ElMessage.success('删除成功')
  fetchRoles()
}

// ── 权限树 ────────────────────────────────────────────────────────────────────
const treeRef = ref()
const permTree = ref<PermissionItem[]>([])
const permLoading = ref(false)
const currentRole = ref<RoleInfo | null>(null)
const checkedPermIds = ref<number[]>([])
const savingPerm = ref(false)

async function handleRoleSelect(row: RoleInfo | null) {
  currentRole.value = row
  if (!row) return
  if (!permTree.value.length) {
    permLoading.value = true
    const res = await permissionApi.permissionTree()
    permTree.value = res.data
    permLoading.value = false
  }
  // TODO: 从后端获取该角色已有权限 ID 列表
  checkedPermIds.value = []
}

async function savePermissions() {
  if (!currentRole.value) return
  savingPerm.value = true
  try {
    const ids: number[] = treeRef.value?.getCheckedKeys() ?? []
    await permissionApi.assignPermissions(currentRole.value.id, ids)
    ElMessage.success('权限保存成功')
  } finally {
    savingPerm.value = false
  }
}

// ── 新增/编辑 ─────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  code: '',
  description: '',
  parent_id: undefined as number | undefined,
  data_scope: 'all',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入角色名' }],
  code: [{ required: true, message: '请输入权限码' }],
}

function openDialog(row?: RoleInfo) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    name: row?.name ?? '',
    code: row?.code ?? '',
    description: row?.description ?? '',
    parent_id: row?.parent_id,
    data_scope: row?.data_scope ?? 'all',
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await permissionApi.roleUpdate(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await permissionApi.roleCreate(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchRoles()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchRoles)
</script>

<style lang="scss" scoped>
.h-full { height: calc(100vh - 160px); overflow: auto; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }
.tree-node { display: flex; align-items: center; gap: 6px; }
.mr-1 { margin-right: 4px; }
.ml-1 { margin-left: 4px; }
</style>
