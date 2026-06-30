<template>
  <div class="page-container codegen-page">
    <el-row :gutter="16">
      <el-col :span="7">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>数据表</span>
              <el-button link type="primary" :icon="Refresh" @click="loadTables">刷新</el-button>
            </div>
          </template>

          <el-input
            v-model="keyword"
            placeholder="搜索表名 / 注释"
            clearable
            :prefix-icon="Search"
            @change="loadTables"
            @clear="loadTables"
          />

          <el-scrollbar class="table-list">
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
        </el-card>
      </el-col>

      <el-col :span="17">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>生成配置</span>
              <el-button
                type="primary"
                :loading="previewLoading"
                :disabled="!form.table_name"
                v-permission="'dev:codegen:preview'"
                @click="generatePreview"
              >
                生成预览
              </el-button>
            </div>
          </template>

          <el-form :model="form" label-width="100px" class="config-form">
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
              <el-col :span="24">
                <el-form-item label="API 前缀">
                  <el-input v-model="form.api_prefix" placeholder="如 /api/v1/customer-orders" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>

          <el-tabs v-model="activeTab" class="result-tabs">
            <el-tab-pane label="字段结构" name="columns">
              <el-table v-loading="columnsLoading" :data="columns" border stripe height="360">
                <el-table-column prop="column_name" label="字段名" min-width="150" fixed />
                <el-table-column prop="column_comment" label="注释" min-width="160" show-overflow-tooltip />
                <el-table-column prop="data_type" label="数据库类型" min-width="130" />
                <el-table-column prop="python_type" label="Python" width="100" />
                <el-table-column prop="ts_type" label="TypeScript" width="150" />
                <el-table-column prop="form_component" label="表单组件" width="110" />
                <el-table-column prop="is_nullable" label="可空" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.is_nullable ? 'info' : 'success'" size="small">
                      {{ row.is_nullable ? '是' : '否' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="is_primary_key" label="主键" width="80">
                  <template #default="{ row }">
                    <el-tag v-if="row.is_primary_key" type="warning" size="small">是</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="代码预览" name="preview">
              <el-empty v-if="files.length === 0" description="请选择数据表并生成预览" />
              <el-tabs v-else v-model="activeFile" tab-position="left" class="file-tabs">
                <el-tab-pane v-for="file in files" :key="file.path" :label="shortPath(file.path)" :name="file.path">
                  <div class="code-header">
                    <span>{{ file.path }}</span>
                    <el-button size="small" type="primary" plain @click="copyCode(file.content)">复制</el-button>
                  </div>
                  <pre class="code-block"><code>{{ file.content }}</code></pre>
                </el-tab-pane>
              </el-tabs>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { codegenApi, type CodegenColumn, type CodegenTable, type GeneratedFile } from '@/api/codegen'

const loadingTables = ref(false)
const columnsLoading = ref(false)
const previewLoading = ref(false)
const keyword = ref('')
const tables = ref<CodegenTable[]>([])
const columns = ref<CodegenColumn[]>([])
const files = ref<GeneratedFile[]>([])
const activeTab = ref('columns')
const activeFile = ref('')

const form = reactive({
  table_name: '',
  module_name: '',
  entity_name: '',
  page_title: '',
  api_prefix: '',
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

async function selectTable(tableName: string) {
  form.table_name = tableName
  form.module_name = toModuleName(tableName)
  form.entity_name = toPascalCase(form.module_name)
  const current = tables.value.find(item => item.table_name === tableName)
  form.page_title = current?.table_comment || form.entity_name
  form.api_prefix = `/api/v1/${form.module_name.replace(/_/g, '-')}`
  files.value = []
  activeTab.value = 'columns'
  await loadColumns(tableName)
}

async function loadColumns(tableName: string) {
  columnsLoading.value = true
  try {
    const res = await codegenApi.columns(tableName)
    columns.value = res.data ?? []
  } finally {
    columnsLoading.value = false
  }
}

async function generatePreview() {
  if (!form.table_name || !form.module_name) {
    ElMessage.warning('请选择数据表并填写模块名')
    return
  }
  previewLoading.value = true
  try {
    const res = await codegenApi.preview({ ...form })
    files.value = res.data?.files ?? []
    activeFile.value = files.value[0]?.path || ''
    activeTab.value = 'preview'
  } finally {
    previewLoading.value = false
  }
}

async function copyCode(content: string) {
  await navigator.clipboard.writeText(content)
  ElMessage.success('已复制')
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

function shortPath(path: string) {
  const parts = path.split('/')
  return parts.slice(-2).join('/')
}

onMounted(loadTables)
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

.table-list {
  height: calc(100% - 48px);
  margin-top: 12px;
}

.table-item {
  padding: 10px 12px;
  border: 1px solid $border-color;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover,
  &.active {
    border-color: $primary-color;
    background: rgba($primary-color, 0.08);
  }
}

.table-name {
  font-weight: 600;
  color: $text-primary;
}

.table-comment {
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.config-form {
  margin-bottom: 8px;
}

.result-tabs {
  height: calc(100% - 154px);

  :deep(.el-tabs__content) {
    height: calc(100% - 55px);
  }

  :deep(.el-tab-pane) {
    height: 100%;
  }
}

.file-tabs {
  height: 100%;

  :deep(.el-tabs__content) {
    height: 100%;
  }
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 10px;
  font-size: 13px;
  color: $text-secondary;
}

.code-block {
  height: calc(100% - 42px);
  margin: 0;
  padding: 14px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.55;
}
</style>
