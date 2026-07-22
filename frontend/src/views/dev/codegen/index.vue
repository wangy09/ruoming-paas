<template>
  <div class="page-container codegen-page">
    <el-row :gutter="16">
      <el-col :span="7">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <el-tabs v-model="sideTab" @tab-change="handleSideTabChange">
                <el-tab-pane label="数据表" name="tables" />
                <el-tab-pane label="配置管理" name="configs" />
                <el-tab-pane label="新建表" name="create" />
              </el-tabs>
            </div>
          </template>

          <el-input
            v-model="keyword"
            placeholder="搜索表名 / 注释"
            clearable
            :prefix-icon="Search"
            @change="sideTab === 'tables' ? loadTables() : loadConfigs()"
            @clear="sideTab === 'tables' ? loadTables() : loadConfigs()"
          />

          <el-scrollbar class="table-list" v-if="sideTab === 'tables'">
            <div
              v-for="table in tables"
              :key="table.table_name"
              class="table-item"
              :class="{ active: form.table_name === table.table_name }"
              @click="selectTable(table.table_name)"
            >
              <div class="table-name">{{ table.table_name }}</div>
              <div class="table-comment">{{ table.table_comment || '暂无注释' }}</div>
            </div>
            <el-empty v-if="!loadingTables && tables.length === 0" description="暂无数据表" />
          </el-scrollbar>

          <el-scrollbar class="table-list" v-else-if="sideTab === 'configs'">
            <div
              v-for="config in configList"
              :key="config.id"
              class="table-item"
              :class="{ active: loadedConfigId === config.id }"
              @click="loadConfig(config.id)"
            >
              <div class="table-name">
                {{ config.table_name }}
                <el-tag
                  v-if="!config.table_exists"
                  size="small"
                  type="warning"
                  effect="light"
                  class="table-status-tag"
                >
                  表不存在
                </el-tag>
              </div>
              <div class="table-comment">{{ config.table_comment || config.module_name }}</div>
              <div class="config-actions">
                <el-button size="small" link @click.stop="downloadCode(config.id)">下载</el-button>
                <el-button size="small" link type="danger" @click.stop="confirmDelete(config)">删除</el-button>
              </div>
            </div>
            <el-empty v-if="!loadingConfigs && configList.length === 0" description="暂无保存的配置" />
          </el-scrollbar>

          <CreateTablePanel v-else @table-created="handleTableCreated" />
        </el-card>
      </el-col>

      <el-col :span="17">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>{{ sideTab === 'create' ? '新建表' : (loadedConfigId ? '已加载配置' : '生成配置') }}</span>
              <div class="header-actions">
                <template v-if="sideTab !== 'create'">
                  <el-button
                    type="warning"
                    :loading="saveLoading"
                    :disabled="!form.table_name"
                    @click="saveConfig"
                    v-permission="'dev:codegen:write'"
                  >
                    {{ loadedConfigId ? '更新配置' : '保存配置' }}
                  </el-button>
                  <el-button
                    :loading="previewLoading"
                    :disabled="!form.table_name"
                    v-permission="'dev:codegen:preview'"
                    @click="generatePreview"
                  >
                    生成预览
                  </el-button>
                  <el-button
                    type="primary"
                    :loading="writeLoading"
                    :disabled="!form.table_name"
                    v-permission="'dev:codegen:write'"
                    @click="writeFiles"
                  >
                    写入文件
                  </el-button>
                  <el-button
                    type="success"
                    :loading="writeLoading"
                    :disabled="!loadedConfigId"
                    v-permission="'dev:codegen:write'"
                    @click="downloadCode(loadedConfigId!)"
                  >
                    下载代码压缩包
                  </el-button>
                </template>
              </div>
            </div>
          </template>

          <div v-if="sideTab === 'create'" class="create-hint">
            <el-empty description="请在左侧配置表结构后点击「创建表并生成代码」">
              <template #image>
                <div style="font-size: 48px; color: #c0c4cc;">📋</div>
              </template>
            </el-empty>
          </div>

          <el-form v-else :model="form" label-width="100px" class="config-form">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="数据表">
                  <el-input v-model="form.table_name" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="模块名">
                  <el-input v-model="form.module_name" placeholder="如 customer_order" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="实体类名">
                  <el-input v-model="form.entity_name" placeholder="如 CustomerOrder" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="页面标题">
                  <el-input v-model="form.page_title" placeholder="如 客户订单" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="API 前缀">
                  <el-input v-model="form.api_prefix" placeholder="如 /api/v1/customer-orders" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="作者">
                  <el-input v-model="form.author" placeholder="如 developer" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="备注">
                  <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注信息" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="生成模板">
                  <el-select v-model="form.template_type" size="small">
                    <el-option label="单表CRUD" value="single" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="写入策略">
                  <el-switch
                    v-model="overwrite"
                    active-text="覆盖已存在文件"
                    inactive-text="已存在则跳过"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>

          <el-tabs v-model="activeTab" class="result-tabs">
            <el-tab-pane label="字段配置" name="columns">
              <ColumnConfigTable :loading="columnsLoading" :column-configs="columnConfigs" />
            </el-tab-pane>

            <el-tab-pane label="代码预览" name="preview">
              <CodePreview :files="files" />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>

    <ResultDialog v-model="resultVisible" :write-results="writeResults" />
    <BatchDialog v-model="batchDialogVisible" :config-list="configList" @batch-generated="handleBatchGenerated" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  codegenApi,
  type CodegenColumn,
  type CodegenTable,
  type ColumnConfig,
  type GeneratedFile,
  type GeneratedWriteResult,
  type GenTableResponse,
} from '@/api/codegen'
import CreateTablePanel from './components/CreateTablePanel.vue'
import ColumnConfigTable from './components/ColumnConfigTable.vue'
import CodePreview from './components/CodePreview.vue'
import ResultDialog from './components/ResultDialog.vue'
import BatchDialog from './components/BatchDialog.vue'

