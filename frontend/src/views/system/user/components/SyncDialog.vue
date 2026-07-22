<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" title="同步外部通讯录" width="min(760px, 92vw)" class="sync-dialog" destroy-on-close>
    <el-alert
      title="支持先预览影响再同步部门、用户基础信息和头像；外部通讯录中缺失的本地用户默认保持不变，可手动开启自动禁用。"
      type="info"
      show-icon
      :closable="false"
      class="sync-dialog-tip"
    />
    <el-form label-width="96px" class="sync-form">
      <div class="sync-section">
        <div class="sync-section-title">基础信息</div>
        <div class="sync-form-grid sync-basic-grid">
          <el-form-item label="同步来源">
            <el-select v-model="syncForm.provider" style="width: 100%" @change="$emit('provider-change')">
              <el-option label="飞书" value="feishu" />
              <el-option label="企业微信" value="wecom" />
              <el-option label="钉钉" value="dingtalk" />
            </el-select>
          </el-form-item>
          <el-form-item label="集成连接">
            <el-select
              v-model="syncForm.connection_id"
              filterable
              placeholder="请选择已启用通讯录同步的连接"
              style="width: 100%"
              :loading="connectionLoading"
              @change="$emit('connection-change')"
            >
              <el-option
                v-for="item in connectionOptions"
                :key="item.id"
                :label="syncConnectionLabel(item)"
                :value="item.id"
              />
            </el-select>
            <div class="form-tip">
              {{ getSyncCredentialTip() }}
            </div>
          </el-form-item>
        </div>
      </div>

      <div class="sync-section">
        <div class="sync-section-title">同步范围</div>
        <div class="sync-option-row">
          <el-form-item label="同步内容" class="sync-inline-item">
            <el-checkbox v-model="syncForm.sync_departments" @change="$emit('clear-results')">部门</el-checkbox>
            <el-checkbox v-model="syncForm.sync_users" @change="$emit('clear-results')">用户</el-checkbox>
            <el-checkbox v-model="syncForm.sync_avatar" @change="$emit('clear-results')">头像</el-checkbox>
          </el-form-item>
          <el-form-item label="缺失用户" class="sync-inline-item">
            <el-switch
              v-model="syncForm.disable_missing_users"
              active-text="自动禁用"
              inactive-text="保持不变"
              @change="$emit('clear-results')"
            />
          </el-form-item>
        </div>
      </div>

      <div class="sync-section">
        <div class="sync-section-title">字段策略</div>
        <div class="sync-form-grid">
          <el-form-item label="用户名">
            <el-select
              v-model="syncForm.username_strategy"
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              @change="$emit('clear-results')"
            >
              <el-option
                v-for="item in usernameStrategyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="form-tip">仅新建用户时生效，按选择顺序依次取值。</div>
          </el-form-item>
          <el-form-item label="昵称">
            <el-select
              v-model="syncForm.nickname_strategy"
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              @change="$emit('clear-results')"
            >
              <el-option
                v-for="item in nicknameStrategyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="form-tip">新建和更新用户都会使用；为空时保留已有昵称。</div>
          </el-form-item>
          <el-form-item label="邮箱更新">
            <el-select v-model="syncForm.email_update_mode" style="width: 100%" @change="$emit('clear-results')">
              <el-option
                v-for="item in fieldUpdateModeOptions"
                :key="`email-${item.value}`"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="手机号更新">
            <el-select v-model="syncForm.phone_update_mode" style="width: 100%" @change="$emit('clear-results')">
              <el-option
                v-for="item in fieldUpdateModeOptions"
                :key="`phone-${item.value}`"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="部门归属">
            <el-select v-model="syncForm.department_update_mode" style="width: 100%" @change="$emit('clear-results')">
              <el-option
                v-for="item in fieldUpdateModeOptions"
                :key="`dept-${item.value}`"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <div class="form-tip">字段为空或外部未返回时不会清空本地数据。</div>
          </el-form-item>
        </div>
      </div>

      <div class="sync-section sync-strategy-panel">
        <div class="sync-strategy-info">
          <div class="sync-section-title">策略与计划</div>
          <div class="sync-strategy-desc">
            先保存当前字段策略，再创建系统计划任务。计划任务默认停用，确认周期和策略后再启用。
          </div>
        </div>
        <div class="sync-strategy-actions">
          <el-button
            :loading="strategySaving"
            :disabled="syncBusy || !syncForm.connection_id"
            @click="$emit('save-strategy')"
          >
            保存为默认策略
          </el-button>
          <el-button
            :loading="strategyLoading"
            :disabled="syncBusy || !syncForm.connection_id"
            @click="$emit('reload-strategy')"
          >
            恢复默认策略
          </el-button>
          <el-button
            type="primary"
            :loading="syncTaskCreating"
            :disabled="syncBusy || !syncForm.connection_id"
            @click="$emit('create-task')"
          >
            创建计划任务
          </el-button>
        </div>
      </div>

      <div class="sync-result-section">
        <el-alert
          v-if="syncCheckResult"
          :type="getSyncCheckAlertType(syncCheckResult.status)"
          show-icon
          :closable="false"
          class="sync-check-alert"
        >
          <template #title>
            {{ syncCheckResult.summary }}：部门 {{ syncCheckResult.departments_count }} 个，用户 {{ syncCheckResult.users_count }} 个，头像 {{ syncCheckResult.avatar_users_count }} 个
          </template>
          <el-table :data="syncCheckResult.checks" size="small" class="sync-check-table" max-height="140">
            <el-table-column label="检查项" prop="name" width="100" />
            <el-table-column label="状态" width="82">
              <template #default="{ row }">
                <el-tag :type="getSyncStatusTagType(row.status)" size="small">
                  {{ getSyncStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" prop="message" min-width="220" />
          </el-table>
        </el-alert>
        <el-alert
          v-if="syncPreviewResult"
          type="info"
          show-icon
          :closable="false"
          class="sync-preview-alert"
        >
          <template #title>
            预览结果：部门新增 {{ syncPreviewResult.departments_created }}、更新 {{ syncPreviewResult.departments_updated }}；
            用户新增 {{ syncPreviewResult.users_created }}、更新 {{ syncPreviewResult.users_updated }}、禁用 {{ syncPreviewResult.users_disabled }}
          </template>
          <div v-if="syncForm.sync_departments && isNoDepartmentSyncChange(syncPreviewResult)" class="sync-preview-details">
            外部平台未返回可同步部门，可能用户都在根部门，或应用通讯录权限范围未包含部门信息。
          </div>
          <div v-if="syncPreviewResult.details.length" class="sync-preview-details">
            <div
              v-for="(item, index) in syncPreviewResult.details.slice(0, 8)"
              :key="`${item.target_type}-${item.action}-${index}`"
            >
              {{ getPreviewActionLabel(item.action) }}{{ getPreviewTargetLabel(item.target_type) }}：
              {{ item.name || item.external_id || item.local_id || '-' }}
              <span v-if="item.reason">（{{ item.reason }}）</span>
            </div>
            <div v-if="syncPreviewResult.details.length > 8">
              仅展示前 8 条，完整明细已记录在同步日志。
            </div>
          </div>
        </el-alert>
        <div class="sync-log-box">
          <div class="sync-log-title">最近同步日志</div>
          <el-table v-loading="syncLogLoading" :data="syncLogs" size="small" max-height="140">
            <el-table-column label="同步时间" width="160">
              <template #default="{ row: r }">
                {{ formatDate((r as ContactSyncLogItem).created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="72">
              <template #default="{ row: r }">
                {{ getSyncOperationLabel((r as ContactSyncLogItem).operation) }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="78">
              <template #default="{ row: r }">
                <el-tag :type="getSyncStatusTagType((r as ContactSyncLogItem).status)" size="small">
                  {{ getSyncStatusLabel((r as ContactSyncLogItem).status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="结果" min-width="220">
              <template #default="{ row: r }">
                {{ getSyncLogSummary(r as ContactSyncLogItem) }}
              </template>
            </el-table-column>
            <el-table-column label="详情" width="64">
              <template #default="{ row: r }">
                <el-button link type="primary" @click="$emit('open-log-detail', r)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-form>
    <template #footer>
      <div class="sync-dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button :loading="checking" :disabled="syncBusy" @click="$emit('check')">同步自检</el-button>
        <el-button :loading="previewing" :disabled="syncBusy" @click="$emit('preview')">预览影响</el-button>
        <el-button type="primary" :loading="syncing" :disabled="syncBusy" @click="$emit('sync')">开始同步</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatDate } from '@/utils/format'
import type {
  ContactSyncCheckResult,
  ContactSyncLogItem,
  ContactSyncPreviewResult,
  IntegrationConnection,
} from '@/types'

type UsernameStrategy = 'email_prefix' | 'phone' | 'name' | 'external_id'
type NicknameStrategy = 'name' | 'nickname' | 'username'
type FieldUpdateMode = 'never' | 'if_empty' | 'always'

interface ContactSyncStrategy {
  sync_departments: boolean
  sync_users: boolean
  sync_avatar: boolean
  disable_missing_users: boolean
  username_strategy: UsernameStrategy[]
  nickname_strategy: NicknameStrategy[]
  overwrite_email: boolean
  overwrite_phone: boolean
  overwrite_department: boolean
  email_update_mode: FieldUpdateMode
  phone_update_mode: FieldUpdateMode
  department_update_mode: FieldUpdateMode
}

const props = defineProps<{
  visible: boolean
  syncForm: {
    provider: 'feishu' | 'wecom' | 'dingtalk'
    connection_id: number | undefined
    sync_departments: boolean
    sync_users: boolean
    sync_avatar: boolean
    disable_missing_users: boolean
    username_strategy: UsernameStrategy[]
    nickname_strategy: NicknameStrategy[]
    email_update_mode: FieldUpdateMode
    phone_update_mode: FieldUpdateMode
    department_update_mode: FieldUpdateMode
    overwrite_email: boolean
    overwrite_phone: boolean
    overwrite_department: boolean
  }
  connectionOptions: IntegrationConnection[]
  syncCheckResult: ContactSyncCheckResult | null
  syncPreviewResult: ContactSyncPreviewResult | null
  syncLogs: ContactSyncLogItem[]
  connectionLoading: boolean
  strategyLoading: boolean
  strategySaving: boolean
  syncTaskCreating: boolean
  checking: boolean
  previewing: boolean
  syncing: boolean
  syncBusy: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'provider-change'): void
  (e: 'connection-change'): void
  (e: 'clear-results'): void
  (e: 'save-strategy'): void
  (e: 'reload-strategy'): void
  (e: 'create-task'): void
  (e: 'check'): void
  (e: 'preview'): void
  (e: 'sync'): void
  (e: 'open-log-detail', row: ContactSyncLogItem): void
}>()

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

function handleClose() {
  emit('update:visible', false)
}

function syncConnectionLabel(item: IntegrationConnection) {
  return `${item.name}${item.is_default ? '（默认）' : ''}${item.secret_configured ? '' : '（未保存密钥）'}`
}

function getSyncCredentialTip() {
  const tips: Record<string, string> = {
    feishu: '同步会使用选中的连接凭证。飞书通讯录同步需要该连接已保存 App ID 和 App Secret。',
    wecom: '同步会使用选中的连接凭证。企业微信通讯录同步需要该连接已保存 Corp ID 和 Corp Secret。',
    dingtalk: '同步会使用选中的连接凭证。钉钉通讯录同步需要该连接已保存 App Key 和 App Secret。',
  }
  return tips[props.syncForm.provider] || '同步会使用选中的连接凭证。'
}

function getPreviewActionLabel(action: string) {
  return { create: '新增', update: '更新', disable: '禁用', skip: '跳过' }[action] || action
}

function getPreviewTargetLabel(targetType: string) {
  return { department: '部门', user: '用户' }[targetType] || targetType
}

function getSyncOperationLabel(operation: string) {
  return operation === 'preview' ? '预览' : operation === 'sync' ? '同步' : operation
}

function getSyncStatusLabel(status: string) {
  return { success: '成功', warning: '警告', partial: '部分成功', failed: '失败' }[status] || status
}

function getSyncStatusTagType(status: string) {
  return status === 'success' ? 'success' : status === 'failed' ? 'danger' : 'warning'
}

function getSyncCheckAlertType(status: string) {
  return status === 'success' ? 'success' : status === 'failed' ? 'error' : 'warning'
}

function isNoDepartmentSyncChange(result: Partial<ContactSyncPreviewResult>) {
  return !result.departments_created && !result.departments_updated
}

function getSyncLogSummary(row: ContactSyncLogItem) {
  const result = (row.result_data || {}) as Partial<ContactSyncPreviewResult>
  const deptSummary = isNoDepartmentSyncChange(result)
    ? '部门无变化'
    : `部门 +${result.departments_created || 0}/改${result.departments_updated || 0}`
  return `${deptSummary}，用户 +${result.users_created || 0}/改${result.users_updated || 0}/禁${result.users_disabled || 0}`
}
</script>

<style lang="scss" scoped>
:deep(.el-dialog__body) {
  max-height: min(68vh, 620px);
  overflow-y: auto;
  padding-top: 12px;
  padding-bottom: 8px;
}
.sync-dialog-tip {
  margin-bottom: 10px;
}
.sync-form {
  :deep(.el-form-item) {
    margin-bottom: 10px;
  }
}
.sync-section,
.sync-result-section {
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.sync-result-section {
  margin-bottom: 0;
}
.sync-section-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.sync-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 14px;
}
.sync-basic-grid {
  align-items: start;

  :deep(.el-form-item) {
    align-items: flex-start;
    margin-bottom: 0;
  }

  :deep(.el-form-item__label) {
    height: 32px;
    line-height: 32px;
  }

  :deep(.el-form-item__content) {
    align-items: flex-start;
  }

  .form-tip {
    width: 100%;
    flex-basis: 100%;
  }
}
.sync-option-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 14px;
}
.sync-strategy-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-color: var(--el-color-primary-light-7);
  background: var(--el-color-primary-light-9);
}
.sync-strategy-info {
  min-width: 0;

  .sync-section-title {
    margin-bottom: 4px;
  }
}
.sync-strategy-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}
.sync-strategy-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;

  :deep(.el-button + .el-button) {
    margin-left: 0;
  }
}
.sync-dialog-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;

  :deep(.el-button + .el-button) {
    margin-left: 0;
  }
}
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}
.sync-preview-alert {
  margin-top: 8px;
}
.sync-check-alert {
  margin-top: 8px;
}
.sync-check-table {
  margin-top: 8px;
}
.sync-preview-details {
  margin-top: 6px;
  max-height: 96px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.6;
}
.sync-log-box {
  margin-top: 12px;
}
.sync-log-title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
@media (max-width: 768px) {
  .sync-form-grid,
  .sync-option-row {
    grid-template-columns: 1fr;
  }

  .sync-strategy-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .sync-strategy-actions {
    justify-content: flex-start;
  }
}
</style>