<template>
  <div class="page-container">
    <div class="page-card">
      <el-form inline class="search-form" @submit.prevent="fetchList">
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" placeholder="租户名/代码" clearable style="width:180px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
            <el-option label="正常" value="active" />
            <el-option label="禁用" value="inactive" />
            <el-option label="暂停" value="suspended" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchList">查询</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <div class="table-toolbar">
        <el-button type="primary" :icon="Plus" v-permission="'system:tenant:create'" @click="openDialog()">
          新增租户
        </el-button>
      </div>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="name" label="租户名" min-width="140" />
        <el-table-column prop="code" label="租户代码" width="140" />
        <el-table-column label="套餐" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="planTagMap[row.plan]" size="small">{{ planLabelMap[row.plan] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :class="`status-${row.status}`" size="small">{{ statusLabelMap[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用户数" width="100" align="center">
          <template #default="{ row }">
            {{ row.current_users ?? '-' }} / {{ row.max_users }}
          </template>
        </el-table-column>
        <el-table-column prop="contact_email" label="联系邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'system:tenant:update'" @click="openDialog(row)">编辑</el-button>
            <el-button
              v-if="row.status !== 'active'"
              link type="success"
              v-permission="'system:tenant:update'"
              @click="handleApprove(row)"
            >启用</el-button>
            <el-button
              v-else
              link type="warning"
              v-permission="'system:tenant:update'"
              @click="handleDisable(row)"
            >禁用</el-button>
            <el-button link type="info" @click="showUsage(row)">用量</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-4"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @change="fetchList"
      />
    </div>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑租户' : '新增租户'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="租户名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="租户代码" prop="code">
          <el-input v-model="form.code" :disabled="!!editId" placeholder="唯一标识，创建后不可改" />
        </el-form-item>
        <el-form-item label="套餐" prop="plan">
          <el-select v-model="form.plan" style="width:100%">
            <el-option label="基础版" value="basic" />
            <el-option label="专业版" value="pro" />
            <el-option label="企业版" value="enterprise" />
          </el-select>
        </el-form-item>
        <el-form-item label="最大用户数">
          <el-input-number v-model="form.max_users" :min="1" />
        </el-form-item>
        <el-form-item label="日 API 配额">
          <el-input-number v-model="form.max_api_calls_per_day" :min="100" :step="100" />
        </el-form-item>
        <el-form-item label="日 Token 配额">
          <el-input-number v-model="form.max_ai_tokens_per_day" :min="1000" :step="10000" />
        </el-form-item>
        <el-form-item label="联系邮箱">
          <el-input v-model="form.contact_email" type="email" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 用量详情 -->
    <el-dialog v-model="usageDialogVisible" title="用量详情" width="400px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="今日 API 调用">{{ usage?.api_calls ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="今日 AI Token">{{ usage?.ai_tokens ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="存储占用 (MB)">{{ usage?.storage_mb ?? '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { tenantApi } from '@/api/tenant'
import { formatDate } from '@/utils/format'
import type { TenantInfo } from '@/types'

const planTagMap: Record<string, string> = { basic: 'info', pro: 'primary', enterprise: 'danger' }
const planLabelMap: Record<string, string> = { basic: '基础版', pro: '专业版', enterprise: '企业版' }
const statusLabelMap: Record<string, string> = { active: '正常', inactive: '禁用', suspended: '暂停' }

const loading = ref(false)
const tableData = ref<TenantInfo[]>([])
const total = ref(0)

const query = reactive({ page: 1, page_size: 10, keyword: '', status: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await tenantApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.status = ''
  query.page = 1
  fetchList()
}

async function handleApprove(row: TenantInfo) {
  await tenantApi.approve(row.id)
  ElMessage.success('已启用')
  fetchList()
}

async function handleDisable(row: TenantInfo) {
  await ElMessageBox.confirm(`确定禁用租户「${row.name}」？`, '警告', { type: 'warning' })
  await tenantApi.disable(row.id)
  ElMessage.success('已禁用')
  fetchList()
}

// 用量
const usageDialogVisible = ref(false)
const usage = ref<{ api_calls: number; ai_tokens: number; storage_mb: number } | null>(null)

async function showUsage(row: TenantInfo) {
  const res = await tenantApi.usage(row.id)
  usage.value = res.data
  usageDialogVisible.value = true
}

// 编辑
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '', code: '', plan: 'basic', contact_email: '',
  max_users: 10, max_api_calls_per_day: 1000, max_ai_tokens_per_day: 100000,
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入租户名' }],
  code: [{ required: true, message: '请输入租户代码' }],
}

function openDialog(row?: TenantInfo) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    name: row?.name ?? '', code: row?.code ?? '', plan: row?.plan ?? 'basic',
    contact_email: row?.contact_email ?? '', max_users: row?.max_users ?? 10,
    max_api_calls_per_day: row?.max_api_calls_per_day ?? 1000,
    max_ai_tokens_per_day: row?.max_ai_tokens_per_day ?? 100000,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await tenantApi.update(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await tenantApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-form { :deep(.el-form-item) { margin-bottom: 0; } }
.table-toolbar { margin-bottom: 12px; }
.mt-4 { margin-top: 16px; }
</style>