const loadingTables = ref(false)
const loadingConfigs = ref(false)
const columnsLoading = ref(false)
const previewLoading = ref(false)
const writeLoading = ref(false)
const saveLoading = ref(false)
const keyword = ref('')
const tables = ref<CodegenTable[]>([])
const configList = ref<GenTableResponse[]>([])
const columns = ref<CodegenColumn[]>([])
const columnConfigs = ref<(CodegenColumn & ColumnConfig)[]>([])
const files = ref<GeneratedFile[]>([])
const writeResults = ref<GeneratedWriteResult[]>([])
const activeTab = ref('columns')
const sideTab = ref('tables')
const overwrite = ref(false)
const resultVisible = ref(false)
const batchDialogVisible = ref(false)
const loadedConfigId = ref<number | null>(null)

const form = reactive({
  table_name: '',
  table_comment: '',
  module_name: '',
  entity_name: '',
  page_title: '',
  api_prefix: '',
  author: '',
  remark: '',
  template_type: 'single' as 'single' | 'master_detail' | 'tree',
})

async function loadTables() {
  loadingTables.value = true
  try {
    const res = await codegenApi.tables({ keyword: keyword.value || undefined })
    tables.value = res.data ?? []
  } finally {
    loadingTables.value = false
  }
}

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    const res = await codegenApi.configs({ keyword: keyword.value || undefined })
    configList.value = res.data?.items ?? []
  } finally {
    loadingConfigs.value = false
  }
}

function handleSideTabChange(val: string | number) {
  if (val === 'configs') {
    loadConfigs()
  } else if (val === 'create') {
    clearFormData()
  } else {
    loadTables()
  }
}

function clearFormData() {
  form.table_name = ''
  form.table_comment = ''
  form.module_name = ''
  form.entity_name = ''
  form.page_title = ''
  form.api_prefix = ''
  form.author = ''
  form.remark = ''
  loadedConfigId.value = null
  columns.value = []
  columnConfigs.value = []
  files.value = []
  activeTab.value = 'columns'
}

