import request from '@/utils/request'

export interface CodegenTable {
  table_name: string
  table_comment?: string
}

export interface CodegenColumn {
  column_name: string
  data_type: string
  udt_name: string
  is_nullable: boolean
  column_default?: string
  character_maximum_length?: number
  numeric_precision?: number
  numeric_scale?: number
  column_comment?: string
  is_primary_key: boolean
  python_type: string
  ts_type: string
  form_component: string
}

export interface CodegenPreviewParams {
  table_name: string
  module_name: string
  entity_name?: string
  page_title?: string
  api_prefix?: string
}

export interface CodegenWriteParams extends CodegenPreviewParams {
  overwrite: boolean
}

export interface GeneratedFile {
  path: string
  language: string
  content: string
}

export interface GeneratedWriteResult {
  path: string
  status: 'created' | 'skipped' | 'overwritten' | 'unavailable' | 'error'
  message: string
}

export const codegenApi = {
  tables: (params?: { keyword?: string }) =>
    request.get('/api/v1/codegen/tables', { params }),
  columns: (tableName: string) =>
    request.get(`/api/v1/codegen/tables/${tableName}/columns`),
  preview: (data: CodegenPreviewParams) =>
    request.post('/api/v1/codegen/preview', data),
  write: (data: CodegenWriteParams) =>
    request.post('/api/v1/codegen/write', data),
}
