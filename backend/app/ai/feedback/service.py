"""
若茗 PaaS - AI 反馈管理服务层
Author: ruoming
"""
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.models import AiAgent
from app.ai.conversation.models import AiMessageFeedback
from app.ai.feedback.schemas import FeedbackCreate, FeedbackUpdate
from app.core.exceptions import NotFoundException, ValidationException
from app.core.utils.pagination import PageParams
from app.modules.message.models import SysUserMessage

logger = structlog.get_logger(__name__)


class FeedbackService:
    """系统问题反馈服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # ── 用户端：创建 / 查询自己的反馈 ──────────────────────────────────────────

    async def create(
        self,
        user_id: int,
        data: FeedbackCreate,
        tenant_id: int | None = None,
    ) -> AiMessageFeedback:
        """
        创建系统反馈（用户可以提交 Bug 报告、功能建议、使用问题等）。

        如果关联了 message_id，会自动冗余 conversation_id 和 agent_id。
        """
        # 自动获取关联信息
        conversation_id = None
        agent_id = data.agent_id

        if data.message_id:
            # 如果关联了 AI 消息，自动获取对话和 Agent 信息
            from app.ai.conversation.models import AiMessage
            msg = await self.db.get(AiMessage, data.message_id)
            if msg:
                conversation_id = msg.conversation_id
                if not agent_id:
                    from app.ai.conversation.models import AiConversation
                    conv = await self.db.get(AiConversation, msg.conversation_id)
                    if conv:
                        agent_id = conv.agent_id

        # 新建反馈
        feedback = AiMessageFeedback(
            title=data.title,
            category=data.category,
            content=data.content,
            severity=data.severity,
            message_id=data.message_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            user_id=user_id,
            rating=None,  # 系统反馈不需要强制评分
            tags=data.tags,
            screenshot_url=data.screenshot_url,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.refresh(feedback)
        logger.info(
            "feedback_created",
            feedback_id=feedback.id,
            category=data.category,
            user_id=user_id,
        )
        return feedback

    async def list_my_feedbacks(
        self,
        user_id: int,
        page_params: PageParams,
    ) -> tuple[list[dict], int]:
        """用户查看自己的反馈列表"""
        stmt = (
            select(
                AiMessageFeedback,
                AiAgent.name.label("agent_name"),
            )
            .outerjoin(AiAgent, AiAgent.id == AiMessageFeedback.agent_id)
            .where(
                AiMessageFeedback.is_deleted == False,  # noqa: E712
                AiMessageFeedback.user_id == user_id,
            )
        )

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.execute(
                stmt.order_by(AiMessageFeedback.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.page_size)
            )
        ).all()

        result = [self._row_to_dict(row) for row in items]
        return result, count or 0

    # ── 管理端：列表 / 统计 / 处理 / 删除 ──────────────────────────────────────

    async def list_feedbacks(
        self,
        filters: dict,
        page_params: PageParams,
    ) -> tuple[list[dict], int]:
        """
        管理端反馈列表（join SysUser 取 username，join AiAgent 取 name）。
        非超管用户按 tenant_id 过滤。
        """
        # 延迟 import 避免循环引用
        from app.modules.user.models import SysUser

        stmt = (
            select(
                AiMessageFeedback,
                AiAgent.name.label("agent_name"),
                SysUser.username.label("username"),
            )
            .select_from(AiMessageFeedback)
            .outerjoin(AiAgent, AiAgent.id == AiMessageFeedback.agent_id)
            .outerjoin(SysUser, SysUser.id == AiMessageFeedback.user_id)
            .where(AiMessageFeedback.is_deleted == False)  # noqa: E712
        )

        # 租户过滤
        stmt = self._apply_tenant_filter(stmt)
        # 业务过滤
        stmt = self._apply_filters(stmt, filters)

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.execute(
                stmt.order_by(AiMessageFeedback.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.page_size)
            )
        ).all()

        result = [self._row_to_dict(row) for row in items]
        return result, count or 0

    async def stats(self, filters: dict) -> dict:
        """
        反馈统计：
        - total / bug_count / feature_count / usage_count / other_count
        - pending_count / resolved_count
        - daily: 按天分组的反馈趋势
        - category_distribution: 分类分布
        """
        base = select(AiMessageFeedback).where(AiMessageFeedback.is_deleted == False)  # noqa: E712
        base = self._apply_tenant_filter(base)
        base = self._apply_filters(base, filters)

        # ── 汇总统计 ──
        summary_stmt = select(
            func.count().label("total"),
            func.count().filter(AiMessageFeedback.category == "bug").label("bug_count"),
            func.count().filter(AiMessageFeedback.category == "feature").label("feature_count"),
            func.count().filter(AiMessageFeedback.category == "usage").label("usage_count"),
            func.count().filter(AiMessageFeedback.category == "other").label("other_count"),
            func.count().filter(AiMessageFeedback.status == "pending").label("pending_count"),
            func.count().filter(AiMessageFeedback.status == "resolved").label("resolved_count"),
        ).select_from(base.subquery())

        row = (await self.db.execute(summary_stmt)).one()
        total = row.total or 0

        # ── 每日趋势 ──
        day_col = func.date_trunc("day", AiMessageFeedback.created_at).label("day")
        daily_stmt = (
            select(
                day_col,
                func.count().label("total"),
            )
            .select_from(AiMessageFeedback)
            .where(AiMessageFeedback.is_deleted == False)  # noqa: E712
        )
        daily_stmt = self._apply_tenant_filter(daily_stmt)
        daily_stmt = self._apply_filters(daily_stmt, filters)
        daily_stmt = daily_stmt.group_by(day_col).order_by(day_col)

        daily_rows = (await self.db.execute(daily_stmt)).all()
        daily = [
            {
                "date": r.day.isoformat() if r.day else None,
                "total": r.total or 0,
            }
            for r in daily_rows
        ]

        # ── 分类分布 ──
        category_col = AiMessageFeedback.category.label("category")
        category_stmt = (
            select(category_col, func.count().label("count"))
            .select_from(AiMessageFeedback)
            .where(AiMessageFeedback.is_deleted == False)  # noqa: E712
        )
        category_stmt = self._apply_tenant_filter(category_stmt)
        category_stmt = self._apply_filters(category_stmt, filters)
        category_stmt = category_stmt.group_by(category_col).order_by(func.count().desc())

        category_rows = (await self.db.execute(category_stmt)).all()
        category_distribution = [
            {"category": r.category, "count": r.count or 0} for r in category_rows
        ]

        return {
            "total": total,
            "bug_count": row.bug_count or 0,
            "feature_count": row.feature_count or 0,
            "usage_count": row.usage_count or 0,
            "other_count": row.other_count or 0,
            "pending_count": row.pending_count or 0,
            "resolved_count": row.resolved_count or 0,
            "daily": daily,
            "category_distribution": category_distribution,
        }

    async def update(
        self,
        feedback_id: int,
        data: FeedbackUpdate,
        admin_id: int,
    ) -> AiMessageFeedback:
        """管理员处理反馈（更新 status/reply/replied_by/replied_at）"""
        feedback = await self._get_feedback_or_raise(feedback_id)

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ValidationException("未提供任何更新字段")

        if data.status is not None:
            feedback.status = data.status
        if data.reply is not None:
            feedback.reply = data.reply
            feedback.replied_by = admin_id
            feedback.replied_at = datetime.now(UTC)

        feedback.updated_by = admin_id
        await self.db.flush()
        await self.db.refresh(feedback)

        # 如果管理员回复了反馈，给反馈提交人发送站内通知
        if data.reply:
            await self._send_feedback_reply_notification(feedback, admin_id)

        logger.info(
            "feedback_updated_by_admin",
            feedback_id=feedback_id,
            admin_id=admin_id,
            status=feedback.status,
        )
        return feedback

    async def delete(self, feedback_id: int) -> bool:
        """软删除反馈"""
        feedback = await self._get_feedback_or_raise(feedback_id)
        feedback.is_deleted = True
        await self.db.flush()
        logger.info("feedback_deleted", feedback_id=feedback_id)
        return True

    # ── 内部工具方法 ────────────────────────────────────────────────────────────

    async def _get_feedback_or_raise(self, feedback_id: int) -> AiMessageFeedback:
        """按 ID 获取反馈（带租户过滤 + 软删除过滤），不存在则抛 404"""
        stmt = select(AiMessageFeedback).where(
            AiMessageFeedback.id == feedback_id,
            AiMessageFeedback.is_deleted == False,  # noqa: E712
        )
        stmt = self._apply_tenant_filter(stmt)
        feedback = await self.db.scalar(stmt)
        if not feedback:
            raise NotFoundException("反馈")
        return feedback

    async def _send_feedback_reply_notification(
        self,
        feedback: AiMessageFeedback,
        admin_id: int,
    ) -> None:
        """管理员回复反馈时，给反馈提交人发送站内通知"""
        try:
            category_labels = {
                "bug": "Bug 报告",
                "feature": "功能建议",
                "usage": "使用问题",
                "other": "其他反馈",
            }
            cat_label = category_labels.get(feedback.category, "反馈")

            title = f"您的{cat_label}已收到回复"
            content = (
                f"您提交的反馈「{feedback.title}」已收到管理员回复：\n\n"
                f"{feedback.reply}\n\n"
                f"请登录平台查看详情。"
            )

            message = SysUserMessage(
                notice_id=None,
                user_id=feedback.user_id,
                sender_id=admin_id,
                title=title,
                content=content,
                message_type="feedback",
                tenant_id=feedback.tenant_id,
            )
            self.db.add(message)
            await self.db.flush()
            logger.info(
                "feedback_reply_notification_sent",
                feedback_id=feedback.id,
                recipient_user_id=feedback.user_id,
                admin_id=admin_id,
            )
        except Exception as e:
            # 通知发送失败不影响反馈处理主流程
            logger.error(
                "feedback_reply_notification_failed",
                feedback_id=feedback.id,
                error=str(e),
            )

    def _apply_tenant_filter(self, stmt):
        """注入租户过滤条件（tenant_id 为 None 时不过滤，即超管查看全量）"""
        if self.tenant_id is not None:
            stmt = stmt.where(AiMessageFeedback.tenant_id == self.tenant_id)
        return stmt

    def _apply_filters(self, stmt, filters: dict):
        """应用业务过滤条件"""
        category = filters.get("category")
        if category:
            stmt = stmt.where(AiMessageFeedback.category == category)

        severity = filters.get("severity")
        if severity:
            stmt = stmt.where(AiMessageFeedback.severity == severity)

        status = filters.get("status")
        if status:
            stmt = stmt.where(AiMessageFeedback.status == status)

        agent_id = filters.get("agent_id")
        if agent_id is not None:
            stmt = stmt.where(AiMessageFeedback.agent_id == agent_id)

        user_id = filters.get("user_id")
        if user_id is not None:
            stmt = stmt.where(AiMessageFeedback.user_id == user_id)

        start_time = filters.get("start_time")
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                stmt = stmt.where(AiMessageFeedback.created_at >= start_dt)
            except ValueError:
                pass

        end_time = filters.get("end_time")
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time)
                stmt = stmt.where(AiMessageFeedback.created_at <= end_dt)
            except ValueError:
                pass

        return stmt

    @staticmethod
    def _row_to_dict(row) -> dict:
        """将 join 查询的 Row 转为字典（含 username / agent_name 冗余字段）"""
        feedback: AiMessageFeedback = row[0]
        agent_name = row[1] if len(row) > 1 else None
        username = row[2] if len(row) > 2 else None

        return {
            "id": feedback.id,
            "title": feedback.title,
            "category": feedback.category,
            "content": feedback.content,
            "severity": feedback.severity,
            "message_id": feedback.message_id,
            "conversation_id": feedback.conversation_id,
            "agent_id": feedback.agent_id,
            "user_id": feedback.user_id,
            "rating": feedback.rating,
            "tags": feedback.tags,
            "screenshot_url": feedback.screenshot_url,
            "status": feedback.status,
            "reply": feedback.reply,
            "replied_by": feedback.replied_by,
            "replied_at": feedback.replied_at,
            "created_at": feedback.created_at,
            "username": username,
            "agent_name": agent_name,
        }
