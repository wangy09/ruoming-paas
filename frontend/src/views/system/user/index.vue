<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <el-form inline class="search-form" @submit.prevent="fetchList" style="flex: 1;">
          <el-form-item label="关键词">
            <el-input v-model="query.keyword" placeholder="用户名 / 邮箱" clearable style="width:200px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
              <el-option label="启用" :value="1" />
              <el-option label="禁用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
            <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="toolbar-actions">
          <el-button :icon="Refresh" v-permission="'system:user:sync'" @click="openSyncDialog">
            同步用户
          </el-button>
          <el-button type="primary" :icon="Plus" v-permission="'system:user:create'" @click="openDialog()">
            新增用户
          </el-button>
        </div>
      </div>

      <el-divider />

      <!-- 表格 -->
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column label="头像" width="72" align="center">
          <template #default="{ row }">
            <el-avatar :size="36" :src="row.avatar || undefined">
              {{ getAvatarText(row) }}
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="nickname" label="用户昵称" min-width="120" show-overflow-tooltip />
        <el-table-column label="来源" min-width="130" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.source_provider"
              :content="getSourceProviderTooltip(row)"
              placement="top"
            >
              <el-tag :type="getSourceProviderTagType(row.source_provider)" size="small">
                {{ getSourceProviderLabel(row.source_provider) }}
              </el-tag>
            </el-tooltip>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dept_name" label="部门" min-width="120">
          <template #default="{ row }">
            {{ row.dept_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="role in row.roles"
              :key="role.id"
              size="small"
              type="info"
              class="mr-1"
            >
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 1"
              :loading="switchLoadingId === row.id"
              @change="toggleActive(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="超管" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_superplatform" type="danger" size="small">超管</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link type="primary"
              v-permission="'system:user:update'"
              @click="openDialog(row)"
            >编辑</el-button>
            <el-button
              v-if="!row.is_superplatform"
              link type="warning"
              v-permission="'system:user:update'"
              @click="openRoleDialog(row)"
            >角色</el-button>
            <el-button
              link type="warning"
              v-permission="'system:user:reset-password'"
              @click="handleResetPwd(row)"
            >重置密码</el-button>
            <el-button
              v-if="!row.is_superplatform"
              link type="danger"
              v-permission="'system:user:delete'"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        class="mt-4"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @change="fetchList"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑用户' : '新增用户'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editId" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="用户姓名" prop="nickname">
          <el-input v-model="form.nickname" placeholder="用户真实姓名或显示名称" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="form.dept_id"
            :data="deptOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            check-strictly
            placeholder="请选择部门（可选）"
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="email@example.com" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="!editId" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色对话框 -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="480px" destroy-on-close>
      <el-checkbox-group v-model="selectedRoleIds">
        <div v-for="role in allRoles" :key="role.id" class="role-item">
          <el-checkbox :label="role.id" :value="role.id">
            <div>
              <span class="font-bold">{{ role.name }}</span>
              <span class="text-gray text-sm ml-2">{{ role.code }}</span>
            </div>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAssignRoles">确定</el-button>
      </template>
    </el-dialog>

    <!-- 通讯录同步对话框 -->
    <el-dialog v-model="syncDialogVisible" title="同步外部通讯录" width="min(760px, 92vw)" class="sync-dialog" destroy-on-close>
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
              <el-select v-model="syncForm.provider" style="width: 100%" @change="handleSyncProviderChange">
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
                @change="handleSyncConnectionChange"
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
              <el-checkbox v-model="syncForm.sync_departments" @change="clearSyncResults">部门</el-checkbox>
              <el-checkbox v-model="syncForm.sync_users" @change="clearSyncResults">用户</el-checkbox>
              <el-checkbox v-model="syncForm.sync_avatar" @change="clearSyncResults">头像</el-checkbox>
            </el-form-item>
            <el-form-item label="缺失用户" class="sync-inline-item">
              <el-switch
                v-model="syncForm.disable_missing_users"
                active-text="自动禁用"
                inactive-text="保持不变"
                @change="clearSyncResults"
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
                @change="clearSyncResults"
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
                @change="clearSyncResults"
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
              <el-select v-model="syncForm.email_update_mode" style="width: 100%" @change="clearSyncResults">
                <el-option
                  v-for="item in fieldUpdateModeOptions"
                  :key="`email-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="手机号更新">
              <el-select v-model="syncForm.phone_update_mode" style="width: 100%" @change="clearSyncResults">
                <el-option
                  v-for="item in fieldUpdateModeOptions"
                  :key="`phone-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="部门归属">
              <el-select v-model="syncForm.department_update_mode" style="width: 100%" @change="clearSyncResults">
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
              @click="handleSaveSyncStrategy"
            >
              保存为默认策略
            </el-button>
            <el-button
              :loading="strategyLoading"
              :disabled="syncBusy || !syncForm.connection_id"
              @click="handleReloadSyncStrategy"
            >
              恢复默认策略
            </el-button>
            <el-button
              type="primary"
              :loading="syncTaskCreating"
              :disabled="syncBusy || !syncForm.connection_id"
              @click="handleCreateContactSyncTask"
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
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="72">
                <template #default="{ row }">
                  {{ getSyncOperationLabel(row.operation) }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="78">
                <template #default="{ row }">
                  <el-tag :type="getSyncStatusTagType(row.status)" size="small">
                    {{ getSyncStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="结果" min-width="220">
                <template #default="{ row }">
                  {{ getSyncLogSummary(row) }}
                </template>
              </el-table-column>
              <el-table-column label="详情" width="64">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openSyncLogDetail(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="sync-dialog-footer">
          <el-button @click="syncDialogVisible = false">取消</el-button>
          <el-button :loading="checking" :disabled="syncBusy" @click="handleCheckSyncContacts">同步自检</el-button>
          <el-button :loading="previewing" :disabled="syncBusy" @click="handlePreviewSyncContacts">预览影响</el-button>
          <el-button type="primary" :loading="syncing" :disabled="syncBusy" @click="handleSyncContacts">开始同步</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="syncLogDetailVisible"
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
        <el-button type="primary" @click="syncLogDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api/user'
import { integrationApi } from '@/api/integration'
import { taskApi } from '@/api/monitor'
import { permissionApi } from '@/api/permission'
import { systemApi } from '@/api/system'
import { formatDate } from '@/utils/format'
import type {
  ContactSyncCheckResult,
  ContactSyncLogItem,
  ContactSyncPreviewItem,
  ContactSyncPreviewResult,
  ContactSyncRequest,
  ContactSyncResult,
  ContactSyncStrategy,
  IntegrationConnection,
  UserListItem,
  RoleInfo,
  DeptInfo,
} from '@/types'

// ── 列表 ──────────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<UserListItem[]>([])
const total = ref(0)
const switchLoadingId = ref<number | null>(null)

type SourceTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'
type UsernameStrategy = 'email_prefix' | 'phone' | 'name' | 'external_id'
type NicknameStrategy = 'name' | 'nickname' | 'username'
type FieldUpdateMode = 'never' | 'if_empty' | 'always'

interface ScheduledTaskItem {
  id: number
  name: string
  func_name: string
  kwargs?: Record<string, unknown> | null
}

const CONTACT_SYNC_TASK_FUNC = 'app.modules.integration.tasks.sync_contact_connection'
const router = useRouter()

interface SourceProviderMeta {
  label: string
  tagType: SourceTagType
}

const SOURCE_PROVIDER_MAP: Record<string, SourceProviderMeta> = {
  feishu: { label: '飞书', tagType: 'primary' },
  dingtalk: { label: '钉钉', tagType: 'warning' },
  wecom: { label: '企业微信', tagType: 'success' },
  custom: { label: '自定义', tagType: 'info' },
}

interface ContactSyncLogDetailData {
  details?: unknown
}

function getSourceProviderMeta(provider?: string | null): SourceProviderMeta {
  const providerCode = provider?.trim()
  if (!providerCode) {
    return { label: '-', tagType: 'info' }
  }
  return SOURCE_PROVIDER_MAP[providerCode] || { label: providerCode, tagType: 'info' }
}

function getSourceProviderLabel(provider?: string | null) {
  return getSourceProviderMeta(provider).label
}

function getSourceProviderTagType(provider?: string | null) {
  return getSourceProviderMeta(provider).tagType
}

function getSourceProviderTooltip(row: UserListItem) {
  const providerLabel = getSourceProviderLabel(row.source_provider)
  const details = [
    `来源：${providerLabel}`,
    row.source_connection_name ? `连接：${row.source_connection_name}` : '',
    row.source_external_id ? `外部ID：${row.source_external_id}` : '',
  ].filter(Boolean)

  // 后端暂未返回连接名或外部 ID 时，至少展示来源名称
  return details.join('；')
}

function getAvatarText(row: UserListItem) {
  const displayName = row.nickname || row.username || ''
  return displayName.trim().slice(0, 1).toUpperCase() || '用'
}

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as number | undefined,
})

async function fetchList() {
  loading.value = true
  try {
    const res = await userApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.status = undefined
  query.page = 1
  fetchList()
}

async function toggleActive(row: UserListItem) {
  const newStatus = row.status === 1 ? 0 : 1
  switchLoadingId.value = row.id
  try {
    await userApi.update(row.id, { status: newStatus })
    row.status = newStatus
    ElMessage.success(`用户已${newStatus === 1 ? '启用' : '禁用'}`)
  } catch {
    // 失败时不更新状态
  } finally {
    switchLoadingId.value = null
  }
}

async function handleDelete(row: UserListItem) {
  await ElMessageBox.confirm(`确定删除用户「${row.username}」？`, '警告', { type: 'warning' })
  await userApi.delete(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

async function handleResetPwd(row: UserListItem) {
  const newPwd = 'ruoming@2024'
  await ElMessageBox.confirm(`重置用户「${row.username}」密码为 ${newPwd}？`, '确认', { type: 'warning' })
  await userApi.resetPassword(row.id, newPwd)
  ElMessage.success('密码已重置')
}

// ── 部门选项 ──────────────────────────────────────────────────────────────────
const deptOptions = ref<DeptInfo[]>([])

async function fetchDeptOptions() {
  try {
    const res = await systemApi.deptOptions()
    deptOptions.value = res.data
  } catch {
    deptOptions.value = []
  }
}

// ── 新增/编辑 ─────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  password: '',
  dept_id: undefined as number | undefined,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }, { min: 6, message: '至少6位' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

function openDialog(row?: UserListItem) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    username: row?.username ?? '',
    nickname: row?.nickname ?? '',
    email: row?.email ?? '',
    phone: row?.phone ?? '',
    password: '',
    dept_id: (row as any)?.dept_id,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await userApi.update(editId.value, { nickname: form.nickname, email: form.email, phone: form.phone, dept_id: form.dept_id })
      ElMessage.success('更新成功')
    } else {
      await userApi.create(form as any)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

// ── 分配角色 ──────────────────────────────────────────────────────────────────
const roleDialogVisible = ref(false)
const allRoles = ref<RoleInfo[]>([])
const selectedRoleIds = ref<number[]>([])
const currentUserId = ref<number>(0)

async function openRoleDialog(row: UserListItem) {
  currentUserId.value = row.id
  selectedRoleIds.value = (row.roles || []).map((r: { id: number }) => r.id)
  if (!allRoles.value.length) {
    const res = await permissionApi.roleList({ page_size: 200 })
    allRoles.value = res.data.items
  }
  roleDialogVisible.value = true
}

async function handleAssignRoles() {
  submitting.value = true
  try {
    await userApi.assignRoles(currentUserId.value, selectedRoleIds.value)
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

// ── 外部通讯录同步 ────────────────────────────────────────────────────────────
const syncDialogVisible = ref(false)
const syncing = ref(false)
const checking = ref(false)
const previewing = ref(false)
const connectionLoading = ref(false)
const strategyLoading = ref(false)
const strategySaving = ref(false)
const syncTaskCreating = ref(false)
const connectionOptions = ref<IntegrationConnection[]>([])
const syncCheckResult = ref<ContactSyncCheckResult | null>(null)
const syncPreviewResult = ref<ContactSyncPreviewResult | null>(null)
const syncLogLoading = ref(false)
const syncLogs = ref<ContactSyncLogItem[]>([])
const syncLogDetailVisible = ref(false)
const currentSyncLog = ref<ContactSyncLogItem | null>(null)
const syncBusy = computed(() => checking.value || previewing.value || syncing.value)

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

const DEFAULT_SYNC_STRATEGY: ContactSyncStrategy = {
  sync_departments: true,
  sync_users: true,
  sync_avatar: true,
  disable_missing_users: false,
  username_strategy: ['email_prefix', 'phone', 'name', 'external_id'],
  nickname_strategy: ['name', 'nickname'],
  overwrite_email: true,
  overwrite_phone: false,
  overwrite_department: true,
  email_update_mode: 'always',
  phone_update_mode: 'never',
  department_update_mode: 'always',
}

const syncForm = reactive({
  provider: 'wecom' as 'feishu' | 'wecom' | 'dingtalk',
  connection_id: undefined as number | undefined,
  ...DEFAULT_SYNC_STRATEGY,
})

async function openSyncDialog() {
  clearSyncResults()
  syncDialogVisible.value = true
  await Promise.all([fetchConnectionOptions(), fetchSyncLogs()])
}

async function handleSyncProviderChange() {
  syncForm.connection_id = undefined
  applySyncStrategy(DEFAULT_SYNC_STRATEGY)
  clearSyncResults()
  await Promise.all([fetchConnectionOptions(), fetchSyncLogs()])
}

async function handleSyncConnectionChange() {
  clearSyncResults()
  await loadSelectedContactSyncStrategy()
}

function clearSyncResults() {
  syncCheckResult.value = null
  syncPreviewResult.value = null
}

async function fetchConnectionOptions() {
  connectionLoading.value = true
  try {
    const res = await integrationApi.connections({
      provider: syncForm.provider,
      enabled: true,
    })
    connectionOptions.value = (res.data || []).filter(item => item.capabilities.includes('contact_sync'))
    if (!connectionOptions.value.some(item => item.id === syncForm.connection_id)) {
      syncForm.connection_id = pickDefaultSyncConnection()?.id
    }
    await loadSelectedContactSyncStrategy()
  } finally {
    connectionLoading.value = false
  }
}

async function loadSelectedContactSyncStrategy(showMessage = false) {
  if (!syncForm.connection_id) {
    applySyncStrategy(DEFAULT_SYNC_STRATEGY)
    return
  }
  strategyLoading.value = true
  try {
    const res = await integrationApi.contactSyncStrategy(syncForm.connection_id)
    applySyncStrategy(normalizeSyncStrategy(res.data))
    clearSyncResults()
    if (showMessage) {
      ElMessage.success('已恢复连接默认策略')
    }
  } finally {
    strategyLoading.value = false
  }
}

async function handleReloadSyncStrategy() {
  await loadSelectedContactSyncStrategy(true)
}

async function handleSaveSyncStrategy() {
  if (!syncForm.connection_id) {
    ElMessage.warning('请先选择集成连接')
    return
  }
  const strategy = buildSyncStrategy()
  if (!strategy) {
    return
  }
  strategySaving.value = true
  try {
    const res = await integrationApi.saveContactSyncStrategy(syncForm.connection_id, strategy)
    applySyncStrategy(normalizeSyncStrategy(res.data))
    clearSyncResults()
    ElMessage.success('默认策略已保存')
  } finally {
    strategySaving.value = false
  }
}

async function handleCreateContactSyncTask() {
  if (!syncForm.connection_id) {
    ElMessage.warning('请先选择集成连接')
    return
  }
  const strategy = buildSyncStrategy()
  if (!strategy) {
    return
  }
  const connection = connectionOptions.value.find(item => item.id === syncForm.connection_id)
  const taskName = `${connection?.name || getSourceProviderLabel(syncForm.provider)} 通讯录每日同步`

  syncTaskCreating.value = true
  try {
    const existingTasks = await taskApi.list({
      page: 1,
      page_size: 200,
      func_name: CONTACT_SYNC_TASK_FUNC,
    })
    const existingTask = (existingTasks.data.items as ScheduledTaskItem[] | undefined)?.find(
      item => Number(item.kwargs?.connection_id) === syncForm.connection_id
    )
    if (existingTask) {
      try {
        await ElMessageBox.confirm(
          `当前连接已存在通讯录同步计划任务「${existingTask.name}」，是否前往系统计划任务中管理？`,
          '计划任务已存在',
          {
            confirmButtonText: '去计划任务',
            cancelButtonText: '留在当前页',
            type: 'warning',
          }
        )
        await router.push('/monitor/task')
      } catch {
        // 用户选择留在当前页
      }
      return
    }

    await ElMessageBox.confirm(
      `将在系统“计划任务”中新增一条停用记录「${taskName}」，任务会复用当前连接保存的默认策略。创建后可在计划任务中修改周期、启停和查看执行日志。`,
      '创建通讯录同步计划任务',
      {
        confirmButtonText: '创建计划任务',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await integrationApi.saveContactSyncStrategy(syncForm.connection_id, strategy)
    await taskApi.create({
      name: taskName,
      task_type: 'interval',
      func_name: CONTACT_SYNC_TASK_FUNC,
      interval_seconds: 86400,
      is_once: false,
      status: 0,
      args: [],
      kwargs: {
        connection_id: syncForm.connection_id,
      },
      remark: '外部通讯录每日自动同步任务。任务由用户同步弹框创建，可在系统计划任务中统一启停、调整周期和查看执行日志。',
    })
    try {
      await ElMessageBox.confirm(
        '已在系统计划任务中创建停用记录。是否现在前往计划任务页面确认周期并启用？',
        '创建成功',
        {
          confirmButtonText: '去计划任务',
          cancelButtonText: '稍后再说',
          type: 'success',
        }
      )
      await router.push('/monitor/task')
    } catch {
      ElMessage.success('已在系统计划任务中创建停用记录，请到计划任务确认后启用')
    }
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('创建计划任务失败')
    }
  } finally {
    syncTaskCreating.value = false
  }
}

async function handleSyncContacts() {
  if (syncBusy.value) {
    return
  }
  const payload = buildSyncPayload()
  if (!payload) {
    return
  }
  syncing.value = true
  try {
    const checkResult = await runSyncCheck(payload, false)
    if (checkResult.status === 'failed') {
      ElMessage.error(checkResult.summary || '同步自检失败，请修复后再开始同步')
      return
    }
    if (checkResult.status === 'warning') {
      const confirmed = await confirmOrCancel(checkResult.summary || '同步自检存在警告，仍要继续同步？', '自检警告')
      if (!confirmed) {
        return
      }
    }
    const confirmed = await confirmOrCancel(`同步会创建或更新${getSyncContentLabel()}，确认开始？`, '确认同步')
    if (!confirmed) {
      return
    }
    const res = await userApi.syncContacts(payload)
    const data = res.data
    ElMessage.success(
      `同步完成：部门新增 ${data.departments_created}、更新 ${data.departments_updated}；用户新增 ${data.users_created}、更新 ${data.users_updated}`
    )
    if (data.errors?.length) {
      ElMessage.warning(`同步完成但有 ${data.errors.length} 条提示，请查看接口返回详情`)
    }
    fetchSyncLogs()
    syncDialogVisible.value = false
    fetchDeptOptions()
    fetchList()
  } finally {
    syncing.value = false
  }
}

async function confirmOrCancel(message: string, title: string) {
  try {
    await ElMessageBox.confirm(message, title, {
      type: 'warning',
    })
    return true
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return false
    }
    throw error
  }
}

async function handleCheckSyncContacts() {
  if (syncBusy.value) {
    return
  }
  const payload = buildSyncPayload()
  if (!payload) {
    return
  }
  await runSyncCheck(payload)
}

async function runSyncCheck(payload: ContactSyncRequest, showMessage = true) {
  checking.value = true
  try {
    const res = await userApi.checkSyncContacts(payload)
    syncCheckResult.value = res.data
    if (showMessage) {
      ElMessage.success('自检完成')
    }
    return res.data
  } finally {
    checking.value = false
  }
}

async function handlePreviewSyncContacts() {
  const payload = buildSyncPayload()
  if (!payload) {
    return
  }
  previewing.value = true
  try {
    const res = await userApi.previewSyncContacts(payload)
    syncPreviewResult.value = res.data
    fetchSyncLogs()
    ElMessage.success('预览完成')
  } finally {
    previewing.value = false
  }
}

function buildSyncPayload(): ContactSyncRequest | null {
  if (!syncForm.connection_id) {
    ElMessage.warning('请选择已启用通讯录同步的集成连接')
    return null
  }
  const strategy = buildSyncStrategy()
  if (!strategy) {
    return null
  }
  return {
    provider: syncForm.provider,
    connection_id: syncForm.connection_id,
    ...strategy,
  }
}

function buildSyncStrategy(): ContactSyncStrategy | null {
  if (!syncForm.sync_departments && !syncForm.sync_users) {
    ElMessage.warning('请至少选择一个同步内容')
    return null
  }
  if (syncForm.sync_users && !syncForm.username_strategy.length) {
    ElMessage.warning('请至少选择一个用户名优先级')
    return null
  }
  if (syncForm.sync_users && !syncForm.nickname_strategy.length) {
    ElMessage.warning('请至少选择一个昵称优先级')
    return null
  }
  return {
    sync_departments: syncForm.sync_departments,
    sync_users: syncForm.sync_users,
    sync_avatar: syncForm.sync_avatar,
    disable_missing_users: syncForm.disable_missing_users,
    username_strategy: [...syncForm.username_strategy],
    nickname_strategy: [...syncForm.nickname_strategy],
    overwrite_email: syncForm.email_update_mode === 'always',
    overwrite_phone: syncForm.phone_update_mode === 'always',
    overwrite_department: syncForm.department_update_mode === 'always',
    email_update_mode: syncForm.email_update_mode,
    phone_update_mode: syncForm.phone_update_mode,
    department_update_mode: syncForm.department_update_mode,
  }
}

function normalizeSyncStrategy(strategy: Partial<ContactSyncStrategy> | null | undefined): ContactSyncStrategy {
  const usernameStrategy = Array.isArray(strategy?.username_strategy)
    ? strategy.username_strategy.filter(isUsernameStrategy)
    : []
  const nicknameStrategy = Array.isArray(strategy?.nickname_strategy)
    ? strategy.nickname_strategy.filter(isNicknameStrategy)
    : []
  const emailUpdateMode = normalizeFieldUpdateMode(
    strategy?.email_update_mode,
    strategy?.overwrite_email,
    DEFAULT_SYNC_STRATEGY.email_update_mode
  )
  const phoneUpdateMode = normalizeFieldUpdateMode(
    strategy?.phone_update_mode,
    strategy?.overwrite_phone,
    DEFAULT_SYNC_STRATEGY.phone_update_mode
  )
  const departmentUpdateMode = normalizeFieldUpdateMode(
    strategy?.department_update_mode,
    strategy?.overwrite_department,
    DEFAULT_SYNC_STRATEGY.department_update_mode
  )

  return {
    sync_departments: typeof strategy?.sync_departments === 'boolean' ? strategy.sync_departments : DEFAULT_SYNC_STRATEGY.sync_departments,
    sync_users: typeof strategy?.sync_users === 'boolean' ? strategy.sync_users : DEFAULT_SYNC_STRATEGY.sync_users,
    sync_avatar: typeof strategy?.sync_avatar === 'boolean' ? strategy.sync_avatar : DEFAULT_SYNC_STRATEGY.sync_avatar,
    disable_missing_users: typeof strategy?.disable_missing_users === 'boolean' ? strategy.disable_missing_users : DEFAULT_SYNC_STRATEGY.disable_missing_users,
    username_strategy: usernameStrategy.length ? usernameStrategy : [...DEFAULT_SYNC_STRATEGY.username_strategy],
    nickname_strategy: nicknameStrategy.length ? nicknameStrategy : [...DEFAULT_SYNC_STRATEGY.nickname_strategy],
    overwrite_email: emailUpdateMode === 'always',
    overwrite_phone: phoneUpdateMode === 'always',
    overwrite_department: departmentUpdateMode === 'always',
    email_update_mode: emailUpdateMode,
    phone_update_mode: phoneUpdateMode,
    department_update_mode: departmentUpdateMode,
  }
}

function applySyncStrategy(strategy: ContactSyncStrategy) {
  syncForm.sync_departments = strategy.sync_departments
  syncForm.sync_users = strategy.sync_users
  syncForm.sync_avatar = strategy.sync_avatar
  syncForm.disable_missing_users = strategy.disable_missing_users
  syncForm.username_strategy = [...strategy.username_strategy] as UsernameStrategy[]
  syncForm.nickname_strategy = [...strategy.nickname_strategy] as NicknameStrategy[]
  syncForm.overwrite_email = strategy.overwrite_email
  syncForm.overwrite_phone = strategy.overwrite_phone
  syncForm.overwrite_department = strategy.overwrite_department
  syncForm.email_update_mode = strategy.email_update_mode
  syncForm.phone_update_mode = strategy.phone_update_mode
  syncForm.department_update_mode = strategy.department_update_mode
}

function isUsernameStrategy(value: unknown): value is UsernameStrategy {
  return usernameStrategyOptions.some(item => item.value === value)
}

function isNicknameStrategy(value: unknown): value is NicknameStrategy {
  return nicknameStrategyOptions.some(item => item.value === value)
}

function isFieldUpdateMode(value: unknown): value is FieldUpdateMode {
  return fieldUpdateModeOptions.some(item => item.value === value)
}

function normalizeFieldUpdateMode(
  mode: unknown,
  legacyOverwrite: unknown,
  defaultMode: FieldUpdateMode
): FieldUpdateMode {
  if (isFieldUpdateMode(mode)) {
    return mode
  }
  if (typeof legacyOverwrite === 'boolean') {
    return legacyOverwrite ? 'always' : 'never'
  }
  return defaultMode
}

function pickDefaultSyncConnection() {
  return connectionOptions.value.find((item: IntegrationConnection) => item.is_default) || connectionOptions.value[0]
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
  return tips[syncForm.provider] || '同步会使用选中的连接凭证。'
}

function getSyncContentLabel() {
  const items = [
    syncForm.sync_departments ? '部门' : '',
    syncForm.sync_users ? '用户资料' : '',
    syncForm.sync_avatar ? '头像' : '',
  ].filter(Boolean)
  return items.length ? items.join('、') : '选中的内容'
}

async function fetchSyncLogs() {
  syncLogLoading.value = true
  try {
    const res = await userApi.contactSyncLogs({
      provider: syncForm.provider,
      limit: 5,
    })
    syncLogs.value = res.data || []
  } finally {
    syncLogLoading.value = false
  }
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

function getSyncLogSummary(row: ContactSyncLogItem) {
  const result = (row.result_data || {}) as Partial<ContactSyncPreviewResult>
  const deptSummary = isNoDepartmentSyncChange(result)
    ? '部门无变化'
    : `部门 +${result.departments_created || 0}/改${result.departments_updated || 0}`
  return `${deptSummary}，用户 +${result.users_created || 0}/改${result.users_updated || 0}/禁${result.users_disabled || 0}`
}

function openSyncLogDetail(row: ContactSyncLogItem) {
  currentSyncLog.value = row
  syncLogDetailVisible.value = true
}

function getSyncLogResult(row: ContactSyncLogItem | null) {
  return (row?.result_data || {}) as Partial<ContactSyncPreviewResult>
}

function getSyncLogRequest(row: ContactSyncLogItem | null) {
  return (row?.request_data || {}) as Partial<ContactSyncRequest>
}

function getSyncLogDetails(row: ContactSyncLogItem | null) {
  const detailData = row?.detail_data as ContactSyncLogDetailData | null | undefined
  if (!Array.isArray(detailData?.details)) {
    return []
  }
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
  if (!hasNewStrategy && !hasLegacyStrategy) {
    return '-'
  }
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

function isSyncPreviewItem(item: unknown): item is ContactSyncPreviewItem {
  if (!item || typeof item !== 'object') {
    return false
  }
  const target = item as Record<string, unknown>
  return typeof target.action === 'string' && typeof target.target_type === 'string'
}

function isNoDepartmentSyncChange(result: Partial<ContactSyncResult>) {
  return !result.departments_created && !result.departments_updated
}

onMounted(() => {
  fetchList()
  fetchDeptOptions()
})
</script>

<style lang="scss" scoped>
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mt-4 { margin-top: 16px; }
.mb-4 { margin-bottom: 16px; }
.mr-1 { margin-right: 4px; }
.ml-2 { margin-left: 8px; }
.text-muted { color: var(--el-text-color-secondary); }
:deep(.sync-dialog .el-dialog__body) {
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
:deep(.sync-log-detail-dialog .el-dialog__body) {
  max-height: min(70vh, 640px);
  overflow-y: auto;
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
.sync-log-detail-title {
  margin: 14px 0 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.sync-log-detail-alert {
  margin-top: 12px;
}
.role-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
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
