from datetime import datetime

from sqlalchemy import {% for import in sqlalchemy_imports %}{{ import }}{% if not loop.last %}, {% endif %}{% endfor %}

{% if has_jsonb %}from sqlalchemy.dialects.postgresql import JSONB
{% endif %}
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class {{ entity_name }}(BaseModel):
    """{{ table_comment }}"""

    __tablename__ = "{{ table_name }}"

{% for field in model_fields %}    {{ field }}
{% endfor %}