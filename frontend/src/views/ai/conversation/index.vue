<template>
  <div class="page-container">
    <el-row :gutter="16" style="height:calc(100vh - 168px)">
      <!-- 对话列表 -->
      <el-col :span="7" style="height:100%">
        <div class="page-card h-full flex flex-col">
          <div class="card-header">
            <div class="header-left">
              <template v-if="batchMode">
                <el-checkbox
                  v-model="selectAll"
                  :indeterminate="isIndeterminate"
                  @change="toggleSelectAll"
                />
                <span class="card-title">已选 {{ selectedIds.length }} 项</span>
              </template>
              <template v-else>
                <span class="card-title">对话历史</span>
              </template>
            </div>
            <div class="header-right">
              <template v-if="batchMode">
                <el-button size="small" @click="exitBatchMode">取消</el-button>
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  :disabled="!selectedIds.length"
                  @click="batchDelete"
                >
                  删除 ({{ selectedIds.length }})
                </el-button>
              </template>
              <template v-else>
                <el-button size="small" :icon="Delete" @click="enterBatchMode">批量删除</el-button>
              </template>
            </div>
          </div>
          <el-scrollbar flex-1>
            <div
              v-for="conv in convList"
              :key="conv.id"
              class="conv-item"
              :class="{ active: !batchMode && currentConv?.id === conv.id, selected: batchMode && selectedIds.includes(conv.id) }"
              @click="batchMode ? toggleSelect(conv.id) : selectConv(conv)"
            >
              <el-checkbox
                v-if="batchMode"
                :model-value="selectedIds.includes(conv.id)"
                class="conv-checkbox"
                @click.stop
                @change="() => toggleSelect(conv.id)"
              />
              <div class="conv-body">
                <div class="conv-title">{{ conv.title || `对话 #${conv.id}` }}</div>
                <div class="conv-meta">
                  {{ conv.message_count }} 条消息 · {{ fromNow(conv.last_message_at || conv.created_at) }}
                </div>
              </div>
            </div>
            <el-empty v-if="!convList.length" description="暂无对话记录" />
          </el-scrollbar>

          <el-pagination
            class="mt-2"
            v-model:current-page="convQuery.page"
            :total="convTotal"
            small
            layout="prev, pager, next"
            @change="fetchConvList"
          />
        </div>
      </el-col>

      <!-- 消息详情 -->
      <el-col :span="17" style="height:100%">
        <div class="page-card h-full flex flex-col">
          <div v-if="!currentConv" class="empty-state">
            <el-empty description="选择左侧对话查看消息" />
          </div>
          <template v-else>
            <div class="card-header">
              <span class="card-title">{{ currentConv.title || `对话 #${currentConv.id}` }}</span>
              <el-button link type="danger" :icon="Delete" @click="deleteConv">删除对话</el-button>
            </div>

            <el-scrollbar flex-1 ref="msgScrollbar">
              <div class="messages">
                <div
                  v-for="msg in messages"
                  :key="msg.id"
                  class="message-wrapper"
                  :class="msg.role"
                >
                  <div class="message-role">
                    <el-avatar :size="32" :class="`avatar-${msg.role}`">
                      {{ msg.role === 'user' ? 'U' : msg.role === 'assistant' ? 'AI' : 'S' }}
                    </el-avatar>
                    <span class="role-label">{{ roleLabel[msg.role] }}</span>
                    <span class="msg-time">{{ formatDate(msg.created_at) }}</span>
                  </div>
                  <div class="message-bubble" :class="`bubble-${msg.role}`">
                    <div class="msg-content" v-html="renderMarkdown(msg.content)" />
                    <div v-if="msg.total_tokens" class="msg-tokens">{{ msg.total_tokens }} tokens</div>
                  </div>
                </div>
              </div>
            </el-scrollbar>
          </template>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { conversationApi } from '@/api/ai'
import { formatDate, fromNow } from '@/utils/format'
import type { Conversation, ChatMessage } from '@/types'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const roleLabel: Record<string, string> = { user: '用户', assistant: 'AI', system: '系统' }

const convList = ref<Conversation[]>([])
const convTotal = ref(0)
const convQuery = reactive({ page: 1, page_size: 20 })
const currentConv = ref<Conversation | null>(null)
const messages = ref<ChatMessage[]>([])
const msgScrollbar = ref()

