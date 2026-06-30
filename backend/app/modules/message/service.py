"""
若茗 PaaS - 消息中心服务
"""
from datetime import datetime, timezone

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.core.utils.pagination import PageParams
from app.modules.message.models import SysNotice, SysUserMessage
from app.modules.message.schemas import NoticeCreate, NoticeUpdate
from app.modules.system.models import SysDept
from app.modules.user.models import SysUser


class MessageService:
    """消息中心业务服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def list_notices(
        self,
        page_params: PageParams,
        keyword: str | None = None,
        status: int | None = None,
        target_type: str | None = None,
    ) -> dict:
        conditions = [SysNotice.is_deleted == False]
        if self.tenant_id is not None:
            conditions.append(SysNotice.tenant_id == self.tenant_id)
        if keyword:
            conditions.append(SysNotice.title.ilike(f"%{keyword}%"))
        if status is not None:
            conditions.append(SysNotice.status == status)
        if target_type:
            conditions.append(SysNotice.target_type == target_type)

        total = await self.db.scalar(select(func.count(SysNotice.id)).where(*conditions))
        rows = await self.db.execute(
            select(SysNotice)
            .where(*conditions)
            .order_by(desc(SysNotice.created_at))
            .offset(page_params.offset)
            .limit(page_params.page_size)
        )
        return {
            "items": rows.scalars().all(),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def get_notice(self, notice_id: int) -> SysNotice:
        conditions = [SysNotice.id == notice_id, SysNotice.is_deleted == False]
        if self.tenant_id is not None:
            conditions.append(SysNotice.tenant_id == self.tenant_id)
        notice = await self.db.scalar(select(SysNotice).where(*conditions))
        if not notice:
            raise NotFoundException("公告")
        return notice

    async def create_notice(self, data: NoticeCreate, publisher: SysUser) -> SysNotice:
        self._validate_target(data.target_type, data.target_dept_ids, data.target_user_ids)

        notice = SysNotice(
            title=data.title,
            content=data.content,
            target_type=data.target_type,
            target_dept_ids=data.target_dept_ids or None,
            target_user_ids=data.target_user_ids or None,
            publisher_id=publisher.id,
            tenant_id=None if publisher.is_superplatform else publisher.tenant_id,
            remark=data.remark,
        )
        self.db.add(notice)
        await self.db.flush()

        if data.publish_now:
            await self.publish_notice(notice, publisher)
        return notice

    async def update_notice(self, notice_id: int, data: NoticeUpdate) -> SysNotice:
        notice = await self.get_notice(notice_id)
        if notice.status == 1:
            raise ValidationException("已发布公告不能编辑")

        update_data = data.model_dump(exclude_unset=True)
        target_type = update_data.get("target_type", notice.target_type)
        target_dept_ids = update_data.get("target_dept_ids", notice.target_dept_ids or [])
        target_user_ids = update_data.get("target_user_ids", notice.target_user_ids or [])
        self._validate_target(target_type, target_dept_ids, target_user_ids)

        for key, value in update_data.items():
            setattr(notice, key, value or None if key in {"target_dept_ids", "target_user_ids"} else value)
        await self.db.flush()
        return notice

    async def delete_notice(self, notice_id: int) -> None:
        notice = await self.get_notice(notice_id)
        notice.is_deleted = True

    async def publish_notice(self, notice: SysNotice, publisher: SysUser) -> SysNotice:
        if notice.status == 1:
            raise ValidationException("公告已发布")

        users = await self._resolve_target_users(notice, publisher)
        now = datetime.now(tz=timezone.utc)
        for user in users:
            self.db.add(SysUserMessage(
                notice_id=notice.id,
                user_id=user.id,
                sender_id=publisher.id,
                title=notice.title,
                content=notice.content,
                message_type=notice.notice_type,
                tenant_id=user.tenant_id,
            ))

        notice.status = 1
        notice.published_at = now
        notice.publisher_id = publisher.id
        notice.receiver_count = len(users)
        await self.db.flush()
        return notice

    async def list_user_messages(
        self,
        user_id: int,
        page_params: PageParams,
        is_read: bool | None = None,
    ) -> dict:
        conditions = [
            SysUserMessage.user_id == user_id,
            SysUserMessage.is_deleted == False,
        ]
        if is_read is not None:
            conditions.append(SysUserMessage.is_read == is_read)

        total = await self.db.scalar(select(func.count(SysUserMessage.id)).where(*conditions))
        rows = await self.db.execute(
            select(SysUserMessage)
            .where(*conditions)
            .order_by(desc(SysUserMessage.created_at))
            .offset(page_params.offset)
            .limit(page_params.page_size)
        )
        return {
            "items": rows.scalars().all(),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def unread_summary(self, user_id: int) -> dict:
        conditions = [
            SysUserMessage.user_id == user_id,
            SysUserMessage.is_deleted == False,
            SysUserMessage.is_read == False,
        ]
        unread_count = await self.db.scalar(select(func.count(SysUserMessage.id)).where(*conditions))
        latest = await self.db.scalar(
            select(SysUserMessage).where(*conditions).order_by(desc(SysUserMessage.created_at)).limit(1)
        )
        return {"unread_count": unread_count or 0, "latest": latest}

    async def mark_read(self, message_id: int, user_id: int) -> SysUserMessage:
        msg = await self.db.scalar(
            select(SysUserMessage).where(
                SysUserMessage.id == message_id,
                SysUserMessage.user_id == user_id,
                SysUserMessage.is_deleted == False,
            )
        )
        if not msg:
            raise NotFoundException("消息")
        if not msg.is_read:
            msg.is_read = True
            msg.read_at = datetime.now(tz=timezone.utc)
        return msg

    async def mark_all_read(self, user_id: int) -> int:
        rows = await self.db.execute(
            select(SysUserMessage).where(
                SysUserMessage.user_id == user_id,
                SysUserMessage.is_deleted == False,
                SysUserMessage.is_read == False,
            )
        )
        messages = rows.scalars().all()
        now = datetime.now(tz=timezone.utc)
        for msg in messages:
            msg.is_read = True
            msg.read_at = now
        return len(messages)

    async def delete_user_message(self, message_id: int, user_id: int) -> None:
        msg = await self.db.scalar(
            select(SysUserMessage).where(
                SysUserMessage.id == message_id,
                SysUserMessage.user_id == user_id,
                SysUserMessage.is_deleted == False,
            )
        )
        if not msg:
            raise NotFoundException("消息")
        msg.is_deleted = True

    async def _resolve_target_users(self, notice: SysNotice, publisher: SysUser) -> list[SysUser]:
        conditions = [SysUser.is_deleted == False, SysUser.status == 1]
        if not publisher.is_superplatform:
            conditions.append(SysUser.tenant_id == publisher.tenant_id)

        if notice.target_type == "all":
            pass
        elif notice.target_type == "user":
            user_ids = notice.target_user_ids or []
            if not user_ids:
                raise ValidationException("请选择接收用户")
            conditions.append(SysUser.id.in_(user_ids))
        elif notice.target_type == "dept":
            dept_ids = await self._expand_dept_ids(notice.target_dept_ids or [], publisher)
            if not dept_ids:
                raise ValidationException("请选择接收部门")
            conditions.append(SysUser.dept_id.in_(dept_ids))
        else:
            raise ValidationException("投放范围不正确")

        rows = await self.db.execute(select(SysUser).where(*conditions).order_by(SysUser.id))
        users = rows.scalars().all()
        if not users:
            raise ValidationException("没有匹配的接收用户")
        return users

    async def _expand_dept_ids(self, dept_ids: list[int], publisher: SysUser) -> list[int]:
        if not dept_ids:
            return []

        conditions = [SysDept.is_deleted == False]
        if not publisher.is_superplatform:
            conditions.append(SysDept.tenant_id == publisher.tenant_id)

        descendant_conditions = [SysDept.id.in_(dept_ids)]
        for dept_id in dept_ids:
            descendant_conditions.append(SysDept.ancestors == str(dept_id))
            descendant_conditions.append(SysDept.ancestors.like(f"{dept_id},%"))
            descendant_conditions.append(SysDept.ancestors.like(f"%,{dept_id},%"))
            descendant_conditions.append(SysDept.ancestors.like(f"%,{dept_id}"))

        rows = await self.db.execute(
            select(SysDept.id).where(and_(*conditions), or_(*descendant_conditions))
        )
        return list({row[0] for row in rows.all()})

    @staticmethod
    def _validate_target(target_type: str, dept_ids: list[int] | None, user_ids: list[int] | None) -> None:
        if target_type == "dept" and not dept_ids:
            raise ValidationException("部门公告需要选择接收部门")
        if target_type == "user" and not user_ids:
            raise ValidationException("指定用户公告需要选择接收用户")
