<template>
  <div class="page-container">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchName"
        placeholder="搜索任务名称"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select v-model="searchStatus" clearable placeholder="状态" style="width: 100px" @change="reload">
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>
      <el-button type="primary" @click="reload">搜索</el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建任务</el-button>
    </div>

    <!-- 任务列表 -->
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="name" label="任务名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="类型" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.task_type === 'cron' ? 'primary' : 'success'" size="small">
            {{ row.task_type === 'cron' ? '周期' : '间隔' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="执行规则" width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.task_type === 'cron'" class="mono">{{ row.cron_expr }}</span>
          <span v-else>每 {{ formatInterval(row.interval_seconds) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="func_name" label="执行方法" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono small">{{ row.func_name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="一次性" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_once" type="warning" size="small">是</el-tag>
          <span v-else class="text-placeholder">否</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.status === 1"
            @change="(v) => toggleStatus(row, Boolean(v))"
          />
        </template>
      </el-table-column>
      <el-table-column label="上次执行" width="160">
        <template #default="{ row }">{{ formatDt(row.last_run_at) }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="success" @click="runNow(row)">执行</el-button>
          <el-button link type="info" @click="openLog(row)">日志</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="reload"
      @size-change="reload"
    />

    <!-- 新建/编辑表单 -->
    <TaskForm
      v-model="formVisible"
      :edit-data="editData"
      @success="reload"
    />

    <!-- 执行日志抽屉 -->
    <ExecutionLog
      v-model="logVisible"
      :task-id="logTaskId"
      :task-name="logTaskName"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { taskApi } from '@/api/monitor'
import type { ScheduledTaskInfo } from '@/types'
import TaskForm from './components/TaskForm.vue'
import ExecutionLog from './components/ExecutionLog.vue'

const loading = ref(false)
const tasks = ref<ScheduledTaskInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchName = ref('')
const searchStatus = ref<number | ''>('')

// 表单
const formVisible = ref(false)
const editData = ref<ScheduledTaskInfo | null>(null)

// 日志
const logVisible = ref(false)
const logTaskId = ref<number | null>(null)
const logTaskName = ref('')

async function reload() {
  loading.value = true
  try {
    const res = await taskApi.list({
      page: page.value,
      page_size: pageSize.value,
      name: searchName.value || undefined,
      status: searchStatus.value === '' ? undefined : searchStatus.value,
    })
    const d = res.data
    tasks.value = d?.items ?? []
    total.value = d?.total ?? 0
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editData.value = null
  formVisible.value = true
}

function openEdit(row: ScheduledTaskInfo) {
  editData.value = { ...row }
  formVisible.value = true
}

function openLog(row: ScheduledTaskInfo) {
  logTaskId.value = row.id
  logTaskName.value = row.name
  logVisible.value = true
}

async function toggleStatus(row: ScheduledTaskInfo, enabled: boolean) {
  try {
    if (enabled) {
      await taskApi.enable(row.id)
      ElMessage.success('已启用')
    } else {
      await taskApi.disable(row.id)
      ElMessage.success('已停用')
    }
    row.status = enabled ? 1 : 0
  } catch {
    ElMessage.error('操作失败')
  }
}

async function runNow(row: ScheduledTaskInfo) {
  await ElMessageBox.confirm(`确定立即执行「${row.name}」？`, '提示', { type: 'warning' })
  try {
    const res = await taskApi.runNow(row.id)
    const taskId = res.data?.celery_task_id
    ElMessage.success(`已触发执行${taskId ? `，Celery ID: ${taskId}` : ''}`)
    reload()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    ElMessage.error(err.response?.data?.message || '触发失败')
  }
}

async function handleDelete(row: ScheduledTaskInfo) {
  await ElMessageBox.confirm(`确定删除任务「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await taskApi.remove(row.id)
    ElMessage.success('已删除')
    reload()
  } catch {
    ElMessage.error('删除失败')
  }
}

function formatDt(dt: string | null) {
  return dt ? dayjs(dt).format('MM-DD HH:mm:ss') : '—'
}

function formatInterval(seconds?: number) {
  const value = Number(seconds || 0)
  const units = [
    { label: '天', seconds: 86400 },
    { label: '小时', seconds: 3600 },
    { label: '分钟', seconds: 60 },
    { label: '秒', seconds: 1 },
  ]

  for (const unit of units) {
    if (value >= unit.seconds && value % unit.seconds === 0) {
      return `${value / unit.seconds} ${unit.label}`
    }
  }

  return `${value} 秒`
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.search-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.mono { font-family: monospace; }
.small { font-size: 12px; }
.text-placeholder { color: #c0c4cc; font-size: 13px; }
</style>
