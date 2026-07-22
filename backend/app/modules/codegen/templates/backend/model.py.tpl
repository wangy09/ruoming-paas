from datetime import datetime
from typing import List

from sqlalchemy import {% for import in sqlalchemy_imports %}{{ import }}{% if not loop.last %}, {% endif %}{% endfor %}

{% if has_jsonb %}from sqlalchemy.dialects.postgresql import JSONB
{% endif %}
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class {{ entity_name }}(BaseModel):
    """{{ table_comment }}"""

    __tablename__ = "{{ table_name }}"

{% for field in model_fields %}    {{ field }}
{% endfor %}

{% if has_sub_tables %}
{% for st in sub_tables %}    {{ st.entity_var }}_list: Mapped[List["{{ st.entity_name }}"]] = relationship(
        "{{ st.entity_name }}",
        back_populates="{{ entity_var }}",
        cascade="all, delete-orphan"
    )
{% endfor %}
{% endif %}


{% if has_sub_tables %}
{% for st in sub_tables %}
class {{ st.entity_name }}(BaseModel):
    """{{ st.table_comment }}"""

    __tablename__ = "{{ st.table_name }}"

    {{ st.parent_key }}: Mapped[int] = mapped_column(nullable=False, comment="{{ entity_name }}ID")

{% for field in st.model_fields %}    {{ field }}
{% endfor %}

    {{ entity_var }}: Mapped["{{ entity_name }}"] = relationship(
        "{{ entity_name }}",
        back_populates="{{ st.entity_var }}_list"
    )
{% endfor %}
{% endif %}