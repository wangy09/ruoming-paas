"""
若茗 PaaS - 工具注册中心
提供工具的注册、发现和调用能力，封装在 LangChain StructuredTool 之上（不向外暴露）。
Author: ruoming
"""
from __future__ import annotations

import httpx
import structlog
from typing import Any, Callable

logger = structlog.get_logger(__name__)


class ToolDefinition:
    """
    工具定义（与 LangChain 解耦的内部表示）。
    实际调用时按需转换为 LangChain StructuredTool。
    """

    def __init__(
        self,
        tool_id: str,
        name: str,
        description: str,
        func: Callable,
        is_async: bool = True,
    ) -> None:
        self.tool_id = tool_id
        self.name = name
        self.description = description
        self.func = func
        self.is_async = is_async

    async def arun(self, **kwargs) -> str:
        """异步执行工具"""
        if self.is_async:
            return await self.func(**kwargs)
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, lambda: self.func(**kwargs))

    def to_langchain_tool(self):
        """转换为 LangChain StructuredTool（延迟导入，避免强依赖）"""
        try:
            from langchain.tools import StructuredTool
            return StructuredTool.from_function(
                coroutine=self.func if self.is_async else None,
                func=None if self.is_async else self.func,
                name=self.name,
                description=self.description,
            )
        except ImportError:
            return None


class ToolRegistry:
    """
    工具注册中心（单例）。
    - register 装饰器注册工具
    - get_tools() 批量获取 LangChain 工具列表
    - get_tool() 获取单个工具定义
    """

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDefinition] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool_id: str, name: str = "", description: str = ""):
        """装饰器：注册工具函数"""
        def decorator(func: Callable) -> Callable:
            definition = ToolDefinition(
                tool_id=tool_id,
                name=name or func.__name__,
                description=description or (func.__doc__ or "").strip(),
                func=func,
                is_async=True,  # 默认异步
            )
            cls._tools[tool_id] = definition
            logger.info("tool_registered", tool_id=tool_id)
            return func
        return decorator

    @classmethod
    def get_tool(cls, tool_id: str) -> ToolDefinition | None:
        return cls._tools.get(tool_id)

    @classmethod
    def get_tools(cls, tool_ids: list[str]) -> list:
        """返回 LangChain StructuredTool 列表（供 AgentExecutor 使用）"""
        tools = []
        for tid in tool_ids:
            definition = cls._tools.get(tid)
            if definition:
                lc_tool = definition.to_langchain_tool()
                if lc_tool:
                    tools.append(lc_tool)
        return tools

    @classmethod
    def list_all(cls) -> list[dict]:
        """列出所有注册的工具（用于前端展示）"""
        return [
            {
                "tool_id": t.tool_id,
                "name": t.name,
                "description": t.description,
            }
            for t in cls._tools.values()
        ]


# ── 内置工具注册 ──────────────────────────────────────────────────────────────

_registry = ToolRegistry()


@ToolRegistry.register(
    "builtin:web_search",
    name="网络搜索",
    description="搜索互联网获取实时信息。输入：query（搜索词），max_results（最大结果数，默认5）",
)
async def web_search(query: str, max_results: int = 5) -> str:
    """通过搜索引擎获取实时网络信息"""
    # 优先使用 Tavily API（专为 RAG 优化），降级到 DuckDuckGo
    try:
        from tavily import TavilyClient
        import os
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
        results = client.search(query=query, max_results=max_results)
        return "\n\n".join([
            f"[{r.get('title')}]({r.get('url')})\n{r.get('content', '')}"
            for r in results.get("results", [])
        ])
    except Exception:
        pass

    # 降级：返回提示信息
    return f"网络搜索功能需要配置 TAVILY_API_KEY。查询词：{query}"


@ToolRegistry.register(
    "builtin:http_request",
    name="HTTP 请求",
    description="发起 HTTP 请求并返回响应内容。输入：url（请求地址），method（GET/POST），headers（可选），body（可选）",
)
async def http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
) -> str:
    """向指定 URL 发起 HTTP 请求"""
    # 安全检查：禁止访问内网地址
    import re
    private_pattern = re.compile(
        r"(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|localhost|::1)",
        re.I,
    )
    if private_pattern.search(url):
        return "[安全限制] 不允许访问内网地址"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                content=body,
            )
            # 截取前 2000 字符避免过大响应
            text = resp.text[:2000]
            return f"状态码：{resp.status_code}\n响应内容：\n{text}"
    except Exception as e:
        return f"HTTP 请求失败：{str(e)}"


@ToolRegistry.register(
    "builtin:calculator",
    name="数学计算器",
    description="执行数学计算表达式。输入：expression（数学表达式，如 '2 + 3 * 4'）",
)
async def calculator(expression: str) -> str:
    """安全的数学计算器（仅支持数学运算，禁止函数调用）"""
    import ast
    try:
        # 严格限制：只允许数字和基本运算符
        allowed_chars = set("0123456789+-*/()., ")
        if not all(c in allowed_chars for c in expression):
            return f"[安全限制] 仅允许数学运算符和数字"

        tree = ast.parse(expression.strip(), mode="eval")
        # 白名单检查节点类型
        allowed_nodes = (
            ast.Expression, ast.BinOp, ast.UnaryOp,
            ast.Num, ast.Constant,  # type: ignore[attr-defined]
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
            ast.UAdd, ast.USub,
        )
        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                return f"[安全限制] 不允许的计算操作"

        result = eval(compile(tree, "<calculator>", "eval"))  # noqa: S307
        return f"计算结果：{result}"
    except SyntaxError:
        return f"表达式语法错误：{expression}"
    except Exception as e:
        return f"计算失败：{str(e)}"
