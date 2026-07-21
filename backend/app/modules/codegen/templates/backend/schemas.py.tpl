from datetime import datetime

from pydantic import BaseModel, Field


class {{ entity_name }}Create(BaseModel):
    """创建{{ page_title }}"""

{% for field in create_schema_fields %}    {{ field }}
{% endfor %}


class {{ entity_name }}Update(BaseModel):
    """更新{{ page_title }}"""

{% for field in update_schema_fields %}    {{ field }}
{% endfor %}


class {{ entity_name }}Info(BaseModel):
    """{{ page_title }}信息"""

{% for field in schema_fields %}    {{ field }}
{% endfor %}

    class Config:
        from_attributes = True


class {{ entity_name }}ListParams(BaseModel):
    """{{ page_title }}列表查询参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
{% if has_search_fields %}    keyword: str | None = None
{% endif %}