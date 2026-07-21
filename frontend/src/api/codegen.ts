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

export interface ColumnConfig {
  column_name: string
  is_list: boolean
  is_form: boolean
  is_search: boolean
  is_required: boolean
  form_component: string
  dict_type?: string
  sort: number
}

export interface CodegenPreviewParams {
  table_name: string
  module_name: string
  entity_name?: string
  page_title?: string
  api_prefix?: string
  column_configs?: ColumnConfig[]
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

export interface GenTableColumnResponse extends ColumnConfig {
  id?: number
  column_comment?: string
  data_type?: string
  udt_name?: string
  is_nullable: boolean
  is_primary_key: boolean
}

export interface GenTableResponse {
  id: number
  table_name: string
  table_comment?: string
  module_name: string
  entity_name: string
  page_title?: string
  api_prefix?: string
  author?: string
  status: number
  remark?: string
  columns: GenTableColumnResponse[]
  table_exists?: boolean
  created_at?: string
  updated_at?: string
}

export interface SaveConfigParams {
  table_name: string
  table_comment?: string
  module_name: string
  entity_name: string
  page_title?: string
  api_prefix?: string
  author?: string
  remark?: string
  columns: ColumnConfig[]
}

export interface BatchGenerateParams {
  config_ids: number[]
  overwrite: boolean
}

export interface FieldTypeInfo {
  type_name: string
  display_name: string
  default_length?: number
  supports_length: boolean
  supports_scale: boolean
  default_nullable: boolean
}

export interface TableFieldConfig {
  column_name: string
  column_comment?: string
  data_type: string
  data_length?: number
  data_scale?: number
  is_nullable: boolean
  is_primary_key: boolean
  column_default?: string
  is_list: boolean
  is_form: boolean
  is_search: boolean
  is_required: boolean
  form_component: string
  dict_type?: string
  sort: number
}

export interface CreateTableParams {
  table_name: string
  table_comment?: string
  module_name: string
  entity_name?: string
  page_title?: string
  api_prefix?: string
  author?: string
  remark?: string
  fields: TableFieldConfig[]
  create_db_table?: boolean
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
  configs: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    request.get('/api/v1/codegen/configs', { params }),
  getConfig: (configId: number) =>
    request.get(`/api/v1/codegen/configs/${configId}`),
  saveConfig: (data: SaveConfigParams) =>
    request.post('/api/v1/codegen/configs', data),
  deleteConfig: (configId: number) =>
    request.delete(`/api/v1/codegen/configs/${configId}`),
  generateFromConfig: (configId: number, params?: { overwrite?: boolean }) =>
    request.post(`/api/v1/codegen/configs/${configId}/generate`, null, { params }),
  batchGenerate: (data: BatchGenerateParams) =>
    request.post('/api/v1/codegen/configs/batch-generate', data),
  downloadCode: (configId: number) =>
    request.get(`/api/v1/codegen/configs/${configId}/download`, { responseType: 'blob' }),
  fieldTypes: () =>
    request.get('/api/v1/codegen/field-types'),
  createTable: (data: CreateTableParams) =>
    request.post('/api/v1/codegen/create-table', data),
}