"""
若茗 PaaS - 数据库模型基类
所有 ORM 模型继承 BaseModel，自动获得：主键、时间戳、软删除、租户字段
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BaseModel(Base):
    """
    所有 ORM 模型的基类。

    字段说明：
        id          - 主键，bigint 自增
        created_at  - 创建时间，自动填充
        updated_at  - 更新时间，自动维护
        is_deleted  - 软删除标记，True=已删除
        tenant_id   - 多租户字段，NULL=平台级数据（超管所属或公共数据）
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="软删除标记"
    )
    tenant_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True, comment="租户ID（NULL=平台级）"
    )
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="创建人"
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="更新人"
    )