async function selectTable(tableName: string) {
  form.table_name = tableName
  form.module_name = toModuleName(tableName)
  form.entity_name = toPascalCase(form.module_name)
  const current = tables.value.find(item => item.table_name === tableName)
  form.table_comment = current?.table_comment || ''
  form.page_title = current?.table_comment || form.entity_name
  form.api_prefix = `/api/v1/${form.module_name.replace(/_/g, '-')}`
  form.author = ''
  form.remark = ''
  files.value = []
  activeTab.value = 'columns'
  loadedConfigId.value = null
  await loadColumns(tableName)
}

async function loadColumns(tableName: string) {
  columnsLoading.value = true
  try {
    const res = await codegenApi.columns(tableName)
    columns.value = res.data ?? []
    columnConfigs.value = columns.value.map(col => ({
      ...col,
      is_list: !['is_deleted', 'tenant_id', 'updated_at'].includes(col.column_name),
      is_form: !col.column_name.startsWith('id') && !['is_deleted', 'tenant_id', 'created_at', 'updated_at'].includes(col.column_name),
      is_search: col.python_type === 'str' || col.data_type === 'text',
      is_required: !col.is_nullable && !col.column_name.startsWith('id'),
      form_component: col.form_component,
      dict_type: undefined,
      sort: 0,
    }))
  } finally {
    columnsLoading.value = false
  }
}

async function loadConfig(configId: number) {
  try {
    const res = await codegenApi.getConfig(configId)
    const config = res.data
    form.table_name = config.table_name
    form.table_comment = config.table_comment || ''
    form.module_name = config.module_name
    form.entity_name = config.entity_name
    form.page_title = config.page_title || ''
    form.api_prefix = config.api_prefix || ''
    form.author = config.author || ''
    form.remark = config.remark || ''
    loadedConfigId.value = configId

    columnsLoading.value = true
    try {
      let allColumns: any[] = []
      let dbTableExists = true
      try {
        const colRes = await codegenApi.columns(config.table_name)
        allColumns = colRes.data ?? []
      } catch {
        allColumns = []
        dbTableExists = false
      }

      if (!dbTableExists) {
        ElMessage.info(`数据表 "${config.table_name}" 不存在，当前使用配置中的字段信息`)
      }

      if (allColumns.length > 0) {
        columnConfigs.value = allColumns.map((col: CodegenColumn) => {
          const saved = config.columns.find((c: ColumnConfig) => c.column_name === col.column_name)
          return {
            ...col,
            is_list: saved?.is_list ?? (!['is_deleted', 'tenant_id', 'updated_at'].includes(col.column_name)),
            is_form: saved?.is_form ?? (!col.column_name.startsWith('id') && !['is_deleted', 'tenant_id', 'created_at', 'updated_at'].includes(col.column_name)),
            is_search: saved?.is_search ?? (col.python_type === 'str' || col.data_type === 'text'),
            is_required: saved?.is_required ?? (!col.is_nullable && !col.column_name.startsWith('id')),
            form_component: saved?.form_component ?? col.form_component,
            dict_type: saved?.dict_type ?? undefined,
            sort: saved?.sort ?? 0,
          }
        })
      } else {
        columnConfigs.value = config.columns.map((col: ColumnConfig) => ({
          ...col,
          is_list: col.is_list ?? true,
          is_form: col.is_form ?? true,
          is_search: col.is_search ?? false,
          is_required: col.is_required ?? false,
          form_component: col.form_component ?? 'input',
          dict_type: col.dict_type ?? undefined,
          sort: col.sort ?? 0,
        }))
      }
      files.value = []
      activeTab.value = 'columns'
    } finally {
      columnsLoading.value = false
    }
  } catch {
    ElMessage.error('加载配置失败')
  }
}

async function saveConfig() {
  if (!form.table_name || !form.module_name) {
    ElMessage.warning('请选择数据表并填写模块名')
    return
  }
  saveLoading.value = true
  try {
    await codegenApi.saveConfig({
      table_name: form.table_name,
      table_comment: form.table_comment || undefined,
      module_name: form.module_name,
      entity_name: form.entity_name,
      page_title: form.page_title || undefined,
      api_prefix: form.api_prefix || undefined,
      author: form.author || undefined,
      remark: form.remark || undefined,
      columns: columnConfigs.value.map(c => ({
        column_name: c.column_name,
        is_list: c.is_list,
        is_form: c.is_form,
        is_search: c.is_search,
        is_required: c.is_required,
        form_component: c.form_component,
        dict_type: c.dict_type || undefined,
        sort: c.sort,
      })),
    })
    ElMessage.success('配置保存成功')
    await loadConfigs()
  } finally {
    saveLoading.value = false
  }
}

