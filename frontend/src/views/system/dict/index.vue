<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-form inline class="search-form" @submit.prevent="loadDictTypes" style="flex: 1;">
          <el-form-item label="关键词">
            <el-input v-model="query.keyword" placeholder="名称 / 编码" clearable style="width:200px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
              <el-option label="正常" :value="1" />
              <el-option label="停用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="loadDictTypes">查询</el-button>
            <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <el-button type="primary" :icon="Plus" v-permission="'system:dict:create'" @click="openDictTypeDialog()">
          新增字典类型
        </el-button>
      </div>

      <el-divider />

      <!-- 表格 -->
      <el-table :data="dictTypes" border style="width: 100%">
        <el-table-column prop="name" label="字典名称" min-width="150" />
        <el-table-column prop="code" label="字典编码" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_system" label="系统内置" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" type="info">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDictItems(row)">字典项</el-button>
            <el-button type="primary" link v-permission="'system:dict:update'" @click="openDictTypeDialog(row)">编辑</el-button>
            <el-button type="danger" link v-permission="'system:dict:delete'" :disabled="row.is_system" @click="deleteDictType(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="字典名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入字典名称" />
        </el-form-item>
        <el-form-item label="字典编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入字典编码" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
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
        <el-button type="primary" @click="submitDictType">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="itemsVisible" title="字典项管理" width="800px" :max-height="500" scrollable>
      <div class="items-header">
        <el-input v-model="itemFilter" placeholder="搜索字典项" style="width: 200px; margin-bottom: 15px" />
        <el-button type="primary" :icon="Plus" @click="openDictItemDialog()" style="float: right">新增字典项</el-button>
      </div>API Base URL

      <el-table :data="filteredItems" border style="width: 100%">
        <el-table-column prop="label" label="显示标签" min-width="120" />
        <el-table-column prop="value" label="实际值" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="150" />
        <el-table-column prop="is_default" label="默认值" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="70" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDictItemDialog(row)">编辑</el-button>
            <el-button type="danger" link @click="deleteDictItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog v-model="itemDialogVisible" :title="itemDialogTitle" width="500px">
        <el-form :model="itemForm" :rules="itemRules" ref="itemFormRef" label-width="100px">
          <el-form-item label="显示标签" prop="label">
            <el-input v-model="itemForm.label" placeholder="请输入显示标签" />
          </el-form-item>
          <el-form-item label="实际值" prop="value">
            <el-input v-model="itemForm.value" placeholder="请输入实际值" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="itemForm.description" type="textarea" placeholder="请输入描述" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="itemForm.sort" :min="0" />
          </el-form-item>
          <el-form-item label="是否默认">
            <el-switch v-model="itemForm.is_default" />
          </el-form-item>
          <el-form-item label="状态">
            <el-radio-group v-model="itemForm.status">
              <el-radio :value="1">正常</el-radio>
              <el-radio :value="0">停用</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="样式类">
            <el-input v-model="itemForm.css_class" placeholder="如 el-tag--success" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="itemDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitDictItem">确定</el-button>
        </template>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox, ElForm } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { dictApi } from '@/api/dict'
import type { DictTypeInfo, DictItemInfo } from '@/types'

const dictTypes = ref<DictTypeInfo[]>([])
const dialogVisible = ref(false)
const itemsVisible = ref(false)
const itemDialogVisible = ref(false)
const formRef = ref<InstanceType<typeof ElForm>>()
const itemFormRef = ref<InstanceType<typeof ElForm>>()
const editId = ref<number | null>(null)
const currentTypeId = ref<number>(0)
const dictItems = ref<DictItemInfo[]>([])
const itemFilter = ref('')
const itemEditId = ref<number | null>(null)

// 搜索参数
const query = reactive({
  keyword: '',
  status: undefined as number | undefined,
})

const form = ref({
  name: '',
  code: '',
  description: '',
  sort: 0,
  status: 1,
})

const itemForm = ref({
  type_id: 0,
  label: '',
  value: '',
  description: '',
  sort: 0,
  status: 1,
  is_default: false,
  css_class: '',
})

const rules = {
  name: [{ required: true, message: '请输入字典名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入字典编码', trigger: 'blur' }],
}

const itemRules = {
  label: [{ required: true, message: '请输入显示标签', trigger: 'blur' }],
  value: [{ required: true, message: '请输入实际值', trigger: 'blur' }],
}

const dialogTitle = computed(() => {
  if (!editId.value) return '新增字典类型'
  return '编辑字典类型'
})

const itemDialogTitle = computed(() => {
  if (!itemEditId.value) return '新增字典项'
  return '编辑字典项'
})

const filteredItems = computed(() => {
  if (!itemFilter.value) return dictItems.value
  return dictItems.value.filter(item =>
    item.label.includes(itemFilter.value) || item.value.includes(itemFilter.value)
  )
})

async function loadDictTypes() {
  const res = await dictApi.getDictTypes(query)
  dictTypes.value = res.data
}

function resetQuery() {
  query.keyword = ''
  query.status = undefined
  loadDictTypes()
}

async function loadDictItems(typeId: number) {
  const res = await dictApi.getDictItems(typeId)
  dictItems.value = res.data
}

function openDictTypeDialog(row?: DictTypeInfo) {
  formRef.value?.resetFields()
  if (row) {
    editId.value = row.id
    form.value = { ...row }
  } else {
    editId.value = null
    form.value = { name: '', code: '', description: '', sort: 0, status: 1 }
  }
  dialogVisible.value = true
}

async function submitDictType() {
  await formRef.value?.validate()
  if (editId.value) {
    await dictApi.updateDictType(editId.value, form.value)
    ElMessage.success('更新成功')
  } else {
    await dictApi.createDictType(form.value)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  await loadDictTypes()
}

async function deleteDictType(row: DictTypeInfo) {
  await ElMessageBox.confirm(`确定删除字典类型「${row.name}」？`, '警告', { type: 'warning' })
  await dictApi.deleteDictType(row.id)
  ElMessage.success('删除成功')
  await loadDictTypes()
}

function viewDictItems(row: DictTypeInfo) {
  currentTypeId.value = row.id
  loadDictItems(row.id)
  itemsVisible.value = true
}

function openDictItemDialog(row?: DictItemInfo) {
  itemFormRef.value?.resetFields()
  itemForm.value.type_id = currentTypeId.value
  if (row) {
    itemEditId.value = row.id
    itemForm.value = { ...row }
  } else {
    itemEditId.value = null
    itemForm.value = { type_id: currentTypeId.value, label: '', value: '', description: '', sort: 0, status: 1, is_default: false, css_class: '' }
  }
  itemDialogVisible.value = true
}

async function submitDictItem() {
  await itemFormRef.value?.validate()
  if (itemEditId.value) {
    await dictApi.updateDictItem(itemEditId.value, itemForm.value)
    ElMessage.success('更新成功')
  } else {
    await dictApi.createDictItem(itemForm.value)
    ElMessage.success('创建成功')
  }
  itemDialogVisible.value = false
  await loadDictItems(currentTypeId.value)
}

async function deleteDictItem(row: DictItemInfo) {
  await ElMessageBox.confirm(`确定删除字典项「${row.label}」？`, '警告', { type: 'warning' })
  await dictApi.deleteDictItem(row.id)
  ElMessage.success('删除成功')
  await loadDictItems(currentTypeId.value)
}

onMounted(() => {
  loadDictTypes()
})
</script>

<style scoped lang="scss">
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.items-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
