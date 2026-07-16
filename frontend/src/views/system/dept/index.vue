<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">部门管理</span>
        <el-button type="primary" :icon="Plus"  v-permission="'system:dept:create'" @click="openDialog()">
          新增部门
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="deptTree"
        row-key="id"
        :tree-props="{ children: 'children', hasChildren: 'children' }"
        :default-expand-all="true"
        border
        class="tree-table"
      >
        <el-table-column prop="name" label="部门名称" min-width="180">
          <template #default="{ row }">
            <div class="tree-cell">
              <el-icon class="dept-icon"><Office /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="70" align="center" />
        <el-table-column prop="leader" label="负责人" width="100" />
        <el-table-column prop="phone" label="联系电话" width="120" />
        <el-table-column prop="status" label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row, row.id)">子部门</el-button>
            <el-button link type="primary" size="small" v-permission="'system:dept:update'" @click="openDialog(row)">编辑</el-button>
            <el-button
              link type="danger"
              size="small"
              v-permission="'system:dept:delete'"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增/编辑部门 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑部门' : '新增部门'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="form.parent_id"
            :data="deptOptions"
            :props="{ label: 'name', children: 'children' }"
            node-key="id"
            value-key="id"
            check-strictly
            placeholder="请选择上级部门（空=根部门）"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.leader" placeholder="请输入负责人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
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
import { Plus, OfficeBuilding as Office } from '@element-plus/icons-vue'
import { systemApi, type DeptInfo, type DeptCreate } from '@/api/system'
import { useCommonStatus } from '@/hooks/useDict'

// 通用状态字典
const { tagType: getStatusTagType, label: getStatusLabel } = useCommonStatus()

// ── 部门列表 ──────────────────────────────────────────────────────────────────
const loading = ref(false)
const deptTree = ref<DeptInfo[]>([])
const deptOptions = ref<DeptInfo[]>([])

async function fetchDepts() {
  loading.value = true
  try {
    const [treeRes, optionsRes] = await Promise.all([
      systemApi.deptTree(),
      systemApi.deptOptions(),
    ])
    deptTree.value = treeRes.data
    deptOptions.value = [{ id: 0, parent_id: 0, name: '根部门', ancestors: null, level: 0, sort: 0, leader: null, phone: null, email: null, status: 1, tenant_id: null, remark: null }, ...optionsRes.data]
  } finally {
    loading.value = false
  }
}

async function handleDelete(row: DeptInfo) {
  await ElMessageBox.confirm(`确定删除部门「${row.name}」？`, '警告', { type: 'warning' })
  await systemApi.deptDelete(row.id)
  ElMessage.success('删除成功')
  fetchDepts()
}

// ── 新增/编辑 ─────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive<DeptCreate & { sort: number; status: number }>({
  parent_id: 0,
  name: '',
  sort: 0,
  leader: '',
  phone: '',
  email: '',
  status: 1,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入部门名称' }],
  sort: [{ required: true, message: '请输入排序' }],
}

function openDialog(row?: DeptInfo, defaultParentId?: number) {
  editId.value = row?.id && !defaultParentId ? row.id : null
  Object.assign(form, {
    parent_id: defaultParentId ?? row?.parent_id ?? 0,
    name: row && !defaultParentId ? row.name : '',
    sort: row && !defaultParentId ? row.sort : 0,
    leader: row && !defaultParentId ? row.leader ?? '' : '',
    phone: row && !defaultParentId ? row.phone ?? '' : '',
    email: row && !defaultParentId ? row.email ?? '' : '',
    status: row && !defaultParentId ? row.status : 1,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await systemApi.deptUpdate(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await systemApi.deptCreate(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchDepts()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchDepts)
</script>

<style lang="scss" scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }

.tree-table {
  :deep(.el-table__body tr:hover > td) {
    background-color: #fafafa;
  }

  :deep(.el-table__cell) {
    .cell {
      display: flex;
      align-items: center;
    }
  }

  :deep(.el-table__indent) {
    width: 32px;
    padding-left: 8px;
  }

  :deep(.el-table__expand-icon) {
    margin-right: 4px;
    font-size: 12px;
    color: #909399;
  }
}

.tree-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.dept-icon {
  color: #409eff;
  font-size: 14px;
  width: 16px;
  flex-shrink: 0;
}
</style>
