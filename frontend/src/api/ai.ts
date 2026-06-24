import { get, post, put, del, upload } from '@/utils/request'
import type {
  ApiResponse, PageData,
  AiModelConfig, AiModelCreate,
  AgentInfo,
  KnowledgeBase, KnowledgeDoc,
  Conversation, ChatMessage,
  PromptTemplate, PromptVersion,
  ToolInfo, CustomToolDetail,
} from '@/types'

// ── LLM 模型 ──────────────────────────────────────────────────────────────────
export const modelApi = {
  list: (params?: { page?: number; page_size?: number; model_type?: string }) =>
    get<ApiResponse<PageData<AiModelConfig>>>('/api/v1/ai/models', params),

  get: (id: number) =>
    get<ApiResponse<AiModelConfig>>(`/api/v1/ai/models/${id}`),

  create: (data: AiModelCreate) =>
    post<ApiResponse<AiModelConfig>>('/api/v1/ai/models', data),

  update: (id: number, data: Partial<AiModelCreate>) =>
    put<ApiResponse<AiModelConfig>>(`/api/v1/ai/models/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/ai/models/${id}`),

  test: (id: number) =>
    post<ApiResponse<{ latency_ms: number; model: string }>>(`/api/v1/ai/models/${id}/test`),
}

// ── Agent ────────────────────────────────────────────────────────────────────
export const agentApi = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    get<ApiResponse<PageData<AgentInfo>>>('/api/v1/ai/agents', params),

  get: (id: number) =>
    get<ApiResponse<AgentInfo>>(`/api/v1/ai/agents/${id}`),

  create: (data: Partial<AgentInfo>) =>
    post<ApiResponse<AgentInfo>>('/api/v1/ai/agents', data),

  update: (id: number, data: Partial<AgentInfo>) =>
    put<ApiResponse<AgentInfo>>(`/api/v1/ai/agents/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/ai/agents/${id}`),
}

// ── 知识库 ────────────────────────────────────────────────────────────────────
export const kbApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    get<ApiResponse<PageData<KnowledgeBase>>>('/api/v1/ai/knowledge', params),

  get: (id: number) =>
    get<ApiResponse<KnowledgeBase>>(`/api/v1/ai/knowledge/${id}`),

  create: (data: Partial<KnowledgeBase> & { embed_model_id?: number }) =>
    post<ApiResponse<KnowledgeBase>>('/api/v1/ai/knowledge', data),

  update: (id: number, data: Partial<KnowledgeBase> & { embed_model_id?: number }) =>
    put<ApiResponse<KnowledgeBase>>(`/api/v1/ai/knowledge/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/ai/knowledge/${id}`),

  docs: (kbId: number, params?: { page?: number; page_size?: number }) =>
    get<ApiResponse<PageData<KnowledgeDoc>>>(`/api/v1/ai/knowledge/${kbId}/docs`, params),

  addUrlSource: (kbId: number, data: { urls: string[]; name?: string; css_selector?: string }) =>
    post<ApiResponse<KnowledgeDoc[]>>(`/api/v1/ai/knowledge/${kbId}/docs/url`, data),

  addApiSource: (kbId: number, data: {
    name: string; source_type: 'api' | 'database';
    url?: string; method?: string; headers?: Record<string, string>; body?: string; json_path?: string;
    db_url?: string; sql?: string;
  }) =>
    post<ApiResponse<KnowledgeDoc>>(`/api/v1/ai/knowledge/${kbId}/docs/api`, data),

  uploadDoc: (kbId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return upload<ApiResponse<KnowledgeDoc>>(`/api/v1/ai/knowledge/${kbId}/docs`, fd)
  },

  uploadInit: (kbId: number, data: { filename: string; file_size: number; file_hash: string; part_count: number }) =>
    post<ApiResponse<{ upload_id: string; part_size: number; uploaded_parts: number[] }>>(
      `/api/v1/ai/knowledge/${kbId}/upload/init`,
      data,
    ),

  uploadPart: (kbId: number, data: { upload_id: string; part_number: number; part_hash: string; file: Blob }) => {
    const fd = new FormData()
    fd.append('upload_id', data.upload_id)
    fd.append('part_number', String(data.part_number))
    fd.append('part_hash', data.part_hash)
    fd.append('file', data.file)
    return upload(`/api/v1/ai/knowledge/${kbId}/upload/part`, fd)
  },

  uploadComplete: (kbId: number, data: { upload_id: string; part_hashes: string[] }) =>
    post<ApiResponse<KnowledgeDoc>>(`/api/v1/ai/knowledge/${kbId}/upload/complete`, data),

  deleteDoc: (kbId: number, docId: number) =>
    del<ApiResponse>(`/api/v1/ai/knowledge/${kbId}/docs/${docId}`),

  search: (kbId: number, query: string, topK = 5) =>
    post<ApiResponse<Array<{ content: string; score: number }>>>(
      `/api/v1/ai/knowledge/${kbId}/search`,
      { query, top_k: topK },
    ),

  getStats: (kbId: number) =>
    get<ApiResponse<{ total_docs: number; total_chars: number; total_chunks: number; done_docs: number; processing_docs: number; error_docs: number }>>(
      `/api/v1/ai/knowledge/${kbId}/stats`,
    ),

  reindexDoc: (kbId: number, docId: number) =>
    post<ApiResponse>(`/api/v1/ai/knowledge/${kbId}/docs/${docId}/reindex`),

  reindexAll: (kbId: number) =>
    post<ApiResponse<{ message: string; task_id: string }>>(
      `/api/v1/ai/knowledge/${kbId}/reindex`,
    ),

  listTasks: (kbId: number) =>
    get<ApiResponse<Array<{ task_id: string; task_type: string; status: string; total: number; completed: number; failed: number; progress: number; created_at: string; updated_at: string }>>>(
      `/api/v1/ai/knowledge/${kbId}/tasks`,
    ),

  getTaskStatus: (kbId: number, taskId: string) =>
    get<ApiResponse<{ task_id: string; kb_id: number; task_type: string; status: string; total: number; completed: number; failed: number; progress: number; current_doc: string | null; result: any; error_msg: string | null; created_at: string; updated_at: string }>>(
      `/api/v1/ai/knowledge/${kbId}/tasks/${taskId}`,
    ),
}

