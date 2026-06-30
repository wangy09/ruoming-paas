<template>
  <div class="page-container">
    <div class="search-bar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索公告标题"
        clearable
        style="width: 220px"
        @keyup.enter="fetchList"
        @clear="fetchList"
      />
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 120px" @change="fetchList">
        <el-option label="草稿" :value="0" />
        <el-option label="已发布" :value="1" />
      </el-select>
      <el-select v-model="query.target_type" clearable placeholder="范围" style="width: 130px" @change="fetchList">
        <el-option label="全平台" value="all" />
        <el-option label="部门" value="dept" />
        <el-option label="指定用户" value="user" />
      </el-select>
      <el-button type="primary" @click="fetchList">查询</el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建公告</el-button>
    </div>

    <el-table v-loading="loading" :data="tableData" border stripe>
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column label="投放范围" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="targetTagType(row.target_type)" size="small">
            {{ targetLabel(row.target_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="receiver_count" label="接收人数" width="100" align="center" />
      <el-table-column label="发布时间" width="170">
        <template #default="{ row }">{{ formatTime(row.published_at) }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 0" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 0" link type="success" @click="handlePublish(row)">发布</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
      @size-change="fetchList"
    />

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" :disabled="detailMode" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="投放范围" required>
          <el-radio-group v-model="form.target_type" :disabled="detailMode">
            <el-radio-button label="all">全平台</el-radio-button>
            <el-radio-button label="dept">部门</el-radio-button>
            <el-radio-button label="user">指定用户</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.target_type === 'dept'" label="接收部门" required>
          <el-tree-select
            v-model="form.target_dept_ids"
            :data="deptOptions"
            :props="deptTreeProps"
            multiple
            check-strictly
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择部门"
            :disabled="detailMode"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="form.target_type === 'user'" label="接收用户" required>
          <el-select
            v-model="form.target_user_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择用户"
            :disabled="detailMode"
            style="width: 100%"
          >
            <el-option
              v-for="user in userOptions"
              :key="user.id"
              :label="`${user.nickname || user.username}（${user.username}）`"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-tabs v-model="contentTab" class="content-tabs">
            <el-tab-pane :label="detailMode ? '内容' : 'Markdown 编辑'" name="edit">
              <el-input
                v-if="!detailMode"
                v-model="form.content"
                type="textarea"
                :rows="10"
                placeholder="请输入公告内容，支持 Markdown 语法"
              />
              <div v-else class="markdown-body" v-html="renderMarkdown(form.content)" />
            </el-tab-pane>
            <el-tab-pane v-if="!detailMode" label="预览" name="preview">
              <div class="markdown-body markdown-preview" v-html="renderMarkdown(form.content)" />
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" :disabled="detailMode" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <template v-if="!detailMode">
          <el-button :loading="submitting" @click="submit(false)">保存草稿</el-button>
          <el-button type="primary" :loading="submitting" @click="submit(true)">保存并发布</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import dayjs from 'dayjs'
import { messageApi } from '@/api/message'
import { systemApi } from '@/api/system'
import { userApi } from '@/api/user'
import type { DeptInfo, NoticeInfo, NoticeTargetType, UserListItem } from '@/types'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref<NoticeInfo[]>([])
const total = ref(0)
const deptOptions = ref<DeptInfo[]>([])
const userOptions = ref<UserListItem[]>([])
const deptTreeProps = { label: 'name', value: 'id', children: 'children' } as any
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  status: undefined as number | undefined,
  target_type: undefined as NoticeTargetType | undefined,
})

const dialogVisible = ref(false)
const detailMode = ref(false)
const editId = ref<number | null>(null)
const contentTab = ref('edit')
const form = reactive({
  title: '',
  content: '',
  target_type: 'all' as NoticeTargetType,
  target_dept_ids: [] as number[],
  target_user_ids: [] as number[],
  remark: '',
})

const dialogTitle = computed(() => {
  if (detailMode.value) return '公告详情'
  return editId.value ? '编辑公告' : '新建公告'
})

async function fetchList() {
  loading.value = true
  try {
    const res = await messageApi.noticeList(query)
    tableData.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

async function fetchOptions() {
  const [deptRes, userRes] = await Promise.all([
    systemApi.deptOptions().catch(() => null),
    userApi.list({ page: 1, page_size: 200 }).catch(() => null),
  ])
  deptOptions.value = deptRes?.data ?? []
  userOptions.value = userRes?.data?.items ?? []
}

function resetForm() {
  editId.value = null
  detailMode.value = false
  contentTab.value = 'edit'
  form.title = ''
  form.content = ''
  form.target_type = 'all'
  form.target_dept_ids = []
  form.target_user_ids = []
  form.remark = ''
}

function fillForm(row: any) {
  editId.value = row.id
  form.title = row.title
  form.content = row.content
  form.target_type = row.target_type
  form.target_dept_ids = row.target_dept_ids ?? []
  form.target_user_ids = row.target_user_ids ?? []
  form.remark = row.remark ?? ''
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: any) {
  resetForm()
  fillForm(row)
  dialogVisible.value = true
}

function openDetail(row: any) {
  resetForm()
  fillForm(row)
  detailMode.value = true
  contentTab.value = 'edit'
  dialogVisible.value = true
}

function validateForm() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入公告标题')
    return false
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入公告内容')
    return false
  }
  if (form.target_type === 'dept' && form.target_dept_ids.length === 0) {
    ElMessage.warning('请选择接收部门')
    return false
  }
  if (form.target_type === 'user' && form.target_user_ids.length === 0) {
    ElMessage.warning('请选择接收用户')
    return false
  }
  return true
}

async function submit(publishNow: boolean) {
  if (!validateForm()) return
  submitting.value = true
  try {
    const payload = {
      title: form.title,
      content: form.content,
      target_type: form.target_type,
      target_dept_ids: form.target_type === 'dept' ? form.target_dept_ids : [],
      target_user_ids: form.target_type === 'user' ? form.target_user_ids : [],
      remark: form.remark || undefined,
    }
    if (editId.value) {
      await messageApi.noticeUpdate(editId.value, payload)
      if (publishNow) await messageApi.noticePublish(editId.value)
    } else {
      await messageApi.noticeCreate({ ...payload, publish_now: publishNow })
    }
    ElMessage.success(publishNow ? '公告已发布' : '保存成功')
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

async function handlePublish(row: any) {
  await ElMessageBox.confirm(`确定发布公告「${row.title}」？发布后将推送给目标用户。`, '发布确认', { type: 'warning' })
  await messageApi.noticePublish(row.id)
  ElMessage.success('发布成功')
  fetchList()
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除公告「${row.title}」？`, '提示', { type: 'warning' })
  await messageApi.noticeDelete(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

function targetLabel(type: NoticeTargetType) {
  return ({ all: '全平台', dept: '部门', user: '指定用户' } as Record<NoticeTargetType, string>)[type]
}

function targetTagType(type: NoticeTargetType) {
  return type === 'all' ? 'danger' : type === 'dept' ? 'warning' : 'primary'
}

function formatTime(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

onMounted(() => {
  fetchList()
  fetchOptions()
})
</script>

<style lang="scss" scoped>
.search-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.content-tabs {
  width: 100%;
}

.markdown-body {
  min-height: 240px;
  max-height: 420px;
  overflow: auto;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  line-height: 1.7;
  color: var(--el-text-color-primary);

  :deep(h1), :deep(h2), :deep(h3) {
    margin: 12px 0 8px;
    line-height: 1.35;
  }

  :deep(p) {
    margin: 0 0 10px;
  }

  :deep(ul), :deep(ol) {
    padding-left: 22px;
    margin: 0 0 10px;
  }

  :deep(blockquote) {
    margin: 0 0 10px;
    padding: 8px 12px;
    border-left: 4px solid var(--el-border-color);
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-light);
  }

  :deep(code) {
    padding: 2px 5px;
    border-radius: 4px;
    background: var(--el-fill-color-light);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }

  :deep(pre) {
    padding: 12px;
    overflow: auto;
    border-radius: 6px;
    background: var(--el-fill-color-light);

    code {
      padding: 0;
      background: transparent;
    }
  }

  :deep(a) {
    color: var(--el-color-primary);
  }
}

.markdown-preview {
  min-height: 268px;
}
</style>
