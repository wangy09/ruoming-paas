from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class {{ entity_name }}Create(BaseModel):
    """创建{{ page_title }}"""

{% for field in create_schema_fields %}    {{ field }}
{% endfor %}
{% if has_sub_tables %}
{% for st in sub_tables %}    {{ st.entity_var }}_list: Optional[List["{{ st.entity_name }}Create"]] = None
{% endfor %}
{% endif %}


class {{ entity_name }}Update(BaseModel):
    """更新{{ page_title }}"""

{% for field in update_schema_fields %}    {{ field }}
{% endfor %}
{% if has_sub_tables %}
{% for st in sub_tables %}    {{ st.entity_var }}_list: Optional[List["{{ st.entity_name }}Update"]] = None
{% endfor %}
{% endif %}


class {{ entity_name }}Info(BaseModel):
    """{{ page_title }}信息"""

{% for field in schema_fields %}    {{ field }}
{% endfor %}
{% if has_sub_tables %}
{% for st in sub_tables %}    {{ st.entity_var }}_list: Optional[List["{{ st.entity_name }}Info"]] = None
{% endfor %}
{% endif %}

    class Config:
        from_attributes = True


class {{ entity_name }}ListParams(BaseModel):
    """{{ page_title }}列表查询参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
{% if has_search_fields %}    keyword: str | None = None
{% endif %}


{% if has_sub_tables %}
{% for st in sub_tables %}

class {{ st.entity_name }}Create(BaseModel):
    """创建{{ st.table_comment }}"""

{% for field in st.create_schema_fields %}    {{ field }}
{% endfor %}


class {{ st.entity_name }}Update(BaseModel):
    """更新{{ st.table_comment }}"""

{% for field in st.update_schema_fields %}    {{ field }}
{% endfor %}


class {{ st.entity_name }}Info(BaseModel):
    """{{ st.table_comment }}信息"""

{% for field in st.schema_fields %}    {{ field }}
{% endfor %}

    class Config:
        from_attributes = True
{% endfor %}
{% endif %}