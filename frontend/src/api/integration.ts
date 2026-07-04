import { del, get, post, put } from '@/utils/request'
import type {
  ApiResponse,
  IntegrationConnection,
  IntegrationConnectionCreate,
  IntegrationConnectionQuery,
  IntegrationConnectionUpdate,
  IntegrationTestResult,
  ProviderInfo,
} from '@/types'

const BASE_URL = '/api/v1/integrations'

// ── 集成中心 ──────────────────────────────────────────────────────────────────
export const integrationApi = {
  providers: () =>
    get<ApiResponse<ProviderInfo[]>>(`${BASE_URL}/providers`),

  connections: (params?: IntegrationConnectionQuery) =>
    get<ApiResponse<IntegrationConnection[]>>(`${BASE_URL}/connections`, params),

  createConnection: (data: IntegrationConnectionCreate) =>
    post<ApiResponse<IntegrationConnection>>(`${BASE_URL}/connections`, data),

  updateConnection: (id: number, data: IntegrationConnectionUpdate) =>
    put<ApiResponse<IntegrationConnection>>(`${BASE_URL}/connections/${id}`, data),

  deleteConnection: (id: number) =>
    del<ApiResponse<null>>(`${BASE_URL}/connections/${id}`),

  testConnection: (id: number) =>
    post<ApiResponse<IntegrationTestResult>>(`${BASE_URL}/connections/${id}/test`),
}
