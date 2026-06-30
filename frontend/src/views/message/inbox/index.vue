<template>
  <div class="page-container">
    <div class="search-bar">
      <el-radio-group v-model="readFilter" @change="reload">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button :label="false">未读</el-radio-button>
        <el-radio-button :label="true">已读</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :disabled="unreadCount === 0" @click="handleReadAll">全部已读</el-button>
      <span class="summary">未读 {{ unreadCount }} 条</span>
    </div>

    <el-table v-loading="loading" :data="messages" border stripe>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_read ? 'info' : 'danger'" size="small">
            {{ row.is_read ? '已读' : '未读' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="message-title-link" :class="{ unread: !row.is_read }" @click="openDetail(row)">
            {{ row.title }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100" align="center">
        <template #default>
          <el-tag size="small">公告</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="阅读时间" width="170">
        <template #default="{ row }">{{ formatTime(row.read_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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

    <el-dialog v-model="detailVisible" title="消息详情" width="680px" class="message-detail-dialog">
      <template v-if="currentMessage">
        <div class="message-detail-header">
          <div class="message-title">{{ currentMessage.title }}</div>
          <div class="message-meta">
            <el-tag size="small" type="primary">公告</el-tag>
            <span>发送时间：{{ formatTime(currentMessage.created_at) }}</span>
            <span>阅读时间：{{ formatTime(currentMessage.read_at) }}</span>
          </div>
        </div>
        <el-divider />
        <div class="message-content markdown-body" v-html="renderMarkdown(currentMessage.content)" />
      </template>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'
import dayjs from 'dayjs'
import { messageApi } from '@/api/message'
import type { MessageInfo } from '@/types'

const loading = ref(false)
const messages = ref<MessageInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const readFilter = ref<boolean | ''>('')
const unreadCount = ref(0)
const detailVisible = ref(false)
const currentMessage = ref<MessageInfo | null>(null)
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

async function reload() {
  loading.value = true
  try {
    const res = await messageApi.inboxList({
      page: page.value,
      page_size: pageSize.value,
      is_read: readFilter.value === '' ? undefined : readFilter.value,
    })
    messages.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
    await fetchUnread()
  } finally {
    loading.value = false
  }
}

async function fetchUnread() {
  const res = await messageApi.unreadSummary()
  unreadCount.value = res.data?.unread_count ?? 0
}

async function openDetail(row: any) {
  currentMessage.value = row
  detailVisible.value = true
  await markRead(row)
}

async function markRead(row: any) {
  if (!row.is_read) {
    const res = await messageApi.markRead(row.id)
    Object.assign(row, res.data)
    await fetchUnread()
  }
}

async function handleReadAll() {
  await messageApi.markAllRead()
  ElMessage.success('已全部标记为已读')
  reload()
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除消息「${row.title}」？`, '提示', { type: 'warning' })
  await messageApi.deleteMessage(row.id)
  ElMessage.success('删除成功')
  reload()
}

function formatTime(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

onMounted(reload)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.search-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.summary {
  color: $text-secondary;
  font-size: 13px;
}

.unread {
  font-weight: 600;
  color: $text-primary;
}

.message-title-link {
  cursor: pointer;

  &:hover {
    color: var(--el-color-primary);
  }
}

.message-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.4;
  color: $text-primary;
  margin-bottom: 12px;
}

.message-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 18px;
  color: $text-secondary;
  font-size: 13px;
}

.message-detail-header {
  padding: 2px 2px 0;
}

.message-content {
  max-height: 520px;
  overflow: auto;
  padding: 4px 2px 0;
  line-height: 1.7;
  color: $text-regular;
}

:deep(.message-detail-dialog .el-divider--horizontal) {
  margin: 18px 0;
}

.markdown-body {
  :deep(h1), :deep(h2), :deep(h3) {
    margin: 12px 0 8px;
    line-height: 1.35;
    color: $text-primary;
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
    color: $text-regular;
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
</style>
