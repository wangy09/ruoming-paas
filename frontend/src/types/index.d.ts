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
  data_scope: string
  is_system: boolean
  created_at: string
}

export interface RoleCreate {
  name: string
  code: string
  description?: string
  parent_id?: number
  data_scope?: string
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
  model_type: 'chat' | 'embedding' | 'multimodal' | 'rerank'
  base_url?: string
  model_name: string
  is_active: boolean
  is_default: boolean
  max_tokens: number
  context_window: number
  temperature: number
  tenant_id?: number
  created_at: string
}

export interface AiModelCreate {
  name: string
  provider: string
  model_type: string
  base_url?: string
  model_name: string
  api_key?: string
  max_tokens?: number
  temperature?: number
  is_default?: boolean
}

// ── Agent 相关 ────────────────────────────────────────────────────────────────
export interface AgentInfo {
  id: number
  name: string
  description?: string
  type: 'chat' | 'rag' | 'tool' | 'workflow'
  status: 'draft' | 'active' | 'archived'
  model_config_id?: number
  system_prompt?: string
  knowledge_base_ids: number[]
  tool_codes: string[]
  max_iterations: number
  temperature: number
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

// ── Prompt 模板 ────────────────────────────────────────────────────────────────
export interface PromptTemplate {
  id: number
  name: string
  description?: string
  category?: string
  template_text: string
  variables: string[]
  status: 'draft' | 'published' | 'archived'
  current_version: number
  created_at: string
}
