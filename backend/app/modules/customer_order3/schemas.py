from datetime import datetime

from pydantic import BaseModel, Field


class CustomerOrder3Create(BaseModel):
    """创建客户订单"""

    title: str | None = None


class CustomerOrder3Update(BaseModel):
    """更新客户订单"""

    title: str | None = None


class CustomerOrder3Info(BaseModel):
    """客户订单信息"""

    title: str | None = None

    class Config:
        from_attributes = True


class CustomerOrder3ListParams(BaseModel):
    """客户订单列表查询参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    keyword: str | None = None
