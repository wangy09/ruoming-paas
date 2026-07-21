import request from '@/utils/request'

export interface {{ entity_name }}Info {
{% for field in ts_type_fields %}  {{ field.name }}: {{ field.type }}
{% endfor %}
}

export interface {{ entity_name }}ListParams {
  page?: number
  page_size?: number
{% if has_search_fields %}  keyword?: string
{% endif %}
}

export const {{ module_name }}Api = {
  list: (params: {{ entity_name }}ListParams) =>
    request.get('{{ api_prefix }}', { params }),
  get: (id: number) =>
    request.get(`{{ api_prefix }}/${id}`),
  create: (data: Record<string, unknown>) =>
    request.post('{{ api_prefix }}', data),
  update: (id: number, data: Record<string, unknown>) =>
    request.put(`{{ api_prefix }}/${id}`, data),
  remove: (id: number) =>
    request.delete(`{{ api_prefix }}/${id}`),
}