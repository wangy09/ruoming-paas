import request, { del, get, post, put, upload } from '@/utils/request'
import type { ApiResponse, FileInfo, PageData, StorageConfigInfo } from '@/types'

export const fileApi = {
  config: () =>
    get<ApiResponse<StorageConfigInfo>>('/api/v1/files/storage/config'),

  list: (params: {
    page?: number
    page_size?: number
    keyword?: string
    status?: number
    biz_type?: string
    category?: string
    file_ext?: string
  }) => get<ApiResponse<PageData<FileInfo>>>('/api/v1/files', params),

  upload: (data: {
    file: File
    biz_type?: string
    biz_id?: string
    category?: string
    remark?: string
    is_public?: boolean
  }) => {
    const fd = new FormData()
    fd.append('file', data.file)
    if (data.biz_type) fd.append('biz_type', data.biz_type)
    if (data.biz_id) fd.append('biz_id', data.biz_id)
    if (data.category) fd.append('category', data.category)
    if (data.remark) fd.append('remark', data.remark)
    fd.append('is_public', String(Boolean(data.is_public)))
    return upload<ApiResponse<FileInfo>>('/api/v1/files/upload', fd)
  },

  update: (id: number, data: Partial<Pick<FileInfo, 'biz_type' | 'biz_id' | 'category' | 'remark' | 'is_public'>>) =>
    put<ApiResponse<FileInfo>>(`/api/v1/files/${id}`, data),

  archive: (id: number, reason?: string) =>
    post<ApiResponse<FileInfo>>(`/api/v1/files/${id}/archive`, { reason }),

  restore: (id: number) =>
    post<ApiResponse<FileInfo>>(`/api/v1/files/${id}/restore`),

  remove: (id: number) =>
    del<ApiResponse>(`/api/v1/files/${id}`),

  previewBlob: (id: number) =>
    request.get<unknown, Blob>(`/api/v1/files/${id}/preview`, { responseType: 'blob' }),

  downloadBlob: (id: number) =>
    request.get<unknown, Blob>(`/api/v1/files/${id}/download`, { responseType: 'blob' }),
}
