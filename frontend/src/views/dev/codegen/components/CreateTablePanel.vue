<template>
  <el-scrollbar class="table-list create-scroll">
    <div>
      <el-form :model="createForm" label-width="80px" size="small" class="create-form">
        <el-form-item label="表名" required>
          <el-input v-model="createForm.table_name" placeholder="如 customer_order" />
        </el-form-item>
        <el-form-item label="表注释">
          <el-input v-model="createForm.table_comment" placeholder="如 客户订单" />
        </el-form-item>
        <el-form-item label="模块名" required>
          <template #label>
            <span>模块名</span>
            <el-tooltip content="用于生成目录结构、API路径、路由路径。如 customer_order 会生成：backend/app/modules/customer_order/（Python用下划线）、/api/v1/customer-order/（API用连字符）" placement="top">
              <span class="tooltip-icon">?</span>
            </el-tooltip>
          </template>
          <el-input v-model="createForm.module_name" placeholder="如 customer_order" />
        </el-form-item>
        <el-form-item label="创建数据库表">
          <el-switch
            v-model="createForm.create_db_table"
            active-text="创建真实表"
            inactive-text="仅保存配置"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="small" @click="addField">添加字段</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="createFields" border stripe class="create-table" row-key="column_name">
        <el-table-column prop="column_name" label="字段名" width="120">
          <template #default="{ row }">
            <el-input v-model="row.column_name" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="column_comment" label="注释" width="120">
          <template #default="{ row }">
            <el-input v-model="row.column_comment" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="data_type" label="类型" width="100">
          <template #default="{ row }">
            <el-select v-model="(row as TableFieldConfig).data_type" size="small" @change="handleFieldTypeChange(row as TableFieldConfig)">
              <el-option v-for="ft in fieldTypes" :key="ft.type_name" :label="ft.display_name" :value="ft.type_name" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="长度" width="80">
          <template #default="{ row }">
            <el-input v-model.number="row.data_length" size="small" v-if="getTypeInfo(row.data_type)?.supports_length" />
          </template>
        </el-table-column>
        <el-table-column label="小数" width="60">
          <template #default="{ row }">
            <el-input v-model.number="row.data_scale" size="small" v-if="getTypeInfo(row.data_type)?.supports_scale" />
          </template>
        </el-table-column>
        <el-table-column label="可空" width="60">
          <template #default="{ row }">
            <el-switch v-model="row.is_nullable" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="主键" width="60">
          <template #default="{ row }">
            <el-switch v-model="row.is_primary_key" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="外键" width="140">
          <template #default="{ row }">
            <el-select v-model="row.foreign_key_table" size="small" placeholder="关联表" :disabled="!['INT', 'BIGINT', 'SMALLINT'].includes(row.data_type)">
              <el-option v-for="table in availableTables" :key="table.table_name" :label="table.table_comment || table.table_name" :value="table.table_name" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="column_default" label="默认值" width="100">
          <template #default="{ row }">
            <el-input v-model="row.column_default" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="表单组件" width="100">
          <template #default="{ row }">
            <el-select v-model="row.form_component" size="small">
              <el-option label="输入框" value="input" />
              <el-option label="下拉框" value="select" />
              <el-option label="数字框" value="number" />
              <el-option label="文本域" value="textarea" />
              <el-option label="开关" value="switch" />
              <el-option label="日期时间" value="datetime" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="字典类型" width="120">
          <template #default="{ row }">
            <el-select v-model="row.dict_type" size="small" placeholder="选择字典" :disabled="row.form_component !== 'select'">
              <el-option v-for="dt in dictTypes" :key="dt.code" :label="dt.name" :value="dt.code" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="removeField(row as TableFieldConfig)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="create-actions">
        <el-button type="primary" :loading="createLoading" @click="handleCreateTable">创建表并生成代码</el-button>
      </div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  codegenApi,
  type CreateTableParams,
  type FieldTypeInfo,
  type TableFieldConfig,
  type CodegenTable,
} from '@/api/codegen'
import { dictApi } from '@/api/dict'

const emit = defineEmits<{
  (e: 'tableCreated'): void
}>()

const createLoading = ref(false)
const fieldTypes = ref<FieldTypeInfo[]>([])
const dictTypes = ref<{ id: number; code: string; name: string }[]>([])
const availableTables = ref<CodegenTable[]>([])

const createForm = reactive({
  table_name: '',
  table_comment: '',
  module_name: '',
  create_db_table: true,
})

