<template>
  <div class="page-container integration-page">
    <div class="integration-layout">
      <el-card class="provider-card" shadow="never">
        <div class="panel-title">协作平台</div>
        <div
          class="provider-item"
          :class="{ active: query.provider === '' }"
          @click="selectProvider('')"
        >
          <div>
            <div class="provider-name">全部平台</div>
            <div class="provider-desc">统一管理所有集成连接</div>
          </div>
          <el-tag size="small" effect="plain">{{ connections.length }}</el-tag>
        </div>
        <div
          v-for="provider in providers"
          :key="provider.code"
          class="provider-item"
          :class="{ active: query.provider === provider.code }"
          @click="selectProvider(provider.code)"
        >
          <div>
            <div class="provider-name">{{ provider.name }}</div>
            <div class="provider-desc">{{ capabilityText(provider.capabilities) }}</div>
          </div>
          <el-tag size="small" effect="plain">{{ providerConnectionCount(provider.code) }}</el-tag>
        </div>
      </el-card>

      <div class="integration-main">
        <el-card class="filter-card" shadow="never">
          <div class="page-header">
            <div>
              <div class="page-title">集成中心</div>
              <div class="page-desc">统一接入飞书、钉钉、企业微信，业务侧通过默认连接无痛切换平台。</div>
            </div>
            <div class="header-stats">
              <el-statistic title="连接数" :value="connections.length" />
              <el-statistic title="已启用" :value="enabledCount" />
              <el-statistic title="默认连接" :value="defaultCount" />
            </div>
          </div>

          <div class="toolbar">
            <div class="filters">
              <el-select v-model="query.provider" placeholder="平台" clearable class="filter-select" @change="reload">
                <el-option label="全部平台" value="" />
                <el-option v-for="item in providers" :key="item.code" :label="item.name" :value="item.code" />
              </el-select>
              <el-select v-model="query.enabled" placeholder="启用状态" clearable class="filter-select" @change="reload">
                <el-option label="已启用" :value="true" />
                <el-option label="已停用" :value="false" />
              </el-select>
              <el-button :icon="Search" type="primary" @click="reload">查询</el-button>
              <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
            </div>
            <el-button type="primary" :icon="Plus" v-permission="'integration:manage'" @click="openCreate">
              新增连接
            </el-button>
          </div>
        </el-card>

        <el-card shadow="never">
          <el-table v-loading="loading" :data="connections" border stripe>
            <el-table-column label="连接" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="connection-cell">
                  <div class="connection-title">
                    <span>{{ row.name }}</span>
                    <el-tag v-if="row.is_default" size="small" type="success" effect="plain">默认</el-tag>
                  </div>
                  <div class="connection-meta">{{ row.provider_name }} / {{ providerCodeText(row.provider) }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="能力" min-width="220">
              <template #default="{ row }">
                <el-space wrap>
                  <el-tag v-for="item in row.capabilities" :key="item" size="small" effect="plain">
                    {{ capabilityLabel(item) }}
                  </el-tag>
                </el-space>
              </template>
            </el-table-column>
            <el-table-column label="凭证" width="110" align="center">
              <template #default="{ row }">
                <el-tag :type="row.secret_configured ? 'success' : 'warning'" size="small">
                  {{ row.secret_configured ? '已配置' : '未配置' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="测试状态" width="150" align="center">
              <template #default="{ row }">
                <el-tooltip v-if="row.last_test_message" :content="row.last_test_message" placement="top">
                  <el-tag :type="testStatusType(row.last_test_status)" size="small">
                    {{ testStatusLabel(row.last_test_status) }}
                  </el-tag>
                </el-tooltip>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="排序" prop="sort" width="80" align="center" />
            <el-table-column label="操作" width="260" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" v-permission="'integration:manage'" :loading="testingId === row.id" @click="handleTest(asConnection(row))">
                  测试
                </el-button>
                <el-button link type="primary" v-permission="'integration:manage'" @click="openEdit(asConnection(row))">编辑</el-button>
                <el-button
                  v-if="!row.is_default"
                  link
                  type="success"
                  v-permission="'integration:manage'"
                  @click="setDefault(asConnection(row))"
                >
                  设默认
                </el-button>
                <el-button link type="danger" v-permission="'integration:manage'" @click="handleDelete(asConnection(row))">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="760px" destroy-on-close>
      <el-alert
        v-if="editId"
        class="secret-tip"
        type="warning"
        show-icon
        :closable="false"
        title="敏感配置不会回显。编辑时敏感字段留空表示保留原值，只会覆盖已填写的字段。"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="平台" prop="provider">
              <el-select v-model="form.provider" class="w-full" :disabled="Boolean(editId)" @change="handleProviderChange">
                <el-option v-for="item in providers" :key="item.code" :label="item.name" :value="item.code" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="连接名称" prop="name">
              <el-input v-model="form.name" maxlength="64" placeholder="如：默认飞书机器人" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="默认连接">
              <el-switch v-model="form.is_default" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :max="9999" class="w-full" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="启用能力" prop="capabilities">
          <el-checkbox-group v-model="form.capabilities">
            <el-checkbox v-for="item in currentProvider?.capabilities || []" :key="item" :value="item">
              {{ capabilityLabel(item) }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <div class="config-section-header">
          <div>
            <div class="config-section-title">配置项</div>
            <div class="config-section-desc">非敏感配置默认显示；敏感配置默认只显示已启用能力需要填写的字段。</div>
          </div>
          <el-switch v-model="showAdvancedConfig" active-text="显示全部高级配置" />
        </div>

        <el-divider content-position="left">非敏感配置</el-divider>
        <el-empty
          v-if="displayConfigFields.length === 0"
          :description="emptyConfigDescription"
          :image-size="72"
        />
        <el-row v-else :gutter="16">
          <el-col v-for="field in displayConfigFields" :key="`${form.provider}-${field}`" :span="12">
            <el-form-item>
              <template #label>
                <span class="field-label">
                  {{ fieldLabel(field) }}
                  <el-tooltip :content="fieldDescription(field)" placement="top" effect="dark">
                    <el-icon class="field-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input
                v-model="form.config[field]"
                autocomplete="off"
                :name="`integration-config-${field}`"
                :placeholder="`请输入 ${fieldLabel(field)}`"
              />
              <div class="field-tip">{{ fieldDescription(field) }}</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">敏感配置</el-divider>
        <el-empty
          v-if="displaySecretFields.length === 0"
          :description="emptySecretDescription"
          :image-size="72"
        />
        <el-row v-else :gutter="16">
          <el-col v-for="field in displaySecretFields" :key="`${form.provider}-${field}`" :span="12">
            <el-form-item>
              <template #label>
                <span class="field-label">
                  {{ fieldLabel(field) }}
                  <el-tooltip :content="fieldDescription(field)" placement="top" effect="dark">
                    <el-icon class="field-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <el-input
                v-model="form.secret_config[field]"
                type="password"
                show-password
                autocomplete="new-password"
                :name="`integration-secret-${field}`"
                :placeholder="secretPlaceholder(field)"
              />
              <div class="field-tip">{{ fieldDescription(field) }}</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, QuestionFilled, Refresh, Search } from '@element-plus/icons-vue'
import { integrationApi } from '@/api/integration'
import type {
  IntegrationCapabilityCode,
  IntegrationConnection,
  IntegrationConnectionCreate,
  IntegrationConnectionUpdate,
  IntegrationProviderCode,
  ProviderInfo,
} from '@/types'

interface FormModel extends Omit<IntegrationConnectionCreate, 'config'> {
  config: Record<string, string>
}

const loading = ref(false)
const saving = ref(false)
const testingId = ref<number | null>(null)
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const providers = ref<ProviderInfo[]>([])
const connections = ref<IntegrationConnection[]>([])
const allConnections = ref<IntegrationConnection[]>([])
const showAdvancedConfig = ref(false)

// 能力字段映射仅控制前端动态展示，不改变后端接口字段和保存结构
const COMMON_CAPABILITY_FIELD_MAP: Partial<Record<IntegrationCapabilityCode, string[]>> = {
  bot_message: ['webhook_url', 'signing_secret'],
}

const PROVIDER_CAPABILITY_FIELD_MAP: Partial<
  Record<IntegrationProviderCode, Partial<Record<IntegrationCapabilityCode, string[]>>>
> = {
  feishu: {
    oauth: ['app_id', 'app_secret'],
    contact_sync: ['app_id', 'app_secret'],
    event_callback: ['verification_token', 'encrypt_key'],
  },
  dingtalk: {
    oauth: ['app_key', 'app_secret'],
    contact_sync: ['app_key', 'app_secret'],
  },
  wecom: {
    contact_sync: ['corp_id', 'corp_secret'],
    event_callback: ['token', 'encoding_aes_key'],
  },
}

const query = reactive({
  provider: '' as IntegrationProviderCode | '',
  enabled: undefined as boolean | undefined,
})

const form = reactive<FormModel>({
  provider: 'feishu',
  name: '',
  enabled: true,
  is_default: false,
  capabilities: ['bot_message'],
  config: {},
  secret_config: {},
  sort: 0,
})

const rules: FormRules = {
  provider: [{ required: true, message: '请选择平台', trigger: 'change' }],
  name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
  capabilities: [{ required: true, message: '请选择至少一个能力', trigger: 'change' }],
}

const dialogTitle = computed(() => (editId.value ? '编辑集成连接' : '新增集成连接'))
const enabledCount = computed(() => connections.value.filter((item: IntegrationConnection) => item.enabled).length)
const defaultCount = computed(() => connections.value.filter((item: IntegrationConnection) => item.is_default).length)
const currentProvider = computed(() => providers.value.find((item: ProviderInfo) => item.code === form.provider))
const configFields = computed(() => currentProvider.value?.config_fields || [])
const secretFields = computed(() => {
  const provider = currentProvider.value
  if (!provider) return []
  return uniqueFields([
    ...provider.required_secret_fields,
    ...provider.optional_secret_fields,
    ...Array.from(capabilityFields(form.provider, provider.capabilities)),
  ]).filter(field => !configFields.value.includes(field))
})
const displayConfigFields = computed(() => {
  return configFields.value
})
const displaySecretFields = computed(() => {
  if (showAdvancedConfig.value) return secretFields.value
  return filterFieldsByCapabilities(secretFields.value)
})
const emptyConfigDescription = computed(() => {
  return '当前平台暂无非敏感配置项'
})
const emptySecretDescription = computed(() => {
  if (!form.capabilities.length) return '请选择启用能力后填写配置'
  return showAdvancedConfig.value ? '当前平台暂无敏感配置项' : '当前启用能力暂无需要填写的敏感配置'
})

onMounted(async () => {
  await loadProviders()
  await reload()
})

async function loadProviders() {
  const res = await integrationApi.providers()
  providers.value = res.data || []
  if (providers.value.length && !providers.value.some(item => item.code === form.provider)) {
    form.provider = providers.value[0].code
  }
}

async function reload() {
  loading.value = true
  try {
    const [listRes, allRes] = await Promise.all([
      integrationApi.connections({
        provider: query.provider || undefined,
        enabled: query.enabled,
      }),
      integrationApi.connections(),
    ])
    connections.value = listRes.data || []
    allConnections.value = allRes.data || []
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.provider = ''
  query.enabled = undefined
  reload()
}

function selectProvider(provider: IntegrationProviderCode | '') {
  query.provider = provider
  reload()
}

function openCreate() {
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: IntegrationConnection) {
  editId.value = row.id
  resetForm()
  form.provider = row.provider
  form.name = row.name
  form.enabled = row.enabled
  form.is_default = row.is_default
  form.capabilities = [...row.capabilities]
  // 编辑时保持 form.config 原对象引用，避免动态 v-model 绑定丢失，同时兼容旧接口未返回 config 的情况
  replaceRecord(form.config, normalizeConfigRecord(row.config, row.provider))
  replaceRecord(form.secret_config, {})
  form.sort = row.sort
  dialogVisible.value = true
}

function resetForm() {
  const provider = query.provider || providers.value[0]?.code || 'feishu'
  showAdvancedConfig.value = false
  form.provider = provider
  form.name = ''
  form.enabled = true
  form.is_default = false
  form.capabilities = defaultCapabilities(provider)
  replaceRecord(form.config, normalizeConfigRecord({}, provider))
  replaceRecord(form.secret_config, {})
  form.sort = 0
  formRef.value?.clearValidate()
}

function handleProviderChange() {
  showAdvancedConfig.value = false
  form.capabilities = defaultCapabilities(form.provider)
  replaceRecord(form.config, normalizeConfigRecord({}, form.provider))
  replaceRecord(form.secret_config, {})
}

async function submitForm() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = buildPayload()
    if (editId.value) {
      await integrationApi.updateConnection(editId.value, payload as IntegrationConnectionUpdate)
      ElMessage.success('保存成功')
    } else {
      await integrationApi.createConnection(payload as IntegrationConnectionCreate)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await reload()
  } finally {
    saving.value = false
  }
}

function buildPayload(): IntegrationConnectionCreate | IntegrationConnectionUpdate {
  const secretConfig = Object.fromEntries(
    Object.entries(form.secret_config).filter(([, value]) => value !== undefined && value !== ''),
  ) as Record<string, string>

  const base = {
    name: form.name,
    enabled: form.enabled,
    is_default: form.is_default,
    capabilities: form.capabilities,
    config: cleanRecord(form.config),
    secret_config: secretConfig,
    sort: form.sort,
  }

  if (editId.value) {
    return base
  }
  return { provider: form.provider, ...base }
}

async function handleTest(row: IntegrationConnection) {
  testingId.value = row.id
  try {
    const res = await integrationApi.testConnection(row.id)
    if (res.data?.success) {
      ElMessage.success(res.data.message || '连接测试成功')
    } else {
      ElMessage.warning(res.data?.message || '连接测试失败')
    }
    await reload()
  } finally {
    testingId.value = null
  }
}

async function setDefault(row: IntegrationConnection) {
  await integrationApi.updateConnection(row.id, { is_default: true })
  ElMessage.success('已设置为默认连接')
  await reload()
}

async function handleDelete(row: IntegrationConnection) {
  await ElMessageBox.confirm(`确认删除连接「${row.name}」吗？`, '删除确认', { type: 'warning' })
  await integrationApi.deleteConnection(row.id)
  ElMessage.success('删除成功')
  await reload()
}

function defaultCapabilities(providerCode: string): IntegrationCapabilityCode[] {
  const provider = providers.value.find((item: ProviderInfo) => item.code === providerCode)
  if (!provider) return ['bot_message']
  return provider.capabilities.includes('bot_message') ? ['bot_message'] : provider.capabilities.slice(0, 1)
}

function filterFieldsByCapabilities(fields: string[]) {
  const allowedFields = capabilityFields(form.provider, form.capabilities)
  return fields.filter(field => allowedFields.has(field))
}

function capabilityFields(provider: IntegrationProviderCode, capabilities: IntegrationCapabilityCode[]) {
  const fields = new Set<string>()

  capabilities.forEach(capability => {
    capabilityFieldMap(provider, capability).forEach((field: string) => fields.add(field))
  })

  return fields
}

function capabilityFieldMap(provider: IntegrationProviderCode, capability: IntegrationCapabilityCode) {
  return PROVIDER_CAPABILITY_FIELD_MAP[provider]?.[capability] || COMMON_CAPABILITY_FIELD_MAP[capability] || []
}

function uniqueFields(fields: string[]) {
  return Array.from(new Set(fields.filter(Boolean)))
}

function normalizeConfigRecord(record: Record<string, unknown> | null | undefined, provider: IntegrationProviderCode) {
  const normalized = stringifyRecord(record || {})
  const providerConfigFields = providers.value.find((item: ProviderInfo) => item.code === provider)?.config_fields || []
  providerConfigFields.forEach((field: string) => {
    if (!(field in normalized)) {
      normalized[field] = ''
    }
  })
  return normalized
}

function replaceRecord(target: Record<string, string>, source: Record<string, string>) {
  Object.keys(target).forEach((key: string) => {
    delete target[key]
  })
  Object.assign(target, source)
}

function providerConnectionCount(provider: string) {
  return allConnections.value.filter((item: IntegrationConnection) => item.provider === provider).length
}

function providerCodeText(provider: string) {
  return providers.value.find((item: ProviderInfo) => item.code === provider)?.name || provider
}

function capabilityText(items: IntegrationCapabilityCode[]) {
  return items.map(capabilityLabel).join(' / ')
}

function capabilityLabel(value: string) {
  const map: Record<string, string> = {
    bot_message: '机器人消息',
    oauth: 'OAuth 登录',
    contact_sync: '通讯录同步',
    event_callback: '事件回调',
  }
  return map[value] || value
}

function fieldLabel(value: string) {
  const map: Record<string, string> = {
    webhook_url: '机器人 Webhook',
    signing_secret: '签名密钥',
    app_id: 'App ID',
    app_key: 'App Key',
    app_secret: 'App Secret',
    corp_id: '企业 ID',
    corp_secret: '企业密钥',
    encrypt_key: '加密 Key',
    verification_token: '校验 Token',
    token: '回调 Token',
    encoding_aes_key: 'EncodingAESKey',
    agent_id: 'Agent ID',
    app_type: '应用类型',
  }
  return map[value] || value
}

function fieldDescription(value: string) {
  // 配置项中文说明仅用于前端提示，不改变提交给后端的字段名和接口结构
  const map: Record<string, string> = {
    webhook_url: '机器人 Webhook 地址，用于发送群消息或通知，请从对应平台机器人配置页复制完整 URL。',
    signing_secret: '机器人签名密钥，用于校验消息来源和生成请求签名，编辑时留空表示继续使用原密钥。',
    app_id: '开放平台应用 ID，通常用于 OAuth、事件订阅或接口调用的应用身份识别。',
    app_key: '开放平台应用 Key，常见于钉钉等平台，用于标识当前应用。',
    app_secret: '开放平台应用密钥，用于换取访问令牌等敏感操作，请妥善保管。',
    corp_id: '企业 ID，用于定位企业租户，例如企业微信 CorpID 或钉钉企业标识。',
    corp_secret: '企业级应用密钥，用于获取企业访问令牌，编辑时留空表示不覆盖原值。',
    encrypt_key: '事件回调加密 Key，用于解密平台推送的加密消息。',
    verification_token: '事件订阅校验 Token，用于校验回调请求是否来自平台。',
    token: '回调 Token，用于事件回调 URL 验证和消息签名校验。',
    encoding_aes_key: 'EncodingAESKey，用于企业微信等平台回调消息的 AES 加解密。',
    agent_id: '应用 Agent ID，用于企业微信或钉钉内部应用消息发送和接口调用。',
    app_type: '应用类型，用于区分自建应用、企业内部应用或第三方应用，请按平台配置填写。',
  }
  return map[value] || '请按对应协作平台控制台提供的配置值填写。'
}

function secretPlaceholder(field: string) {
  return editId.value ? `留空不覆盖 ${fieldLabel(field)}` : `请输入 ${fieldLabel(field)}`
}

function testStatusLabel(status?: string | null) {
  if (status === 'success') return '测试成功'
  if (status === 'failed') return '测试失败'
  return '未测试'
}

function testStatusType(status?: string | null) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

function cleanRecord(record: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(record).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
}

function stringifyRecord(record: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [key, value == null ? '' : String(value)]),
  )
}

function asConnection(row: unknown) {
  return row as IntegrationConnection
}
</script>

<style scoped lang="scss">
.integration-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
}

.provider-card {
  height: fit-content;
}

.panel-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
}

.provider-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  transition: all 0.2s;

  &:hover,
  &.active {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary-light-5);
  }
}

.provider-name,
.page-title,
.connection-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.provider-desc,
.page-desc,
.connection-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.integration-main {
  min-width: 0;
}

.filter-card {
  margin-bottom: 16px;
}

.page-header,
.toolbar,
.connection-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header {
  margin-bottom: 16px;
}

.header-stats {
  display: flex;
  gap: 28px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-select {
  width: 150px;
}

.connection-cell {
  min-width: 0;
}

.secret-tip {
  margin-bottom: 16px;
}

.config-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.config-section-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.config-section-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.field-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.field-help {
  color: var(--el-text-color-secondary);
  cursor: help;
}

.field-tip {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.w-full {
  width: 100%;
}

@media (max-width: 1200px) {
  .integration-layout {
    grid-template-columns: 1fr;
  }
}
</style>
