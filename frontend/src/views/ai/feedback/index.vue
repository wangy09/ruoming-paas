<template>
  <div class="page-container">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon total">📋</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">总反馈数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon bug">🐛</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.bug_count }}</div>
            <div class="stat-label">Bug 报告</div>
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon feature">💡</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.feature_count }}</div>
            <div class="stat-label">功能建议</div>
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon usage">❓</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.usage_count }}</div>
            <div class="stat-label">使用问题</div>
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon pending">⏳</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.pending_count }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-icon resolved">✅</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.resolved_count }}</div>
            <div class="stat-label">已处理</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="page-card">
      <!-- 筛选区 -->
      <div class="search-bar">
        <el-form inline class="search-form" @submit.prevent="handleSearch" style="flex:1;">
          <el-form-item label="分类">
            <el-select v-model="query.category" placeholder="全部" clearable style="width:140px">
              <el-option label="Bug 报告" value="bug" />
              <el-option label="功能建议" value="feature" />
              <el-option label="使用问题" value="usage" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="严重程度">
            <el-select v-model="query.severity" placeholder="全部" clearable style="width:140px">
              <el-option label="🟢 轻微" value="low" />
              <el-option label="🟡 一般" value="medium" />
              <el-option label="🟠 严重" value="high" />
              <el-option label="🔴 致命" value="critical" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
              <el-option label="待处理" value="pending" />
              <el-option label="已处理" value="resolved" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </el-form-item>
          <el-form-item label="Agent">
            <el-select
              v-model="query.agent_id"
              placeholder="全部"
              clearable
              filterable
              style="width:180px"
            >
              <el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width:240px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
            <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-divider />

      <!-- 反馈列表 -->
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column label="标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row as FeedbackInfo).title || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="分类" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="categoryTagType((row as FeedbackInfo).category)" size="small">
              {{ categoryLabel((row as FeedbackInfo).category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="(row as FeedbackInfo).severity" :type="severityTagType((row as FeedbackInfo).severity)" size="small">
              {{ severityLabel((row as FeedbackInfo).severity) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row as FeedbackInfo).content || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="140">
          <template #default="{ row }">
            <el-tag
              v-for="tag in (row as FeedbackInfo).tags || []"
              :key="tag"
              size="small"
              class="mr-1"
            >{{ tag }}</el-tag>
            <span v-if="!(row as FeedbackInfo).tags?.length" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="用户" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ (row as FeedbackInfo).username || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType((row as FeedbackInfo).status)" size="small">
              {{ statusLabel((row as FeedbackInfo).status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatDate((row as FeedbackInfo).created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row as FeedbackInfo)">详情</el-button>
            <el-button link type="success" @click="handleStatusUpdate(row as FeedbackInfo, 'resolved')">标记已处理</el-button>
            <el-button link type="warning" @click="handleStatusUpdate(row as FeedbackInfo, 'ignored')">忽略</el-button>
            <el-button link type="danger" @click="handleDelete(row as FeedbackInfo)">删除</el-button>
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

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="反馈详情" size="560px">
      <template v-if="currentDetail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="标题">
            {{ currentDetail.title }}
          </el-descriptions-item>
          <el-descriptions-item label="分类">
            <el-tag :type="categoryTagType(currentDetail.category)" size="small">
              {{ categoryLabel(currentDetail.category) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.severity" label="严重程度">
            <el-tag :type="severityTagType(currentDetail.severity)" size="small">
              {{ severityLabel(currentDetail.severity) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentDetail.status)" size="small">
              {{ statusLabel(currentDetail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用户">{{ currentDetail.username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ currentDetail.agent_name || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.tags?.length" label="标签">
            <el-tag
              v-for="tag in currentDetail.tags"
              :key="tag"
              size="small"
              class="mr-1"
            >{{ tag }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatDate(currentDetail.created_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.message_id" label="关联 AI 消息">
            <span>消息 ID: {{ currentDetail.message_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="详细内容">
            <div class="snapshot-content">{{ currentDetail.content }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentDetail.reply" label="管理员回复">
            <div class="snapshot-content">{{ currentDetail.reply }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 回复表单 -->
        <div class="reply-section">
          <div class="section-label">回复反馈</div>
          <el-input
            v-model="replyContent"
            type="textarea"
            :rows="4"
            placeholder="请输入回复内容"
          />
          <div class="reply-actions">
            <el-button type="primary" :loading="replying" @click="handleReply">提交回复</el-button>
            <el-button :loading="replying" @click="handleReplyAndResolve">回复并标记已处理</el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { feedbackApi, agentApi } from '@/api/ai'
import { formatDate } from '@/utils/format'
import type { FeedbackInfo, FeedbackStats, AgentInfo } from '@/types'

// ── 统计数据 ──────────────────────────────────────────────────────────────────
const stats = ref<FeedbackStats>({
  total: 0,
  bug_count: 0,
  feature_count: 0,
  usage_count: 0,
  other_count: 0,
  pending_count: 0,
  resolved_count: 0,
  daily: [],
  category_distribution: [],
})

// ── 列表与筛选 ────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<FeedbackInfo[]>([])
const total = ref(0)
const dateRange = ref<[string, string] | null>(null)

const query = reactive({
  page: 1,
  page_size: 10,
  category: undefined as string | undefined,
  severity: undefined as string | undefined,
  status: undefined as string | undefined,
  agent_id: undefined as number | undefined,
})

// 构建查询参数（合并日期范围）
function buildParams() {
  const params: {
    page?: number
    page_size?: number
    category?: string
    severity?: string
    status?: string
    agent_id?: number
    start_date?: string
    end_date?: string
  } = { ...query }
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

async function fetchList() {
  loading.value = true
  try {
    const res = await feedbackApi.adminList(buildParams())
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  const params: { start_date?: string; end_date?: string } = {}
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  const res = await feedbackApi.stats(params)
  stats.value = res.data
}

function handleSearch() {
  query.page = 1
  fetchList()
  fetchStats()
}

function resetQuery() {
  query.category = undefined
  query.severity = undefined
  query.status = undefined
  query.agent_id = undefined
  dateRange.value = null
  query.page = 1
  fetchList()
  fetchStats()
}

// ── Agent 选项 ────────────────────────────────────────────────────────────────
const agents = ref<AgentInfo[]>([])

async function fetchAgents() {
  const res = await agentApi.list({ page_size: 200 })
  agents.value = res.data.items
}

// ── 映射函数 ──────────────────────────────────────────────────────────────────
function categoryLabel(category: string): string {
  const map: Record<string, string> = { bug: 'Bug 报告', feature: '功能建议', usage: '使用问题', other: '其他' }
  return map[category] || category
}

type CategoryTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function categoryTagType(category: string): CategoryTagType {
  const map: Record<string, CategoryTagType> = { bug: 'danger', feature: 'primary', usage: 'warning', other: 'info' }
  return map[category] || 'info'
}

function severityLabel(severity: string): string {
  const map: Record<string, string> = { low: '轻微', medium: '一般', high: '严重', critical: '致命' }
  return map[severity] || severity
}

type SeverityTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function severityTagType(severity: string): SeverityTagType {
  const map: Record<string, SeverityTagType> = { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[severity] || 'info'
}

type StatusTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function statusLabel(status: string): string {
  const map: Record<string, string> = { pending: '待处理', resolved: '已处理', ignored: '已忽略' }
  return map[status] || status
}

function statusTagType(status: string): StatusTagType | undefined {
  const map: Record<string, StatusTagType> = { pending: 'warning', resolved: 'success', ignored: 'info' }
  return map[status]
}

// ── 详情抽屉 ──────────────────────────────────────────────────────────────────
const detailVisible = ref(false)
const currentDetail = ref<FeedbackInfo | null>(null)
const replyContent = ref('')
const replying = ref(false)

function openDetail(row: FeedbackInfo) {
  currentDetail.value = row
  replyContent.value = row.reply || ''
  detailVisible.value = true
}

// 仅提交回复
async function handleReply() {
  if (!currentDetail.value) return
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replying.value = true
  try {
    const res = await feedbackApi.update(currentDetail.value.id, { reply: replyContent.value.trim() })
    currentDetail.value.reply = res.data.reply
    ElMessage.success('回复成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '回复失败')
  } finally {
    replying.value = false
  }
}

// 回复并标记为已处理
async function handleReplyAndResolve() {
  if (!currentDetail.value) return
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replying.value = true
  try {
    const res = await feedbackApi.update(currentDetail.value.id, {
      reply: replyContent.value.trim(),
      status: 'resolved',
    })
    currentDetail.value.reply = res.data.reply
    currentDetail.value.status = res.data.status
    ElMessage.success('回复成功并已标记为已处理')
    fetchList()
    fetchStats()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    replying.value = false
  }
}

// 更新反馈状态（标记已处理 / 忽略）
async function handleStatusUpdate(row: FeedbackInfo, status: string) {
  try {
    await feedbackApi.update(row.id, { status })
    row.status = status
    ElMessage.success('状态已更新')
    fetchStats()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// 删除反馈
async function handleDelete(row: FeedbackInfo) {
  await ElMessageBox.confirm('确定删除该反馈记录？删除后不可恢复。', '警告', { type: 'warning' })
  await feedbackApi.remove(row.id)
  ElMessage.success('删除成功')
  fetchList()
  fetchStats()
}

onMounted(() => {
  fetchAgents()
  fetchList()
  fetchStats()
})
</script>

<style lang="scss" scoped>
.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    flex-shrink: 0;

    &.total { background: #ecf5ff; }
    &.bug { background: #fef0f0; }
    &.feature { background: #ecf5ff; }
    &.usage { background: #fdf6ec; }
    &.pending { background: #fdf6ec; }
    &.resolved { background: #f0f9eb; }
  }

  .stat-info {
    .stat-value {
      font-size: 24px;
      font-weight: 700;
      color: #303133;
      line-height: 1.2;
    }

    .stat-label {
      font-size: 13px;
      color: #909399;
      margin-top: 4px;
    }
  }
}

.search-form {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mt-4 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }
.text-muted { color: var(--el-text-color-secondary); }

.snapshot-content {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.reply-section {
  margin-top: 24px;

  .section-label {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 10px;
  }

  .reply-actions {
    display: flex;
    gap: 10px;
    margin-top: 10px;
  }
}
</style>
