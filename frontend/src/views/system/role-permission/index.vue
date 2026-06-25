<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">角色授权</span>
      </div>

      <el-row :gutter="16" class="role-auth-row">
        <el-col :span="8">
          <div class="left-panel">
            <div class="panel-section">
              <div class="section-header">
                <span class="section-title">角色列表</span>
                <el-input
                  v-model="keyword"
                  placeholder="搜索"
                  size="small"
                  class="search-input"
                  clearable
                  @input="fetchRoles"
                />
              </div>
              <el-tree
                :data="roles"
                :props="{ label: 'name', children: 'children' }"
                node-key="id"
                default-expand-all
                :highlight-current="true"
                :current-node-key="currentRoleId"
                @node-click="handleRoleSelect"
                class="role-tree"
              >
                <template #default="{ node, data }">
                  <span class="tree-node">
                    <el-tag v-if="data.is_system" type="info" size="small" class="mr-2">内置</el-tag>
                    {{ node.label }}
                    <span class="text-gray text-sm ml-2">{{ data.code }}</span>
                  </span>
                </template>
              </el-tree>
            </div>

            <div class="panel-section">
              <div class="section-header">
                <span class="section-title">数据授权</span>
              </div>
              <div v-if="currentRole" class="data-auth-form">
                <el-form-item label="数据范围">
                  <el-select v-model="dataScopeForm.data_scope" style="width:100%" @change="onDataScopeChange">
                    <el-option v-for="opt in scopeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="dataScopeForm.data_scope === 5" label="授权部门">
                  <el-tree-select
                    v-model="dataScopeForm.data_scope_depts"
                    :data="deptOptions"
                    :props="{ label: 'name', value: 'id', children: 'children', checkStrictly: true }"
                    multiple
                    placeholder="请选择授权部门"
                    clearable
                    style="width: 100%"
                  />
                </el-form-item>
                <el-button type="primary" size="small" :loading="savingData" @click="saveDataScope">
                  保存数据授权
                </el-button>
              </div>
              <el-empty v-else description="请选择角色" />
            </div>
          </div>
        </el-col>

        <el-col :span="16">
          <div class="right-panel">
            <el-empty v-if="!currentRole" description="请选择左侧角色" />

            <template v-else>
              <div class="perm-header">
                <span class="perm-title">「{{ currentRole.name }}」的菜单权限</span>
                <el-button
                  type="primary"
                  size="small"
                  :loading="savingPerm"
                  @click="savePermissions"
                >
                  保存菜单权限
                </el-button>
              </div>

              <div class="perm-tree-wrapper">
                <el-tree
                  ref="treeRef"
                  v-loading="permLoading"
                  :data="permTree"
                  :props="{ label: 'name', children: 'children' }"
                  show-checkbox
                  node-key="id"
                  :default-checked-keys="checkedPermIds"
                  :default-expanded-keys="expandedKeys"
                  :indent="32"
                  class="perm-tree"
                >
                  <template #default="{ node, data }">
                    <span class="tree-node">
                      <el-icon class="menu-icon" :color="typeTagMap[data.type] ? '#409eff' : '#909399'">
                        <component :is="getIcon(data.icon, data.type)" />
                      </el-icon>
                      <el-tag
                        :type="(typeTagMap[data.type] || 'info') as 'primary' | 'success' | 'warning' | 'info' | 'danger'"
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
            </template>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, type PermissionItem, type RoleInfo, type DeptInfo } from 'element-plus'
import { Search, Menu, Setting, List, Link, Box } from '@element-plus/icons-vue'
import * as ElIcons from '@element-plus/icons-vue'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { useDataScope } from '@/hooks/useDict'

const { options: scopeOptions } = useDataScope()

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

const keyword = ref('')
const roles = ref<RoleInfo[]>([])
const currentRoleId = ref<number | null>(null)
const currentRole = ref<RoleInfo | null>(null)
const deptOptions = ref<DeptInfo[]>([])

const dataScopeForm = reactive({
  data_scope: 1,
  data_scope_depts: [] as number[],
})
const savingData = ref(false)

