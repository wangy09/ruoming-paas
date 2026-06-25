"""
若茗 PaaS - AI Agent 示例种子数据
为 5 种内置场景（chitchat / professional / task / rag / creative）各创建一个 Agent。
依赖：init_data.py 已经执行过（admin 用户、默认租户、至少 1 个模型配置已存在）。

执行方式（在 backend 目录下）：
    python -m scripts.seed_agents
或：
    python scripts/seed_agents.py

可选参数：
    --force       强制重建：删除已存在的同名 Agent 后重新创建
    --reset       完全重置：删除所有 Agent 后重新创建
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


def parse_args() -> dict:
    """解析命令行参数"""
    args = {"force": False, "reset": False}
    for arg in sys.argv[1:]:
        if arg == "--force":
            args["force"] = True
        elif arg == "--reset":
            args["reset"] = True
    return args


async def find_admin(db) -> tuple[int | None, int | None]:
    """查找超管用户，返回 (creator_id, tenant_id)"""
    from sqlalchemy import select
    from app.modules.user.models import SysUser

    # 1. 优先查找 is_superplatform
    result = await db.execute(
        select(SysUser).where(SysUser.is_superplatform == True)  # noqa: E712
    )
    admin = result.scalar_one_or_none()
    if admin:
        return admin.id, admin.tenant_id

    # 2. 兜底：username='admin'
    result = await db.execute(
        select(SysUser).where(SysUser.username == "admin")
    )
    admin = result.scalar_one_or_none()
    if admin:
        return admin.id, admin.tenant_id

    return None, None


async def find_model_config(db) -> int | None:
    """查找可用的模型配置 ID"""
    from sqlalchemy import select
    from app.ai.llm.models import AiModelConfig

    # 1. 优先 is_default=True
    result = await db.execute(
        select(AiModelConfig)
        .where(AiModelConfig.status == 1)
        .where(AiModelConfig.is_default == True)  # noqa: E712
        .order_by(AiModelConfig.id.asc())
        .limit(1)
    )
    model = result.scalar_one_or_none()
    if model:
        return model.id

    # 2. 兜底：任意 status=1 的模型
    result = await db.execute(
        select(AiModelConfig)
        .where(AiModelConfig.status == 1)
        .order_by(AiModelConfig.id.asc())
        .limit(1)
    )
    model = result.scalar_one_or_none()
    if model:
        return model.id

    return None


async def seed_agents() -> None:
    from sqlalchemy import select, delete
    from app.core.logging import setup_logging
    from app.database import AsyncSessionFactory
    from app.ai.agent.models import AiAgent
    from app.ai.llm.models import AiModelConfig
    from app.modules.user.models import SysUser

    args = parse_args()
    force = args["force"]
    reset = args["reset"]

    setup_logging()
    import structlog
    logger = structlog.get_logger(__name__)

    print("\n" + "=" * 70)
    print("若茗 PaaS - AI Agent 种子数据初始化")
    if reset:
        print("  ⚠️  模式: --reset (清空所有 Agent 后重建)")
    elif force:
        print("  ⚠️  模式: --force (覆盖同名 Agent)")
    else:
        print("  ℹ️  模式: 默认 (跳过已存在的 Agent)")
    print("=" * 70)

    async with AsyncSessionFactory() as db:
        # ── 1. 找到超管用户（创建人） ─────────────────────────────────
        creator_id, tenant_id = await find_admin(db)
        if not creator_id:
            print("\n❌ 错误：未找到超管用户，请先执行 init_data.py")
            return
        print(f"\n✓ 找到超管用户: id={creator_id}, tenant_id={tenant_id}")

        # ── 2. 找一个默认模型配置（用作 Agent 的 model_config_id） ────
        model_id = await find_model_config(db)
        if not model_id:
            print("⚠️  警告：未找到可用模型配置，将以 model_config_id=NULL 创建")
            print("   后续可在前端「模型管理」中配置模型后，再编辑 Agent 绑定。")
        else:
            print(f"✓ 找到默认模型: model_config_id={model_id}")

        # ── 3. --reset 模式：清空所有 Agent ─────────────────────────────
        if reset:
            del_result = await db.execute(
                delete(AiAgent).where(AiAgent.id > 0)
            )
            await db.commit()
            print(f"\n🗑️  已清空所有 Agent（删除 {del_result.rowcount} 条）")

        # ── 4. 为每个场景创建 Agent ─────────────────────────────────
        created, updated, skipped = 0, 0, 0
        for tpl in AGENT_TEMPLATES:
            exists_result = await db.execute(
                select(AiAgent).where(AiAgent.name == tpl["name"])
            )
            existing = exists_result.scalar_one_or_none()

            if existing and not force:
                logger.info("agent_skip", name=tpl["name"], reason="已存在")
                skipped += 1
                continue

            if existing and force:
                # 更新已存在的 Agent
                existing.description = tpl["description"]
                existing.model_config_id = model_id
                existing.system_prompt = tpl["system_prompt"]
                existing.default_scene = tpl["default_scene"]
                existing.temperature = tpl["temperature"]
                existing.max_tokens = tpl["max_tokens"]
                existing.memory_type = tpl["memory_type"]
                existing.status = 1
                updated += 1
                logger.info("agent_updated", name=tpl["name"], scene=tpl["default_scene"])
                continue

            # 创建新 Agent
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

        # ── 5. 输出汇总 ──────────────────────────────────────────────
        print("\n" + "-" * 70)
        print(f"✅ Agent 种子数据初始化完成")
        print(f"   新建: {created} 个  |  更新: {updated} 个  |  跳过: {skipped} 个")
        print("-" * 70)
        print("\n场景分布：")
        for tpl in AGENT_TEMPLATES:
            print(f"  • [{tpl['default_scene']:>12}] {tpl['name']:<14} (temp={tpl['temperature']}, memory={tpl['memory_type']})")
        print("\n下一步：登录前端 → AI 管理 → Agent 管理，查看与调试。")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_agents())
