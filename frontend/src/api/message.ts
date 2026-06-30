import { get, post, put, del } from '@/utils/request'
import type { ApiResponse, MessageInfo, MessageUnreadSummary, NoticeCreate, NoticeInfo, NoticeUpdate, PageData } from '@/types'

export const messageApi = {
  noticeList: (params: {
    page?: number
    page_size?: number
    keyword?: string
    status?: number
    target_type?: string
  }) => get<ApiResponse<PageData<NoticeInfo>>>('/api/v1/messages/notices', params),

  noticeDetail: (id: number) =>
    get<ApiResponse<NoticeInfo>>(`/api/v1/messages/notices/${id}`),

  noticeCreate: (data: NoticeCreate) =>
    post<ApiResponse<NoticeInfo>>('/api/v1/messages/notices', data),

  noticeUpdate: (id: number, data: NoticeUpdate) =>
    put<ApiResponse<NoticeInfo>>(`/api/v1/messages/notices/${id}`, data),

  noticeDelete: (id: number) =>
    del<ApiResponse>(`/api/v1/messages/notices/${id}`),

  noticePublish: (id: number) =>
    post<ApiResponse<NoticeInfo>>(`/api/v1/messages/notices/${id}/publish`),

  inboxList: (params: {
    page?: number
    page_size?: number
    is_read?: boolean
  }) => get<ApiResponse<PageData<MessageInfo>>>('/api/v1/messages/inbox', params),

  unreadSummary: () =>
    get<ApiResponse<MessageUnreadSummary>>('/api/v1/messages/inbox/unread'),

  markRead: (id: number) =>
    post<ApiResponse<MessageInfo>>(`/api/v1/messages/inbox/${id}/read`),

  markAllRead: () =>
    post<ApiResponse<{ updated: number }>>('/api/v1/messages/inbox/read-all'),

  deleteMessage: (id: number) =>
    del<ApiResponse>(`/api/v1/messages/inbox/${id}`),
}
