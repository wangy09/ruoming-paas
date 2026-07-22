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

    <FormDialog
      v-model:visible="dialogVisible"
      :edit-id="editId"
      :editing-row="editingRow"
      :initial-form="form"
      @submit="handleFormSubmit"
    />

    <HistoryDialog
      v-model="historyVisible"
      :config-key="historyConfigKey"
      :loading="historyLoading"
      :rows="historyRows"
      :total="historyTotal"
      :page="historyPage"
      :page-size="historyPageSize"
      @refresh="loadHistory"
      @page-change="loadHistory"
      @page-size-change="handleHistoryPageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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
import FormDialog from './components/FormDialog.vue'
import HistoryDialog from './components/HistoryDialog.vue'

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

const categoryOptions = [
  { label: '全部配置', value: '', description: '查看当前作用域下全部配置' },
  { label: '站点配置', value: 'site', description: '系统名称、Logo、登录页文案' },
  { label: '界面配置', value: 'ui', description: '主题色、水印等前端公开配置' },
  { label: '文件配置', value: 'file', description: '上传大小、扩展名白名单' },
  { label: '登录安全', value: 'auth', description: '失败锁定、密码和验证码策略' },
  { label: '限流配置', value: 'rate_limit', description: '全局/IP/用户/租户级限流规则' },
  { label: 'AI 配置', value: 'ai', description: '模型默认参数、调用默认值' },
  { label: '消息配置', value: 'message', description: '消息提醒和公告行为' },
  { label: '任务配置', value: 'task', description: '计划任务和执行日志策略' },
  { label: '审计配置', value: 'audit', description: '操作日志保留和审计策略' },
  { label: '监控配置', value: 'monitor', description: '监控刷新和采集策略' },
]

const loading = ref(false)
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
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const editingRow = ref<ConfigInfo | null>(null)

const importInputRef = ref<HTMLInputElement>()

const query = reactive({
  scope: 'global' as ConfigScope | undefined,
  keyword: '',
  is_public: undefined as boolean | undefined,
  is_encrypted: undefined as boolean | undefined,
  status: undefined as number | undefined,
})

const form = reactive<ConfigFormState>(createDefaultForm())

const pagedTableData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tableData.value.slice(start, start + pageSize.value)
})

const activeCategoryInfo = computed(() => (
  categoryOptions.find((item) => item.value === activeCategory.value) ?? categoryOptions[0]
))
const publicCount = computed(() => tableData.value.filter((item) => item.is_public).length)
const encryptedCount = computed(() => tableData.value.filter((item) => item.is_encrypted).length)

function scopeLabel(scope: string) {
  return scopeOptions.find(item => item.value === scope)?.label || scope
}

function scopeTagType(scope: string) {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = { global: 'success', tenant: 'warning', app: 'primary', user: 'info' }
  return map[scope] || 'info'
}

function configTypeLabel(type: string) {
  const map: Record<string, string> = {
    input: '输入框', textarea: '多行文本', switch: '开关',
    select: '下拉框', json: 'JSON', password: '密码框', number: '数字输入',
  }
  return map[type] || type
}

function categoryCount(category: string) {
  if (!category) return categoryData.value.length
  return categoryData.value.filter(item => item.category === category).length
}

function toConfigRow(row: unknown): ConfigInfo {
  return row as ConfigInfo
}

function displayConfigValue(row: ConfigInfo) {
  if (row.is_encrypted) return '******'
  const val = row.display_val ?? row.config_val
  if (typeof val === 'string' && val.length > 50) return val.slice(0, 50) + '...'
  return val ?? '-'
}

function ownerText(row: ConfigInfo) {
  if (row.scope === 'app') return `应用: ${row.app_key || '-'}`
  if (row.scope === 'user') return `用户: ${row.user_id || '-'}`
  if (row.scope === 'tenant') return '租户'
  return '全局'
}

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
      filters: { ...query, category: activeCategory.value || undefined },
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
  if (!row.is_encrypted) {
    form.config_val = row.config_val ?? row.display_val ?? ''
  }
  dialogVisible.value = true
}