const treeRef = ref()
const permTree = ref<PermissionItem[]>([])
const permLoading = ref(false)
const checkedPermIds = ref<number[]>([])
const savingPerm = ref(false)
const expandedKeys = ref<number[]>([])

function collectLevel2Keys(items: PermissionItem[], level: number): number[] {
  const keys: number[] = []
  for (const item of items) {
    if (level <= 2) {
      keys.push(item.id)
    }
    if (item.children && item.children.length) {
      keys.push(...collectLevel2Keys(item.children, level + 1))
    }
  }
  return keys
}

async function fetchRoles() {
  const res = await permissionApi.roleList({ page_size: 500, keyword: keyword.value })
  roles.value = res.data.items
}

async function fetchDeptOptions() {
  const res = await systemApi.deptOptions()
  deptOptions.value = res.data
}

async function loadRoleData(roleId: number) {
  const permRes = await permissionApi.getRolePermissions(roleId)
  checkedPermIds.value = permRes.data.permission_ids || []

  const roleRes = await permissionApi.roleList({ page_size: 200 })
  const role = roleRes.data.items.find(r => r.id === roleId)
  if (role) {
    dataScopeForm.data_scope = role.data_scope ?? 1
    if (role.data_scope_depts) {
      try {
        dataScopeForm.data_scope_depts = JSON.parse(role.data_scope_depts as unknown as string)
      } catch {
        dataScopeForm.data_scope_depts = []
      }
    } else {
      dataScopeForm.data_scope_depts = []
    }
  }
}

async function handleRoleSelect(node: unknown) {
  const role = node as RoleInfo
  currentRoleId.value = role.id
  currentRole.value = role

  if (!permTree.value.length) {
    permLoading.value = true
    const res = await permissionApi.permissionTree()
    permTree.value = res.data
    expandedKeys.value = collectLevel2Keys(permTree.value, 1)
    permLoading.value = false
  }

  await loadRoleData(role.id)

  nextTick(() => {
    treeRef.value?.setCheckedKeys(checkedPermIds.value)
  })
}

async function savePermissions() {
  if (!currentRole.value) return
  savingPerm.value = true
  try {
    const ids: number[] = treeRef.value?.getCheckedKeys() ?? []
    await permissionApi.assignPermissions(currentRole.value.id, ids)
    ElMessage.success('菜单权限保存成功')
  } finally {
    savingPerm.value = false
  }
}

function onDataScopeChange(val: number) {
  if (val !== 5) {
    dataScopeForm.data_scope_depts = []
  }
}

async function saveDataScope() {
  if (!currentRole.value) return
  savingData.value = true
  try {
    await permissionApi.roleUpdate(currentRole.value.id, {
      data_scope: dataScopeForm.data_scope,
      data_scope_depts: dataScopeForm.data_scope_depts,
    })
    ElMessage.success('数据授权保存成功')
  } finally {
    savingData.value = false
  }
}

async function initDefaultRole() {
  if (roles.value.length > 0) {
    await handleRoleSelect(roles.value[0])
  }
}

onMounted(async () => {
  await fetchRoles()
  await fetchDeptOptions()
  await initDefaultRole()
})
</script>

<style lang="scss" scoped>
.role-auth-row {
  height: calc(100vh - 200px);
  display: flex;
}

.role-auth-row > .el-col {
  height: 100%;
  overflow: hidden;
}

.left-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color);
  padding-right: 12px;
  gap: 12px;
}

.panel-section {
  background: var(--el-bg-color);
  border-radius: var(--el-border-radius-base);
  border: 1px solid var(--el-border-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-section:first-child {
  flex: 1;
  min-height: 0;
}

.panel-section:last-child {
  flex: 1;
  min-height: 0;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
}

.search-input {
  width: 140px;
}

.role-tree {
  flex: 1;
  overflow: auto;
  padding: 8px;
  min-height: 0;
}

.data-auth-form {
  flex: 1;
  overflow: auto;
  padding: 12px;
  min-height: 0;
}

.right-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.perm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.perm-title {
  font-size: 15px;
  font-weight: 600;
}

.perm-tree-wrapper {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

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