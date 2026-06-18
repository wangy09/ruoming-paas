<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 搜索栏 -->
      <el-form inline class="search-form" @submit.prevent="fetchList">
        <el-form-item label="用户名">
          <el-input v-model="query.username" placeholder="用户名" clearable style="width:160px" />
        </el-form-item>
        <el-form-item label="登录状态">
          <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
            <el-option label="成功" :value="1" />
            <el-option label="失败" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <!-- 表格 -->
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="100" />
        <el-table-column prop="login_type" label="登录类型" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.login_type === 'password'" size="small" type="info">密码</el-tag>
            <el-tag v-else-if="row.login_type === 'oauth'" size="small" type="success">OAuth</el-tag>
            <span v-else>{{ row.login_type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'success'" size="small" type="success">成功</el-tag>
            <el-tag v-else-if="row.status === 'fail'" size="small" type="danger">失败</el-tag>
            <el-tag v-else size="small" type="warning">锁定</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fail_reason" label="失败原因" min-width="150" show-overflow-tooltip />
        <el-table-column prop="login_ip" label="登录IP" min-width="120" />
        <el-table-column prop="browser" label="浏览器" width="100" />
        <el-table-column prop="os" label="操作系统" width="100" />
        <el-table-column prop="device" label="设备" width="80" />
        <el-table-column prop="created_at" label="登录时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { auditApi } from '@/api/audit'
import { formatDate } from '@/utils/format'
import type { LoginLog } from '@/types'

// ── 列表 ──────────────────────────────────────────────────────────────────────
const loading = ref(false)
const tableData = ref<LoginLog[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 10,
  username: '',
  status: undefined as string | undefined,
})

/**
 * 获取登录日志列表
 */
async function fetchList() {
  loading.value = true
  try {
    const res = await auditApi.loginLogs({
      page: query.page,
      page_size: query.page_size,
      username: query.username || undefined,
      status: query.status ? (query.status === '1' ? 1 : 0) : undefined,
    })
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

/**
 * 重置查询条件
 */
function resetQuery() {
  query.username = ''
  query.status = undefined
  query.page = 1
  fetchList()
}

/**
 * 从 user_agent 解析操作系统
 */
function parseOs(userAgent?: string): string {
  if (!userAgent) return '-'
  if (userAgent.includes('Windows')) return 'Windows'
  if (userAgent.includes('Mac OS')) return 'MacOS'
  if (userAgent.includes('Linux')) return 'Linux'
  if (userAgent.includes('Android')) return 'Android'
  if (userAgent.includes('iPhone') || userAgent.includes('iPad')) return 'iOS'
  return '-'
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.mt-4 { margin-top: 16px; }
</style>