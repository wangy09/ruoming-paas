import { get, post, put, del, upload } from '@/utils/request'
import type {
  ApiResponse, PageData,
  AiModelConfig, AiModelCreate,
  AgentInfo,
  KnowledgeBase, KnowledgeDoc,
  Conversation, ChatMessage,
  PromptTemplate,
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
    get<ApiResponse<PageData<KnowledgeBase>>>('/api/v1/ai/knowledge-bases', params),

  get: (id: number) =>
    get<ApiResponse<KnowledgeBase>>(`/api/v1/ai/knowledge-bases/${id}`),

  create: (data: Partial<KnowledgeBase>) =>
    post<ApiResponse<KnowledgeBase>>('/api/v1/ai/knowledge-bases', data),

  update: (id: number, data: Partial<KnowledgeBase>) =>
    put<ApiResponse<KnowledgeBase>>(`/api/v1/ai/knowledge-bases/${id}`, data),

  delete: (id: number) =>
    del<ApiResponse>(`/api/v1/ai/knowledge-bases/${id}`),

  docs: (kbId: number, params?: { page?: number; page_size?: number }) =>
    get<ApiResponse<PageData<KnowledgeDoc>>>(`/api/v1/ai/knowledge-bases/${kbId}/documents`, params),

  uploadDoc: (kbId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return upload<ApiResponse<KnowledgeDoc>>(`/api/v1/ai/knowledge-bases/${kbId}/documents`, fd)
  },

  deleteDoc: (kbId: number, docId: number) =>
    del<ApiResponse>(`/api/v1/ai/knowledge-bases/${kbId}/documents/${docId}`),

  search: (kbId: number, query: string, topK = 5) =>
    post<ApiResponse<Array<{ content: string; score: number }>>>(
      `/api/v1/ai/knowledge-bases/${kbId}/search`,
      { query, top_k: topK },
    ),
}

// ── 对话历史 ────────────────────────────────────────────────────────────────────
export const conversationApi = {
  list: (params?: { page?: number; page_size?: number; agent_id?: number }) =>
    get<ApiResponse<PageData<Conversation>>>('/api/v1/ai/conversations', params),

  messages: (convId: number) =>
    get<ApiResponse<ChatMessage[]>>(`/api/v1/ai/conversations/${convId}/messages`),

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

  publish: (id: number) =>
    post<ApiResponse>(`/api/v1/ai/prompts/${id}/publish`),

  rollback: (id: number, version: number) =>
    post<ApiResponse>(`/api/v1/ai/prompts/${id}/rollback`, { version }),

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
