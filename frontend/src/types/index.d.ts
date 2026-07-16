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

// ── 文件中心 ────────────────────────────────────────────────────────────────────
export interface FileInfo {
  id: number
  original_name: string
  file_name: string
  file_ext?: string | null
  mime_type?: string | null
  file_size: number
  file_hash: string
  storage_backend: 'local' | 'minio' | 'oss' | string
  storage_key: string
  storage_url?: string | null
  biz_type?: string | null
  biz_id?: string | null
  category?: string | null
  remark?: string | null
  uploader_id?: number | null
  download_count: number
  is_public: boolean
  status: 1 | 2
  archived_at?: string | null
  archived_by?: number | null
  archive_reason?: string | null
  created_at: string
  updated_at: string
}

export interface StorageConfigInfo {
  backend: string
  upload_dir?: string | null
  max_upload_size_mb: number
  allowed_extensions: string[]
  supports: string[]
}

// ── 配置中心 ────────────────────────────────────────────────────────────────────
export type ConfigScope = 'global' | 'tenant' | 'app' | 'user'
export type ConfigValueType = 'string' | 'int' | 'number' | 'bool' | 'json'
export type ConfigFormType = 'input' | 'textarea' | 'switch' | 'select' | 'json' | 'password' | 'number'

export interface ConfigOption {
  label: string
  value: string | number | boolean
}

export interface ConfigInfo {
  id: number
  scope: ConfigScope
  config_key: string
  config_val?: string | null
  display_val?: string | null
  val_type: ConfigValueType | string
  is_encrypted: boolean
  category?: string | null
  config_type: ConfigFormType | string
  default_value?: string | null
  options?: ConfigOption[] | Record<string, unknown> | null
  required: boolean
  regex?: string | null
  min_value?: number | null
  max_value?: number | null
  sort: number
  status: 0 | 1
  label?: string | null
  description?: string | null
  is_public: boolean
  app_key?: string | null
  user_id?: number | null
  tenant_id?: number | null
}

export interface ConfigPayload {
  scope: ConfigScope
  config_key: string
  config_val?: string | null
  val_type: string
  is_encrypted: boolean
  category?: string | null
  config_type: string
  default_value?: string | null
  options?: ConfigOption[] | Record<string, unknown> | null
  required: boolean
  regex?: string | null
  min_value?: number | null
  max_value?: number | null
  sort: number
  status: 0 | 1
  label?: string | null
  description?: string | null
  is_public: boolean
  app_key?: string | null
  user_id?: number | null
}

export interface ConfigHistoryInfo {
  id: number
  config_key: string
  scope_type: string
  scope_id?: number | null
  old_value?: string | null
  new_value?: string | null
  changed_by?: number | null
  changed_by_name?: string | null
  changed_at: string
  remark?: string | null
}

export interface ConfigImportResult {
  created: number
  updated: number
  skipped: number
  errors: string[]
}

// ── 集成中心 ────────────────────────────────────────────────────────────────────
export type IntegrationProviderCode = 'feishu' | 'dingtalk' | 'wecom' | 'custom'
export type IntegrationCapabilityCode = 'bot_message' | 'oauth' | 'contact_sync' | 'event_callback'
export type IntegrationTestStatus = 'success' | 'failed'

export interface ProviderInfo {
  code: IntegrationProviderCode
  name: string
  capabilities: IntegrationCapabilityCode[]
  required_secret_fields: string[]
  optional_secret_fields: string[]
  config_fields: string[]
}

export interface IntegrationConnection {
  id: number
  provider: IntegrationProviderCode
  provider_name: string
  name: string
  enabled: boolean
  is_default: boolean
  capabilities: IntegrationCapabilityCode[]
  config?: Record<string, unknown> | null
  secret_configured: boolean
  status: 0 | 1 | number
  last_test_status?: IntegrationTestStatus | null
  last_test_message?: string | null
  sort: number
  tenant_id?: number | null
}

export interface IntegrationConnectionCreate {
  provider: IntegrationProviderCode
  name: string
  enabled: boolean
  is_default: boolean
  capabilities: IntegrationCapabilityCode[]
  config: Record<string, unknown>
  secret_config: Record<string, string>
  sort: number
}

export type IntegrationConnectionUpdate = Partial<Omit<IntegrationConnectionCreate, 'provider'>>

