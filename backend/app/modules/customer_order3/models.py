from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class CustomerOrder3(BaseModel):
    """客户订单"""

    __tablename__ = "customer_order3"

    title: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None, comment="标题")
