"""
若茗 PaaS - 权限 ORM 模型（RBAC + 菜单 + 按钮 + 列权限统一）
Author: ruoming
"""
from sqlalchemy import BigInteger, Boolean, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysRole(BaseModel):
    """角色表（支持角色继承）"""

    __tablename__ = "sys_role"

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="角色标识（全局唯一）"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="角色描述")
    parent_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="父角色 ID（0=无父角色，支持角色继承）"
    )
    data_scope: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        server_default="1",
        comment="数据范围：1全部 2本部门及子部门 3本部门 4本人 5自定义",
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1启用 0禁用"
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="显示排序")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class SysPermission(BaseModel):
    """
    权限（资源）表 - 统一管理所有类型权限，包含菜单结构。
    type=menu 时，path/component/icon 等路由字段有效。
    """

    __tablename__ = "sys_permission"

    parent_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="父权限 ID（0=根）"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="权限名称（展示用）")
    code: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="权限标识，如 system:user:create"
    )
    perm_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="类型：menu/button/column/api/data"
    )

    # 菜单类型专用字段（perm_type=menu 时有效）
    path: Mapped[str | None] = mapped_column(String(256), comment="前端路由路径")
    component: Mapped[str | None] = mapped_column(String(256), comment="前端组件路径")
    redirect: Mapped[str | None] = mapped_column(String(256), comment="重定向路径")
    icon: Mapped[str | None] = mapped_column(String(64), comment="菜单图标")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="显示排序")
    is_visible: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", comment="菜单是否显示"
    )
    is_cache: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否缓存页面（keep-alive）"
    )
    is_external: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否外链"
    )

    # 按钮/API 类型字段
    resource: Mapped[str | None] = mapped_column(String(256), comment="对应后端 API 路径")
    method: Mapped[str | None] = mapped_column(
        String(10), comment="HTTP 方法（API 类型使用）：GET/POST/PUT/DELETE"
    )
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")


class SysColumnPermission(BaseModel):
    """表格列权限配置"""

    __tablename__ = "sys_column_permission"
    __table_args__ = (
        UniqueConstraint("resource_key", "column_key", name="uq_col_perm_resource_column"),
    )

    resource_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="资源标识，如 user_list"
    )
    column_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="列字段名")
    column_label: Mapped[str] = mapped_column(String(64), nullable=False, comment="列展示名")
    permission_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="关联权限 ID（sys_permission.id）"
    )
    is_editable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否可编辑（区别于仅可见）"
    )


class SysUserRole(BaseModel):
    """用户-角色关联表"""

    __tablename__ = "sys_user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户 ID")
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="角色 ID")


class SysRolePermission(BaseModel):
    """角色-权限关联表"""

    __tablename__ = "sys_role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="角色 ID")
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="权限 ID")


class SysUserPermission(BaseModel):
    """用户直接权限（特例授权，支持白名单/黑名单）"""

    __tablename__ = "sys_user_permission"
    __table_args__ = (
        UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户 ID")
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="权限 ID")
    is_exclude: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="True=排除此权限（黑名单），False=授予此权限（白名单）",
    )


class SysRoleDept(BaseModel):
    """角色-自定义部门（数据权限 scope=5 自定义时使用）"""

    __tablename__ = "sys_role_dept"
    __table_args__ = (
        UniqueConstraint("role_id", "dept_id", name="uq_role_dept"),
    )

    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="角色 ID")
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="部门 ID")