const createFields = ref<TableFieldConfig[]>([])

async function loadFieldTypes() {
  try {
    const res = await codegenApi.fieldTypes()
    fieldTypes.value = res.data ?? []
  } catch {
    fieldTypes.value = []
  }
}

async function loadDictTypes() {
  try {
    const res = await dictApi.getDictTypes()
    dictTypes.value = res.data ?? []
  } catch {
    dictTypes.value = []
  }
}

async function loadTables() {
  try {
    const res = await codegenApi.tables()
    availableTables.value = res.data ?? []
  } catch {
    availableTables.value = []
  }
}

function getTypeInfo(typeName: string): FieldTypeInfo | undefined {
  return fieldTypes.value.find(ft => ft.type_name === typeName)
}

function addField() {
  const newField: TableFieldConfig = {
    column_name: '',
    column_comment: '',
    data_type: 'VARCHAR',
    data_length: 128,
    data_scale: undefined,
    is_nullable: true,
    is_primary_key: false,
    column_default: undefined,
    foreign_key_table: undefined,
    is_list: true,
    is_form: true,
    is_search: true,
    is_required: false,
    form_component: 'input',
    dict_type: undefined,
    sort: createFields.value.length,
  }
  createFields.value.push(newField)
}

function removeField(row: TableFieldConfig) {
  const index = createFields.value.indexOf(row)
  if (index > -1) {
    createFields.value.splice(index, 1)
  }
}

function handleFieldTypeChange(row: TableFieldConfig) {
  const typeInfo = getTypeInfo(row.data_type)
  if (typeInfo) {
    row.data_length = typeInfo.default_length
    row.is_nullable = typeInfo.default_nullable
    row.data_scale = undefined
    row.form_component = row.data_type === 'BOOLEAN' ? 'switch' :
                        row.data_type === 'DECIMAL' || row.data_type === 'INT' || row.data_type === 'BIGINT' || row.data_type === 'SMALLINT' ? 'number' :
                        row.data_type === 'TEXT' ? 'textarea' :
                        row.data_type === 'DATE' || row.data_type === 'TIMESTAMP' ? 'datetime' : 'input'
    if (!['INT', 'BIGINT', 'SMALLINT'].includes(row.data_type)) {
      row.foreign_key_table = undefined
    }
  }
}

async function handleCreateTable() {
  if (!createForm.table_name || !createForm.module_name) {
    ElMessage.warning('请填写表名和模块名')
    return
  }
  if (createFields.value.length === 0) {
    ElMessage.warning('请至少添加一个字段')
    return
  }

  try {
    await ElMessageBox.confirm(
      createForm.create_db_table
        ? `确定要创建表 "${createForm.table_name}"（真实数据库表）并生成代码吗？`
        : `确定要保存表 "${createForm.table_name}" 配置并生成代码吗？`,
      '创建确认',
      { type: 'warning' }
    )
  } catch {
    return
  }

  createLoading.value = true
  try {
    const params: CreateTableParams = {
      table_name: createForm.table_name,
      table_comment: createForm.table_comment || undefined,
      module_name: createForm.module_name,
      entity_name: toPascalCase(createForm.module_name),
      page_title: createForm.table_comment || toPascalCase(createForm.module_name),
      api_prefix: `/api/v1/${createForm.module_name.replace(/_/g, '-')}`,
      fields: createFields.value,
      create_db_table: createForm.create_db_table,
    }
    await codegenApi.createTable(params)
    ElMessage.success(createForm.create_db_table ? '表创建成功，代码已生成' : '配置保存成功，代码已生成')
    createForm.table_name = ''
    createForm.table_comment = ''
    createForm.module_name = ''
    createForm.create_db_table = true
    createFields.value = []
    emit('tableCreated')
    loadTables()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '创建失败')
  } finally {
    createLoading.value = false
  }
}

function toPascalCase(value: string) {
  if (!value) return ''
  return value
    .split('_')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

onMounted(() => {
  loadFieldTypes()
  loadDictTypes()
  loadTables()
})
</script>

<style lang="scss" scoped>
.create-form {
  margin-bottom: 12px;
}

.create-table {
  margin-bottom: 12px;
  font-size: 12px;
}

.create-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.create-scroll {
  height: calc(100% - 92px);
  margin-top: 12px;
}

.tooltip-icon {
  display: inline-block;
  width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  background: #f5f7fa;
  color: #909399;
  border-radius: 50%;
  font-size: 12px;
  margin-left: 4px;
  cursor: help;
}
</style>