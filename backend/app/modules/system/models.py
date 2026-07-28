"""
若茗 PaaS - 部门 + 字典 ORM 模型
"""
from sqlalchemy import BigInteger, Boolean, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


# ============ 初始化版本模型 ============

class SysInitVersion(BaseModel):
    """初始化版本记录表（用于增量更新）"""

    __tablename__ = "sys_init_version"
    __table_args__ = (
        UniqueConstraint("version", name="uq_init_version"),
    )

    version: Mapped[str] = mapped_column(String(32), nullable=False, comment="版本号（如 20260722.1）")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="版本名称/描述")
    executed_at: Mapped[str] = mapped_column(String(32), nullable=False, comment="执行时间")


# ============ 部门模型 ============

class SysDept(BaseModel):
    """部门表（支持树形结构）"""

    __tablename__ = "sys_dept"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "parent_id", name="uq_tenant_dept_name_parent"),
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="部门名称")
    parent_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="父部门 ID（0=根部门）"
    )
    ancestors: Mapped[str | None] = mapped_column(
        String(512), comment="祖级列表（如 0,1,2），逗号分隔"
    )
    level: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="层级深度（根=1）"
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="显示排序")
    leader: Mapped[str | None] = mapped_column(String(32), comment="负责人")
    leader_id: Mapped[int | None] = mapped_column(BigInteger, comment="负责人用户 ID")
    phone: Mapped[str | None] = mapped_column(String(20), comment="联系电话")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1正常 0停用"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="逻辑删除"
    )
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属租户 ID")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


# ============ 字典模型 ============

class SysDictType(BaseModel):
    """字典类型表"""

    __tablename__ = "sys_dict_type"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_dict_code"),
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="字典类型名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, comment="字典类型编码")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1正常 0停用"
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否系统内置"
    )
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, comment="所属租户")


class SysDictItem(BaseModel):
    """字典项表"""

    __tablename__ = "sys_dict_item"
    __table_args__ = (
        UniqueConstraint("type_id", "value", name="uq_type_item_value"),
    )

    type_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="所属字典类型 ID")
    label: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示标签")
    value: Mapped[str] = mapped_column(String(128), nullable=False, comment="实际值")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="排序")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1正常 0停用"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否默认值"
    )
    css_class: Mapped[str | None] = mapped_column(String(128), comment="样式类")
