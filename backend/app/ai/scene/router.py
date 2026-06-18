"""
若茗 PaaS - AI 场景路由器
基于混合模式（前端显式 > Agent默认 > 规则引擎 > 模型分类 > 兜底）自动识别用户意图场景，
为 Agent 执行器提供最佳的 Prompt / temperature / 模型参数。
Author: ruoming
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.ai.llm.providers.base import BaseLLMProvider

logger = structlog.get_logger(__name__)

# ── 规则引擎关键词 ────────────────────────────────────────────────────────────

_PROFESSIONAL_RE = re.compile(
    r"分析|报告|方案|实现|优化|比较|评估|原理|解释|总结|翻译|写作|调研|研究|"
    r"analyze|explain|compare|implement|optimize|summarize|report",
    re.I,
)
_TASK_RE = re.compile(
    r"帮我写|帮我做|生成|创建|设计|制作|出一份|做一个|请写|给我写|"
    r"create|generate|write|design|build|make",
    re.I,
)
_RAG_RE = re.compile(
    r"根据文档|文件中|资料里|知识库|上传的|附件|文档显示|"
    r"based on document|in the file|according to",
    re.I,
)
_CREATIVE_RE = re.compile(
    r"创意|头脑风暴|想象|故事|小说|诗|剧本|创作|brainstorm|creative|story|poem|fiction",
    re.I,
)

# 内置场景类型
SCENE_TYPES = frozenset({"chitchat", "professional", "task", "rag", "creative"})


@dataclass
class SceneRouteResult:
    """场景路由结果"""
    scene_type: str      # 场景类型
    source: str          # 来源：explicit / agent_default / rule / model / fallback


class SceneRouter:
    """
    AI 场景路由器：混合模式。
    优先级（从高到低）：
    ① 前端显式传入 scene_type（最准确）
    ② Agent 绑定的默认场景（agent.default_scene）
    ③ 规则引擎推断（关键词 / 长度特征，覆盖 ~80% 请求，零成本）
    ④ 轻量模型分类（规则兜不住时，可选，有 Token 成本）
    ⑤ 系统兜底（professional）
    """

    def __init__(self, classifier_llm: "BaseLLMProvider | None" = None) -> None:
        self._classifier = classifier_llm

    async def resolve(
        self,
        message: str,
        *,
        explicit_scene: str | None = None,
        agent_default_scene: str | None = None,
        has_attachment: bool = False,
        use_model_classifier: bool = False,
    ) -> SceneRouteResult:
        """解析场景，按优先级链依次尝试"""

        # ① 前端显式传入
        if explicit_scene and explicit_scene in SCENE_TYPES:
            return SceneRouteResult(scene_type=explicit_scene, source="explicit")

        # ② Agent 绑定默认场景
        if agent_default_scene and agent_default_scene in SCENE_TYPES:
            return SceneRouteResult(scene_type=agent_default_scene, source="agent_default")

        # ③ 规则引擎
        rule_result = self._rule_infer(message, has_attachment)
        if rule_result:
            return SceneRouteResult(scene_type=rule_result, source="rule")

        # ④ 模型分类（可选，需显式开启）
        if use_model_classifier and self._classifier:
            try:
                model_result = await self._model_classify(message)
                if model_result:
                    return SceneRouteResult(scene_type=model_result, source="model")
            except Exception as e:
                logger.warning("scene_model_classify_failed", error=str(e))

        # ⑤ 兜底
        return SceneRouteResult(scene_type="professional", source="fallback")

    # ── 私有：规则引擎 ──────────────────────────────────────────────────────

    @staticmethod
    def _rule_infer(message: str, has_attachment: bool) -> str | None:
        """顺序匹配，命中即返回（无 LLM 调用，零成本）"""
        if has_attachment:
            return "rag"
        if _RAG_RE.search(message):
            return "rag"
        if _CREATIVE_RE.search(message):
            return "creative"
        if _TASK_RE.search(message):
            return "task"
        if _PROFESSIONAL_RE.search(message):
            return "professional"
        # 短消息（≤15字且无专业词汇）→ 闲聊
        if len(message.strip()) <= 15:
            return "chitchat"
        return None

    # ── 私有：模型分类 ──────────────────────────────────────────────────────

    async def _model_classify(self, message: str) -> str | None:
        """使用轻量模型进行意图分类（仅规则兜不住时调用）"""
        prompt = (
            "将以下用户消息分类到一个场景类型，只返回类型名，不要任何解释。\n"
            "场景类型：chitchat / professional / task / rag / creative\n\n"
            f"用户消息：{message[:200]}\n\n"
            "场景类型："
        )
        from app.ai.llm.providers.base import ChatMessage

        result = await self._classifier.chat(  # type: ignore[union-attr]
            messages=[ChatMessage(role="user", content=prompt)],
            model="",  # 由调用方传入的 classifier 已绑定 model
            temperature=0.0,
            max_tokens=10,
        )
        scene = result.content.strip().lower()
        return scene if scene in SCENE_TYPES else None
