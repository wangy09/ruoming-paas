<template>
  <div class="page-container">
    <div class="page-card h-full flex flex-col">
      <div class="card-header">
        <span class="card-title">AI 对话</span>
        <el-button type="primary" @click="startNewChat">新对话</el-button>
      </div>

      <div class="chat-layout">
        <!-- 左侧：Agent 列表 + 对话历史 -->
        <div class="chat-sidebar">
          <div class="sidebar-section">
            <div class="section-header">
              <el-icon><List /></el-icon>
              <span>可用 Agent</span>
            </div>
            <div class="agent-list">
              <div
                v-for="agent in agentList"
                :key="agent.id"
                class="agent-item"
                :class="{ active: selectedAgent?.id === agent.id }"
                @click="selectAgent(agent)"
              >
                <div class="agent-icon-sm" :style="{ background: getSceneBgColor(agent.default_scene) }">
                  <el-icon :size="18" :color="getSceneIconColor(agent.default_scene)">
                    <component :is="getSceneIcon(agent.default_scene)" />
                  </el-icon>
                </div>
                <div class="agent-info-sm">
                  <div class="agent-name-sm">{{ agent.name }}</div>
                  <div class="agent-scene-sm">{{ agent.scene_label }}</div>
                </div>
              </div>
              <el-empty v-if="!agentList.length" description="暂无可用 Agent" :image-size="32" />
            </div>
          </div>

          <div class="sidebar-section">
            <div class="section-header">
              <el-icon><Message /></el-icon>
              <span>对话历史</span>
            </div>
            <div class="conv-list">
              <div
                v-for="conv in convList"
                :key="conv.id"
                class="conv-item"
                :class="{ active: currentConv?.id === conv.id }"
                @click="selectConv(conv)"
              >
                <div class="conv-title">{{ conv.title || `对话 #${conv.id}` }}</div>
                <div class="conv-meta">
                  {{ conv.message_count }} 条消息 · {{ fromNow(conv.last_message_at || conv.created_at) }}
                </div>
              </div>
              <el-empty v-if="!convList.length" description="暂无对话记录" :image-size="32" />
            </div>
          </div>
        </div>

        <!-- 右侧：聊天窗口 -->
        <div class="chat-main">
          <div v-if="!currentConv && !selectedAgent" class="empty-chat">
            <el-empty description="选择一个 Agent 开始对话" />
          </div>
          <template v-else>
            <div class="chat-header">
              <div class="chat-title">
                <div v-if="selectedAgent" class="chat-agent-info">
                  <div class="agent-icon-sm" :style="{ background: getSceneBgColor(selectedAgent.default_scene) }">
                    <el-icon :size="20" :color="getSceneIconColor(selectedAgent.default_scene)">
                      <component :is="getSceneIcon(selectedAgent.default_scene)" />
                    </el-icon>
                  </div>
                  <span>{{ selectedAgent.name }}</span>
                  <el-tag :type="getSceneTagType(selectedAgent.default_scene)" size="small">{{ selectedAgent.scene_label }}</el-tag>
                </div>
                <div v-else-if="currentConv">
                  <span>{{ currentConv.title || `对话 #${currentConv.id}` }}</span>
                </div>
              </div>
              <el-button v-if="currentConv" link type="danger" @click="deleteConv">删除对话</el-button>
            </div>

            <el-scrollbar class="chat-messages" ref="msgScrollbar">
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
                    <div v-if="msg.token_count" class="msg-tokens">{{ msg.token_count }} tokens</div>
                  </div>
                </div>

                <div v-if="isLoading" class="message-wrapper assistant">
                  <div class="message-role">
                    <el-avatar size="32" class="avatar-assistant">AI</el-avatar>
                    <span class="role-label">AI</span>
                  </div>
                  <div class="message-bubble bubble-assistant">
                    <div class="typing-indicator">
                      <span class="typing-dot"></span>
                      <span class="typing-dot"></span>
                      <span class="typing-dot"></span>
                    </div>
                  </div>
                </div>
              </div>
            </el-scrollbar>

            <div class="chat-input-area">
              <el-input
                v-model="inputMessage"
                type="textarea"
                :rows="3"
                placeholder="输入消息..."
                :disabled="isLoading || !selectedAgent"
                @keydown.ctrl.enter="sendMessage"
              />
              <div class="input-actions">
                <span class="hint">Ctrl + Enter 发送</span>
                <el-button
                  type="primary"
                  :loading="isLoading"
                  :disabled="!inputMessage.trim() || !selectedAgent || isLoading"
                  @click="sendMessage"
                >
                  发送
                </el-button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { List, Message, Plus, MoreFilled, MagicStick, Refresh, Setting, Box, Collection } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { agentApi, conversationApi } from '@/api/ai'
