<template>
  <el-drawer
    v-model="visible"
    :title="`执行日志${taskName ? '：' + taskName : ''}`"
    size="850px"
    :close-on-click-modal="false"
  >
    <!-- 工具栏 -->
    <div class="log-toolbar">
      <el-select v-model="filterStatus" clearable placeholder="状态筛选" style="width: 130px" @change="reload">
        <el-option label="等待中" value="pending" />
        <el-option label="执行中" value="running" />
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <el-button type="danger" plain @click="handleClear">清空日志</el-button>
    </div>

    <!-- 日志表格 -->
    <el-table :data="logs" v-loading="loading" size="small" stripe style="margin-top: 12px">
      <el-table-column label="触发方式" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.triggered_by === 'manual' ? 'warning' : 'info'" size="small">
            {{ row.triggered_by === 'manual' ? '手动' : '调度' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="90" align="right">
        <template #default="{ row }">
          {{ row.duration_ms != null ? row.duration_ms + ' ms' : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="{ row }">{{ formatDt(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="Celery ID" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.celery_task_id || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="showDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 12px; justify-content: flex-end"
      @current-change="reload"
      @size-change="reload"
    />

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="执行详情" width="560px" append-to-body>
      <el-descriptions :column="2" border size="small" v-if="detailLog">
        <el-descriptions-item label="任务名称" :span="2">{{ detailLog.task_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(detailLog.status)" size="small">{{ statusLabel(detailLog.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="触发方式">
          {{ detailLog.triggered_by === 'manual' ? '手动触发' : '调度触发' }}
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDt(detailLog.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatDt(detailLog.finished_at) }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ detailLog.duration_ms != null ? detailLog.duration_ms + ' ms' : '—' }}</el-descriptions-item>
        <el-descriptions-item label="Celery ID">
          <span class="mono">{{ detailLog.celery_task_id || '—' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template v-if="detailLog?.error_msg">
        <el-divider>错误信息</el-divider>
        <pre class="error-block">{{ detailLog.error_msg }}</pre>
      </template>
      <template v-if="detailLog?.result">
        <el-divider>执行结果</el-divider>
        <pre class="result-block">{{ JSON.stringify(detailLog.result, null, 2) }}</pre>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi } from '@/api/monitor'
import type { TaskExecutionLogInfo } from '@/types'
import dayjs from 'dayjs'

const props = defineProps<{
  modelValue: boolean
  taskId: number | null
  taskName?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => emit('update:modelValue', v))

const loading = ref(false)
const logs = ref<TaskExecutionLogInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const filterStatus = ref('')
const detailVisible = ref(false)
const detailLog = ref<TaskExecutionLogInfo | null>(null)

watch(() => props.taskId, (id) => {
  if (id != null && visible.value) reload()
})
watch(visible, (v) => {
  if (v && props.taskId != null) reload()
})

async function reload() {
  if (props.taskId == null) return
  loading.value = true
  try {
    const res = await taskApi.logs(props.taskId, {
      page: page.value,
      page_size: pageSize.value,
      status: filterStatus.value || undefined,
    })
    const d = res.data
    logs.value = d?.items ?? []
    total.value = d?.total ?? 0
  } finally {
    loading.value = false
  }
}

function showDetail(row: TaskExecutionLogInfo) {
  detailLog.value = row
  detailVisible.value = true
}

async function handleClear() {
  await ElMessageBox.confirm('确定清空该任务的所有执行日志？', '提示', { type: 'warning' })
  await taskApi.clearLogs({ task_id: props.taskId ?? undefined })
  ElMessage.success('清空成功')
  reload()
}

function statusLabel(s: string) {
  return { pending: '等待中', running: '执行中', success: '成功', failed: '失败' }[s] ?? s
}
function statusTagType(s: string): 'info' | 'warning' | 'success' | 'danger' {
  return { pending: 'info', running: 'warning', success: 'success', failed: 'danger' }[s] as any ?? 'info'
}
function formatDt(dt: string | null) {
  return dt ? dayjs(dt).format('YYYY-MM-DD HH:mm:ss') : '—'
}
</script>

<style lang="scss" scoped>
.log-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.mono { font-family: monospace; font-size: 12px; }
.error-block {
  background: #fff5f5;
  border: 1px solid #ffc0c0;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  white-space: pre-wrap;
  color: #c00;
  max-height: 200px;
  overflow: auto;
}
.result-block {
  background: #f6f8fa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 12px;
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
</style>
