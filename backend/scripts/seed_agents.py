"""
若茗 PaaS - AI Agent 示例种子数据
为 5 种内置场景（chitchat / professional / task / rag / creative）各创建一个 Agent。
依赖：init_data.py 已经执行过（admin 用户、默认租户、至少 1 个模型配置已存在）。

执行方式（在 backend 目录下）：
    python -m scripts.seed_agents
或：
    python scripts/seed_agents.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 5 种场景的 Agent 配置
AGENT_TEMPLATES = [
    {
        "name": "闲聊助手",
        "description": "日常闲聊、问候、情感陪伴，适用于客服、问候等场景",
        "default_scene": "chitchat",
        "temperature": 0.9,
        "system_prompt": (
            "你是一个友好、活泼的闲聊助手，名字叫「小茗」。\n"
            "职责：\n"
            "1. 用轻松自然的语气与用户聊天\n"
            "2. 适当表达关心和幽默\n"
            "3. 涉及专业问题时，礼貌引导到专业 Agent\n"
            "风格：亲切、口语化、避免长篇大论。"
        ),
        "max_tokens": 1024,
        "memory_type": "buffer",
    },
    {
        "name": "专业分析师",
        "description": "专业问答、数据分析、报告撰写，逻辑严谨、回答准确",
        "default_scene": "professional",
        "temperature": 0.2,
        "system_prompt": (
            "你是一位资深行业分析师，具备严谨的逻辑思维和广博的专业知识。\n"
            "职责：\n"
            "1. 对专业问题给出准确、有依据的回答\n"
            "2. 必要时拆解问题、列出关键要点\n"
            "3. 涉及数据时给出明确的推理过程\n"
            "风格：客观、严谨、结构化（多用列表/小标题）。\n"
            "如不确定，请明确指出并说明需要哪些额外信息。"
        ),
        "max_tokens": 4096,
        "memory_type": "summary",
    },
    {
        "name": "编程助理",
        "description": "代码生成、Bug 排查、技术实现，支持多语言",
        "default_scene": "task",
        "temperature": 0.3,
        "system_prompt": (
            "你是一位经验丰富的全栈工程师，擅长 Python / TypeScript / Go / Java 等主流语言。\n"
            "职责：\n"
            "1. 根据需求生成高质量、可运行的代码\n"
            "2. 排查 Bug 并给出修复方案\n"
            "3. 解释技术方案时给出代码示例\n"
            "风格：先给结论，再给实现，最后说明关键点。\n"
            "代码必须：可运行、关键处有注释、命名规范。"
        ),
        "max_tokens": 4096,
        "memory_type": "buffer",
    },
    {
        "name": "知识库问答",
        "description": "基于企业知识库的文档问答，自动检索相关内容并引用出处",
        "default_scene": "rag",
        "temperature": 0.1,
        "system_prompt": (
            "你是企业知识库助手，严格基于检索到的文档内容回答问题。\n"
            "职责：\n"
            "1. 仅使用【知识库检索】返回的内容作答\n"
            "2. 回答时引用具体的来源文档和片段\n"
            "3. 文档中找不到答案时，明确告知用户「知识库中未找到相关信息」\n"
            "4. 禁止凭空编造数据\n"
            "风格：精准、可溯源、简明扼要。"
        ),
        "max_tokens": 2048,
        "memory_type": "vector",
    },
    {
        "name": "创意写手",
        "description": "文案创作、头脑风暴、营销策划，富有想象力和感染力",
        "default_scene": "creative",
        "temperature": 1.0,
        "system_prompt": (
            "你是一位富有想象力的创意写手，擅长文案、营销、故事和品牌策划。\n"
            "职责：\n"
            "1. 提供多个角度的创意方案\n"
            "2. 文案有感染力、有画面感\n"
            "3. 头脑风暴时不设限，鼓励发散\n"
            "风格：生动、跳跃、富有诗意。\n"
            "如需收敛，明确告知用户后会切回理性输出。"
        ),
        "max_tokens": 4096,
        "memory_type": "buffer",
    },
]


async def seed_agents() -> None:
    from sqlalchemy import select
    from app.config import settings
    from app.core.logging import setup_logging
    from app.database import AsyncSessionFactory
    from app.ai.agent.models import AiAgent
    from app.ai.llm.models import AiModelConfig
    from app.modules.user.models import SysUser

    setup_logging()
    import structlog
    logger = structlog.get_logger(__name__)

    async with AsyncSessionFactory() as db:
        # ── 1. 找到超管用户（创建人） ─────────────────────────────────
        admin_result = await db.execute(
            select(SysUser).where(SysUser.is_superplatform == True)  # noqa: E712
        )
        admin = admin_result.scalar_one_or_none()
        if not admin:
            logger.error("admin_not_found", msg="未找到超管用户，请先执行 init_data.py")
            return
        creator_id = admin.id
        tenant_id = admin.tenant_id  # 平台级用户 tenant_id 通常为 None
        logger.info("creator_found", user_id=creator_id, tenant_id=tenant_id)

        # ── 2. 找一个默认模型配置（用作 Agent 的 model_config_id） ────
        model_result = await db.execute(
            select(AiModelConfig)
            .where(AiModelConfig.status == 1)
            .where(AiModelConfig.is_default == True)  # noqa: E712
            .order_by(AiModelConfig.id.asc())
            .limit(1)
        )
        model = model_result.scalar_one_or_none()
        if not model:
            # 兜底：取任意一个启用的模型
            fallback_result = await db.execute(
                select(AiModelConfig)
                .where(AiModelConfig.status == 1)
                .order_by(AiModelConfig.id.asc())
                .limit(1)
            )
            model = fallback_result.scalar_one_or_none()
        if not model:
            logger.warning(
                "no_model_config",
                msg="未找到可用模型配置，将以 model_config_id=NULL 创建（Agent 执行时需先配置模型）",
            )
            model_id = None
        else:
            model_id = model.id
            logger.info("model_config_used", model_id=model_id, model_name=model.name)

        # ── 3. 为每个场景创建 Agent（已存在则跳过） ─────────────────
        created, skipped = 0, 0
        for tpl in AGENT_TEMPLATES:
            exists_result = await db.execute(
                select(AiAgent).where(AiAgent.name == tpl["name"])
            )
            if exists_result.scalar_one_or_none():
                logger.info("agent_skip", name=tpl["name"], reason="已存在")
                skipped += 1
                continue

            agent = AiAgent(
                name=tpl["name"],
                description=tpl["description"],
                model_config_id=model_id,
                system_prompt=tpl["system_prompt"],
                default_scene=tpl["default_scene"],
                max_rounds=10,
                temperature=tpl["temperature"],
                max_tokens=tpl["max_tokens"],
                node_timeout_sec=60,
                memory_type=tpl["memory_type"],
                tool_ids=[],
                kb_ids=[],
                status=1,
                tenant_id=tenant_id,
                created_by=creator_id,
            )
            db.add(agent)
            created += 1
            logger.info(
                "agent_created",
                name=tpl["name"],
                scene=tpl["default_scene"],
                temperature=tpl["temperature"],
            )

        await db.commit()

        # ── 4. 输出汇总 ──────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("✅ Agent 种子数据初始化完成")
        print(f"   新建：{created} 个  |  跳过（已存在）：{skipped} 个")
        print("=" * 60)
        print("\n场景分布：")
        for tpl in AGENT_TEMPLATES:
            marker = "新建" if created > 0 else "已存在"
            print(f"  • [{tpl['default_scene']:>12}] {tpl['name']:<14} (temp={tpl['temperature']})  {marker}")
        print("\n下一步：登录前端 → AI 管理 → Agent 管理，查看与调试。")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_agents())
