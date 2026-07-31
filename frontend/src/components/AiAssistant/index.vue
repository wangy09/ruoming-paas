<template>
  <div v-if="appStore.aiAssistantEnabled" class="ai-assistant">
    <!-- 浮动机器人按钮 -->
    <transition name="fade">
      <div
        v-show="!panelVisible"
        class="ai-float-btn"
        @click="togglePanel"
      >
        <div class="robot-wrapper">
          <div class="robot-glow"></div>
          <svg class="robot-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
            <!-- 天线 -->
            <line x1="32" y1="8" x2="32" y2="16" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
            <circle cx="32" cy="6" r="3" fill="#fff" class="antenna-light"/>
            
            <!-- 机器人头部 -->
            <rect x="14" y="14" width="36" height="30" rx="8" ry="8" fill="#fff"/>
            
            <!-- 脸部背景 -->
            <rect x="18" y="18" width="28" height="22" rx="5" ry="5" fill="#1a1a2e"/>
            
            <!-- 眼睛 -->
            <g class="robot-eyes">
              <circle cx="26" cy="28" r="4" fill="#4ade80" class="eye left-eye"/>
              <circle cx="38" cy="28" r="4" fill="#4ade80" class="eye right-eye"/>
              <circle cx="26" cy="28" r="2" fill="#fff" class="eye-shine left-shine"/>
              <circle cx="38" cy="28" r="2" fill="#fff" class="eye-shine right-shine"/>
            </g>
            
            <!-- 嘴巴/微笑 -->
            <path d="M 28 36 Q 32 40 36 36" stroke="#4ade80" stroke-width="2" fill="none" stroke-linecap="round"/>
            
            <!-- 身体 -->
            <rect x="20" y="44" width="24" height="12" rx="4" ry="4" fill="#fff" opacity="0.9"/>
            
            <!-- 胸口灯 -->
            <circle cx="32" cy="50" r="3" fill="#fbbf24" class="chest-light"/>
          </svg>
        </div>
        <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
        <div class="robot-label">AI 助手</div>
      </div>
    </transition>

    <!-- 对话面板 -->
    <transition name="slide-fade">
      <div v-show="panelVisible" class="ai-panel">
        <div class="panel-header">
          <div class="header-left">
            <div class="ai-avatar">
              <svg viewBox="0 0 48 48" width="24" height="24" xmlns="http://www.w3.org/2000/svg">
                <line x1="24" y1="6" x2="24" y2="12" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
                <circle cx="24" cy="5" r="2" fill="#fff"/>
                <rect x="10" y="10" width="28" height="22" rx="6" ry="6" fill="#fff"/>
                <rect x="13" y="13" width="22" height="16" rx="3" ry="3" fill="#1a1a2e"/>
                <circle cx="20" cy="21" r="2.5" fill="#4ade80"/>
                <circle cx="28" cy="21" r="2.5" fill="#4ade80"/>
                <circle cx="20" cy="21" r="1.2" fill="#fff"/>
                <circle cx="28" cy="21" r="1.2" fill="#fff"/>
                <path d="M 21 26 Q 24 29 27 26" stroke="#4ade80" stroke-width="1.5" fill="none" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="ai-info">
              <div class="ai-name">AI 智能助手</div>
              <div class="ai-status">
                <span class="status-dot"></span>
                在线服务中
              </div>
            </div>
          </div>
          <div class="header-actions">
            <el-tooltip content="刷新">
              <el-icon class="action-icon" @click="handleRefresh">
                <Refresh />
              </el-icon>
            </el-tooltip>
            <el-tooltip content="关闭">
              <el-icon class="action-icon" @click="togglePanel">
                <Close />
              </el-icon>
            </el-tooltip>
          </div>
        </div>

        <div class="panel-quick-actions">
          <div
            v-for="action in quickActions"
            :key="action.key"
            class="quick-action"
            @click="handleQuickAction(action)"
          >
            <el-icon :size="16">
              <component :is="action.icon" />
            </el-icon>
            <span>{{ action.label }}</span>
          </div>
        </div>

        <el-scrollbar class="panel-messages" ref="msgScrollbar">
          <div class="messages-wrapper">
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="message-item"
              :class="msg.role"
            >
              <div class="msg-avatar" :class="msg.role">
                {{ msg.role === 'user' ? '我' : 'AI' }}
              </div>
              <div class="msg-content">
                <div class="msg-bubble" :class="msg.role">
                  <div v-html="renderMarkdown(msg.content)" />
                  <div v-if="msg.action && msg.action.type === 'navigate' && msg.action.path" class="msg-action">
                    <el-button
                      type="primary"
                      size="small"
                      :icon="Guide"
                      @click="handleNavigate(msg.action.path!)"
                    >
                      前往 {{ msg.action.label || msg.action.path }}
                    </el-button>
                  </div>
                </div>
                <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>

            <div v-if="isLoading" class="message-item assistant">
              <div class="msg-avatar assistant">AI</div>
              <div class="msg-content">
                <div class="msg-bubble assistant">
                  <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-scrollbar>

        <div class="panel-input-wrapper">
          <div class="panel-input">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="2"
              placeholder="输入消息，如：帮我打开用户管理"
              :disabled="isLoading"
              resize="none"
              @keydown.ctrl.enter.prevent="sendMessage"
            />
            <el-button
              type="primary"
              :loading="isLoading"
              :disabled="!inputMessage.trim() || isLoading"
              @click="sendMessage"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="panel-footer-actions">
            <el-tooltip content="问题反馈">
              <el-icon class="footer-action" @click="openFeedback">
                <Warning />
              </el-icon>
            </el-tooltip>
            <el-tooltip content="使用文档">
              <el-icon class="footer-action" @click="navigateToManual">
                <Reading />
              </el-icon>
            </el-tooltip>
          </div>
        </div>
      </div>
    </transition>

    <!-- 反馈弹窗 -->
    <FeedbackDialog
      v-model:visible="feedbackVisible"
      @success="handleFeedbackSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close, Refresh, Promotion, Guide, QuestionFilled, Menu, Warning, Reading } from '@element-plus/icons-vue'
