"""
若茗 PaaS - 组织/部门 ORM 模型
Author: ruoming
"""
from sqlalchemy import BigInteger, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysDept(BaseModel):
    """部门/组织架构表（树形结构）"""

    __tablename__ = "sys_dept"

    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="部门名称")
    code: Mapped[str | None] = mapped_column(String(64), comment="部门编码")
    parent_id: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", comment="父部门 ID（0=根部门）"
    )
    ancestors: Mapped[str | None] = mapped_column(
        String(512), comment="祖先 ID 路径，如 0,1,2（用于快速查询子树）"
    )
    leader: Mapped[str | None] = mapped_column(String(64), comment="负责人姓名")
    leader_user_id: Mapped[int | None] = mapped_column(BigInteger, comment="负责人用户 ID")
    phone: Mapped[str | None] = mapped_column(String(20), comment="部门联系电话")
    email: Mapped[str | None] = mapped_column(String(128), comment="部门邮箱")
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1正常 0禁用"
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="显示排序")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")
