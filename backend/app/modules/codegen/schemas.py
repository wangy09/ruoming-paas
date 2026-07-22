"""
若茗 PaaS - 代码生成器 Schema
"""
from __future__ import annotations

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
    foreign_key_table: str | None = None


class ColumnConfig(BaseModel):
    """字段配置"""

    column_name: str
    is_list: bool = True
    is_form: bool = True
    is_search: bool = False
    is_required: bool = False
    form_component: str = "input"
    dict_type: str | None = None
    sort: int = 0
    is_sub_table: bool = False
    sub_table_name: str | None = None


class TableFieldConfig(BaseModel):
    """前端建表字段配置"""

    column_name: str = Field(..., min_length=1, max_length=128, description="字段名")
    column_comment: str | None = Field(None, max_length=256, description="字段注释")
    data_type: str = Field(..., description="数据类型")
    data_length: int | None = Field(None, description="长度")
    data_scale: int | None = Field(None, description="小数位数")
    is_nullable: bool = Field(True, description="是否可空")
    is_primary_key: bool = Field(False, description="是否主键")
    column_default: str | None = Field(None, description="默认值")
    foreign_key_table: str | None = Field(None, description="外键关联表名")
    is_list: bool = Field(True, description="是否列表显示")
    is_form: bool = Field(True, description="是否表单编辑")
    is_search: bool = Field(False, description="是否搜索条件")
    is_required: bool = Field(False, description="是否必填")
    form_component: str = Field("input", description="表单组件")
    dict_type: str | None = Field(None, description="字典类型编码")
    sort: int = Field(0, description="排序")


class SubTableConfig(BaseModel):
    """子表配置"""

    table_name: str = Field(..., description="子表名称")
    table_comment: str | None = Field(None, description="子表注释")
    parent_key: str = Field(..., description="父表外键字段名")
    entity_name: str | None = Field(None, description="子表实体类名")
    columns: list[TableFieldConfig] = Field([], description="子表字段配置")


class GeneratePreviewRequest(BaseModel):
    """生成代码预览请求"""

    table_name: str = Field(..., min_length=1, max_length=128)
    module_name: str = Field(..., min_length=1, max_length=64, description="模块名，如 customer")
    entity_name: str | None = Field(None, max_length=64, description="实体类名，如 Customer")
    page_title: str | None = Field(None, max_length=64, description="页面标题")
    api_prefix: str | None = Field(None, max_length=128, description="API 前缀，如 /api/v1/customers")
    template_type: str = Field("single", description="生成模板类型：single-单表CRUD, master_detail-主子表CRUD, tree-树形CRUD")
    column_configs: list[ColumnConfig] | None = None
    sub_tables: list[SubTableConfig] | None = None

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, value: str) -> str:
        value = value.strip().lower().replace("-", "_")
        if not value.replace("_", "").isalnum():
            raise ValueError("module_name 只能包含字母、数字和下划线")
        return value


class GenerateWriteRequest(GeneratePreviewRequest):
    """写入生成文件请求"""

    overwrite: bool = Field(False, description="是否覆盖已存在文件")


class GeneratedFile(BaseModel):
    """生成文件预览"""

    path: str
    language: str
    content: str


class GeneratedWriteResult(BaseModel):
    """生成文件写入结果"""

    path: str
    status: str = Field(..., description="created/skipped/overwritten/unavailable/error")
    message: str


class GeneratePreviewResponse(BaseModel):
    """生成代码预览响应"""

    table: TableInfo
    columns: list[ColumnInfo]
    files: list[GeneratedFile]


class GenerateWriteResponse(GeneratePreviewResponse):
    """生成代码写入响应"""

    results: list[GeneratedWriteResult]


class GenTableColumnResponse(ColumnConfig):
    """生成表字段配置响应"""

    id: int | None = None
    column_comment: str | None = None
    data_type: str | None = None
    udt_name: str | None = None
    is_nullable: bool = True
    is_primary_key: bool = False


class GenTableResponse(BaseModel):
    """生成表配置响应"""

    id: int
    table_name: str
    table_comment: str | None = None
    module_name: str
    entity_name: str
    page_title: str | None = None
    api_prefix: str | None = None
    author: str | None = None
    status: int = 1
    remark: str | None = None
    columns: list[GenTableColumnResponse] = []
    table_exists: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SaveConfigRequest(BaseModel):
    """保存配置请求"""

    table_name: str = Field(..., min_length=1, max_length=128)
    table_comment: str | None = None
    module_name: str = Field(..., min_length=1, max_length=64)
    entity_name: str = Field(..., min_length=1, max_length=64)
    page_title: str | None = None
    api_prefix: str | None = None
    author: str | None = None
    remark: str | None = None
    columns: list[ColumnConfig] = []
    sub_tables: list[SubTableConfig] = []

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, value: str) -> str:
        value = value.strip().lower().replace("-", "_")
        if not value.replace("_", "").isalnum():
            raise ValueError("module_name 只能包含字母、数字和下划线")
        return value


class UpdateConfigRequest(SaveConfigRequest):
    """更新配置请求"""

    pass


class ListConfigResponse(BaseModel):
    """配置列表响应"""

    total: int
    items: list[GenTableResponse]


class BatchGenerateRequest(BaseModel):
    """批量生成请求"""

    config_ids: list[int] = Field(..., min_length=1, description="配置 ID 列表")
    overwrite: bool = False


class FieldTypeInfo(BaseModel):
    """字段类型信息"""

    type_name: str = Field(..., description="类型名称")
    display_name: str = Field(..., description="显示名称")
    default_length: int | None = Field(None, description="默认长度")
    supports_length: bool = Field(True, description="是否支持长度")
    supports_scale: bool = Field(False, description="是否支持小数位数")
    default_nullable: bool = Field(True, description="默认是否可空")


class CreateTableRequest(BaseModel):
    """前端建表请求"""

    table_name: str = Field(..., min_length=1, max_length=128, description="表名")
    table_comment: str | None = Field(None, max_length=256, description="表注释")
    module_name: str = Field(..., min_length=1, max_length=64, description="模块名")
    entity_name: str | None = Field(None, max_length=64, description="实体类名")
    page_title: str | None = Field(None, max_length=64, description="页面标题")
    api_prefix: str | None = Field(None, max_length=128, description="API 前缀")
    author: str | None = Field(None, max_length=64, description="作者")
    remark: str | None = Field(None, description="备注")
    fields: list[TableFieldConfig] = Field(..., min_length=1, description="字段列表")
    create_db_table: bool = Field(True, description="是否创建真实数据库表")
    sub_tables: list[SubTableConfig] | None = Field(None, description="子表配置")

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        value = value.strip().lower().replace("-", "_")
        if not value.replace("_", "").isalnum():
            raise ValueError("table_name 只能包含字母、数字和下划线")
        return value

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, value: str) -> str:
        value = value.strip().lower().replace("-", "_")
        if not value.replace("_", "").isalnum():
            raise ValueError("module_name 只能包含字母、数字和下划线")
        return value