async function confirmDelete(config: GenTableResponse) {
  try {
    await ElMessageBox.confirm(
      `确定要删除配置 "${config.table_name}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await codegenApi.deleteConfig(config.id)
    ElMessage.success('配置已删除')
    if (loadedConfigId.value === config.id) {
      loadedConfigId.value = null
      form.table_name = ''
      columnConfigs.value = []
      files.value = []
    }
    await loadConfigs()
  } catch {
    return
  }
}

async function downloadCode(configId: number) {
  try {
    const res = await codegenApi.downloadCode(configId)
    const blob = res.data
    const config = configList.value.find(c => c.id === configId)
    const filename = `${config?.module_name || 'codegen'}_codegen.zip`
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch {
    ElMessage.error('下载失败')
  }
}

async function generatePreview() {
  if (!form.table_name || !form.module_name) {
    ElMessage.warning('请选择数据表并填写模块名')
    return
  }
  previewLoading.value = true
  try {
    const res = await codegenApi.preview({
      ...form,
      column_configs: columnConfigs.value.map(c => ({
        column_name: c.column_name,
        is_list: c.is_list,
        is_form: c.is_form,
        is_search: c.is_search,
        is_required: c.is_required,
        form_component: c.form_component,
        dict_type: c.dict_type,
        sort: c.sort,
      })),
    })
    files.value = res.data?.files ?? []
    activeTab.value = 'preview'
  } finally {
    previewLoading.value = false
  }
}

async function writeFiles() {
  if (!form.table_name || !form.module_name) {
    ElMessage.warning('请选择数据表并填写模块名')
    return
  }

  try {
    await ElMessageBox.confirm(
      `
        <div style="padding: 20px;">
          <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
            <div style="font-size: 32px; margin-right: 16px;">${overwrite.value ? '🔔' : '📋'}</div>
            <div>
              <h3 style="margin: 0 0 8px 0; font-size: 16px; color: #303133;">代码生成确认</h3>
              <p style="margin: 0; font-size: 13px; color: #909399;">即将生成代码并写入项目目录</p>
            </div>
          </div>
          
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
            <div style="padding: 12px; background: #fafafa; border-radius: 8px;">
              <p style="margin: 0 0 4px 0; font-size: 12px; color: #909399;">数据库表</p>
              <p style="margin: 0; font-size: 14px; font-weight: 600; color: #303133;">${form.table_name}</p>
            </div>
            <div style="padding: 12px; background: #fafafa; border-radius: 8px;">
              <p style="margin: 0 0 4px 0; font-size: 12px; color: #909399;">模块名称</p>
              <p style="margin: 0; font-size: 14px; font-weight: 600; color: #303133;">${form.module_name}</p>
            </div>
            <div style="padding: 12px; background: #fafafa; border-radius: 8px;">
              <p style="margin: 0 0 4px 0; font-size: 12px; color: #909399;">实体类名</p>
              <p style="margin: 0; font-size: 14px; font-weight: 600; color: #303133;">${form.entity_name || form.module_name.replace(/_([a-z])/g, (m, c) => c.toUpperCase()).replace(/^[a-z]/, c => c.toUpperCase())}</p>
            </div>
            <div style="padding: 12px; background: #fafafa; border-radius: 8px;">
              <p style="margin: 0 0 4px 0; font-size: 12px; color: #909399;">写入路径</p>
              <p style="margin: 0; font-size: 14px; font-weight: 600; color: #303133;">/app/</p>
            </div>
          </div>
          
          <div style="padding: 16px; background: #f5f7fa; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: #303133;">📁 将生成以下文件：</p>
            <div style="display: grid; grid-template-columns: 1fr; gap: 6px;">
              <p style="margin: 0; font-size: 13px; color: #606266;">• <code style="background: #e4e7ed; padding: 2px 6px; border-radius: 4px;">backend/app/modules/${form.module_name}/</code> (模型、服务、路由)</p>
              <p style="margin: 0; font-size: 13px; color: #606266;">• <code style="background: #e4e7ed; padding: 2px 6px; border-radius: 4px;">backend/migrations/versions/</code> (数据库迁移脚本)</p>
              <p style="margin: 0; font-size: 13px; color: #606266;">• <code style="background: #e4e7ed; padding: 2px 6px; border-radius: 4px;">frontend/src/views/${form.module_name}/</code> (前端页面)</p>
              <p style="margin: 0; font-size: 13px; color: #606266;">• <code style="background: #e4e7ed; padding: 2px 6px; border-radius: 4px;">frontend/src/api/${form.module_name}.ts</code> (API接口)</p>
              <p style="margin: 0; font-size: 13px; color: #606266;">• <code style="background: #e4e7ed; padding: 2px 6px; border-radius: 4px;">frontend/src/router/${form.module_name}.ts</code> (路由配置)</p>
            </div>
          </div>
          
          <div style="padding: 12px 16px; border-radius: 8px; ${overwrite.value ? 'background: #fef0f0; border: 1px solid #fbc4c4;' : 'background: #f0f9ff; border: 1px solid #b3d8ff;'}">
            <p style="margin: 0; font-size: 14px; font-weight: 500; ${overwrite.value ? 'color: #d93026;' : 'color: #096dd9;'}">
              ${overwrite.value ? '⚠️ 覆盖模式：已存在的文件将被覆盖！' : '✅ 安全模式：已存在的文件将自动跳过'}
            </p>
          </div>
        </div>
      `,
      '写入文件确认',
      {
        icon: '',
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认写入',
        cancelButtonText: '取消',
        confirmButtonClass: overwrite.value ? 'el-button--danger' : '',
      }
    )
  } catch {
    return
  }

  writeLoading.value = true
  try {
    const res = await codegenApi.write({
      ...form,
      overwrite: overwrite.value,
      column_configs: columnConfigs.value.map(c => ({
        column_name: c.column_name,
        is_list: c.is_list,
        is_form: c.is_form,
        is_search: c.is_search,
        is_required: c.is_required,
        form_component: c.form_component,
        dict_type: c.dict_type,
        sort: c.sort,
      })),
    })
    files.value = res.data?.files ?? []
    writeResults.value = res.data?.results ?? []
    activeTab.value = 'preview'
    resultVisible.value = true
    ElMessage.success('生成完成')
  } catch (error) {
    ElMessage.error(`写入失败：${getErrorMessage(error)}`)
  } finally {
    writeLoading.value = false
  }
}

function handleTableCreated() {
  loadTables()
  loadConfigs()
}

function handleBatchGenerated() {
  loadConfigs()
}

function toModuleName(tableName: string) {
  return tableName.replace(/^sys_/, '').replace(/^ai_/, '')
}

function toPascalCase(value: string) {
  return value
    .split('_')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return '请查看接口错误详情'
}

onMounted(() => {
  loadTables()
})
</script>

<style lang="scss" scoped>
.codegen-page {
  .panel-card {
    height: calc(100vh - 126px);
  }

  :deep(.el-card__body) {
    height: calc(100% - 57px);
    overflow: hidden;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.table-list {
  height: calc(100% - 92px);
  margin-top: 12px;
}

.table-item {
  padding: 10px 12px;
  border: 1px solid $border-color;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;

  &:hover,
  &.active {
    border-color: $primary-color;
    background: rgba($primary-color, 0.08);
  }
}

.table-name {
  font-weight: 600;
  color: $text-primary;
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-status-tag {
  margin-left: 4px;
}

.table-comment {
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.config-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.config-form {
  margin-bottom: 8px;
}

.create-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.result-tabs {
  height: calc(100% - 200px);

  :deep(.el-tabs__content) {
    height: calc(100% - 55px);
  }

  :deep(.el-tab-pane) {
    height: 100%;
  }
}
</style>