// ── 工具管理 ────────────────────────────────────────────────────────────────────
export const toolApi = {
  list: () =>
    get<ApiResponse<ToolInfo[]>>('/api/v1/ai/tools'),
  create: (data: { name: string; description: string; url: string; method: string; headers: Record<string, string> }) =>
    post<ApiResponse<CustomToolDetail>>('/api/v1/ai/tools', data),
  update: (id: number, data: Partial<{ name: string; description: string; url: string; method: string; headers: Record<string, string>; status: number }>) =>
    put<ApiResponse<CustomToolDetail>>(`/api/v1/ai/tools/${id}`, data),
  remove: (id: number) =>
    del<ApiResponse<null>>(`/api/v1/ai/tools/${id}`),
}

// ── 对话历史 ────────────────────────────────────────────────────────────────────
export const conversationApi = {
  list: (params?: { page?: number; page_size?: number; agent_id?: number }) =>
    get<ApiResponse<PageData<Conversation>>>('/api/v1/ai/conversations', params),

  messages: (convId: number) =>
    get<ApiResponse<PageData<ChatMessage>>>(`/api/v1/ai/conversations/${convId}/messages`),

  delete: (convId: number) =>
    del<ApiResponse>(`/api/v1/ai/conversations/${convId}`),
}

// ── Prompt 模板 ────────────────────────────────────────────────────────────────
export const promptApi = {
  list: (params?: { page?: number; page_size?: number; category?: string }) =>
    get<ApiResponse<PageData<PromptTemplate>>>('/api/v1/ai/prompts', params),

  get: (id: number) =>
    get<ApiResponse<PromptTemplate>>(`/api/v1/ai/prompts/${id}`),

  create: (data: Partial<PromptTemplate>) =>
    post<ApiResponse<PromptTemplate>>('/api/v1/ai/prompts', data),

  update: (id: number, data: Partial<PromptTemplate>) =>
    put<ApiResponse<PromptTemplate>>(`/api/v1/ai/prompts/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/ai/prompts/${id}`),

  // 版本管理
  versions: (id: number) =>
    get<ApiResponse<PromptVersion[]>>(`/api/v1/ai/prompts/${id}/versions`),

  addVersion: (id: number, data: { content: string; variables?: string[]; changelog?: string }) =>
    post<ApiResponse<PromptVersion>>(`/api/v1/ai/prompts/${id}/versions`, data),

  publishVersion: (id: number, version: number) =>
    post<ApiResponse<PromptVersion>>(`/api/v1/ai/prompts/${id}/versions/${version}/publish`),

  rollbackVersion: (id: number, version: number) =>
    post<ApiResponse<PromptTemplate>>(`/api/v1/ai/prompts/${id}/versions/${version}/rollback`),

  preview: (id: number, variables: Record<string, string>) =>
    post<ApiResponse<{ rendered: string }>>(`/api/v1/ai/prompts/${id}/preview`, { variables }),
}

// ── 审计日志 ────────────────────────────────────────────────────────────────────
export const auditApi = {
  list: (params?: {
    page?: number
    page_size?: number
    action?: string
    resource_type?: string
    start_time?: string
    end_time?: string
  }) => get<ApiResponse<PageData<import('@/types').AuditLog>>>('/api/v1/audit/logs', params),

  loginLogs: (params?: { page?: number; page_size?: number; user_id?: number }) =>
    get<ApiResponse<PageData<import('@/types').LoginLog>>>('/api/v1/audit/login-logs', params),
}
