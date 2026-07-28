<template>
  <div class="page-container">
    <div class="page-card">
      <div class="search-header">
        <el-form inline class="search-form" @submit.prevent="fetchList">
          <el-form-item label="用户名">
            <el-input v-model="query.username" placeholder="用户名" clearable style="width: 160px" />
          </el-form-item>
          <el-form-item label="动作">
            <el-input v-model="query.action" placeholder="create/update/delete" clearable style="width: 180px" />
          </el-form-item>
          <el-form-item label="资源类型">
            <el-input v-model="query.resource_type" placeholder="资源类型" clearable style="width: 160px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width: 120px">
              <el-option label="成功" :value="1" />
              <el-option label="失败" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期范围">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 280px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
            <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
        <el-button type="danger" :icon="Delete" @click="confirmClear" v-if="permStore.hasPermission('system:audit:clear')">清除日志</el-button>
      </div>

      <el-divider />

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="100" show-overflow-tooltip />
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column prop="path" label="请求路径" min-width="220" show-overflow-tooltip />
        <el-table-column prop="event_type" label="事件类型" min-width="150" show-overflow-tooltip />
        <el-table-column prop="action" label="动作" width="110" show-overflow-tooltip />
        <el-table-column prop="resource_type" label="资源类型" min-width="120" show-overflow-tooltip />
        <el-table-column label="结果" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 1" size="small" type="success">成功</el-tag>
            <el-tag v-else size="small" type="danger">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_code" label="状态码" width="90" align="center" />
        <el-table-column prop="error_msg" label="错误信息" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'error-text': row.error_msg }">{{ row.error_msg || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="接口返回内容" min-width="130" align="center">
          <template #default="{ row }">
            <el-button
              v-if="hasResponseBody(row.response_body)"
              link
              type="primary"
              @click="openResponseDialog(row.response_body)"
            >
              查看
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="trace_id" label="TraceID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="操作时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>

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

    <el-dialog v-model="responseDialogVisible" title="接口返回内容" width="720px">
      <pre class="json-block">{{ currentResponseBody }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Refresh, Search, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { auditApi } from '@/api/audit'
import { formatDate } from '@/utils/format'
import { usePermissionStore } from '@/store/permission'
import type { AuditLog } from '@/types'

const permStore = usePermissionStore()

const loading = ref(false)
const tableData = ref<AuditLog[]>([])
const total = ref(0)
const responseDialogVisible = ref(false)
const currentResponseBody = ref('')
const dateRange = ref<[string, string] | null>(null)

const query = reactive({
  page: 1,
  page_size: 10,
  username: '',
  action: '',
  resource_type: '',
  status: undefined as number | undefined,
})

async function fetchList() {
  loading.value = true
  try {
    const res = await auditApi.logs({
      page: query.page,
      page_size: query.page_size,
      username: query.username || undefined,
      action: query.action || undefined,
      resource_type: query.resource_type || undefined,
      status: query.status,
      start_time: dateRange.value ? `${dateRange.value[0]} 00:00:00` : undefined,
      end_time: dateRange.value ? `${dateRange.value[1]} 23:59:59` : undefined,
    })
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.username = ''
  query.action = ''
  query.resource_type = ''
  query.status = undefined
  dateRange.value = null
  query.page = 1
  fetchList()
}

async function confirmClear() {
  try {
    const startLabel = dateRange.value ? dateRange.value[0] : '最早'
    const endLabel = dateRange.value ? dateRange.value[1] : '最新'
    await ElMessageBox.confirm(
      `<div style="padding: 16px;">
        <div style="font-size: 16px; margin-bottom: 12px;">确定要清除以下范围的操作日志吗？</div>
        <div style="background: #f5f7fa; padding: 12px; border-radius: 6px;">
          <div style="color: #606266;">日期范围：</div>
          <div style="font-weight: 600;">${startLabel} 至 ${endLabel}</div>
        </div>
        <div style="margin-top: 12px; color: #f56c6c; font-size: 13px;">⚠️ 此操作不可恢复，请谨慎操作</div>
      </div>`,
      '清除日志确认',
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认清除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await clearLogs()
  } catch {
    return
  }
}

async function clearLogs() {
  loading.value = true
  try {
    const params: { start_time?: string; end_time?: string } = {}
    if (dateRange.value) {
      params.start_time = `${dateRange.value[0]} 00:00:00`
      params.end_time = `${dateRange.value[1]} 23:59:59`
    }
    const res = await auditApi.clearLogs(params)
    ElMessage.success(`成功清除 ${res.data.deleted_count} 条日志`)
    await fetchList()
  } catch {
    ElMessage.error('清除日志失败')
  } finally {
    loading.value = false
  }
}

function hasResponseBody(value: AuditLog['response_body']) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.length > 0
  return true
}

function formatResponseBody(value: AuditLog['response_body']) {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function openResponseDialog(responseBody: AuditLog['response_body']) {
  currentResponseBody.value = formatResponseBody(responseBody)
  responseDialogVisible.value = true
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.search-form {
  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.mt-4 {
  margin-top: 16px;
}

.error-text {
  color: var(--el-color-danger);
}

.json-block {
  max-height: 520px;
  padding: 12px;
  overflow: auto;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
</style>
