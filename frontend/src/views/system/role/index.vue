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
            <el-table-column label="系统内置" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_system" type="info" size="small">是</el-tag>
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
            :indent="32"
            class="perm-tree"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <el-icon class="menu-icon" :color="typeTagMap[data.type] ? '#409eff' : '#909399'">
                  <component :is="getIcon(data.icon, data.type)" />
                </el-icon>
                <el-tag
                  :type="typeTagMap[data.type] || 'info'"
                  size="small"
                  class="ml-1"
                >{{ typeLabelMap[data.type] || data.type }}</el-tag>
                <span class="ml-1">{{ node.label }}</span>
                <el-tooltip :content="data.code" placement="top">
                  <span class="text-gray text-sm ml-1">{{ data.code }}</span>
                </el-tooltip>
              </span>
            </template>
          </el-tree>
        </div>
      </el-col>
    </el-row>

    <!-- 新增/编辑角色 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑角色' : '新增角色'" width="520px" destroy-on-close>
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
        <el-form-item label="数据范围" prop="data_scope">
          <el-select v-model="form.data_scope" style="width:100%" @change="onDataScopeChange">
            <el-option v-for="opt in scopeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.data_scope === 5" label="授权部门">
          <el-tree-select
            v-model="form.data_scope_depts"
            :data="deptOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            multiple
            check-strictly
            placeholder="请选择授权部门"
            clearable
            style="width: 100%"
          />
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
import { Plus, Menu, Setting, List, Link, Box } from '@element-plus/icons-vue'
import * as ElIcons from '@element-plus/icons-vue'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { useDataScope } from '@/hooks/useDict'
import type { RoleInfo, PermissionItem, DeptInfo } from '@/types'

// 数据权限范围字典
const { options: scopeOptions, label: getScopeLabel } = useDataScope()

const typeTagMap: Record<string, string> = {
  menu: 'primary', button: 'success', column: 'warning',
}
const typeLabelMap: Record<string, string> = {
  menu: '菜单', button: '按钮', column: '列',
}
const typeIconMap: Record<string, unknown> = {
  menu: Menu,
  button: Setting,
  column: List,
  api: Link,
  data: Box,
}

function getIcon(iconName: string | undefined, type: string) {
  if (iconName) {
    return (ElIcons as Record<string, unknown>)[iconName] || typeIconMap[type] || Menu
  }
  return typeIconMap[type] || Menu
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

// ── 部门选项 ──────────────────────────────────────────────────────────────────
const deptOptions = ref<DeptInfo[]>([])

async function fetchDeptOptions() {
  const res = await systemApi.deptOptions()
  deptOptions.value = res.data
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
  data_scope: 1,
  data_scope_depts: [] as number[],
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入角色名' }],
  code: [{ required: true, message: '请输入权限码' }],
}

function onDataScopeChange(val: number) {
  // 切换到非自定义时清空部门选择
  if (val !== 2) {
    form.data_scope_depts = []
  }
}

function openDialog(row?: RoleInfo) {
  editId.value = row?.id ?? null

  // 解析 data_scope_depts JSON
  let dataScopeDepts: number[] = []
  if (row?.data_scope_depts) {
    try {
      dataScopeDepts = JSON.parse(row.data_scope_depts as unknown as string)
    } catch {
      dataScopeDepts = []
    }
  }

  Object.assign(form, {
    name: row?.name ?? '',
    code: row?.code ?? '',
    description: row?.description ?? '',
    parent_id: row?.parent_id,
    data_scope: row?.data_scope ?? 1,
    data_scope_depts: dataScopeDepts,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      ...form,
      parent_id: form.parent_id ?? 0,
    }
    if (editId.value) {
      await permissionApi.roleUpdate(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await permissionApi.roleCreate(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchRoles()
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchRoles()
  fetchDeptOptions()
})
</script>

<style lang="scss" scoped>
.h-full { height: calc(100vh - 160px); overflow: auto; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.menu-icon {
  font-size: 14px;
  width: 16px;
  flex-shrink: 0;
}

.text-gray { color: #909399; }

.perm-tree {
  :deep(.el-tree-node__content) {
    height: auto;
    padding: 6px 0;
  }

  :deep(.el-tree-node__expand-icon) {
    font-size: 12px;
    color: #909399;
    margin-right: 4px;
  }

  :deep(.el-tree-node__expand-icon.is-expanded) {
    color: #409eff;
  }

  :deep(.el-tree-node__expand-icon.is-leaf) {
    opacity: 0;
    width: 18px;
  }
}
</style>