import { createEnhancedMd, setupCodeBlockHandlers } from '@/utils/markdown'
import { useAppStore } from '@/store/app'
import { usePermissionStore } from '@/store/permission'
import { useAuthStore } from '@/store/auth'
import { agentApi } from '@/api/ai'
import { tokenStorage } from '@/utils/token'
import FeedbackDialog from './FeedbackDialog.vue'
import type { MenuPermission } from '@/types'

const md = createEnhancedMd()
const appStore = useAppStore()
const permStore = usePermissionStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const panelVisible = ref(false)
const inputMessage = ref('')
const isLoading = ref(false)
const msgScrollbar = ref()
// 消息项类型
interface MessageItem {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: Date
  action?: { type: string; path?: string; label?: string }
}
const messages = ref<MessageItem[]>([])
const unreadCount = ref(0)

interface NavRoute {
  path: string
  label: string
  keywords: string[]
}

// 所有可能的路由映射（权限过滤后使用）
const allNavRoutes: NavRoute[] = [
  { path: '/dashboard', label: '工作台', keywords: ['工作台', '首页', 'dashboard', 'home'] },
  { path: '/system/users', label: '用户管理', keywords: ['用户管理', '用户', '账号', '成员', 'user'] },
  { path: '/system/depts', label: '部门管理', keywords: ['部门管理', '部门', '组织架构', 'dept'] },
  { path: '/system/roles', label: '角色管理', keywords: ['角色管理', '角色', 'role'] },
  { path: '/system/role-permission', label: '角色授权', keywords: ['角色授权', '分配权限', '授权'] },
  { path: '/system/permissions', label: '权限管理', keywords: ['权限管理', '权限', 'permission'] },
  { path: '/system/dicts', label: '字典管理', keywords: ['字典管理', '字典', 'dict'] },
  { path: '/system/config', label: '系统配置', keywords: ['系统配置', '配置', 'config'] },
  { path: '/system/integrations', label: '集成中心', keywords: ['集成中心', '集成', 'integration'] },
  { path: '/system/files', label: '文件管理', keywords: ['文件管理', '文件', '附件'] },
  { path: '/audit/logs', label: '审计日志', keywords: ['审计日志', '审计', '操作日志', 'log'] },
  { path: '/audit/login-logs', label: '登录日志', keywords: ['登录日志', '登录记录'] },
  { path: '/message/notices', label: '通知管理', keywords: ['通知管理', '通知', '公告', 'notice'] },
  { path: '/message/inbox', label: '我的消息', keywords: ['我的消息', '消息', '收件箱', 'inbox'] },
  { path: '/dev/codegen', label: '代码生成', keywords: ['代码生成', '生成代码', 'codegen'] },
  { path: '/ai/chat', label: 'AI对话', keywords: ['ai对话', '对话', 'chat', '聊天'] },
  { path: '/ai/models', label: '模型管理', keywords: ['模型管理', '模型', 'model'] },
  { path: '/ai/agents', label: 'Agent管理', keywords: ['agent', '智能体', '助手'] },
  { path: '/ai/knowledge', label: '知识库', keywords: ['知识库', '知识', 'knowledge'] },
  { path: '/ai/conversations', label: '对话历史', keywords: ['对话历史', '历史对话', '历史'] },
  { path: '/ai/prompts', label: '提示词', keywords: ['提示词', 'prompt'] },
  { path: '/ai/tools', label: '工具管理', keywords: ['工具管理', '工具', 'tool'] },
  { path: '/monitor/server', label: '服务器监控', keywords: ['服务器监控', '服务器', 'server'] },
  { path: '/monitor/task', label: '任务监控', keywords: ['任务监控', '任务', 'task'] },
  { path: '/monitor/circuit', label: '熔断监控', keywords: ['熔断监控', '熔断', 'circuit'] },
  { path: '/help/manual', label: '使用文档', keywords: ['使用文档', '文档', '帮助', 'help', 'manual'] },
  { path: '/ai/feedback', label: '反馈管理', keywords: ['反馈', 'feedback'] },
]