// 批量选择模式
const batchMode = ref(false)
const selectedIds = ref<number[]>([])
const selectAll = ref(false)
const isIndeterminate = computed(() => {
  const len = selectedIds.value.length
  return len > 0 && len < convList.value.length
})

function enterBatchMode() {
  batchMode.value = true
  selectedIds.value = []
  selectAll.value = false
}

function exitBatchMode() {
  batchMode.value = false
  selectedIds.value = []
  selectAll.value = false
}

function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
  selectAll.value = selectedIds.value.length === convList.value.length
}

function toggleSelectAll(val: boolean) {
  selectedIds.value = val ? convList.value.map(c => c.id) : []
}

async function fetchConvList() {
  const res = await conversationApi.list(convQuery)
  convList.value = res.data.items
  convTotal.value = res.data.total
  // 翻页后重置选择状态
  selectedIds.value = []
  selectAll.value = false
}

async function selectConv(conv: Conversation) {
  currentConv.value = conv
  const res = await conversationApi.messages(conv.id)
  messages.value = res.data.items || []
  nextTick(() => {
    const el = msgScrollbar.value?.$el?.querySelector('.el-scrollbar__wrap')
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function deleteConv() {
  if (!currentConv.value) return
  await ElMessageBox.confirm('确定删除此对话记录？', '警告', { type: 'warning' })
  await conversationApi.delete(currentConv.value.id)
  ElMessage.success('已删除')
  currentConv.value = null
  messages.value = []
  fetchConvList()
}

async function batchDelete() {
  if (!selectedIds.value.length) return
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedIds.value.length} 条对话？此操作不可恢复。`,
    '批量删除',
    { type: 'warning' },
  )
  const res = await conversationApi.batchDelete(selectedIds.value)
  const deleted = res.data?.data?.deleted ?? 0
  ElMessage.success(`成功删除 ${deleted} 条对话`)
  exitBatchMode()
  // 如果当前查看的对话被删除，清空详情
  if (currentConv.value && !convList.value.find(c => c.id === currentConv.value!.id)) {
    currentConv.value = null
    messages.value = []
  }
  fetchConvList()
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

onMounted(fetchConvList)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.h-full { height: 100%; overflow: hidden; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-1 { flex: 1; overflow: hidden; }
.mt-2 { margin-top: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-shrink: 0; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.card-title { font-size: 15px; font-weight: 600; }
.empty-state { display: flex; align-items: center; justify-content: center; flex: 1; }

.conv-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background .15s;

  &:hover { background: #f5f5f5; }
  &.active { background: #e6f4ff; }
  &.selected { background: #fff0f0; }

  .conv-checkbox { flex-shrink: 0; margin-top: 2px; }
  .conv-body { flex: 1; min-width: 0; }
  .conv-title { font-size: 13px; font-weight: 500; color: $text-primary; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .conv-meta { font-size: 11px; color: $text-secondary; margin-top: 3px; }
}

.messages { padding: 12px 16px; }

.message-wrapper {
  margin-bottom: 20px;

  .message-role {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    .role-label { font-size: 13px; font-weight: 600; color: $text-primary; }
    .msg-time { font-size: 11px; color: $text-secondary; }
  }

  .message-bubble {
    max-width: 85%;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.7;

    &.bubble-user { background: #e6f4ff; border: 1px solid #91caff; }
    &.bubble-assistant { background: #f6ffed; border: 1px solid #b7eb8f; }
    &.bubble-system { background: #fff7e6; border: 1px solid #ffd591; }
  }

  .msg-content {
    :deep(pre) { background: #f0f0f0; padding: 8px; border-radius: 4px; overflow: auto; font-size: 12px; }
    :deep(code) { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-size: 12px; }
    :deep(p) { margin-bottom: 6px; &:last-child { margin-bottom: 0; } }
  }

  .msg-tokens { font-size: 11px; color: $text-secondary; margin-top: 6px; text-align: right; }

  &.assistant .message-bubble { margin-left: 0; }
  &.user {
    .message-role { flex-direction: row-reverse; }
    .message-bubble { margin-left: auto; }
  }
}

.avatar-user { background: $primary-color !important; }
.avatar-assistant { background: #52c41a !important; }
.avatar-system { background: #faad14 !important; }
</style>