async function handleFormSubmit(formData: ConfigFormState) {
  const payload = buildPayload(formData)
  if (editId.value) {
    await configApi.update(editId.value, payload)
    ElMessage.success('更新成功')
  } else {
    await configApi.create(payload as ConfigPayload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  reload()
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

function buildPayload(formData: ConfigFormState): Partial<ConfigPayload> {
  const payload: Partial<ConfigPayload> = {
    scope: formData.scope,
    config_key: formData.config_key.trim(),
    val_type: formData.val_type,
    is_encrypted: formData.is_encrypted,
    category: trimToNull(formData.category),
    config_type: formData.config_type,
    default_value: trimToNull(formData.default_value),
    options: formData.config_type === 'select' ? parseOptionsText(formData.optionsText, true) : null,
    required: formData.required,
    regex: trimToNull(formData.regex),
    min_value: showNumberLimit(formData) ? formData.min_value ?? null : null,
    max_value: showNumberLimit(formData) ? formData.max_value ?? null : null,
    sort: formData.sort,
    status: formData.status,
    label: trimToNull(formData.label),
    description: trimToNull(formData.description),
    is_public: formData.is_public,
    app_key: formData.scope === 'app' || formData.scope === 'user' ? trimToNull(formData.app_key) : null,
    user_id: formData.scope === 'user' ? formData.user_id ?? null : null,
  }

  if (!(editId.value && editingRow.value?.is_encrypted && !formData.config_val.trim())) {
    payload.config_val = formData.config_val
  }

  return payload
}

function showNumberLimit(formData: ConfigFormState) {
  return ['int', 'number'].includes(formData.val_type) || formData.config_type === 'number'
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
    .map((item): ConfigPayload => ({
      scope: normalizeScope(item.scope),
      config_key: String(item.config_key || '').trim(),
      config_val: item.config_val === null || item.config_val === undefined ? null : String(item.config_val),
      val_type: String(item.val_type || 'string'),
      is_encrypted: Boolean(item.is_encrypted),
      category: toNullableString(item.category),
      config_type: String(item.config_type || 'input'),
      default_value: toNullableString(item.default_value),
      options: item.options ? (item.options as ConfigOption[]) : null,
      required: Boolean(item.required),
      regex: toNullableString(item.regex),
      min_value: typeof item.min_value === 'number' ? item.min_value : null,
      max_value: typeof item.max_value === 'number' ? item.max_value : null,
      sort: typeof item.sort === 'number' ? item.sort : 0,
      status: (item.status === 0 || item.status === 1) ? (item.status as 0 | 1) : 1,
      label: toNullableString(item.label),
      description: toNullableString(item.description),
      is_public: Boolean(item.is_public),
      app_key: toNullableString(item.app_key),
      user_id: typeof item.user_id === 'number' ? item.user_id : null,
    }))
}

function normalizeScope(scope: unknown): ConfigScope {
  const validScopes: ConfigScope[] = ['global', 'tenant', 'app', 'user']
  return validScopes.includes(scope as ConfigScope) ? (scope as ConfigScope) : 'global'
}

function toNullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null
  return String(value).trim() || null
}

function trimToNull(value: string): string | null {
  return value.trim() || null
}

function formatFileDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${y}${m}${d}_${h}${min}`
}

function formatOptionsText(options: unknown): string {
  if (!options) return ''
  try {
    return JSON.stringify(options, null, 2)
  } catch {
    return ''
  }
}

function parseOptionsText(text: string, strict: boolean): ConfigOption[] | null {
  try {
    return JSON.parse(text) as ConfigOption[]
  } catch {
    return []
  }
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return '未知错误'
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.config-layout {
  display: flex;
  gap: 16px;
}
.category-card {
  width: 260px;
  flex-shrink: 0;
}
.category-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}
.category-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 8px;
  transition: background-color 0.2s;
  &:hover { background-color: var(--el-fill-color-light); }
  &.active { background-color: var(--el-color-primary-light-9); }
}
.category-name { font-size: 13px; font-weight: 500; }
.category-desc { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.config-main { flex: 1; min-width: 0; }
.category-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.category-header-title { font-size: 16px; font-weight: 600; }
.category-header-desc { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.category-stats {
  display: flex;
  gap: 24px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
}
.filter-select { width: 120px; }
.filter-select-sm { width: 100px; }
.filter-input { width: 240px; }
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hidden-file-input { display: none; }
.config-key-cell { display: flex; flex-direction: column; }
.config-key-line { display: flex; align-items: center; gap: 8px; }
.config-key { font-weight: 600; font-size: 13px; }
.config-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.value-text { font-family: monospace; font-size: 12px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>