import { formatDate, fromNow } from '@/utils/format'
import { tokenStorage } from '@/utils/token'
import type { AgentInfo, Conversation, ChatMessage } from '@/types'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const roleLabel: Record<string, string> = { user: '用户', assistant: 'AI', system: '系统' }

function getSceneTagType(scene: string | undefined): string {
  const map: Record<string, string> = { chitchat: 'warning', professional: 'primary', task: 'success', rag: 'danger', creative: 'info' }
  return map[scene || ''] || 'default'
}

function getSceneIcon(scene: string | undefined) {
  const map: Record<string, any> = { chitchat: Refresh, professional: Setting, task: Box, rag: Collection, creative: List }
  return map[scene || ''] || MagicStick
}

function getSceneBgColor(scene: string | undefined): string {
  const map: Record<string, string> = {
    chitchat: 'rgba(250,173,20,0.1)',
    professional: 'rgba(22,119,255,0.1)',
    task: 'rgba(82,196,26,0.1)',
    rag: 'rgba(255,77,79,0.1)',
    creative: 'rgba(144,147,153,0.1)',
  }
  return map[scene || ''] || 'rgba(22,119,255,0.1)'
}

function getSceneIconColor(scene: string | undefined): string {
  const map: Record<string, string> = {
    chitchat: '#faad14', professional: '#1677ff', task: '#52c41a', rag: '#ff4d4f', creative: '#909399',
  }
  return map[scene || ''] || '#1677ff'
}

const agentList = ref<AgentInfo[]>([])
const selectedAgent = ref<AgentInfo | null>(null)
const convList = ref<Conversation[]>([])
const convQuery = reactive({ page: 1, page_size: 20 })
const currentConv = ref<Conversation | null>(null)
const messages = ref<ChatMessage[]>([])
const msgScrollbar = ref()
const inputMessage = ref('')
const isLoading = ref(false)

async function fetchAgents() {
  const res = await agentApi.list({ page_size: 100 })
  agentList.value = res.data.items.filter(a => a.status === 1)
}

async function fetchConvList() {
  const res = await conversationApi.list(convQuery)
  convList.value = res.data.items
}

function selectAgent(agent: AgentInfo) {
  selectedAgent.value = agent
  currentConv.value = null
  messages.value = []
}

async function selectConv(conv: Conversation) {
  currentConv.value = conv
  const res = await conversationApi.messages(conv.id)
  messages.value = res.data.items || []
  nextTick(() => scrollToBottom())

  const agent = agentList.value.find(a => a.id === conv.agent_id)
  if (agent) selectedAgent.value = agent
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

function startNewChat() {
  currentConv.value = null
  messages.value = []
  inputMessage.value = ''
}

async function sendMessage() {
  const msg = inputMessage.value.trim()
  if (!msg || !selectedAgent.value || isLoading.value) return

  isLoading.value = true
  inputMessage.value = ''

  messages.value.push({
    id: Date.now(),
    conversation_id: currentConv.value?.id || 0,
    role: 'user',
    content: msg,
    created_at: new Date().toISOString(),
  })
  nextTick(() => scrollToBottom())

  try {
    const res = await fetch(`/api/v1/ai/agents/${selectedAgent.value.id}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${tokenStorage.getAccessToken()}`,
      },
      body: JSON.stringify({
        message: msg,
        stream: true,
        conversation_id: currentConv.value?.id,
      }),
    })

    const reader = res.body?.getReader()
    if (!reader) {
      ElMessage.error('无法建立连接')
      isLoading.value = false
      return
    }

    const decoder = new TextDecoder()
    const aiMsgId = Date.now() + 1
    let aiContent = ''
    let aiMsgCreated = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value, { stream: true })
      const lines = text.split('\n')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') continue

        try {
          const event = JSON.parse(data)
          if (event.type === 'meta') {
            // 后端返回新建对话的 conversation_id，更新当前对话以便后续消息复用
            if (event.conversation_id && !currentConv.value) {
              currentConv.value = {
                ...(currentConv.value || {}),
                id: event.conversation_id,
                message_count: 0,
                created_at: new Date().toISOString(),
              } as Conversation
            }
          } else if (event.type === 'content') {
            aiContent += event.text || ''
            if (!aiMsgCreated) {
              messages.value.push({
                id: aiMsgId,
                conversation_id: currentConv.value?.id || 0,
                role: 'assistant',
                content: aiContent,
                created_at: new Date().toISOString(),
              })
              aiMsgCreated = true
            } else {
              const msgIdx = messages.value.findIndex(m => m.id === aiMsgId)
              if (msgIdx !== -1) {
                messages.value[msgIdx] = { ...messages.value[msgIdx], content: aiContent }
              }
            }
            nextTick(() => scrollToBottom())
          } else if (event.type === 'done') {
            break
          } else if (event.type === 'error') {
            throw new Error(event.message || '未知错误')
          }
        } catch (e: any) {
          if (e?.message) throw e
        }
      }
    }

    fetchConvList()
  } catch (err: any) {
    ElMessage.error(err.message || '对话失败')
  } finally {
    isLoading.value = false
  }
}

