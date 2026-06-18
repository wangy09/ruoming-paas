"""
若茗 PaaS - 分页参数工具
Author: ruoming
"""
from pydantic import BaseModel, Field


class PageParams(BaseModel):
    """统一分页参数"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=200, description="每页数量，最大 200")
    order_by: str = Field(default="created_at", description="排序字段名")
    order_dir: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="排序方向：asc / desc",
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
