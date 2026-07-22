"""
若茗 PaaS - 代码生成器配置模型

gen_table: 存储表级代码生成配置
gen_table_column: 存储列级代码生成配置
"""
from sqlalchemy import BigInteger, Boolean, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class GenTable(BaseModel):
    """代码生成表配置"""

    __tablename__ = "gen_table"

    table_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="数据库表名"
    )
    table_comment: Mapped[str | None] = mapped_column(
        String(256), comment="表注释"
    )
    module_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="模块名"
    )
    entity_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="实体类名"
    )
    page_title: Mapped[str | None] = mapped_column(
        String(64), comment="页面标题"
    )
    api_prefix: Mapped[str | None] = mapped_column(
        String(128), comment="API 前缀"
    )
    author: Mapped[str | None] = mapped_column(
        String(64), comment="作者"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1启用 0禁用"
    )
    remark: Mapped[str | None] = mapped_column(
        Text, comment="备注"
    )


class GenTableColumn(BaseModel):
    """代码生成字段配置"""

    __tablename__ = "gen_table_column"

    table_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="关联 gen_table.id"
    )
    column_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="字段名"
    )
    column_comment: Mapped[str | None] = mapped_column(
        String(256), comment="字段注释"
    )
    data_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="数据库类型"
    )
    udt_name: Mapped[str] = mapped_column(
        String(32), comment="UDT 名称"
    )
    is_nullable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否可空"
    )
    is_primary_key: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否主键"
    )
    is_list: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否列表显示"
    )
    is_form: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="是否表单编辑"
    )
    is_search: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否搜索条件"
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否必填"
    )
    form_component: Mapped[str] = mapped_column(
        String(32), default="input", server_default="input", comment="表单组件"
    )
    dict_type: Mapped[str | None] = mapped_column(
        String(64), comment="字典类型编码"
    )
    foreign_key_table: Mapped[str | None] = mapped_column(
        String(128), comment="外键关联表名"
    )
    sort: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="显示排序"
    )