function scrollToBottom() {
  const el = msgScrollbar.value?.$el?.querySelector('.el-scrollbar__wrap')
  if (el) el.scrollTop = el.scrollHeight
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

onMounted(async () => {
  await fetchAgents()
  await fetchConvList()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.page-container { height: calc(100vh - 100px); }
.h-full { height: 100%; overflow: hidden; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-shrink: 0; }
.card-title { font-size: 15px; font-weight: 600; }

.chat-layout { flex: 1; display: flex; overflow: hidden; }

.chat-sidebar { width: 280px; border-right: 1px solid $border-color; display: flex; flex-direction: column; overflow: hidden; }
.sidebar-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-bottom: 1px solid $border-color; }
.section-header { display: flex; align-items: center; gap: 6px; padding: 10px 12px; font-size: 13px; font-weight: 600; color: $text-primary; background: $bg-base; }
.agent-list, .conv-list { flex: 1; overflow-y: auto; padding: 4px; }

.agent-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background .15s; margin-bottom: 2px;
  &:hover { background: #f5f5f5; }
  &.active { background: #e6f4ff; }
  .agent-icon-sm { width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .agent-info-sm { flex: 1; min-width: 0; }
  .agent-name-sm { font-size: 13px; font-weight: 500; color: $text-primary; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .agent-scene-sm { font-size: 11px; color: $text-secondary; }
}

.conv-item { padding: 8px 10px; border-radius: 8px; cursor: pointer; margin-bottom: 2px; transition: background .15s;
  &:hover { background: #f5f5f5; }
  &.active { background: #e6f4ff; }
  .conv-title { font-size: 13px; font-weight: 500; color: $text-primary; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .conv-meta { font-size: 11px; color: $text-secondary; margin-top: 2px; }
}

.chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.empty-chat { flex: 1; display: flex; align-items: center; justify-content: center; }

.chat-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid $border-color; flex-shrink: 0; }
.chat-title { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; color: $text-primary; }
.chat-agent-info { display: flex; align-items: center; gap: 8px; }

.chat-messages { flex: 1; overflow: hidden; }
.messages { padding: 12px 16px; }

.message-wrapper { margin-bottom: 20px;
  .message-role { display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    .role-label { font-size: 13px; font-weight: 600; color: $text-primary; }
    .msg-time { font-size: 11px; color: $text-secondary; }
  }
  .message-bubble { max-width: 85%; padding: 12px 16px; border-radius: 10px; font-size: 13px; line-height: 1.7;
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

.typing-indicator { display: flex; gap: 4px; align-items: center; padding: 8px 0;
  .typing-dot { width: 6px; height: 6px; border-radius: 50%; background: $text-secondary; animation: typing 1.4s infinite ease-in-out both;
    &:nth-child(1) { animation-delay: -0.32s; }
    &:nth-child(2) { animation-delay: -0.16s; }
  }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-input-area { padding: 12px 16px; border-top: 1px solid $border-color; flex-shrink: 0; }
.input-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.hint { font-size: 12px; color: $text-secondary; }
</style>
