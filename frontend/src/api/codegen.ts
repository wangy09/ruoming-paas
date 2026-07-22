import request from '@/utils/request'
import type {
  BatchGenerateParams,
  CodegenColumn,
  CodegenPreviewParams,
  CodegenTable,
  CodegenWriteParams,
  ColumnConfig,
  CreateTableParams,
  FieldTypeInfo,
  GeneratedFile,
  GeneratedWriteResult,
  GenTableColumnResponse,
  GenTableResponse,
  SaveConfigParams,
  TableFieldConfig,
} from '@/types/codegen'

export const codegenApi = {
  tables: (params?: { keyword?: string }) =>
    request.get<{ code: number; message: string; data: CodegenTable[] }>('/api/v1/codegen/tables', { params }),
  columns: (tableName: string) =>
    request.get<{ code: number; message: string; data: CodegenColumn[] }>(`/api/v1/codegen/tables/${tableName}/columns`),
  preview: (data: CodegenPreviewParams) =>
    request.post<{ code: number; message: string; data: { files: GeneratedFile[]; results: GeneratedWriteResult[] } }>('/api/v1/codegen/preview', data),
  write: (data: CodegenWriteParams) =>
    request.post<{ code: number; message: string; data: { files: GeneratedFile[]; results: GeneratedWriteResult[] } }>('/api/v1/codegen/write', data),
  configs: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    request.get<{ code: number; message: string; data: { items: GenTableResponse[]; total: number } }>('/api/v1/codegen/configs', { params }),
  getConfig: (configId: number) =>
    request.get<{ code: number; message: string; data: GenTableResponse }>(`/api/v1/codegen/configs/${configId}`),
  saveConfig: (data: SaveConfigParams) =>
    request.post<{ code: number; message: string; data: GenTableResponse }>('/api/v1/codegen/configs', data),
  deleteConfig: (configId: number) =>
    request.delete<{ code: number; message: string }>(`/api/v1/codegen/configs/${configId}`),
  generateFromConfig: (configId: number, params?: { overwrite?: boolean }) =>
    request.post<{ code: number; message: string; data: { files: GeneratedFile[]; results: GeneratedWriteResult[] } }>(`/api/v1/codegen/configs/${configId}/generate`, null, { params }),
  batchGenerate: (data: BatchGenerateParams) =>
    request.post<{ code: number; message: string }>('/api/v1/codegen/configs/batch-generate', data),
  downloadCode: (configId: number) =>
    request.get<Blob>(`/api/v1/codegen/configs/${configId}/download`, { responseType: 'blob' }),
  fieldTypes: () =>
    request.get<{ code: number; message: string; data: FieldTypeInfo[] }>('/api/v1/codegen/field-types'),
  createTable: (data: CreateTableParams) =>
    request.post<{ code: number; message: string }>('/api/v1/codegen/create-table', data),
}
