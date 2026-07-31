"""
若茗 PaaS - 代码错误检测工具
对用户提供的代码进行静态审查，识别潜在 Bug、安全漏洞、性能问题、规范违规。
Author: ruoming
"""
from __future__ import annotations

import json
import structlog

from app.ai.tool.registry import ToolRegistry

logger = structlog.get_logger(__name__)

# ── 检查维度配置 ──────────────────────────────────────────────────────────────

_FOCUS_MAP = {
    "all": "安全漏洞、潜在 Bug、性能问题、代码规范、最佳实践",
    "security": "SQL 注入、XSS、CSRF、敏感信息泄露、权限绕过等安全漏洞",
    "performance": "N+1 查询、内存泄漏、不必要的循环、低效算法等性能问题",
    "bug": "空指针、类型错误、边界条件、异常处理缺失等潜在 Bug",
    "style": "命名规范、代码结构、注释缺失、重复代码等规范问题",
}

# ── 项目规范摘要（注入 system prompt）──────────────────────────────────────────

_PROJECT_STANDARDS = """\
若茗 PaaS 项目技术栈与规范：
- 后端：FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Repository 模式
  * 路由层 (router.py)：依赖注入、权限校验 (require_permissions)、统一响应 (ApiResponse)
  * 服务层 (service.py)：业务逻辑、@audit_log 装饰器、异常抛出 (NotFoundException)
  * 仓储层 (repository.py)：数据访问、_base_query 多租户过滤
  * 模型层 (models.py)：BaseModel 基类（含 tenant_id、is_deleted、created_at）
  * Schema (schemas.py)：Create/Update/Info 三件套，model_config = {"from_attributes": True}
- 前端：Vue3 + Element Plus + TypeScript + Pinia
  * API 封装 (api/*.ts)：统一 axios 实例、泛型响应类型
  * 页面 (views/*)：组合式 API、<script setup lang="ts">
  * 类型定义 (types/index.d.ts)：接口类型集中管理
- 安全规范：禁止内联 SQL 拼接、敏感配置加密存储、文件上传校验扩展名
"""


async def _check_code_internal(code: str, language: str, focus: str = "all") -> str:
    """
    代码审查内部函数（供 code_writer 自检调用，不经过 ToolRegistry）。
    返回 markdown 格式的审查结果。
    """
    from app.ai.llm.providers.base import ChatMessage
    from app.ai.llm.service import LLMService
    from app.database import AsyncSessionFactory

    focus_desc = _FOCUS_MAP.get(focus, _FOCUS_MAP["all"])

    system_prompt = f"""你是资深代码审查专家，正在审查若茗 PaaS 项目中的代码。
{_PROJECT_STANDARDS}

请按以下维度审查代码：{focus_desc}

输出严格 JSON（不要包含 markdown 代码块标记）：
{{
  "summary": "总体评价（1-2句话）",
  "score": 85,
  "issues": [
    {{
      "severity": "critical",
      "category": "安全",
      "line": 12,
      "title": "SQL 注入风险",
      "desc": "问题描述",
      "suggestion": "修复建议",
      "fixed_code": "修复后的代码片段（可选）"
    }}
  ]
}}

severity 取值：critical（严重，必须修复）/ warning（警告，建议修复）/ info（建议，可选优化）
如果代码没有问题，issues 返回空数组 []。
"""

    try:
        async with AsyncSessionFactory() as safe_db:
            llm_svc = LLMService()
            result = await llm_svc.chat(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=f"请审查以下 {language} 代码：\n\n```\n{code}\n```"),
                ],
                model_config_id=None,
                db=safe_db,
                temperature=0,
                call_type="tool_code_check",
                use_cache=True,
            )

        # 解析 JSON
        content = result.content.strip()
        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        try:
            data = json.loads(content)
            return _format_review_result(data)
        except json.JSONDecodeError:
            # JSON 解析失败，降级为纯文本
            logger.warning("code_check_json_parse_failed", content_length=len(content))
            return f"## 代码审查结果\n\n{content}"
    except Exception as e:
        logger.warning("code_check_failed", error=str(e))
        return f"## 代码审查结果\n\n审查过程中出现错误：{e}"


def _format_review_result(data: dict) -> str:
    """将 JSON 审查结果格式化为 markdown"""
    lines = ["## 代码审查结果\n"]
    lines.append(f"**总体评价**：{data.get('summary', '无')}")
    lines.append(f"**评分**：{data.get('score', 'N/A')} / 100\n")

    issues = data.get("issues", [])
    if not issues:
        lines.append("✅ 未发现明显问题，代码质量良好。")
        return "\n".join(lines)

    # 按严重级别分组
    critical = [i for i in issues if i.get("severity") == "critical"]
    warning = [i for i in issues if i.get("severity") == "warning"]
    info = [i for i in issues if i.get("severity") == "info"]

    if critical:
        lines.append(f"### 🔴 严重问题（{len(critical)} 个）\n")
        for i, issue in enumerate(critical, 1):
            lines.append(_format_issue(i, issue))

    if warning:
        lines.append(f"### 🟡 警告（{len(warning)} 个）\n")
        for i, issue in enumerate(warning, 1):
            lines.append(_format_issue(i, issue))

    if info:
        lines.append(f"### 🔵 建议（{len(info)} 个）\n")
        for i, issue in enumerate(info, 1):
            lines.append(_format_issue(i, issue))

    return "\n".join(lines)


def _format_issue(idx: int, issue: dict) -> str:
    """格式化单个问题"""
    line = issue.get("line")
    line_str = f"（第 {line} 行）" if line else ""
    parts = [
        f"**{idx}. {issue.get('title', '未知问题')}**{line_str}",
        f"- 类别：{issue.get('category', '未分类')}",
        f"- 描述：{issue.get('desc', '无')}",
        f"- 建议：{issue.get('suggestion', '无')}",
    ]
    fixed = issue.get("fixed_code")
    if fixed:
        parts.append(f"- 修复代码：\n```\n{fixed}\n```")
    parts.append("")
    return "\n".join(parts)


# ── 工具注册 ──────────────────────────────────────────────────────────────────

@ToolRegistry.register(
    "builtin:code_check",
    name="代码错误检测",
    description=(
        "对用户提供的代码进行静态审查，识别潜在 Bug、安全漏洞、性能问题、规范违规。"
        "输入：code（待检测的代码全文），language（编程语言，如 python/typescript/vue/sql），"
        "focus（检测重点：security/performance/bug/style/all，默认 all），"
        "context（可选，相关业务背景或框架信息）。"
        "返回：分严重级别（critical/warning/info）列出问题，每条含行号、问题描述、修复建议。"
    ),
)
async def code_check(
    code: str,
    language: str,
    focus: str = "all",
    context: str = "",
) -> str:
    """
    代码错误检测工具。
    AI Agent 在用户要求检测代码、审查代码、找 bug 时调用此工具。
    """
    if not code.strip():
        return "请提供要检测的代码。"

    # 如果有额外上下文，拼接到代码前
    full_code = code
    if context:
        full_code = f"// 上下文：{context}\n\n{code}"

    return await _check_code_internal(full_code, language, focus)
