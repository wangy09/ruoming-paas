"""
若茗 PaaS - Agent 执行器
封装 LangChain，向外只暴露自定义类型（AgentRunResult），不泄露任何 langchain.* 类型。
LangChain 版本升级只需改此文件内部。
Author: ruoming
"""
from __future__ import annotations

import asyncio
import time
import uuid
from copy import deepcopy
from typing import TYPE_CHECKING, Any, AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.models import AiAgent, AiSceneConfig
from app.ai.agent.schemas import AgentRunResult
from app.ai.scene.router import SceneRouter, SceneRouteResult
from app.core.exceptions import AppException

if TYPE_CHECKING:
    from app.ai.tool.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class AgentTimeoutError(AppException):
    def __init__(self, message: str = "Agent 执行超时"):
        super().__init__(status_code=504, message=message)


class AgentRunner:
    """
    单 Agent 执行器。
    - 负责场景路由 → 参数合并 → RAG 检索 → LangChain 推理
    - 流式：返回 AsyncGenerator
    - 非流式：返回 AgentRunResult
    """

    def __init__(
        self,
        agent: AiAgent,
        db: AsyncSession,
        tool_registry: "ToolRegistry | None" = None,
    ) -> None:
        self.agent = agent
        self.db = db
        self.tool_registry = tool_registry

    async def run(
        self,
        user_message: str,
        *,
        session_id: str | None = None,
        conversation_history: list[dict] | None = None,
        stream: bool = False,
        scene_type: str | None = None,
        has_attachment: bool = False,
        timeout_sec: int | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AgentRunResult:
        """
        执行 Agent，支持场景路由 + RAG + 超时控制。
        stream=True 时请使用 stream_run()。
        """
        sid = session_id or str(uuid.uuid4())
        timeout = timeout_sec or self.agent.node_timeout_sec or 60

        try:
            result = await asyncio.wait_for(
                self._do_run(
                    user_message,
                    sid,
                    conversation_history or [],
                    scene_type,
                    has_attachment,
                    tenant_id,
                    user_id,
                ),
                timeout=timeout,
            )
            result.session_id = sid
            result.conversation_id = conversation_id or 0
            return result
        except asyncio.TimeoutError:
            raise AgentTimeoutError(f"Agent [{self.agent.name}] 执行超时（{timeout}s）")

    async def stream_run(
        self,
        user_message: str,
        *,
        session_id: str | None = None,
        conversation_history: list[dict] | None = None,
        scene_type: str | None = None,
        has_attachment: bool = False,
        timeout_sec: int | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        流式执行 Agent。
        yield 事件 dict：{type: 'meta', ...} | {type: 'content', text: str} | {type: 'done'} | {type: 'error', message: str}
        """
        sid = session_id or str(uuid.uuid4())
        timeout = timeout_sec or self.agent.node_timeout_sec or 60

        try:
            async for event in self._do_stream_run(
                user_message=user_message,
                session_id=sid,
                history=conversation_history or [],
                explicit_scene=scene_type,
                has_attachment=has_attachment,
                tenant_id=tenant_id,
                user_id=user_id,
            ):
                event["session_id"] = sid
                event["conversation_id"] = conversation_id or 0
                yield event
        except asyncio.TimeoutError:
            yield {"type": "error", "message": f"Agent [{self.agent.name}] 执行超时（{timeout}s）"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}

    async def _do_stream_run(
        self,
        user_message: str,
        session_id: str,
        history: list[dict],
        explicit_scene: str | None,
        has_attachment: bool,
        tenant_id: int | None,
        user_id: int | None,
    ) -> AsyncGenerator[dict, None]:
        """内部流式执行逻辑"""
        # 1. 场景路由
        scene = await self._resolve_scene(
            user_message, explicit_scene, has_attachment, tenant_id, user_id
        )
        yield {"type": "meta", "scene": scene.scene_type, "scene_source": scene.source}

        # 2. 加载场景配置（合并参数）
        effective = await self._merge_effective_config(scene.scene_type, tenant_id, user_id)

        # 3. RAG 检索（如果有）
        rag_context = ""
        if effective.get("enable_rag") and self.agent.kb_ids:
            rag_context = await self._retrieve_rag(
                user_message,
                kb_ids=self.agent.kb_ids,
                top_k=effective.get("rag_top_k", 5),
                score_threshold=effective.get("rag_score_threshold", 0.5),
            )
            if rag_context:
                yield {"type": "meta", "rag_context_loaded": True}

        system_prompt = effective.get("system_prompt") or self.agent.system_prompt or ""
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}"

        # 4. 流式 LLM 调用
        model_config_id = effective.get("model_config_id") or self.agent.model_config_id
        temperature = effective.get("temperature", self.agent.temperature)
        max_tokens = effective.get("max_tokens", self.agent.max_tokens)

        from app.ai.llm.providers.base import ChatMessage
        from app.ai.llm.service import LLMService

        llm_svc = LLMService()

        # 根据 memory_type 获取记忆
        memories = await self._get_memories(history)

        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        for h in memories:
            messages.append(ChatMessage(role=h["role"], content=h["content"]))
        messages.append(ChatMessage(role="user", content=user_message))

        # 流式输出
        full_output = ""
        async for chunk in llm_svc.stream_chat(
            messages=messages,
            model_config_id=model_config_id,
            db=self.db,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            full_output += chunk
            yield {"type": "content", "text": chunk}

        yield {"type": "done", "output": full_output}

    async def _do_run(
        self,
        user_message: str,
        session_id: str,
        history: list[dict],
        explicit_scene: str | None,
        has_attachment: bool,
        tenant_id: int | None,
        user_id: int | None,
    ) -> AgentRunResult:
        start_ms = int(time.time() * 1000)

        # 1. 场景路由
        scene = await self._resolve_scene(
            user_message, explicit_scene, has_attachment, tenant_id, user_id
        )

        # 2. 加载场景配置（合并参数）
        effective = await self._merge_effective_config(scene.scene_type, tenant_id, user_id)

        # 3. 若场景开启 RAG，先检索上下文
        rag_context = ""
        if effective.get("enable_rag") and self.agent.kb_ids:
            rag_context = await self._retrieve_rag(
                user_message,
                kb_ids=self.agent.kb_ids,
                top_k=effective.get("rag_top_k", 5),
                score_threshold=effective.get("rag_score_threshold", 0.5),
            )

        system_prompt = effective.get("system_prompt") or self.agent.system_prompt or ""
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}"

        # 4. 执行推理（使用 LangChain 或直接调用 LLM）
        model_config_id = effective.get("model_config_id") or self.agent.model_config_id
        output, intermediate_steps, total_tokens = await self._invoke_llm(
            user_message=user_message,
            system_prompt=system_prompt,
            history=history,
            model_config_id=model_config_id,
            temperature=effective.get("temperature", self.agent.temperature),
            max_tokens=effective.get("max_tokens", self.agent.max_tokens),
        )

        latency_ms = int(time.time() * 1000) - start_ms

        return AgentRunResult(
            output=output,
            conversation_id=0,  # 由调用方填充
            session_id=session_id,
            scene=scene.scene_type,
            scene_source=scene.source,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            intermediate_steps=intermediate_steps,
        )

    # ── 场景路由 ──────────────────────────────────────────────────────────────

    async def _resolve_scene(
        self,
        message: str,
        explicit_scene: str | None,
        has_attachment: bool,
        tenant_id: int | None,
        user_id: int | None,
    ) -> SceneRouteResult:
        """结合 config_center 的租户级场景路由开关"""
        use_model_classifier = False
        routing_enabled = True

        try:
            from app.modules.config_center.service import ConfigCenterService
            cfg_svc = ConfigCenterService(self.db)
            values = await cfg_svc.get_merged(
                keys=["ai.scene_routing.enabled", "ai.scene_routing.use_model_classifier"],
                tenant_id=tenant_id,
                app_key="ai",
                user_id=user_id,
            )
            routing_enabled = values.get("ai.scene_routing.enabled", "true") == "true"
            use_model_classifier = values.get("ai.scene_routing.use_model_classifier", "false") == "true"
        except Exception:
            pass  # config_center 查询失败不影响主流程

        if not routing_enabled:
            return SceneRouteResult(scene_type="professional", source="tenant_disabled")

        router = SceneRouter()
        return await router.resolve(
            message=message,
            explicit_scene=explicit_scene,
            agent_default_scene=self.agent.default_scene,
            has_attachment=has_attachment,
            use_model_classifier=use_model_classifier,
        )

    # ── 配置合并 ──────────────────────────────────────────────────────────────

    async def _merge_effective_config(
        self,
        scene_type: str,
        tenant_id: int | None,
        user_id: int | None,
    ) -> dict:
        """场景配置 > Agent 配置 > Prompt 模板，返回最终生效参数"""
        from sqlalchemy import select

        result = await self.db.execute(
            select(AiSceneConfig)
            .where(AiSceneConfig.agent_id == self.agent.id)
            .where(AiSceneConfig.scene_type == scene_type)
            .where(AiSceneConfig.is_active == True)
        )
        scene_cfg: AiSceneConfig | None = result.scalar_one_or_none()

        # Prompt 模板优先级：场景配置 > Agent 配置
        prompt_template_id = (
            scene_cfg.prompt_template_id if scene_cfg and scene_cfg.prompt_template_id else None
        ) or self.agent.prompt_template_id
        prompt_version = (
            scene_cfg.prompt_version if scene_cfg and scene_cfg.prompt_version else None
        ) or getattr(self.agent, 'prompt_version', None)

        # 如果有 prompt_template_id，尝试加载模板内容
        system_prompt_from_template: str | None = None
        if prompt_template_id:
            try:
                from app.ai.prompt.service import PromptService
                prompt_svc = PromptService(self.db)
                system_prompt_from_template = await prompt_svc.get_version_content(
                    prompt_template_id, prompt_version
                )
            except Exception:
                pass  # prompt 模板加载失败不影响主流程

        return {
            "model_config_id": (
                scene_cfg.model_config_id if scene_cfg else None
            ) or self.agent.model_config_id,
            "system_prompt": (
                system_prompt_from_template
                or (scene_cfg.system_prompt if scene_cfg else None)
                or self.agent.system_prompt
            ),
            "temperature": (
                scene_cfg.temperature
                if scene_cfg and scene_cfg.temperature is not None
                else self.agent.temperature
            ),
            "max_tokens": (
                scene_cfg.max_tokens if scene_cfg else None
            ) or self.agent.max_tokens,
            "enable_rag": scene_cfg.enable_rag if scene_cfg else False,
            "rag_top_k": scene_cfg.rag_top_k if scene_cfg else 5,
            "rag_score_threshold": scene_cfg.rag_score_threshold if scene_cfg else 0.5,
        }

    # ── RAG 检索 ──────────────────────────────────────────────────────────────

    async def _retrieve_rag(
        self,
        query: str,
        kb_ids: list[int],
        top_k: int = 5,
        score_threshold: float = 0.5,
    ) -> str:
        """从关联知识库检索上下文，合并多个知识库结果"""
        try:
            from app.ai.knowledge.service import KnowledgeService
            kb_svc = KnowledgeService(self.db)

            all_chunks = []
            for kb_id in kb_ids:
                chunks = await kb_svc.search(kb_id, query, top_k=top_k, score_threshold=score_threshold)
                all_chunks.extend(chunks)

            if not all_chunks:
                return ""

            # 按分数排序，去重，取前 top_k 条
            seen: set[str] = set()
            unique_chunks = []
            for chunk in sorted(all_chunks, key=lambda x: x.get("score", 0), reverse=True):
                content = chunk.get("content", "")
                if content and content not in seen:
                    seen.add(content)
                    unique_chunks.append(content)
                    if len(unique_chunks) >= top_k:
                        break

            context = "\n\n---\n\n".join(unique_chunks)
            return f"以下是相关参考资料：\n\n{context}"
        except Exception as e:
            logger.warning("agent_rag_retrieve_failed", error=str(e))
            return ""

    # ── LLM 推理 ──────────────────────────────────────────────────────────────

    async def _get_memories(self, history: list[dict]) -> list[dict]:
        """
        根据 memory_type 获取记忆。
        - buffer: 返回最近 max_rounds * 2 条消息
        - summary: 返回摘要 + 最近 rounds 条消息
        - vector: （未来扩展）基于语义检索相关历史
        """
        memory_type = getattr(self.agent, 'memory_type', 'buffer') or 'buffer'
        max_rounds = getattr(self.agent, 'max_rounds', 10) or 10

        if memory_type == 'buffer' or not history:
            # buffer 模式：保留最近 N 轮对话
            return history[-max_rounds * 2:] if history else []

        if memory_type == 'summary':
            # summary 模式：保留最近 N 轮 + 早期摘要
            # 简化实现：超过 max_rounds 的历史返回摘要占位
            if len(history) <= max_rounds * 2:
                return history
            # TODO: 实现 LLM 摘要生成
            # 长期记忆 = summarize(早期历史)
            # 返回 [{"role": "system", "content": f"对话摘要: {summary}"}] + 近期历史
            recent = history[-max_rounds * 2:]
            summary_content = f"[早期对话摘要，共 {len(history) - max_rounds * 2} 条消息已省略]"
            return [{"role": "system", "content": summary_content}] + recent

        if memory_type == 'vector':
            # vector 模式：（未来扩展）需要 embedding 模型 + 向量存储
            # TODO: 实现语义检索
            # 1. embedding_model 嵌入当前用户消息
            # 2. 向量数据库相似度搜索
            # 3. 返回相关历史
            logger.warning("memory_vector_not_implemented", note="向量记忆模式需要 embedding 基础设施")
            return history[-max_rounds * 2:] if history else []

        # 默认 buffer
        return history[-max_rounds * 2:] if history else []

    async def _invoke_llm(
        self,
        user_message: str,
        system_prompt: str,
        history: list[dict],
        model_config_id: int | None,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, list[Any], int]:
        """
        调用 LLM 进行推理（当 tool_ids 为空时直接对话，有工具则走 Agent 链）。
        返回 (output, intermediate_steps, total_tokens)
        """
        from app.ai.llm.providers.base import ChatMessage
        from app.ai.llm.service import LLMService

        llm_svc = LLMService()

        # 根据 memory_type 获取记忆
        memories = await self._get_memories(history)

        # 构建消息列表
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        for h in memories:
            messages.append(ChatMessage(role=h["role"], content=h["content"]))
        messages.append(ChatMessage(role="user", content=user_message))

        # 无工具时直接对话
        if not self.agent.tool_ids:
            result = await llm_svc.chat(
                messages=messages,
                model_config_id=model_config_id,
                db=self.db,
                temperature=temperature,
                max_tokens=max_tokens,
                call_type="agent",
            )
            return result.content, [], result.total_tokens

        # 有工具时（LangChain Agent 链，需要 langchain 已安装）
        return await self._invoke_with_tools(
            messages=messages,
            model_config_id=model_config_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _invoke_with_tools(
        self,
        messages: list,
        model_config_id: int | None,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, list[Any], int]:
        """使用 LangChain 构建工具链 Agent"""
        try:
            from langchain.agents import AgentExecutor, create_openai_tools_agent
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain_openai import ChatOpenAI

            from app.ai.llm.models import AiModelConfig
            from app.ai.llm.service import LLMService

            config = await LLMService._load_config(model_config_id, self.db) if model_config_id else None
            from app.core.security import decrypt_value
            api_key = decrypt_value(config.api_key) if config and config.api_key else ""
            base_url = config.base_url if config else None

            lc_llm = ChatOpenAI(
                model=config.model_id if config else "gpt-3.5-turbo",
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=False,
            )

            tools = self.tool_registry.get_tools(self.agent.tool_ids) if self.tool_registry else []

            # 从 messages 中分离 system / history / current
            lc_messages = []
            for m in messages[:-1]:  # 最后一条（user）在 {input} 里
                if m.role == "system":
                    lc_messages.append(SystemMessage(content=m.content))
                elif m.role == "user":
                    lc_messages.append(HumanMessage(content=m.content))
                elif m.role == "assistant":
                    lc_messages.append(AIMessage(content=m.content))

            system_content = next(
                (m.content for m in messages if m.role == "system"), "You are a helpful assistant."
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_content),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ])

            agent = create_openai_tools_agent(lc_llm, tools, prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                max_iterations=self.agent.max_rounds,
                return_intermediate_steps=True,
                handle_parsing_errors=True,
            )

            user_content = messages[-1].content
            agent_result = await executor.ainvoke({
                "input": user_content,
                "chat_history": lc_messages,
            })

            output = agent_result.get("output", "")
            steps = agent_result.get("intermediate_steps", [])
            return output, steps, 0  # LangChain Agent 暂不统计 Token

        except ImportError:
            logger.warning("langchain_not_installed", note="工具链需要安装 langchain 和 langchain-openai")
            # 降级为直接对话
            from app.ai.llm.providers.base import ChatMessage
            from app.ai.llm.service import LLMService

            llm_svc = LLMService()
            result = await llm_svc.chat(
                messages=messages,
                model_config_id=model_config_id,
                db=self.db,
                call_type="agent",
            )
            return result.content, [], result.total_tokens


# ── 工作流编排器 ──────────────────────────────────────────────────────────────

class WorkflowLoopError(AppException):
    def __init__(self, message: str):
        super().__init__(status_code=422, message=message)


class WorkflowOrchestrator:
    """
    Multi-Agent 工作流编排器（有向图，支持受控循环）。
    - 执行路径：BFS 遍历 + 条件边选择（支持回退循环）
    - 每个节点最多执行 max_loop_count 次（默认 3），超出则报错
    - 并行节点使用 asyncio.gather() + asyncio.Lock 保证上下文并发安全
    """

    def __init__(
        self,
        graph_json: dict,
        db: AsyncSession,
        tool_registry: "ToolRegistry | None" = None,
    ) -> None:
        self.graph = graph_json
        self.db = db
        self.tool_registry = tool_registry
        self._context: dict[str, Any] = {}
        # per-key 锁，避免全局锁在嵌套并行时死锁
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._key_locks_lock = asyncio.Lock()
        self._node_exec_count: dict[str, int] = {}
        self._run_id: int | None = None

    async def _get_key_lock(self, key: str) -> asyncio.Lock:
        """获取指定 key 的锁（lazy 创建）"""
        async with self._key_locks_lock:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            return self._key_locks[key]

    async def run(self, input_data: dict, run_id: int) -> dict:
        """执行工作流，返回最终输出"""
        self._run_id = run_id
        await self._set_context("start", input_data)
        node_map = {n["id"]: n for n in self.graph["nodes"]}

        current_node_id = "start"
        while current_node_id and current_node_id != "end":
            node = node_map.get(current_node_id)
            if not node:
                break
            current_node_id = await self._run_node(node)

        ctx = await self._get_context()
        return ctx.get("end", {})

    async def _set_context(self, key: str, value: Any) -> None:
        """设置 context 值（带 per-key 锁，支持并行安全）"""
        lock = await self._get_key_lock(key)
        async with lock:
            self._context[key] = value

    async def _get_context(self) -> dict:
        """获取全部 context（全局只读，无需锁）"""
        return deepcopy(self._context)

    async def _record_node_run(
        self,
        node_id: str,
        node_type: str | None,
        status: str,
        input_data: dict | None = None,
        output_data: dict | None = None,
        error: str | None = None,
    ) -> None:
        """写入节点执行明细到 AiWorkflowNodeRun"""
        if not self._run_id:
            return
        try:
            from datetime import datetime, UTC
            from app.ai.agent.models import AiWorkflowNodeRun

            node_run = AiWorkflowNodeRun(
                run_id=self._run_id,
                node_id=node_id,
                node_type=node_type,
                status=status,
                input=input_data,
                output=output_data,
                error=error,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            self.db.add(node_run)
            await self.db.flush()
        except Exception:
            pass  # 节点记录失败不影响主流程

    async def _run_node(self, node: dict) -> str | None:
        """执行单个节点，返回下一个节点 ID"""
        node_id = node["id"]
        node_type = node["type"]

        # 循环次数守卫
        self._node_exec_count[node_id] = self._node_exec_count.get(node_id, 0) + 1
        max_loop = node.get("config", {}).get("max_loop_count", 3)
        if self._node_exec_count[node_id] > max_loop:
            raise WorkflowLoopError(
                f"节点 [{node_id}] 执行次数超过限制 {max_loop}，工作流终止"
            )

        condition_result = None
        iteration = self._node_exec_count[node_id]

        match node_type:
            case "start":
                await self._record_node_run(node_id, node_type, "success", input_data={"start": True})
            case "end":
                ctx = await self._get_context()
                # 将所有 context 汇总到 end 节点
                await self._set_context("end", ctx)
                await self._record_node_run(node_id, node_type, "success", output_data=ctx)
            case "agent":
                ctx = await self._get_context()
                timeout = node.get("config", {}).get("timeout_sec", 60)
                node_input = {"input_template": node.get("config", {}).get("input_template", "{input}"), "context_keys": list(ctx.keys())}
                try:
                    result = await asyncio.wait_for(
                        self._run_agent_node(node),
                        timeout=timeout,
                    )
                    await self._set_context(node_id, result)
                    await self._record_node_run(node_id, node_type, "success", input_data=node_input, output_data=result)
                except asyncio.TimeoutError:
                    await self._record_node_run(node_id, node_type, "failed", input_data=node_input, error=f"执行超时（{timeout}s）")
                    raise AgentTimeoutError(f"节点 [{node_id}] 执行超时（{timeout}s）")
                except Exception as e:
                    await self._record_node_run(node_id, node_type, "failed", input_data=node_input, error=str(e))
                    raise
            case "tool":
                ctx = await self._get_context()
                node_input = {"tool_id": node.get("config", {}).get("tool_id"), "params": node.get("config", {}).get("params", {})}
                result = await self._run_tool_node(node)
                await self._set_context(node_id, result)
                await self._record_node_run(node_id, node_type, "success" if "error" not in result else "failed", input_data=node_input, output_data=result, error=result.get("error"))
            case "condition":
                ctx = await self._get_context()
                node_input = {"condition": node.get("config", {}).get("condition", "")}
                condition_result = self._evaluate_condition(node, ctx)
                await self._set_context(node_id, {"result": condition_result})
                await self._record_node_run(node_id, node_type, "success", input_data=node_input, output_data={"result": condition_result})
            case "parallel":
                await self._run_parallel_nodes(node)

        return self._pick_next_node(node_id, condition_result)

    def _pick_next_node(self, current_id: str, condition_result: bool | None) -> str | None:
        edges = [e for e in self.graph["edges"] if e["from"] == current_id]
        for edge in edges:
            edge_cond = edge.get("condition")
            if edge_cond is None:
                return edge["to"]
            if condition_result is not None and str(condition_result).lower() == edge_cond.lower():
                return edge["to"]
        return None

    async def _run_agent_node(self, node: dict) -> dict:
        config = node.get("config", {})
        agent_id = config.get("agent_id")
        if not agent_id:
            return {"error": "agent_id 未配置"}

        from sqlalchemy import select
        agent_row = await self.db.get(AiAgent, agent_id)
        if not agent_row:
            return {"error": f"Agent ID={agent_id} 不存在"}

        ctx = await self._get_context()
        input_text = self._render_template(config.get("input_template", "{input}"), ctx)

        runner = AgentRunner(agent=agent_row, db=self.db, tool_registry=self.tool_registry)
        result = await runner.run(
            user_message=input_text,
            session_id=str(node["id"]),
            timeout_sec=config.get("timeout_sec"),
        )
        return {"output": result.output, "scene": result.scene, "tokens": result.total_tokens}

    async def _run_tool_node(self, node: dict) -> dict:
        config = node.get("config", {})
        tool_id = config.get("tool_id")
        if not self.tool_registry or not tool_id:
            return {"error": "tool_id 未配置或工具注册中心不可用"}

        ctx = await self._get_context()
        params = {k: self._render_template(str(v), ctx) for k, v in config.get("params", {}).items()}

        tool = self.tool_registry.get_tool(tool_id)
        if not tool:
            return {"error": f"工具 {tool_id} 未注册"}

        try:
            result = await tool.arun(**params)
            return {"output": result}
        except Exception as e:
            return {"error": str(e)}

    async def _run_parallel_nodes(self, parallel_node: dict) -> None:
        sub_node_ids = parallel_node.get("config", {}).get("nodes", [])
        node_map = {n["id"]: n for n in self.graph["nodes"]}

        tasks = [
            self._run_agent_node(node_map[nid])
            for nid in sub_node_ids
            if nid in node_map
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for nid, result in zip(sub_node_ids, results):
            if isinstance(result, Exception):
                await self._set_context(nid, {"error": str(result)})
                await self._record_node_run(nid, "agent", "failed", error=str(result))
            elif isinstance(result, dict):
                await self._set_context(nid, result)
                await self._record_node_run(nid, "agent", "success", output_data=result)
            else:
                await self._set_context(nid, {"error": str(result)})
                await self._record_node_run(nid, "agent", "failed", error=str(result))

    def _evaluate_condition(self, node: dict, context: dict) -> bool:
        """安全地对条件表达式求值（使用 AST 解析，禁止任意代码执行）"""
        import ast
        import operator

        condition = node.get("config", {}).get("condition", "false")
        rendered = self._render_template(condition, context)
        try:
            return self._safe_eval(rendered)
        except Exception:
            return False

    def _safe_eval(self, expr: str) -> bool:
        """使用 AST 的安全表达式求值器，仅支持比较运算和布尔逻辑"""
        import ast
        import operator

        OPERATORS = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
            ast.In: lambda a, b: a in b,
            ast.NotIn: lambda a, b: a not in b,
            ast.And: None,  # handled specially
            ast.Or: None,  # handled specially
            ast.Not: None,  # handled specially
            ast.NameConstant: None,  # True/False/None (Python 3.7-)
            ast.Constant: None,  # True/False/None (Python 3.8+)
            ast.Num: None,  # numbers (Python 3.7)
            ast.Str: None,  # strings (Python 3.7)
            ast.Name: None,  # identifiers
            ast.Subscript: None,
        }

        # 二元运算映射
        BINARY_OPS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }

        def safe_name(node: ast.Name) -> bool | str | int | float | None:
            # 允许的标识符
            ALLOWED_NAMES = {
                "true": True, "false": False, "null": None, "none": None,
                "True": True, "False": False, "None": None,
            }
            if node.id in ALLOWED_NAMES:
                return ALLOWED_NAMES[node.id]
            # 从上下文查找
            raise NameError(f"未知变量: {node.id}")

        def safe_getattr(node: ast.Attribute) -> Any:
            left = visit(node.value)
            return getattr(left, node.attr)

        def safe_subscript(node: ast.Subscript) -> Any:
            val = visit(node.value)
            key = visit(node.slice)
            return val[key]

        def visit(n: ast.AST) -> Any:
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.NameConstant):  # Python 3.7
                return n.value
            if isinstance(n, ast.Num):  # Python 3.7
                return n.n
            if isinstance(n, ast.Str):  # Python 3.7
                return n.s
            if isinstance(n, ast.Name):
                return safe_name(n)
            if isinstance(n, ast.Attribute):
                return safe_getattr(n)
            if isinstance(n, ast.BinOp):
                op_type = type(n.op)
                if op_type in BINARY_OPS:
                    return BINARY_OPS[op_type](visit(n.left), visit(n.right))
                raise ValueError(f"不支持的二元运算符: {op_type.__name__}")
            if isinstance(n, ast.UnaryOp):
                if isinstance(n.op, ast.Not):
                    return not visit(n.operand)
                if isinstance(n.op, ast.USub):
                    return -visit(n.operand)
                if isinstance(n.op, ast.UAdd):
                    return +visit(n.operand)
                raise ValueError(f"不支持的一元运算符: {type(n.op).__name__}")
            if isinstance(n, ast.Subscript):
                return safe_subscript(n)
            if isinstance(n, ast.BoolOp):
                if isinstance(n.op, ast.And):
                    return all(visit(v) for v in n.values)
                if isinstance(n.op, ast.Or):
                    return any(visit(v) for v in n.values)
                raise ValueError(f"不支持的布尔运算符: {type(n.op).__name__}")
            if isinstance(n, ast.Compare):
                left = visit(n.left)
                for op, comparator in zip(n.ops, n.comparators):
                    op_func = OPERATORS.get(type(op))  # type: ignore[index]
                    if op_func is None:
                        raise ValueError(f"不支持的比较运算符: {type(op).__name__}")
                    right = visit(comparator)
                    if not op_func(left, right):
                        return False
                    left = right
                return True
            raise ValueError(f"不支持的 AST 节点: {type(n).__name__}")

        tree = ast.parse(expr, mode="eval")
        return bool(visit(tree.body))

    def _render_template(self, template: str, context: dict) -> str:
        """将 {{node_id.field}} 形式的模板变量替换为 context 中的值"""
        import re

        def replace(m: re.Match) -> str:
            keys = m.group(1).strip().split(".")
            val: Any = context
            for k in keys:
                val = val.get(k, "") if isinstance(val, dict) else ""
            return str(val)

        return re.sub(r"\{\{(.+?)\}\}", replace, template)
