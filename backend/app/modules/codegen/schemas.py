"""
若茗 PaaS - 代码生成器 Schema
"""
from pydantic import BaseModel, Field, field_validator


class TableInfo(BaseModel):
    """数据库表信息"""

    table_name: str
    table_comment: str | None = None


class ColumnInfo(BaseModel):
    """数据库字段信息"""

    column_name: str
    data_type: str
    udt_name: str
    is_nullable: bool
    column_default: str | None = None
    character_maximum_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    column_comment: str | None = None
    is_primary_key: bool = False
    python_type: str
    ts_type: str
    form_component: str


class GeneratePreviewRequest(BaseModel):
    """生成代码预览请求"""

    table_name: str = Field(..., min_length=1, max_length=128)
    module_name: str = Field(..., min_length=1, max_length=64, description="模块名，如 customer")
    entity_name: str | None = Field(None, max_length=64, description="实体类名，如 Customer")
    page_title: str | None = Field(None, max_length=64, description="页面标题")
    api_prefix: str | None = Field(None, max_length=128, description="API 前缀，如 /api/v1/customers")

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, value: str) -> str:
        value = value.strip().lower().replace("-", "_")
        if not value.replace("_", "").isalnum():
            raise ValueError("module_name 只能包含字母、数字和下划线")
        return value


class GeneratedFile(BaseModel):
    """生成文件预览"""

    path: str
    language: str
    content: str


class GeneratePreviewResponse(BaseModel):
    """生成代码预览响应"""

    table: TableInfo
    columns: list[ColumnInfo]
    files: list[GeneratedFile]
