<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">菜单管理</span>
        <el-button type="primary" :icon="Plus" v-permission="'system:permission:create'" @click="openDialog()">
          新增菜单
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="permTree"
        row-key="id"
        :tree-props="{ children: 'children', hasChildren: 'children' }"
        :default-expand-all="false"
        border
        class="tree-table"
      >
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <div class="tree-cell">
              <el-icon class="menu-icon" :color="typeMap[row.type] ? '#409eff' : '#909399'">
                <component :is="getIcon(row.icon, row.type)" />
              </el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="权限码" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="typeMap[row.type]" size="small">{{ typeLabelMap[row.type] || row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路径/组件" min-width="200" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="70" align="center" />
        <el-table-column label="系统内置" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_system" color="#52c41a"><Check /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="可见" width="70" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_visible" color="#52c41a"><Check /></el-icon>
            <el-icon v-else color="#f56c6c"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" v-permission="'system:permission:create'" @click="openDialog(row, row.id)">新增子节点</el-button>
            <el-button link type="primary" size="small" v-permission="'system:permission:update'" @click="openDialog(row)">编辑</el-button>
            <el-button
              link type="danger"
              size="small"
              v-permission="'system:permission:delete'"
              :disabled="row.is_system"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="父节点">
          <el-cascader
            v-model="form.parent_id"
            :options="permTree"
            :props="{ label: 'name', value: 'id', children: 'children', checkStrictly: true, emitPath: false }"
            placeholder="顶级节点"
            clearable
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="form.type">
            <el-radio value="menu">菜单</el-radio>
            <el-radio value="button">按钮</el-radio>
            <el-radio value="column">列</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="菜单名称" />
        </el-form-item>
        <el-form-item label="权限码" prop="code">
          <el-input v-model="form.code" placeholder="如：system:user:create" />
        </el-form-item>
        <el-form-item v-if="form.type === 'menu'" label="路由路径">
          <el-input v-model="form.path" placeholder="/system/users" />
        </el-form-item>
        <el-form-item v-if="form.type === 'menu'" label="组件路径">
          <el-input v-model="form.component" placeholder="system/user/index" />
        </el-form-item>
        <el-form-item v-if="form.type === 'menu'" label="图标">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="9999" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Check, Close, Menu, Setting, List, Link, Box } from '@element-plus/icons-vue'
import * as ElIcons from '@element-plus/icons-vue'
import { permissionApi } from '@/api/permission'
import type { PermissionItem } from '@/types'

const typeMap: Record<string, string> = {
  menu: 'primary', button: 'success', column: 'warning', api: 'info', data: 'danger',
}
const typeLabelMap: Record<string, string> = {
  menu: '菜单', button: '按钮', column: '列', api: 'API', data: '数据',
}

const loading = ref(false)
const permTree = ref<PermissionItem[]>([])

async function fetchTree() {
  loading.value = true
  try {
    const res = await permissionApi.permissionTree()
    permTree.value = res.data
  } finally {
    loading.value = false
  }
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

async function handleDelete(row: PermissionItem) {
  await ElMessageBox.confirm(`确定删除菜单「${row.name}」？`, '警告', { type: 'warning' })
  await permissionApi.permissionDelete(row.id)
  ElMessage.success('删除成功')
  fetchTree()
}

const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  parent_id: undefined as number | undefined,
  type: 'button' as PermissionItem['type'],
  name: '',
  code: '',
  path: '',
  component: '',
  icon: '',
  sort_order: 0,
})

const rules: FormRules = {
  type: [{ required: true }],
  name: [{ required: true, message: '请输入名称' }],
  code: [{ required: true, message: '请输入权限码' }],
}

const dialogTitle = computed(() => {
  if (!editId.value) return '新增菜单'
  return '编辑菜单'
})

function openDialog(row?: PermissionItem, defaultParentId?: number) {
  editId.value = row?.id && !defaultParentId ? row.id : null
  Object.assign(form, {
    parent_id: defaultParentId ?? row?.parent_id,
    type: row && !defaultParentId ? row.type : 'button',
    name: row && !defaultParentId ? row.name : '',
    code: row && !defaultParentId ? row.code : '',
    path: row && !defaultParentId ? (row.path ?? '') : '',
    component: row && !defaultParentId ? (row.component ?? '') : '',
    icon: row && !defaultParentId ? (row.icon ?? '') : '',
    sort_order: row && !defaultParentId ? row.sort_order : 0,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    // 字段映射：前端 type -> 后端 perm_type，sort_order -> sort
    const payload = {
      parent_id: form.parent_id ?? 0,
      perm_type: form.type,
      name: form.name,
      code: form.code,
      path: form.path || undefined,
      component: form.component || undefined,
      icon: form.icon || undefined,
      sort: form.sort_order,
    }
    if (editId.value) {
      await permissionApi.permissionUpdate(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await permissionApi.permissionCreate(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTree()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchTree)
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

.menu-icon {
  font-size: 14px;
  width: 16px;
  flex-shrink: 0;
}

.tree-indent-line {
  width: 1px;
  height: 20px;
  background-color: #e4e7ed;
  margin-right: 6px;
  flex-shrink: 0;
}
</style>
