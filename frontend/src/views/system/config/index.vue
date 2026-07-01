<template>
  <div class="page-container config-center-page">
    <div class="config-layout">
      <el-card class="category-card" shadow="never">
        <div class="category-title">配置分类</div>
        <div
          v-for="item in categoryOptions"
          :key="item.value"
          class="category-item"
          :class="{ active: activeCategory === item.value }"
          @click="selectCategory(item.value)"
        >
          <div>
            <div class="category-name">{{ item.label }}</div>
            <div class="category-desc">{{ item.description }}</div>
          </div>
          <el-tag size="small" effect="plain">{{ categoryCount(item.value) }}</el-tag>
        </div>
      </el-card>

      <div class="config-main">
        <el-card class="filter-card" shadow="never">
          <div class="category-header">
            <div>
              <div class="category-header-title">{{ activeCategoryInfo.label }}</div>
              <div class="category-header-desc">{{ activeCategoryInfo.description }}</div>
            </div>
            <div class="category-stats">
              <el-statistic title="配置数" :value="tableData.length" />
              <el-statistic title="公开配置" :value="publicCount" />
              <el-statistic title="加密配置" :value="encryptedCount" />
            </div>
          </div>
          <div class="toolbar">
            <div class="filters">
              <el-select v-model="query.scope" placeholder="作用域" clearable class="filter-select" @change="reload">
                <el-option v-for="item in scopeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <el-input
                v-model="query.keyword"
                placeholder="搜索配置键 / 名称 / 描述"
                clearable
                class="filter-input"
                @keyup.enter="reload"
                @clear="reload"
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-select v-model="query.is_public" placeholder="公开" clearable class="filter-select-sm" @change="reload">
                <el-option label="公开" :value="true" />
                <el-option label="私有" :value="false" />
              </el-select>
              <el-select v-model="query.is_encrypted" placeholder="加密" clearable class="filter-select-sm" @change="reload">
                <el-option label="加密" :value="true" />
                <el-option label="明文" :value="false" />
              </el-select>
              <el-select v-model="query.status" placeholder="状态" clearable class="filter-select-sm" @change="reload">
                <el-option label="启用" :value="1" />
                <el-option label="停用" :value="0" />
              </el-select>
              <el-button :icon="Search" type="primary" @click="reload">查询</el-button>
              <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
            </div>
            <div class="actions">
              <el-button v-permission="'config:list'" :loading="exporting" @click="handleExport">导出</el-button>
              <el-button v-permission="'config:create'" :loading="importing" @click="triggerImport">导入</el-button>
              <el-button v-permission="'config:update'" :loading="cacheClearing" @click="clearCache">清缓存</el-button>
              <el-button type="primary" :icon="Plus" v-permission="'config:create'" @click="openCreate">新增配置</el-button>
              <input ref="importInputRef" type="file" accept="application/json,.json" class="hidden-file-input" @change="handleImportFileChange" />
            </div>
          </div>
        </el-card>

        <el-card shadow="never">
          <el-table v-loading="loading" :data="pagedTableData" border stripe>
        <el-table-column label="配置项" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="config-key-cell">
              <div class="config-key-line">
                <span class="config-key">{{ row.config_key }}</span>
                <el-tag v-if="row.is_encrypted" type="warning" size="small" effect="plain">加密</el-tag>
              </div>
              <div class="config-meta">{{ row.label || row.description || '-' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="作用域" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="scopeTagType(row.scope)" size="small">{{ scopeLabel(row.scope) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="130" show-overflow-tooltip />
        <el-table-column label="配置值" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="value-text">{{ displayConfigValue(toConfigRow(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="值类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ row.val_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="控件" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ configTypeLabel(row.config_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="公开" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_public ? 'success' : 'info'" size="small">
              {{ row.is_public ? '公开' : '私有' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column label="归属" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ ownerText(toConfigRow(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'config:update'" @click="openEdit(toConfigRow(row))">编辑</el-button>
            <el-button link type="primary" @click="openHistory(toConfigRow(row))">历史</el-button>
            <el-button link type="warning" v-permission="'config:update'" @click="restoreDefault(toConfigRow(row))">恢复默认</el-button>
            <el-button link type="danger" v-permission="'config:delete'" @click="handleDelete(toConfigRow(row))">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="tableData.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="handlePageSizeChange"
      />
        </el-card>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="920px" destroy-on-close>
      <el-alert
        v-if="isEncryptedEdit"
        class="encrypted-tip"
        type="warning"
        show-icon
        :closable="false"
        title="该配置为加密字段，编辑时配置值留空将不覆盖原密文。"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="作用域" prop="scope">
              <el-select v-model="form.scope" class="w-full" @change="handleScopeChange">
                <el-option v-for="item in scopeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="配置键" prop="config_key">
              <el-input v-model="form.config_key" :disabled="Boolean(editId)" placeholder="如：site.title" maxlength="128" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="如：基础配置 / 安全配置" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称">
              <el-input v-model="form.label" placeholder="配置展示名称" maxlength="128" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="值类型" prop="val_type">
              <el-select v-model="form.val_type" class="w-full" @change="handleValueTypeChange">
                <el-option v-for="item in valueTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="控件类型" prop="config_type">
              <el-select v-model="form.config_type" class="w-full">
                <el-option v-for="item in formTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="必填">
              <el-switch v-model="form.required" active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio-button :value="1">启用</el-radio-button>
                <el-radio-button :value="0">停用</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="公开访问">
              <el-switch v-model="form.is_public" active-text="公开" inactive-text="私有" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="加密存储">
              <el-switch v-model="form.is_encrypted" active-text="加密" inactive-text="明文" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="应用标识" :required="form.scope === 'app'">
              <el-input
                v-model="form.app_key"
                :disabled="form.scope !== 'app' && form.scope !== 'user'"
                placeholder="scope 为 app/user 时可填写"
                maxlength="64"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用户ID" :required="form.scope === 'user'">
              <el-input-number
                v-model="form.user_id"
                :disabled="form.scope !== 'user'"
                :min="1"
                :precision="0"
                class="w-full"
                placeholder="scope 为 user 时填写"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="配置值" prop="config_val">
          <el-switch
            v-if="form.config_type === 'switch'"
            v-model="form.config_val"
            active-value="true"
            inactive-value="false"
            active-text="true"
            inactive-text="false"
          />
          <el-select
            v-else-if="form.config_type === 'select'"
            v-model="form.config_val"
            filterable
            clearable
            placeholder="请选择配置值"
            class="w-full"
          >
            <el-option
              v-for="option in parsedSelectOptions"
              :key="String(option.value)"
              :label="option.label"
              :value="String(option.value)"
            />
          </el-select>
          <el-input
            v-else-if="isMultiLineValue"
            v-model="form.config_val"
            type="textarea"
            :rows="5"
            :placeholder="configValuePlaceholder"
          />
          <el-input-number
            v-else-if="form.config_type === 'number'"
            :model-value="numberConfigValue"
            :min="form.min_value"
            :max="form.max_value"
            :precision="form.val_type === 'int' ? 0 : undefined"
            class="w-full"
            @update:model-value="handleNumberConfigValueChange"
          />
          <el-input
            v-else
            v-model="form.config_val"
            :type="form.config_type === 'password' || form.is_encrypted ? 'password' : 'text'"
            :show-password="form.config_type === 'password' || form.is_encrypted"
            :placeholder="configValuePlaceholder"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="默认值">
              <el-input v-model="form.default_value" placeholder="可选默认值" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :max="999999" :precision="0" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item v-if="form.config_type === 'select'" label="选项配置" prop="optionsText">
          <el-input
            v-model="form.optionsText"
            type="textarea"
            :rows="5"
            placeholder='JSON 数组，例如：[{"label":"启用","value":"1"},{"label":"停用","value":"0"}]'
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="正则校验">
              <el-input v-model="form.regex" placeholder="可选，如：^\\w+$" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最小值">
              <el-input-number v-model="form.min_value" :disabled="!showNumberLimit" class="w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大值">
              <el-input-number v-model="form.max_value" :disabled="!showNumberLimit" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="historyVisible" title="配置变更历史" width="820px">
      <div class="history-title">
        <span>{{ historyConfigKey }}</span>
        <el-button :icon="Refresh" :loading="historyLoading" @click="loadHistory">刷新</el-button>
      </div>
      <el-table v-loading="historyLoading" :data="historyRows" border stripe>
        <el-table-column label="变更时间" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ formatChangedAt(row.changed_at) }}</template>
        </el-table-column>
        <el-table-column prop="old_value" label="旧值" min-width="180" show-overflow-tooltip />
        <el-table-column prop="new_value" label="新值" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作人" width="130" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.changed_by_name || row.changed_by || '-' }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="historyPage"
        v-model:page-size="historyPageSize"
        :total="historyTotal"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="loadHistory"
        @size-change="handleHistoryPageSizeChange"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { configApi } from '@/api/config'
import type {
  ConfigFormType,
  ConfigHistoryInfo,
  ConfigInfo,
  ConfigOption,
  ConfigPayload,
  ConfigScope,
  ConfigValueType,
} from '@/types'

interface ConfigFormState {
  scope: ConfigScope
  config_key: string
  config_val: string
  val_type: ConfigValueType
  is_encrypted: boolean
  category: string
  config_type: ConfigFormType
  default_value: string
  optionsText: string
  required: boolean
  regex: string
  min_value?: number
  max_value?: number
  sort: number
  status: 0 | 1
  label: string
  description: string
  is_public: boolean
  app_key: string
  user_id?: number
}

const scopeOptions: Array<{ label: string; value: ConfigScope }> = [
  { label: '全局', value: 'global' },
  { label: '租户', value: 'tenant' },
  { label: '应用', value: 'app' },
  { label: '用户', value: 'user' },
]

const valueTypeOptions: Array<{ label: string; value: ConfigValueType }> = [
  { label: '字符串', value: 'string' },
  { label: '整数', value: 'int' },
  { label: '数字', value: 'number' },
  { label: '布尔', value: 'bool' },
  { label: 'JSON', value: 'json' },
]

const formTypeOptions: Array<{ label: string; value: ConfigFormType }> = [
  { label: '输入框', value: 'input' },
  { label: '多行文本', value: 'textarea' },
  { label: '开关', value: 'switch' },
  { label: '下拉框', value: 'select' },
  { label: 'JSON', value: 'json' },
  { label: '密码框', value: 'password' },
  { label: '数字输入', value: 'number' },
]

const categoryOptions = [
  { label: '全部配置', value: '', description: '查看当前作用域下全部配置' },
  { label: '站点配置', value: 'site', description: '系统名称、Logo、登录页文案' },
  { label: '界面配置', value: 'ui', description: '主题色、水印等前端公开配置' },
  { label: '文件配置', value: 'file', description: '上传大小、扩展名白名单' },
  { label: '登录安全', value: 'auth', description: '失败锁定、密码和验证码策略' },
  { label: 'AI 配置', value: 'ai', description: '模型默认参数、调用默认值' },
  { label: '消息配置', value: 'message', description: '消息提醒和公告行为' },
  { label: '任务配置', value: 'task', description: '计划任务和执行日志策略' },
  { label: '审计配置', value: 'audit', description: '操作日志保留和审计策略' },
  { label: '监控配置', value: 'monitor', description: '监控刷新和采集策略' },
]

const loading = ref(false)
const submitting = ref(false)
const exporting = ref(false)
const importing = ref(false)
const cacheClearing = ref(false)
const tableData = ref<ConfigInfo[]>([])
const categoryData = ref<ConfigInfo[]>([])
const page = ref(1)
const pageSize = ref(10)
const activeCategory = ref('')
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyConfigKey = ref('')
const historyRows = ref<ConfigHistoryInfo[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = ref(10)

const query = reactive({
  scope: 'global' as ConfigScope | undefined,
  keyword: '',
  is_public: undefined as boolean | undefined,
  is_encrypted: undefined as boolean | undefined,
  status: undefined as number | undefined,
})

const formRef = ref<FormInstance>()
const importInputRef = ref<HTMLInputElement>()
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const editingRow = ref<ConfigInfo | null>(null)

const form = reactive<ConfigFormState>(createDefaultForm())

const rules: FormRules<ConfigFormState> = {
  scope: [{ required: true, message: '请选择作用域', trigger: 'change' }],
  config_key: [{ required: true, message: '请输入配置键', trigger: 'blur' }],
  val_type: [{ required: true, message: '请选择值类型', trigger: 'change' }],
  config_type: [{ required: true, message: '请选择控件类型', trigger: 'change' }],
  config_val: [{ validator: validateConfigValue, trigger: 'blur' }],
  optionsText: [{ validator: validateOptionsText, trigger: 'blur' }],
}

const dialogTitle = computed(() => (editId.value ? '编辑配置' : '新增配置'))

const pagedTableData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tableData.value.slice(start, start + pageSize.value)
})

const showNumberLimit = computed(() => ['int', 'number'].includes(form.val_type) || form.config_type === 'number')
const isMultiLineValue = computed(() => form.config_type === 'textarea' || form.config_type === 'json' || form.val_type === 'json')
const isEncryptedEdit = computed(() => Boolean(editId.value && editingRow.value?.is_encrypted))
const activeCategoryInfo = computed(() => (
  categoryOptions.find((item) => item.value === activeCategory.value) ?? categoryOptions[0]
))
const publicCount = computed(() => tableData.value.filter((item) => item.is_public).length)
const encryptedCount = computed(() => tableData.value.filter((item) => item.is_encrypted).length)
const numberConfigValue = computed(() => {
  if (!form.config_val) return undefined
  const value = Number(form.config_val)
  return Number.isFinite(value) ? value : undefined
})

const configValuePlaceholder = computed(() => {
  if (isEncryptedEdit.value) return '留空不覆盖原密文'
  if (form.val_type === 'json') return '请输入合法 JSON'
  return '请输入配置值'
})

const parsedSelectOptions = computed<ConfigOption[]>(() => {
  const parsed = parseOptionsText(form.optionsText, false)
  return Array.isArray(parsed) ? parsed : []
})

async function reload() {
  loading.value = true
  try {
    const [res, categoryRes] = await Promise.all([
      configApi.list({
        scope: query.scope,
        category: activeCategory.value || undefined,
        keyword: query.keyword || undefined,
        is_public: query.is_public,
        is_encrypted: query.is_encrypted,
        status: query.status,
      }),
      configApi.list({
        scope: query.scope,
        is_public: query.is_public,
        is_encrypted: query.is_encrypted,
        status: query.status,
      }),
    ])
    // Axios 拦截器已返回业务响应对象，因此这里只读取 res.data
    tableData.value = normalizeListData(res.data)
    categoryData.value = normalizeListData(categoryRes.data)
    page.value = 1
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.scope = 'global'
  query.keyword = ''
  query.is_public = undefined
  query.is_encrypted = undefined
  query.status = undefined
  reload()
}

async function handleExport() {
  exporting.value = true
  try {
    const res = await configApi.exportConfigs({
      scope: query.scope,
      category: activeCategory.value || undefined,
      keyword: query.keyword || undefined,
      is_public: query.is_public,
      is_encrypted: query.is_encrypted,
      status: query.status,
    })
    const payload = {
      version: res.data.version,
      exported_at: new Date().toISOString(),
      filters: {
        scope: query.scope,
        category: activeCategory.value || undefined,
        keyword: query.keyword || undefined,
        is_public: query.is_public,
        is_encrypted: query.is_encrypted,
        status: query.status,
      },
      items: res.data.items,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `config-center-${query.scope || 'global'}-${formatFileDate(new Date())}.json`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${res.data.items.length} 条配置`)
  } finally {
    exporting.value = false
  }
}

function triggerImport() {
  importInputRef.value?.click()
}

async function handleImportFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  importing.value = true
  try {
    const text = await file.text()
    const parsed = JSON.parse(text) as unknown
    const items = normalizeImportItems(parsed)
    if (!items.length) {
      ElMessage.warning('导入文件中没有可用配置项')
      return
    }

    let overwrite = false
    try {
      await ElMessageBox.confirm(
        `即将导入 ${items.length} 条配置。是否覆盖已存在配置？`,
        '导入配置',
        {
          type: 'warning',
          confirmButtonText: '覆盖已有',
          cancelButtonText: '跳过已有',
          distinguishCancelAndClose: true,
        },
      )
      overwrite = true
    } catch (action) {
      if (action === 'close') return
      overwrite = false
    }

    const res = await configApi.importConfigs({ items, overwrite })
    const result = res.data
    const message = `导入完成：新增 ${result.created}，更新 ${result.updated}，跳过 ${result.skipped}`
    if (result.errors.length) {
      ElMessage.warning(`${message}，失败 ${result.errors.length} 条`)
      console.warn('配置导入失败明细：', result.errors)
    } else {
      ElMessage.success(message)
    }
    await reload()
  } catch (error) {
    ElMessage.error(`导入失败：${getErrorMessage(error)}`)
  } finally {
    importing.value = false
  }
}

async function clearCache() {
  await ElMessageBox.confirm('确定清理配置中心运行时缓存？下次读取会重新从数据库加载。', '清理缓存', {
    type: 'warning',
    confirmButtonText: '清理',
    cancelButtonText: '取消',
  })
  cacheClearing.value = true
  try {
    const res = await configApi.clearCache()
    ElMessage.success(`已清理 ${res.data.cleared} 个缓存键`)
  } finally {
    cacheClearing.value = false
  }
}

function handleNumberConfigValueChange(value: number | undefined) {
  form.config_val = value === undefined ? '' : String(value)
}

function selectCategory(category: string) {
  activeCategory.value = category
  page.value = 1
  reload()
}

function handlePageSizeChange() {
  page.value = 1
}

function openCreate() {
  editId.value = null
  editingRow.value = null
  Object.assign(form, createDefaultForm())
  form.category = activeCategory.value
  dialogVisible.value = true
}

function openEdit(row: ConfigInfo) {
  editId.value = row.id
  editingRow.value = row
  Object.assign(form, {
    scope: row.scope,
    config_key: row.config_key,
    config_val: '',
    val_type: row.val_type as ConfigValueType,
    is_encrypted: row.is_encrypted,
    category: row.category ?? '',
    config_type: row.config_type as ConfigFormType,
    default_value: row.default_value ?? '',
    optionsText: formatOptionsText(row.options),
    required: row.required,
    regex: row.regex ?? '',
    min_value: row.min_value ?? undefined,
    max_value: row.max_value ?? undefined,
    sort: row.sort,
    status: row.status,
    label: row.label ?? '',
    description: row.description ?? '',
    is_public: row.is_public,
    app_key: row.app_key ?? '',
    user_id: row.user_id ?? undefined,
  })
  // 非加密配置编辑时展示原值；加密配置留空，避免误覆盖密文
  if (!row.is_encrypted) {
    form.config_val = row.config_val ?? row.display_val ?? ''
  }
  dialogVisible.value = true
}

async function submitForm() {
  await formRef.value?.validate()
  const payload = buildPayload()
  submitting.value = true
  try {
    if (editId.value) {
      await configApi.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await configApi.create(payload as ConfigPayload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    reload()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: ConfigInfo) {
  await ElMessageBox.confirm(`确定删除配置「${row.config_key}」？删除后不可恢复。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await configApi.remove(row.id)
  ElMessage.success('删除成功')
  reload()
}

async function restoreDefault(row: ConfigInfo) {
  if (!row.default_value) {
    ElMessage.warning('该配置没有设置默认值')
    return
  }
  await ElMessageBox.confirm(`确定将「${row.config_key}」恢复为默认值？`, '恢复默认值', {
    type: 'warning',
    confirmButtonText: '恢复',
    cancelButtonText: '取消',
  })
  await configApi.update(row.id, { config_val: row.default_value })
  ElMessage.success('已恢复默认值')
  reload()
}

async function openHistory(row: ConfigInfo) {
  historyConfigKey.value = row.config_key
  historyPage.value = 1
  historyVisible.value = true
  await loadHistory()
}

async function loadHistory() {
  if (!historyConfigKey.value) return
  historyLoading.value = true
  try {
    const res = await configApi.history({
      config_key: historyConfigKey.value,
      page: historyPage.value,
      page_size: historyPageSize.value,
    })
    historyRows.value = res.data?.items ?? []
    historyTotal.value = res.data?.total ?? 0
  } finally {
    historyLoading.value = false
  }
}

function handleHistoryPageSizeChange() {
  historyPage.value = 1
  loadHistory()
}

function createDefaultForm(): ConfigFormState {
  return {
    scope: 'global',
    config_key: '',
    config_val: '',
    val_type: 'string',
    is_encrypted: false,
    category: '',
    config_type: 'input',
    default_value: '',
    optionsText: '',
    required: false,
    regex: '',
    min_value: undefined,
    max_value: undefined,
    sort: 0,
    status: 1,
    label: '',
    description: '',
    is_public: false,
    app_key: '',
    user_id: undefined,
  }
}

function buildPayload(): Partial<ConfigPayload> {
  const payload: Partial<ConfigPayload> = {
    scope: form.scope,
    config_key: form.config_key.trim(),
    val_type: form.val_type,
    is_encrypted: form.is_encrypted,
    category: trimToNull(form.category),
    config_type: form.config_type,
    default_value: trimToNull(form.default_value),
    options: form.config_type === 'select' ? parseOptionsText(form.optionsText, true) : null,
    required: form.required,
    regex: trimToNull(form.regex),
    min_value: showNumberLimit.value ? form.min_value ?? null : null,
    max_value: showNumberLimit.value ? form.max_value ?? null : null,
    sort: form.sort,
    status: form.status,
    label: trimToNull(form.label),
    description: trimToNull(form.description),
    is_public: form.is_public,
    app_key: form.scope === 'app' || form.scope === 'user' ? trimToNull(form.app_key) : null,
    user_id: form.scope === 'user' ? form.user_id ?? null : null,
  }

  // 加密字段编辑时留空不覆盖，新增或明文编辑时按表单值提交
  if (!(isEncryptedEdit.value && !form.config_val.trim())) {
    payload.config_val = form.config_val
  }

  return payload
}

function normalizeListData(data: unknown): ConfigInfo[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object' && Array.isArray((data as { items?: unknown }).items)) {
    return (data as { items: ConfigInfo[] }).items
  }
  return []
}

function normalizeImportItems(parsed: unknown): ConfigPayload[] {
  const source = Array.isArray(parsed)
    ? parsed
    : parsed && typeof parsed === 'object' && Array.isArray((parsed as { items?: unknown }).items)
      ? (parsed as { items: unknown[] }).items
      : []

  return source
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
    .map((item) => {
      const payload: ConfigPayload = {
        scope: normalizeScope(item.scope),
        config_key: String(item.config_key || '').trim(),
        config_val: item.config_val === null || item.config_val === undefined ? null : String(item.config_val),
        val_type: String(item.val_type || 'string'),
        is_encrypted: Boolean(item.is_encrypted),
        category: toNullableString(item.category),
        config_type: String(item.config_type || 'input'),
        default_value: toNullableString(item.default_value),
        options: normalizeOptions(item.options),
        required: Boolean(item.required),
        regex: toNullableString(item.regex),
        min_value: toNullableNumber(item.min_value),
        max_value: toNullableNumber(item.max_value),
        sort: Number(item.sort || 0),
        status: item.status === 0 ? 0 : 1,
        label: toNullableString(item.label),
        description: toNullableString(item.description),
        is_public: Boolean(item.is_public),
        app_key: toNullableString(item.app_key),
        user_id: toNullableNumber(item.user_id),
      }
      return payload
    })
    .filter((item) => item.config_key)
}

function normalizeScope(value: unknown): ConfigScope {
  return ['global', 'tenant', 'app', 'user'].includes(String(value)) ? String(value) as ConfigScope : 'global'
}

function normalizeOptions(value: unknown): ConfigPayload['options'] {
  if (Array.isArray(value)) return value as ConfigPayload['options']
  if (value && typeof value === 'object') return value as Record<string, unknown>
  return null
}

function toNullableString(value: unknown) {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return text || null
}

function toNullableNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function parseOptionsText(value: string, throwError: true): ConfigPayload['options']
function parseOptionsText(value: string, throwError: false): ConfigOption[] | Record<string, unknown> | null
function parseOptionsText(value: string, throwError: boolean) {
  const text = value.trim()
  if (!text) return null
  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) {
      return parsed.map((item) => ({
        label: String(item.label ?? item.value ?? ''),
        value: item.value,
      })).filter((item) => item.label && item.value !== undefined)
    }
    if (form.config_type === 'select') {
      throw new Error('下拉框选项必须是 JSON 数组')
    }
    if (parsed && typeof parsed === 'object') return parsed
    throw new Error('选项配置必须是 JSON 数组或对象')
  } catch (error) {
    if (throwError) throw error
    return null
  }
}

function formatOptionsText(options: ConfigInfo['options']) {
  if (!options) return ''
  return JSON.stringify(options, null, 2)
}

function validateOptionsText(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (form.config_type !== 'select' || !value.trim()) {
    callback()
    return
  }
  try {
    parseOptionsText(value, true)
    callback()
  } catch {
    callback(new Error('请输入合法的选项 JSON'))
  }
}

function validateConfigValue(_rule: unknown, value: string, callback: (error?: Error) => void) {
  const empty = !String(value ?? '').trim()
  if (form.required && empty && !(isEncryptedEdit.value && form.is_encrypted)) {
    callback(new Error('请输入配置值'))
    return
  }
  if (form.val_type === 'json' && !empty) {
    try {
      JSON.parse(value)
    } catch {
      callback(new Error('请输入合法 JSON'))
      return
    }
  }
  if (['int', 'number'].includes(form.val_type) && !empty) {
    const num = Number(value)
    if (!Number.isFinite(num)) {
      callback(new Error('请输入合法数字'))
      return
    }
    if (form.val_type === 'int' && !Number.isInteger(num)) {
      callback(new Error('请输入整数'))
      return
    }
    if (form.min_value !== undefined && num < form.min_value) {
      callback(new Error('配置值不能小于最小值'))
      return
    }
    if (form.max_value !== undefined && num > form.max_value) {
      callback(new Error('配置值不能大于最大值'))
      return
    }
  }
  if (form.scope === 'app' && !form.app_key.trim()) {
    callback(new Error('应用作用域必须填写应用标识'))
    return
  }
  if (form.scope === 'user' && !form.user_id) {
    callback(new Error('用户作用域必须填写用户ID'))
    return
  }
  if (form.min_value !== undefined && form.max_value !== undefined && form.min_value > form.max_value) {
    callback(new Error('最小值不能大于最大值'))
    return
  }
  callback()
}

function handleScopeChange() {
  if (form.scope !== 'app' && form.scope !== 'user') form.app_key = ''
  if (form.scope !== 'user') form.user_id = undefined
}

function handleValueTypeChange() {
  // 按值类型同步推荐控件，用户仍可手动调整
  if (form.val_type === 'bool') form.config_type = 'switch'
  if (form.val_type === 'json') form.config_type = 'json'
  if (['int', 'number'].includes(form.val_type)) form.config_type = 'number'
  if (!showNumberLimit.value) {
    form.min_value = undefined
    form.max_value = undefined
  }
}

function scopeLabel(scope: string) {
  return scopeOptions.find((item) => item.value === scope)?.label ?? scope
}

function scopeTagType(scope: string) {
  const map: Record<string, 'success' | 'warning' | 'primary' | 'info'> = {
    global: 'success',
    tenant: 'warning',
    app: 'primary',
    user: 'info',
  }
  return map[scope] ?? 'info'
}

function configTypeLabel(type: string) {
  return formTypeOptions.find((item) => item.value === type)?.label ?? type
}

function displayConfigValue(row: ConfigInfo) {
  if (row.is_encrypted) return row.display_val || '******'
  return row.display_val ?? row.config_val ?? '-'
}

function toConfigRow(row: unknown) {
  return row as ConfigInfo
}

function ownerText(row: ConfigInfo) {
  if (row.scope === 'app') return row.app_key ? `应用：${row.app_key}` : '-'
  if (row.scope === 'user') return row.user_id ? `用户：${row.user_id}` : '-'
  if (row.scope === 'tenant') return row.tenant_id ? `租户：${row.tenant_id}` : '当前租户'
  return '全局'
}

function categoryCount(category: string) {
  if (!category) return categoryData.value.length
  return categoryData.value.filter((item) => item.category === category).length
}

function formatChangedAt(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  // 后端返回 ISO UTC 时间，这里按浏览器本地时区展示为 YYYY-MM-DD HH:mm:ss
  const year = date.getFullYear()
  const month = padDatePart(date.getMonth() + 1)
  const day = padDatePart(date.getDate())
  const hour = padDatePart(date.getHours())
  const minute = padDatePart(date.getMinutes())
  const second = padDatePart(date.getSeconds())
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

function padDatePart(value: number) {
  return String(value).padStart(2, '0')
}

function formatFileDate(date: Date) {
  const year = date.getFullYear()
  const month = padDatePart(date.getMonth() + 1)
  const day = padDatePart(date.getDate())
  const hour = padDatePart(date.getHours())
  const minute = padDatePart(date.getMinutes())
  const second = padDatePart(date.getSeconds())
  return `${year}${month}${day}${hour}${minute}${second}`
}

function trimToNull(value: string) {
  const text = value.trim()
  return text || null
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return '未知错误'
}

onMounted(reload)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.config-center-page {
  .filter-card {
    margin-bottom: 16px;
  }
}

.config-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.category-card {
  position: sticky;
  top: 16px;
}

.category-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.category-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;

  &:hover,
  &.active {
    background: rgba(64, 158, 255, 0.1);
  }

  &.active .category-name {
    color: var(--el-color-primary);
  }
}

.category-name {
  font-weight: 600;
  color: $text-primary;
}

.category-desc {
  margin-top: 4px;
  color: $text-secondary;
  font-size: 12px;
  line-height: 1.4;
}

.config-main {
  min-width: 0;
}

.category-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.category-header-title {
  font-size: 18px;
  font-weight: 600;
  color: $text-primary;
}

.category-header-desc {
  margin-top: 4px;
  color: $text-secondary;
}

.category-stats {
  display: flex;
  gap: 28px;
  text-align: center;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.hidden-file-input {
  display: none;
}

.filter-input {
  width: 260px;
}

.filter-select {
  width: 150px;
}

.filter-select-sm {
  width: 120px;
}

.config-key-cell {
  line-height: 1.4;
}

.config-key-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-key {
  font-weight: 600;
  color: $text-primary;
}

.config-meta {
  margin-top: 3px;
  color: $text-secondary;
  font-size: 12px;
}

.value-text {
  color: $text-regular;
  word-break: break-all;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.encrypted-tip {
  margin-bottom: 16px;
}

.history-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-weight: 600;
}

.w-full {
  width: 100%;
}

@media (max-width: 1200px) {
  .config-layout {
    grid-template-columns: 1fr;
  }

  .category-card {
    position: static;
  }
}
</style>
