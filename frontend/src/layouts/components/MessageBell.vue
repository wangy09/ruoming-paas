<template>
  <el-popover placement="bottom-end" width="320" trigger="click" @show="fetchUnread">
    <template #reference>
      <el-badge :value="badgeValue" :hidden="unreadCount === 0" :max="99">
        <el-icon class="header-icon">
          <Bell />
        </el-icon>
      </el-badge>
    </template>

    <div class="message-popover">
      <div class="popover-header">
        <span>新消息</span>
        <el-button link type="primary" @click="goInbox">查看全部</el-button>
      </div>
      <div v-if="unreadCount === 0" class="empty">暂无未读消息</div>
      <div v-else class="latest" @click="goInbox">
        <div class="latest-title">{{ latest?.title || `你有 ${unreadCount} 条未读消息` }}</div>
        <div v-if="latest?.content" class="latest-content markdown-preview" v-html="renderMarkdown(latest.content)" />
        <div class="latest-time">{{ formatTime(latest?.created_at) }}</div>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import dayjs from 'dayjs'
import { messageApi } from '@/api/message'
import type { MessageInfo } from '@/types'

const router = useRouter()
const unreadCount = ref(0)
const latest = ref<MessageInfo | null>(null)
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
let timer: number | null = null

const badgeValue = computed(() => (unreadCount.value > 99 ? '99+' : unreadCount.value))

async function fetchUnread() {
  try {
    const res = await messageApi.unreadSummary()
    unreadCount.value = res.data?.unread_count ?? 0
    latest.value = res.data?.latest ?? null
  } catch {
    unreadCount.value = 0
    latest.value = null
  }
}

function goInbox() {
  router.push('/message/inbox')
}

function formatTime(value?: string | null) {
  return value ? dayjs(value).format('MM-DD HH:mm') : ''
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

onMounted(() => {
  fetchUnread()
  timer = window.setInterval(fetchUnread, 60000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.header-icon {
  font-size: 18px;
  cursor: pointer;
  color: $text-regular;
  &:hover { color: $primary-color; }
}

.message-popover {
  .popover-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    margin-bottom: 8px;
  }

  .empty {
    color: $text-secondary;
    text-align: center;
    padding: 18px 0;
  }

  .latest {
    cursor: pointer;
    border-radius: 6px;
    padding: 10px;
    background: #f5f7fa;

    &:hover {
      background: #ecf5ff;
    }
  }

  .latest-title {
    font-weight: 600;
    margin-bottom: 6px;
  }

  .latest-content {
    color: $text-regular;
    font-size: 13px;
    line-height: 1.5;
    max-height: 42px;
    overflow: hidden;

    :deep(p) {
      margin: 0;
    }

    :deep(ul), :deep(ol) {
      margin: 0;
      padding-left: 18px;
    }

    :deep(h1), :deep(h2), :deep(h3) {
      margin: 0;
      font-size: 13px;
      line-height: 1.5;
    }

    :deep(code) {
      padding: 1px 4px;
      border-radius: 3px;
      background: var(--el-fill-color);
    }

    :deep(a) {
      color: var(--el-color-primary);
    }
  }

  .latest-time {
    color: $text-secondary;
    font-size: 12px;
    margin-top: 8px;
  }
}
</style>