// 根据用户权限过滤后的可用路由
const navRouteMap = computed<NavRoute[]>(() => {
  const userMenuPaths = new Set<string>()
  collectMenuPaths(permStore.menuTree, userMenuPaths)
  // 如果没有权限数据，返回所有路由（开发/演示模式）
  if (userMenuPaths.size === 0) return allNavRoutes
  // 过滤出用户有权限的路由
  return allNavRoutes.filter(r => userMenuPaths.has(r.path))
})

// 收集菜单路径
function collectMenuPaths(menus: MenuPermission[], paths: Set<string>) {
  for (const menu of menus) {
    if (menu.path && menu.isVisible) {
      paths.add(menu.path)
    }
    if (menu.children?.length) {
      collectMenuPaths(menu.children, paths)
    }
  }
}

interface QuickAction {
  key: string
  label: string
  icon: any
  message: string
  action?: 'quick-nav' | 'send'
  targetPath?: string
}

// 动态生成快速导航按钮
const quickActions = computed<QuickAction[]>(() => {
  const actions: QuickAction[] = []
  const availableRoutes = navRouteMap.value

  // 添加动态快捷入口（取前3个有权限的常用页面）
  const commonPages = ['/dashboard', '/message/inbox', '/ai/chat', '/system/users', '/monitor/task']
  for (const path of commonPages) {
    const route = availableRoutes.find(r => r.path === path)
    if (route && actions.length < 3) {
      actions.push({
        key: `nav-${route.path}`,
        label: route.label,
        icon: Guide,
        message: `打开${route.label}`,
        action: 'quick-nav',
        targetPath: route.path,
      })
    }
  }

  // 如果有权限的页面不够3个，补充功能按钮
  if (actions.length < 3) {
    actions.push(
      { key: 'help', label: '使用帮助', icon: QuestionFilled, message: '如何使用系统？', action: 'send' },
    )
  }

  // 确保至少有2个按钮
  if (actions.length < 2) {
    actions.push(
      { key: 'search', label: '功能列表', icon: Menu, message: '我有哪些可用功能？', action: 'send' },
    )
  }

  return actions
})

const currentAgentId = ref<number | null>(null)

