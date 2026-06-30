// ── 通用 API 响应结构 ──────────────────────────────────────────────────────────
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  trace_id?: string
}

export interface PageData<T = unknown> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ── 消息中心 ────────────────────────────────────────────────────────────────────
export type NoticeTargetType = 'all' | 'dept' | 'user'

export interface NoticeInfo {
  id: number
  title: string
  content: string
  notice_type: string
  target_type: NoticeTargetType
  target_dept_ids?: number[] | null
  target_user_ids?: number[] | null
  status: 0 | 1
  publisher_id?: number | null
  published_at?: string | null
  receiver_count: number
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface NoticeCreate {
  title: string
  content: string
  target_type: NoticeTargetType
  target_dept_ids?: number[]
  target_user_ids?: number[]
  remark?: string
  publish_now?: boolean
}

export type NoticeUpdate = Partial<Omit<NoticeCreate, 'publish_now'>>

export interface MessageInfo {
  id: number
  notice_id?: number | null
  user_id: number
  sender_id?: number | null
  title: string
  content: string
  message_type: string
  is_read: boolean
  read_at?: string | null
  created_at: string
}

export interface MessageUnreadSummary {
  unread_count: number
  latest?: MessageInfo | null
}

// ── 用户相关 ────────────────────────────────────────────────────────────────────
export interface UserInfo {
  id: number
  username: string
  nickname?: string
  email?: string
  phone?: string
  avatar?: string
  is_active: boolean
  is_superplatform: boolean
  tenant_id: number
  tenant_code?: string
  roles: RoleInfo[]
  created_at: string
  locked_until?: string
}

export interface LoginRequest {
  username: string
  password: string
  tenant_code?: string
  captcha_key?: string
  captcha_code?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

export interface UserListItem {
  id: number
  username: string
  nickname?: string
  email?: string
  phone?: string
  is_active: boolean
  is_superplatform: boolean
  tenant_id: number
  dept_id?: number
  dept_name?: string
  roles: RoleInfo[]
  created_at: string
  login_fail_count: number
  locked_until?: string
}

export interface UserCreate {
  username: string
  password: string
  nickname?: string
  email?: string
  phone?: string
  tenant_id?: number
  role_ids?: number[]
}

export interface UserUpdate {
  nickname?: string
  email?: string
  phone?: string
  is_active?: boolean
}

// ── 角色权限 ────────────────────────────────────────────────────────────────────
export interface RoleInfo {
  id: number
  name: string
  code: string
  description?: string
  parent_id?: number
  data_scope: number
  data_scope_depts?: string | null
  is_system: boolean
  created_at: string
}

export interface RoleCreate {
  name: string
  code: string
  description?: string
  parent_id?: number
  data_scope?: number
  data_scope_depts?: number[]
}

// ── 部门管理 ────────────────────────────────────────────────────────────────────
export interface DeptInfo {
  id: number
  parent_id: number
  name: string
  ancestors: string | null
  level: number
  sort: number
  leader: string | null
  phone: string | null
  email: string | null
  status: number
  tenant_id: number | null
  children?: DeptInfo[]
  remark: string | null
}

export interface PermissionItem {
  id: number
  name: string
  code: string
  type: 'menu' | 'button' | 'column' | 'api' | 'data'
  parent_id?: number
  icon?: string
  path?: string
  component?: string
  sort_order: number
  is_system: boolean
  children?: PermissionItem[]
}

export interface MenuPermission {
  id: number
  title: string
  path: string
  component: string
  icon?: string
  children?: MenuPermission[]
  permissionCode?: string
  keepAlive?: boolean
}

export interface UserPermissions {
  codes: string[]
  buttons: string[]
  menus: MenuPermission[]
  columns: Record<string, string[]>
}

// ── 租户相关 ────────────────────────────────────────────────────────────────────
export interface TenantInfo {
  id: number
  name: string
  code: string
  status: 'active' | 'inactive' | 'suspended'
  plan: 'basic' | 'pro' | 'enterprise'
  max_users: number
  max_storage_mb: number
  max_api_calls_per_day: number
  max_ai_tokens_per_day: number
  current_users?: number
  contact_email?: string
  created_at: string
}

// ── AI 模型管理 ────────────────────────────────────────────────────────────────
export interface AiModelConfig {
  id: number
  name: string
  provider: string
  model_id: string
  base_url?: string
  is_default: boolean
  is_embed: boolean
  is_rerank: boolean
  is_fallback: boolean
  max_tokens: number
  context_length: number
  status: number
  tenant_id?: number
  created_at: string
  has_api_key: boolean
}

export interface AiModelCreate {
  name: string
  provider: string
  model_id: string
  base_url?: string
  api_key?: string
  max_tokens?: number
  context_length?: number
  is_default?: boolean
  is_embed?: boolean
  is_rerank?: boolean
  status?: number
}

// ── Agent 相关 ────────────────────────────────────────────────────────────────
export interface AgentInfo {
  id: number
  name: string
  description?: string
  default_scene?: 'chitchat' | 'professional' | 'task' | 'rag' | 'creative'
  scene_label?: string
  model_config_id?: number
  model_name?: string
  system_prompt?: string
  tool_ids: number[]
  tool_count?: number
  kb_ids: number[]
  kb_count?: number
  max_rounds: number
  temperature: number
  max_tokens: number
  memory_type: 'buffer' | 'summary' | 'vector'
  memory_label?: string
  node_timeout_sec: number
  status: number
  tenant_id?: number
  created_at: string
}

// ── 知识库 ────────────────────────────────────────────────────────────────────
export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  embed_model_id?: number
  chunk_size: number
  chunk_overlap: number
  doc_count: number
  chunk_count: number
  status: 'ready' | 'processing' | 'error'
  created_at: string
}

export interface KnowledgeDoc {
  id: number
  kb_id: number
  name: string
  file_type: string
  file_size: number
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  chunk_count: number
  error_msg?: string
  created_at: string
}

// ── 对话历史 ────────────────────────────────────────────────────────────────────
export interface Conversation {
  id: number
  title?: string
  agent_id?: number
  message_count: number
  last_message_at?: string
  created_at: string
}

export interface ChatMessage {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  token_count?: number
  created_at: string
}

// ── 审计日志 ────────────────────────────────────────────────────────────────────
export interface AuditLog {
  id: number
  user_id?: number
  username?: string
  tenant_id?: number
  action: string
  resource_type: string
  resource_id?: string
  before_data?: Record<string, unknown>
  after_data?: Record<string, unknown>
  ip_address?: string
  status: 'success' | 'fail'
  created_at: string
}

export interface LoginLog {
  id: number
  user_id: number
  username: string
  ip_address?: string
  user_agent?: string
  status: 'success' | 'fail' | 'locked'
  fail_reason?: string
  created_at: string
}

// ── 工具 ────────────────────────────────────────────────────────────────────
export interface ToolInfo {
  tool_id: string
  name: string
  description: string
  tool_type?: string   // builtin | api | custom
  db_id?: number       // 自定义工具的数据库 ID
  status?: number
  url?: string | null
  method?: string | null
  headers?: Record<string, string>
}

export interface CustomToolDetail {
  id: number
  name: string
  description: string | null
  tool_type: string
  url: string | null
  method: string | null
  headers: Record<string, string>
  status: number
}

// ── Prompt 版本 ────────────────────────────────────────────────────────────────
export interface PromptVersion {
  id: number
  template_id: number
  version: number
  content: string
  variables: string[]
  changelog?: string
  is_published: boolean
  created_at: string
}

// ── Prompt 模板 ────────────────────────────────────────────────────────────────
export interface PromptTemplate {
  id: number
  name: string
  description?: string
  category?: string
  content: string
  variables: string[]
  status: 'draft' | 'published' | 'archived'
  current_version: number
  created_at: string
}
