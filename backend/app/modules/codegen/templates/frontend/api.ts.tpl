import request from '@/utils/request'

{% if has_sub_tables %}
{% for st in sub_tables %}
export interface {{ st.entity_name }}Info {
{% for field in st.ts_type_fields %}  {{ field.name }}: {{ field.type }}
{% endfor %}
}
{% endfor %}
{% endif %}

export interface {{ entity_name }}Info {
{% for field in ts_type_fields %}  {{ field.name }}: {{ field.type }}
{% endfor %}
{% if has_sub_tables %}
{% for st in sub_tables %}  {{ st.entity_var }}_list?: {{ st.entity_name }}Info[]
{% endfor %}
{% endif %}
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