async function loadDefaultAgent() {
  try {
    // 等待配置加载完成
    if (!appStore.publicConfigLoaded) {
      console.log('[AI Assistant] Waiting for public config to load...')
      await appStore.loadPublicConfig()
    }

    // 优先使用配置中心的 agent_id（Pinia 自动解包 ref，直接读取数值）
    const configAgentId = appStore.aiAssistantAgentId
    if (configAgentId && Number(configAgentId) > 0) {
      currentAgentId.value = Number(configAgentId)
      console.log('[AI Assistant] Using config agent_id:', currentAgentId.value)
      return
    }

    // 如果配置了 agent_id 但值为空，跳过兜底逻辑（表示用户明确不想用默认 Agent）
    // 只有当配置项不存在时才使用兜底
    console.log('[AI Assistant] No config agent_id set, fetching agents list for fallback...')
    const res = await agentApi.list({ page_size: 100 })
    const agents = res.data.items.filter((a: any) => a.status === 1)
    if (agents.length > 0) {
      currentAgentId.value = agents[0].id
      console.log('[AI Assistant] Using first available agent:', currentAgentId.value)
    } else {
      console.log('[AI Assistant] No available agents found')
    }
  } catch (e) {
    console.warn('[AI Assistant] Failed to load agent:', e)
  }
}

// 监听配置变化，自动更新 Agent ID（Pinia 自动解包 ref，newId 即 number | null）
watch(() => appStore.aiAssistantAgentId, (newId) => {
  if (newId && Number(newId) > 0 && (!currentAgentId.value || currentAgentId.value !== Number(newId))) {
    currentAgentId.value = Number(newId)
    console.log('[AI Assistant] Agent ID updated from config:', currentAgentId.value)
  }
}, { immediate: true })

function togglePanel() {
  panelVisible.value = !panelVisible.value
  if (panelVisible.value && messages.value.length === 0) {
    initWelcomeMessage()
  }
}

function initWelcomeMessage() {
  const welcome = appStore.aiAssistantWelcome || '你好！我是 AI 助手，可以帮您导航页面、回答问题。'
  messages.value.push({
    id: Date.now(),
    role: 'assistant',
    content: welcome,
    created_at: new Date(),
  })
  scrollToBottom()
}

function handleQuickAction(action: QuickAction) {
  if (action.action === 'quick-nav' && action.targetPath) {
    // 直接导航到目标页面，同时显示一条消息
    const targetRoute = navRouteMap.value.find(r => r.path === action.targetPath)
    messages.value.push({
      id: Date.now(),
      role: 'user',
      content: `打开${targetRoute?.label || action.targetPath}`,
      created_at: new Date(),
    })
    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      content: `好的，正在为您打开「${targetRoute?.label || action.targetPath}」页面。`,
      created_at: new Date(),
      action: { type: 'navigate', path: action.targetPath, label: targetRoute?.label },
    })
    scrollToBottom()
  } else {
    inputMessage.value = action.message
    sendMessage()
  }
}

function handleRefresh() {
  messages.value = []
  initWelcomeMessage()
}

function renderMarkdown(content: string) {
  return md.render(content || '')
}

function formatTime(date: Date) {
  const d = new Date(date)
  const h = d.getHours().toString().padStart(2, '0')
  const m = d.getMinutes().toString().padStart(2, '0')
  return `${h}:${m}`
}

function scrollToBottom() {
  nextTick(() => {
    const el = msgScrollbar.value?.$el?.querySelector('.el-scrollbar__wrap')
    if (el) el.scrollTop = el.scrollHeight
  })
}

function findRouteByLabel(label: string): NavRoute | undefined {
  return navRouteMap.value.find(r => r.label === label)
}

function parseAIResponse(content: string): { text: string; action?: { type: string; path?: string; label?: string } } {
  // 尝试解析导航指令
  const navMatch = content.match(/打开\s*[「""](.+?)[」""]/) || content.match(/导航到\s*[「""](.+?)[」""]/)
  if (navMatch) {
    const targetName = navMatch[1]
    const route = findRouteByLabel(targetName)
    if (route) {
      return {
        text: `好的，正在为您打开「${targetName}」`,
        action: { type: 'navigate', path: route.path, label: targetName },
      }
    }
  }

  // 检查是否包含路径
  const pathMatch = content.match(/path[:：]\s*(\/\S+)/i)
  if (pathMatch) {
    return {
      text: '正在为您导航...',
      action: { type: 'navigate', path: pathMatch[1] },
    }
  }

  return { text: content }
}

