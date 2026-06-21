import request from '@/utils/request'

export const dictApi = {
  getDictTypes: (params?: { keyword?: string; status?: number }) =>
    request.get('/api/v1/dict/types', { params }),
  getDictType: (typeId: number) => request.get(`/api/v1/dict/types/${typeId}`),
  createDictType: (data: any) => request.post('/api/v1/dict/types', data),
  updateDictType: (typeId: number, data: any) => request.put(`/api/v1/dict/types/${typeId}`, data),
  deleteDictType: (typeId: number) => request.delete(`/api/v1/dict/types/${typeId}`),

  getDictItems: (typeId: number) => request.get('/api/v1/dict/items', { params: { type_id: typeId } }),
  createDictItem: (data: any) => request.post('/api/v1/dict/items', data),
  updateDictItem: (itemId: number, data: any) => request.put(`/api/v1/dict/items/${itemId}`, data),
  deleteDictItem: (itemId: number) => request.delete(`/api/v1/dict/items/${itemId}`),

  getDictByCode: (code: string) => request.get(`/api/v1/dict/code/${code}`),
}