export interface IntegrationConnectionQuery {
  provider?: string
  enabled?: boolean
}

export interface IntegrationTestResult {
  success: boolean
  provider: string
  message: string
  details: Record<string, unknown>
}

export interface ContactSyncStrategy {
  sync_departments: boolean
  sync_users: boolean
  sync_avatar: boolean
  disable_missing_users: boolean
  username_strategy: Array<'email_prefix' | 'phone' | 'name' | 'external_id'>
  nickname_strategy: Array<'name' | 'nickname' | 'username'>
  overwrite_email: boolean
  overwrite_phone: boolean
  overwrite_department: boolean
  email_update_mode: 'never' | 'if_empty' | 'always'
  phone_update_mode: 'never' | 'if_empty' | 'always'
  department_update_mode: 'never' | 'if_empty' | 'always'
}

export interface ContactSyncRequest extends ContactSyncStrategy {
  provider: 'feishu' | 'dingtalk' | 'wecom'
  connection_id?: number | null
}

export interface ContactSyncResult {
  provider: string
  connection_id: number
  departments_created: number
  departments_updated: number
  users_created: number
  users_updated: number
  users_disabled: number
  skipped_users: number
  errors: string[]
}

export interface ContactSyncPreviewItem {
  action: string
  target_type: string
  external_id?: string | null
  local_id?: number | null
  name?: string | null
  reason?: string | null
}

export interface ContactSyncPreviewResult extends ContactSyncResult {
  details: ContactSyncPreviewItem[]
}

export interface ContactSyncCheckItem {
  key: string
  name: string
  status: 'success' | 'warning' | 'failed' | string
  message: string
  details?: Record<string, unknown>
}

export interface ContactSyncCheckResult {
  provider: string
  connection_id?: number | null
  status: 'success' | 'warning' | 'failed' | string
  summary: string
  departments_count: number
  users_count: number
  avatar_users_count: number
  missing_users_count: number
  checks: ContactSyncCheckItem[]
}

export interface ContactSyncLogItem {
  id: number
  provider: string
  connection_id: number
  operation: string
  status: string
  operator_id?: number | null
  request_data?: Record<string, unknown> | null
  result_data?: Record<string, unknown> | null
  detail_data?: Record<string, unknown> | null
  created_at?: string
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
  avatar?: string
  status: number
  is_active: boolean
  is_superplatform: boolean
  tenant_id: number
  dept_id?: number
  dept_name?: string
  roles: RoleInfo[]
  /** 外部同步来源提供商，例如 feishu / dingtalk / wecom */
  source_provider?: IntegrationProviderCode | string | null
  /** 外部同步来源连接名称 */
  source_connection_name?: string | null
  /** 外部系统用户 ID */
  source_external_id?: string | null
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
  dept_id?: number
  tenant_id?: number
  role_ids?: number[]
}

export interface UserUpdate {
  nickname?: string
  email?: string
  phone?: string
  dept_id?: number
  status?: number
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
  dashboard_template?: 'platform' | 'tenant' | 'developer' | 'personal' | null
  sort?: number
  status?: number
  tenant_id?: number | null
  is_system?: boolean
  created_at?: string
}

export interface RoleCreate {
  name: string
  code: string
  description?: string
  parent_id?: number
  data_scope?: number
  data_scope_depts?: number[]
  dashboard_template?: 'platform' | 'tenant' | 'developer' | 'personal' | null
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
  redirect?: string
  children?: MenuPermission[]
  permissionCode?: string
  keepAlive?: boolean
  isVisible?: boolean
  isCache?: boolean
  isExternal?: boolean
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
  tenant_id?: number | null
  user_id?: number | null
  username?: string | null
  module?: string | null
  action?: string | null
  resource_type?: string | null
  resource_id?: string | null
  event_type: string
  before_data?: Record<string, unknown> | null
  after_data?: Record<string, unknown> | null
  detail?: Record<string, unknown> | null
  request_body?: Record<string, unknown> | unknown[] | string | number | boolean | null
  response_body?: Record<string, unknown> | unknown[] | string | number | boolean | null
  status_code?: number | null
  request_ip?: string | null
  user_agent?: string | null
  browser?: string | null
  os?: string | null
  device?: string | null
  trace_id?: string | null
  path?: string | null
  method?: string | null
  status: number
  error_msg?: string | null
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