async function sendMessage() {
  const msg = inputMessage.value.trim()
  if (!msg || isLoading.value) return

  isLoading.value = true
  inputMessage.value = ''

  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: msg,
    created_at: new Date(),
  })
  scrollToBottom()

  try {
    // 检查是否直接匹配导航
    const matchedRoute = matchDirectNavigation(msg)
    if (matchedRoute) {
      await simulateNavResponse(matchedRoute.label, matchedRoute.path, matchedRoute.label)
      return
    }

    // 调用 AI Agent
    if (currentAgentId.value) {
      await callAgent(msg)
    } else {
      // 无 Agent 时使用简单响应
      await simulateResponse(msg)
    }
  } catch (err: any) {
    messages.value.push({
      id: Date.now(),
      role: 'assistant',
      content: `抱歉，出现了错误：${err.message || '未知错误'}`,
      created_at: new Date(),
    })
    scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

// 导航意图关键词：用户需要明确表达"要去哪里"
const NAV_INTENT_KEYWORDS = ['打开', '进入', '去', '跳转', '跳到', '导航到', '前往', '启动', '查看']

function matchDirectNavigation(msg: string): NavRoute | null {
  const normalized = msg.toLowerCase()
  
  // 检查是否有明确的导航意图
  const hasNavIntent = NAV_INTENT_KEYWORDS.some(kw => msg.includes(kw))
  if (!hasNavIntent) return null  // 没有导航意图，交给 AI Agent 处理
  
  // 检查是否匹配到具体页面
  for (const route of navRouteMap.value) {
    for (const keyword of route.keywords) {
      if (normalized.includes(keyword.toLowerCase())) {
        return route
      }
    }
  }
  return null
}

async function simulateNavResponse(targetName: string, path: string, label: string) {
  await delay(500)
  messages.value.push({
    id: Date.now(),
    role: 'assistant',
    content: `好的，正在为您打开「${targetName}」页面，点击下方按钮可直接跳转。`,
    created_at: new Date(),
    action: { type: 'navigate', path, label: targetName },
  })
  scrollToBottom()
}

async function simulateResponse(msg: string) {
  await delay(600)
  let reply = ''
  const modules = [...new Set(navRouteMap.value.map(r => r.keywords[0]))]
  
  if (msg.includes('你好') || msg.includes('hi') || msg.includes('hello')) {
    reply = '你好！我是 AI 助手 🤖，可以帮您：\n- 🧭 快速导航到任何页面（如"打开用户管理"）\n- 💡 回答系统使用问题\n- 🚀 提供操作指引和建议\n\n> ⚠️ 当前未绑定 AI Agent，部分功能受限。请在「系统管理 → 配置中心」中设置 AI Agent ID。'
  } else if (msg.includes('功能') || msg.includes('有什么') || msg.includes('介绍') || msg.includes('概述') || msg.includes('是啥') || msg.includes('是什么')) {
    reply = `## 若茗 PaaS 系统功能概览\n\n**一、系统管理**\n${modules.filter(m => ['用户', '部门', '角色', '权限', '字典', '配置'].some(k => m.includes(k))).map(m => `- ${m}`).join('\n')}\n\n**二、AI 智能**\n- AI 对话、模型管理、Agent 管理、知识库、工具管理\n\n**三、开发工具**\n- 代码生成器\n\n**四、运维监控**\n- 服务器监控、任务监控\n\n> 💡 绑定 AI Agent 后，我可以基于知识库回答更详细的系统问题哦！`
  } else if (msg.includes('怎么') || msg.includes('如何') || msg.includes('使用') || msg.includes('教程')) {
    reply = '关于使用问题，您可以：\n1. 📖 打开「使用文档」查看详细教程\n2. 🤖 绑定 AI Agent 后直接问我，我会基于知识库回答\n3. 🧭 告诉我想做什么，我帮您导航\n\n例如："打开用户管理"、"如何创建用户"'
  } else if (msg.includes('模型') || msg.includes('ai') || msg.includes('智能')) {
    reply = '本系统支持多种 AI 能力：\n- 🤖 AI 对话：与 AI 进行自然语言交互\n- 📚 知识库：上传文档，AI 基于知识回答\n- 🧠 Agent：创建自定义智能体\n- 🔧 代码生成：自动生成 CRUD 代码\n\n前往「AI 管理」查看更多功能'
  } else {
    const topModules = navRouteMap.value.slice(0, 8).map(r => r.label).join('、')
    reply = `我暂时还在学习中 📚\n\n您可以尝试：\n- "打开用户管理" - 导航到指定页面\n- "介绍系统" - 了解系统功能\n- "如何使用" - 获取使用帮助\n\n> 💡 配置 AI Agent 后，我可以基于知识库回答您的问题。当前可用功能：${topModules}等。`
  }
  messages.value.push({
    id: Date.now(),
    role: 'assistant',
    content: reply,
    created_at: new Date(),
  })
  scrollToBottom()
}

async function callAgent(msg: string, retryWithNewToken = false) {
  const agentId = currentAgentId.value
  console.log('[AI Assistant] Calling agent:', agentId, 'message:', msg)
  
  try {
    const accessToken = tokenStorage.getAccessToken()
    const res = await fetch(`/api/v1/ai/agents/${agentId}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        message: msg,
        stream: true,
      }),
    })

    console.log('[AI Assistant] Response status:', res.status, 'ok:', res.ok)

    // Token 过期时，刷新 Token 后重试（仅重试一次）
    if (res.status === 401 && !retryWithNewToken) {
      console.log('[AI Assistant] Token expired, refreshing...')
      try {
        await authStore.refreshToken()
        console.log('[AI Assistant] Token refreshed, retrying...')
        return await callAgent(msg, true)  // 使用新 Token 重试
      } catch (refreshErr) {
        console.error('[AI Assistant] Token refresh failed:', refreshErr)
        // 刷新失败，跳转到登录页
        ElMessage.error('登录已过期，请重新登录')
        authStore.clear()
        router.push('/login')
        return
      }
    }

    if (!res.ok) {
      const errorText = await res.text()
      console.error('[AI Assistant] API error:', res.status, errorText)
      throw new Error(`HTTP ${res.status}: ${errorText}`)
    }

    const reader = res.body?.getReader()
    if (!reader) {
      console.warn('[AI Assistant] No reader in response body')
      throw new Error('Response body is not readable')
    }

    const decoder = new TextDecoder()
    let aiContent = ''
    let aiMsgCreated = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        console.log('[AI Assistant] Stream done, total content length:', aiContent.length)
        break
      }

      const text = decoder.decode(value, { stream: true })
      const lines = text.split('\n')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') continue

        try {
          const event = JSON.parse(data)
          console.log('[AI Assistant] Event type:', event.type)
          
          if (event.type === 'content') {
            aiContent += event.text || ''
            if (!aiMsgCreated) {
              const parsed = parseAIResponse(aiContent)
              messages.value.push({
                id: Date.now(),
                role: 'assistant',
                content: parsed.text,
                created_at: new Date(),
                action: parsed.action,
              })
              aiMsgCreated = true
            } else {
              const idx = messages.value.length - 1
              if (idx >= 0) {
                const parsed = parseAIResponse(aiContent)
                messages.value[idx] = {
                  ...messages.value[idx],
                  content: parsed.text,
                  action: parsed.action,
                }
              }
            }
            scrollToBottom()
          } else if (event.type === 'error') {
            throw new Error(event.message || '未知错误')
          } else if (event.type === 'meta') {
            console.log('[AI Assistant] Meta:', event)
          }
        } catch (e: any) {
          if (e?.message) throw e
        }
      }
    }
  } catch (err: any) {
    console.error('[AI Assistant] callAgent failed:', err?.message || err)
    // 如果是因为 Token 过期被处理过，不再调用 simulateResponse
    if (retryWithNewToken && err?.message?.includes('401')) {
      return  // 已经重试过还是失败，不再显示模拟响应
    }
    // Agent 调用失败时使用模拟响应
    await simulateResponse(msg)
  }
}

function handleNavigate(path: string) {
  panelVisible.value = false
  ElMessage.success('已在新标签页打开')
  router.push(path)
}

// ── 系统反馈 ──────────────────────────────────────────────────────────────────
const feedbackVisible = ref(false)

// 打开反馈弹窗
function openFeedback() {
  feedbackVisible.value = true
}

// 跳转到使用文档
function navigateToManual() {
  const route = navRouteMap.value.find(r => r.path === '/help/manual')
  if (route) {
    navigateToRoute(route)
  } else {
    ElMessage.info('使用文档暂未开放')
  }
}

// 反馈提交成功回调
function handleFeedbackSuccess() {
  ElMessage.success('反馈已提交，感谢您的建议！')
}

function navigateToRoute(route: NavRoute) {
  panelVisible.value = false
  ElMessage.success(`正在跳转到「${route.label}」`)
  router.push(route.path)
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

onMounted(() => {
  loadDefaultAgent()
  // 初始化代码块工具栏（复制/下载）事件委托
  setupCodeBlockHandlers('.ai-panel')
})

// 监听路由变化，自动关闭面板
watch(() => route.path, () => {
  panelVisible.value = false
})
</script>

<style lang="scss" scoped>
.ai-assistant {
  position: fixed;
  right: 24px;
  bottom: 80px;
  z-index: 9999;
}

.ai-float-btn {
  width: 64px;
  height: 64px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;

  &:hover {
    .robot-wrapper {
      transform: scale(1.25) translateY(-10px) rotate(-5deg);
      animation-play-state: paused;
      
      .robot-svg {
        filter: drop-shadow(0 8px 24px rgba(102, 126, 234, 0.6)) 
                drop-shadow(0 0 20px rgba(74, 222, 128, 0.4));
        
        .eye {
          r: 5.5;
        }
        
        .chest-light {
          fill: #4ade80;
          animation-duration: 0.5s;
        }
      }
    }
    
    .robot-glow {
      opacity: 1;
      transform: translate(-50%, -50%) scale(1.8);
      background: radial-gradient(circle, rgba(102, 126, 234, 0.5) 0%, rgba(74, 222, 128, 0.3) 40%, transparent 70%);
    }
    
    .robot-label {
      opacity: 1;
      transform: translateX(-50%) translateY(-12px) scale(1.1);
      box-shadow: 0 4px 16px rgba(102, 126, 234, 0.5);
    }
  }

  .robot-wrapper {
    position: relative;
    width: 60px;
    height: 60px;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    animation: float 3s ease-in-out infinite;
  }

  .robot-glow {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 70px;
    height: 70px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(102, 126, 234, 0.4) 0%, transparent 70%);
    opacity: 0.6;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    animation: pulse 2s ease-in-out infinite;
    z-index: -1;
  }

  .robot-svg {
    width: 100%;
    height: 100%;
    transition: filter 0.3s ease;
    filter: drop-shadow(0 4px 12px rgba(102, 126, 234, 0.4));
    
    .eye {
      transition: r 0.3s ease;
      r: 4;
    }
    
    .eye-shine {
      animation: shine 2s ease-in-out infinite;
    }
    
    .chest-light {
      transition: fill 0.3s ease, animation-duration 0.3s ease;
      animation: blink 1.5s ease-in-out infinite;
    }
    
    .antenna-light {
      animation: blink 1s ease-in-out infinite;
    }
  }

  .robot-label {
    position: absolute;
    bottom: -24px;
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
    white-space: nowrap;
    opacity: 0;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    pointer-events: none;
    
    &::before {
      content: '';
      position: absolute;
      top: -4px;
      left: 50%;
      transform: translateX(-50%) rotate(45deg);
      width: 8px;
      height: 8px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
  }

  .badge {
    position: absolute;
    top: -4px;
    right: -8px;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(255, 107, 107, 0.4);
    animation: badge-bounce 0.5s ease-out;
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-6px);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.15);
    opacity: 0.4;
  }
}

@keyframes shine {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(0.8);
  }
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

@keyframes badge-bounce {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
  }
}

.ai-panel {
  width: 380px;
  height: 520px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e8e8e8;
}

.panel-header {
  padding: 14px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .ai-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .ai-info {
    color: #fff;

    .ai-name {
      font-size: 14px;
      font-weight: 600;
    }

    .ai-status {
      font-size: 12px;
      opacity: 0.9;
      display: flex;
      align-items: center;
      gap: 4px;

      .status-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #52c41a;
        display: inline-block;
      }
    }
  }

  .header-actions {
    display: flex;
    gap: 12px;

    .action-icon {
      font-size: 18px;
      color: rgba(255, 255, 255, 0.85);
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: #fff;
      }
    }
  }
}

.panel-quick-actions {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;

  .quick-action {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 8px 6px;
    background: #fff;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 12px;
    color: #666;

    &:hover {
      border-color: #667eea;
      color: #667eea;
      background: #f5f7ff;
    }
  }
}

.panel-messages {
  flex: 1;
  overflow: hidden;

  .messages-wrapper {
    padding: 12px;
  }
}

.message-item {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;

  &.user {
    flex-direction: row-reverse;

    .msg-content {
      align-items: flex-end;
    }

    .msg-bubble {
      background: #e6f4ff;
      border-color: #91caff;
    }
  }

  &.assistant {
    .msg-bubble {
      background: #f6ffed;
      border-color: #b7eb8f;
    }
  }

  .msg-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;

    &.user {
      background: #667eea;
      color: #fff;
    }

    &.assistant {
      background: #52c41a;
      color: #fff;
    }
  }

  .msg-content {
    max-width: calc(100% - 44px);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .msg-bubble {
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid;
    font-size: 13px;
    line-height: 1.6;
    word-break: break-word;

    :deep(pre) {
      background: #f5f5f5;
      padding: 6px;
      border-radius: 4px;
      overflow: auto;
      font-size: 12px;
    }

    :deep(code) {
      background: #f5f5f5;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 12px;
    }

    :deep(p) {
      margin-bottom: 4px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    // 代码块工具栏（复制 / 下载）
    :deep(.code-block-wrapper) {
      margin: 6px 0;
      border: 1px solid #3a3a3a;
      border-radius: 6px;
      overflow: hidden;
      background: #1e1e1e;

      .code-block-toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 10px;
        background: #2d2d2d;
        border-bottom: 1px solid #3a3a3a;

        .code-lang {
          font-size: 11px;
          color: #bbb;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .code-btn {
          padding: 2px 8px;
          font-size: 11px;
          color: #ddd;
          background: #3a3a3a;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.2s;

          &:hover {
            background: #4a4a4a;
            color: #fff;
          }

          &.code-download {
            margin-left: auto;
          }
        }
      }

      pre {
        margin: 0;
        background: #1e1e1e;
        padding: 10px;
        border-radius: 0;

        code {
          background: transparent;
          color: #d4d4d4;
          padding: 0;
        }
      }
    }
  }

  .msg-action {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed #e8e8e8;
  }

  .msg-time {
    font-size: 11px;
    color: #999;
  }
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;

  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #999;
    animation: typing 1.4s infinite ease-in-out both;

    &:nth-child(1) {
      animation-delay: -0.32s;
    }

    &:nth-child(2) {
      animation-delay: -0.16s;
    }
  }
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

.panel-input-wrapper {
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-input {
  padding: 10px 12px;
  display: flex;
  gap: 8px;
  align-items: flex-end;

  :deep(.el-textarea__inner) {
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
  }

  .el-button {
    height: 40px;
    border-radius: 8px;
  }
}

.panel-footer-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 4px 12px 8px;
  border-top: 1px solid #f5f5f5;

  .footer-action {
    font-size: 16px;
    color: #909399;
    cursor: pointer;
    transition: color 0.2s ease;

    &:hover {
      color: #409eff;
    }
  }
}

// 动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
</style>
