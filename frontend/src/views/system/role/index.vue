<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">角色管理</span>
        <el-button type="primary" :icon="Plus" size="small" v-permission="'system:role:create'" @click="openDialog()">
          新增
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="roles"
        stripe
      >
        <el-table-column prop="name" label="角色名" min-width="120" />
        <el-table-column prop="code" label="权限码" min-width="140" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="系统内置" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" type="info" size="small">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据范围" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ getScopeLabel(row.data_scope) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
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
            :props="{ label: 'name', value: 'id', children: 'children', checkStrictly: true }"
            multiple
            placeholder="请选择授权部门"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
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
import { systemApi } from '@/api/system'
import { useDataScope } from '@/hooks/useDict'
import type { RoleInfo, DeptInfo } from '@/types'

const { options: scopeOptions, label: getScopeLabel } = useDataScope()

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

const deptOptions = ref<DeptInfo[]>([])

async function fetchDeptOptions() {
  const res = await systemApi.deptOptions()
  deptOptions.value = res.data
}

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
  status: 1,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入角色名' }],
  code: [{ required: true, message: '请输入权限码' }],
}

function onDataScopeChange(val: number) {
  if (val !== 2) {
    form.data_scope_depts = []
  }
}

function openDialog(row?: RoleInfo) {
  editId.value = row?.id ?? null

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
    status: row?.status ?? 1,
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
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }
</style>