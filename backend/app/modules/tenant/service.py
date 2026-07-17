"""
若茗 PaaS - 租户管理 Service
Author: ruoming
"""
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.core.security import hash_password
from app.modules.tenant.models import SysTenant, SysTenantUsage
from app.modules.tenant.schemas import TenantCreate, TenantUpdate, TenantQuotaUpdate, TenantApprove
from app.modules.user.models import SysUser
from app.modules.permission.models import SysRole, SysUserRole


class TenantService:
    """租户服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        status: int | None = None,
        plan: str | None = None,
    ) -> tuple[list[SysTenant], int]:
        """获取租户列表"""
        conditions = [SysTenant.is_deleted == False]  # noqa: E712

        if keyword:
            conditions.append(
                SysTenant.name.like(f"%{keyword}%") | SysTenant.code.like(f"%{keyword}%")
            )
        if status is not None:
            conditions.append(SysTenant.status == status)
        if plan:
            conditions.append(SysTenant.plan == plan)

        stmt = select(SysTenant).where(*conditions).order_by(SysTenant.created_at.desc())

        total_stmt = select(func.count(SysTenant.id)).where(*conditions)
        total = await self.db.scalar(total_stmt)

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.scalars(stmt)
        return result.all(), total or 0

    async def get_by_id(self, tenant_id: int) -> SysTenant | None:
        """根据ID获取租户"""
        stmt = select(SysTenant).where(SysTenant.id == tenant_id, SysTenant.is_deleted == False)
        return await self.db.scalar(stmt)

    async def get_by_code(self, code: str) -> SysTenant | None:
        """根据code获取租户"""
        stmt = select(SysTenant).where(SysTenant.code == code, SysTenant.is_deleted == False)
        return await self.db.scalar(stmt)

    async def create(self, data: TenantCreate, registered_by: int | None = None) -> SysTenant:
        """创建租户"""
        existing = await self.get_by_code(data.code)
        if existing:
            raise BusinessException(code=400, message=f"租户标识 '{data.code}' 已存在")

        now = datetime.now()
        trial_end_at = None
        if data.plan == "trial":
            trial_end_at = now + timedelta(days=14)

        tenant = SysTenant(
            name=data.name,
            code=data.code,
            plan=data.plan,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            remark=data.remark,
            trial_end_at=trial_end_at,
            registered_by=registered_by,
            status=2 if data.plan == "trial" else 0,
        )

        self.db.add(tenant)
        await self.db.flush()
        await self.db.refresh(tenant)

        existing_user = await self.db.execute(
            select(SysUser.id).where(
                SysUser.username == data.admin_username,
                SysUser.is_deleted == False,
            )
        )
        if existing_user.scalar_one_or_none():
            raise BusinessException(code=400, message=f"用户名 '{data.admin_username}' 已存在")

        admin_user = SysUser(
            username=data.admin_username,
            password=hash_password(data.admin_password),
            nickname=data.admin_username,
            email=data.admin_email,
            tenant_id=tenant.id,
            status=1,
        )
        self.db.add(admin_user)
        await self.db.flush()
        await self.db.refresh(admin_user)

        role_result = await self.db.execute(
            select(SysRole.id).where(
                SysRole.code == "tenant:admin",
                SysRole.is_deleted == False,
            )
        )
        tenant_admin_role_id = role_result.scalar_one_or_none()
        if tenant_admin_role_id:
            user_role = SysUserRole(
                user_id=admin_user.id,
                role_id=tenant_admin_role_id,
                tenant_id=tenant.id,
            )
            self.db.add(user_role)

        await self.db.commit()
        return tenant

    async def update(self, tenant_id: int, data: TenantUpdate) -> SysTenant:
        """更新租户"""
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException("租户")

        if data.name is not None:
            tenant.name = data.name
        if data.domain is not None:
            tenant.domain = data.domain
        if data.logo is not None:
            tenant.logo = data.logo
        if data.plan is not None:
            tenant.plan = data.plan
            if data.plan == "trial" and not tenant.trial_end_at:
                tenant.trial_end_at = datetime.now() + timedelta(days=14)
                tenant.status = 2
        if data.status is not None:
            tenant.status = data.status
        if data.contact_email is not None:
            tenant.contact_email = data.contact_email
        if data.contact_phone is not None:
            tenant.contact_phone = data.contact_phone
        if data.remark is not None:
            tenant.remark = data.remark

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def update_quota(self, tenant_id: int, data: TenantQuotaUpdate) -> SysTenant:
        """更新租户配额"""
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException("租户")

        if data.max_users is not None:
            tenant.max_users = data.max_users
        if data.max_storage_gb is not None:
            tenant.max_storage_gb = data.max_storage_gb
        if data.max_api_calls_day is not None:
            tenant.max_api_calls_day = data.max_api_calls_day
        if data.max_ai_tokens_day is not None:
            tenant.max_ai_tokens_day = data.max_ai_tokens_day
        if data.max_concurrent is not None:
            tenant.max_concurrent = data.max_concurrent

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def approve(self, tenant_id: int, data: TenantApprove, approved_by: int) -> SysTenant:
        """审核租户"""
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException("租户")

        tenant.status = data.status
        tenant.approved_by = approved_by
        tenant.approved_at = datetime.now()
        tenant.remark = data.remark

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def delete(self, tenant_id: int) -> None:
        """删除租户（软删除）"""
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundException("租户")

        tenant.is_deleted = True
        await self.db.commit()

    async def get_usage(
        self,
        tenant_id: int | None = None,
        stat_date: str | None = None,
        limit: int = 30,
    ) -> list[SysTenantUsage]:
        """获取租户用量统计"""
        conditions = [SysTenantUsage.is_deleted == False]

        if tenant_id:
            conditions.append(SysTenantUsage.tenant_id == tenant_id)
        if stat_date:
            conditions.append(SysTenantUsage.stat_date == stat_date)

        stmt = (
            select(SysTenantUsage)
            .where(*conditions)
            .order_by(SysTenantUsage.stat_date.desc())
            .limit(limit)
        )

        result = await self.db.scalars(stmt)
        return result.all()