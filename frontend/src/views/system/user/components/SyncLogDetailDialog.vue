<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="同步日志详情"
    width="min(760px, 92vw)"
    class="sync-log-detail-dialog"
    append-to-body
    destroy-on-close
  >
    <template v-if="currentSyncLog">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="同步时间">{{ formatDate(currentSyncLog.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="平台">{{ getSourceProviderLabel(currentSyncLog.provider) }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ getSyncOperationLabel(currentSyncLog.operation) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ getSyncStatusLabel(currentSyncLog.status) }}</el-descriptions-item>
        <el-descriptions-item label="连接ID">{{ currentSyncLog.connection_id }}</el-descriptions-item>
        <el-descriptions-item label="同步内容">{{ getSyncLogContentLabel(currentSyncLog) }}</el-descriptions-item>
        <el-descriptions-item label="头像">{{ getSyncLogAvatarLabel(currentSyncLog) }}</el-descriptions-item>
        <el-descriptions-item label="缺失用户">{{ getSyncLogMissingUserLabel(currentSyncLog) }}</el-descriptions-item>
        <el-descriptions-item label="用户名策略">{{ getSyncLogUsernameStrategyLabel(currentSyncLog) }}</el-descriptions-item>
        <el-descriptions-item label="昵称策略">{{ getSyncLogNicknameStrategyLabel(currentSyncLog) }}</el-descriptions-item>
        <el-descriptions-item label="更新策略">{{ getSyncLogOverwriteStrategyLabel(currentSyncLog) }}</el-descriptions-item>
      </el-descriptions>

      <div class="sync-log-detail-title">统计结果</div>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="部门新增">{{ getSyncLogResult(currentSyncLog).departments_created || 0 }}</el-descriptions-item>
        <el-descriptions-item label="部门更新">{{ getSyncLogResult(currentSyncLog).departments_updated || 0 }}</el-descriptions-item>
        <el-descriptions-item label="用户新增">{{ getSyncLogResult(currentSyncLog).users_created || 0 }}</el-descriptions-item>
        <el-descriptions-item label="用户更新">{{ getSyncLogResult(currentSyncLog).users_updated || 0 }}</el-descriptions-item>
        <el-descriptions-item label="用户禁用">{{ getSyncLogResult(currentSyncLog).users_disabled || 0 }}</el-descriptions-item>
        <el-descriptions-item label="用户跳过">{{ getSyncLogResult(currentSyncLog).skipped_users || 0 }}</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="getSyncLogErrors(currentSyncLog).length"
        type="warning"
        show-icon
        :closable="false"
        class="sync-log-detail-alert"
      >
        <template #title>同步提示</template>
        <div v-for="(error, index) in getSyncLogErrors(currentSyncLog)" :key="index">
          {{ error }}
        </div>
      </el-alert>

      <div class="sync-log-detail-title">变更明细</div>
      <el-table
        v-if="getSyncLogDetails(currentSyncLog).length"
        :data="getSyncLogDetails(currentSyncLog)"
        size="small"
        max-height="260"
      >
        <el-table-column label="动作" width="80">
          <template #default="{ row }">{{ getPreviewActionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column label="对象" width="80">
          <template #default="{ row }">{{ getPreviewTargetLabel(row.target_type) }}</template>
        </el-table-column>
        <el-table-column label="名称" min-width="140">
          <template #default="{ row }">{{ row.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="外部ID" min-width="160">
          <template #default="{ row }">{{ row.external_id || '-' }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="160">
          <template #default="{ row }">{{ row.reason || '-' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="本条日志没有明细记录" :image-size="60" />
    </template>
    <template #footer>
      <el-button type="primary" @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { formatDate } from '@/utils/format'
import type {
  ContactSyncLogItem,
  ContactSyncPreviewResult,
  ContactSyncRequest,
  ContactSyncPreviewItem,
} from '@/types'

type UsernameStrategy = 'email_prefix' | 'phone' | 'name' | 'external_id'
type NicknameStrategy = 'name' | 'nickname' | 'username'
type FieldUpdateMode = 'never' | 'if_empty' | 'always'

interface ContactSyncLogDetailData {
  details?: unknown
}

interface SourceProviderMeta {
  label: string
  tagType: 'primary' | 'success' | 'info' | 'warning' | 'danger'
}

const SOURCE_PROVIDER_MAP: Record<string, SourceProviderMeta> = {
  feishu: { label: '飞书', tagType: 'primary' },
  dingtalk: { label: '钉钉', tagType: 'warning' },
  wecom: { label: '企业微信', tagType: 'success' },
  custom: { label: '自定义', tagType: 'info' },
}

const usernameStrategyOptions: Array<{ label: string; value: UsernameStrategy }> = [
  { label: '邮箱前缀', value: 'email_prefix' },
  { label: '手机号', value: 'phone' },
  { label: '姓名', value: 'name' },
  { label: '外部ID', value: 'external_id' },
]

const nicknameStrategyOptions: Array<{ label: string; value: NicknameStrategy }> = [
  { label: '姓名', value: 'name' },
  { label: '昵称', value: 'nickname' },
  { label: '用户名', value: 'username' },
]

const fieldUpdateModeOptions: Array<{ label: string; value: FieldUpdateMode }> = [
  { label: '不更新', value: 'never' },
  { label: '仅本地为空时填充', value: 'if_empty' },
  { label: '外部有值时覆盖', value: 'always' },
]

const props = defineProps<{
  visible: boolean
  currentSyncLog: ContactSyncLogItem | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

function handleClose() {
  emit('update:visible', false)
}

function getSourceProviderLabel(provider?: string | null) {
  const providerCode = provider?.trim()
  if (!providerCode) return '-'
  return SOURCE_PROVIDER_MAP[providerCode]?.label || providerCode
}

function getSyncOperationLabel(operation: string) {
  return operation === 'preview' ? '预览' : operation === 'sync' ? '同步' : operation
}

function getSyncStatusLabel(status: string) {
  return { success: '成功', warning: '警告', partial: '部分成功', failed: '失败' }[status] || status
}

function getSyncLogResult(row: ContactSyncLogItem | null) {
  return (row?.result_data || {}) as Partial<ContactSyncPreviewResult>
}

function getSyncLogRequest(row: ContactSyncLogItem | null) {
  return (row?.request_data || {}) as Partial<ContactSyncRequest>
}

function getSyncLogDetails(row: ContactSyncLogItem | null) {
  const detailData = row?.detail_data as ContactSyncLogDetailData | null | undefined
  if (!Array.isArray(detailData?.details)) return []
  return detailData.details.filter(isSyncPreviewItem)
}

function getSyncLogErrors(row: ContactSyncLogItem | null) {
  const errors = getSyncLogResult(row).errors
  return Array.isArray(errors) ? errors : []
}

function getSyncLogContentLabel(row: ContactSyncLogItem | null) {
  const request = getSyncLogRequest(row)
  const items = [
    request.sync_departments ? '部门' : '',
    request.sync_users ? '用户' : '',
  ].filter(Boolean)
  return items.length ? items.join('、') : '-'
}

function getSyncLogAvatarLabel(row: ContactSyncLogItem | null) {
  const value = getSyncLogRequest(row).sync_avatar
  return typeof value === 'boolean' ? (value ? '同步头像' : '不同步头像') : '-'
}

function getSyncLogMissingUserLabel(row: ContactSyncLogItem | null) {
  const value = getSyncLogRequest(row).disable_missing_users
  return typeof value === 'boolean' ? (value ? '自动禁用' : '保持不变') : '-'
}

function getSyncLogUsernameStrategyLabel(row: ContactSyncLogItem | null) {
  const strategy = getSyncLogRequest(row).username_strategy
  return Array.isArray(strategy) && strategy.length
    ? strategy.map(item => getUsernameStrategyLabel(item)).join(' > ')
    : '-'
}

function getSyncLogNicknameStrategyLabel(row: ContactSyncLogItem | null) {
  const strategy = getSyncLogRequest(row).nickname_strategy
  return Array.isArray(strategy) && strategy.length
    ? strategy.map(item => getNicknameStrategyLabel(item)).join(' > ')
    : '-'
}

function getSyncLogOverwriteStrategyLabel(row: ContactSyncLogItem | null) {
  const request = getSyncLogRequest(row)
  const emailMode = normalizeFieldUpdateMode(request.email_update_mode, request.overwrite_email, 'never')
  const phoneMode = normalizeFieldUpdateMode(request.phone_update_mode, request.overwrite_phone, 'never')
  const departmentMode = normalizeFieldUpdateMode(request.department_update_mode, request.overwrite_department, 'never')
  const hasNewStrategy = [request.email_update_mode, request.phone_update_mode, request.department_update_mode].some(isFieldUpdateMode)
  const hasLegacyStrategy = ['overwrite_email', 'overwrite_phone', 'overwrite_department'].some(
    key => typeof request[key as keyof ContactSyncRequest] === 'boolean'
  )
  if (!hasNewStrategy && !hasLegacyStrategy) return '-'
  return [
    `邮箱：${getFieldUpdateModeLabel(emailMode)}`,
    `手机号：${getFieldUpdateModeLabel(phoneMode)}`,
    `部门：${getFieldUpdateModeLabel(departmentMode)}`,
  ].join('；')
}

function getUsernameStrategyLabel(value: string) {
  return usernameStrategyOptions.find(item => item.value === value)?.label || value
}

function getNicknameStrategyLabel(value: string) {
  return nicknameStrategyOptions.find(item => item.value === value)?.label || value
}

function getFieldUpdateModeLabel(value: string) {
  return fieldUpdateModeOptions.find(item => item.value === value)?.label || value
}

function getPreviewActionLabel(action: string) {
  return { create: '新增', update: '更新', disable: '禁用', skip: '跳过' }[action] || action
}

function getPreviewTargetLabel(targetType: string) {
  return { department: '部门', user: '用户' }[targetType] || targetType
}

function isSyncPreviewItem(item: unknown): item is ContactSyncPreviewItem {
  if (!item || typeof item !== 'object') return false
  const target = item as Record<string, unknown>
  return typeof target.action === 'string' && typeof target.target_type === 'string'
}

function isFieldUpdateMode(value: unknown): value is FieldUpdateMode {
  return fieldUpdateModeOptions.some(item => item.value === value)
}

function normalizeFieldUpdateMode(
  mode: unknown,
  legacyOverwrite: unknown,
  defaultMode: FieldUpdateMode
): FieldUpdateMode {
  if (isFieldUpdateMode(mode)) return mode
  if (typeof legacyOverwrite === 'boolean') return legacyOverwrite ? 'always' : 'never'
  return defaultMode
}
</script>

<style lang="scss" scoped>
:deep(.el-dialog__body) {
  max-height: min(70vh, 640px);
  overflow-y: auto;
}
.sync-log-detail-title {
  margin: 14px 0 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.sync-log-detail-alert {
  margin-top: 12px;
}
</style>