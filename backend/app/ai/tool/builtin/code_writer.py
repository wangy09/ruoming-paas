"""
若茗 PaaS - 代码生成工具
按项目规范生成任意代码片段或完整 CRUD 模块，生成后自动自检。
Author: ruoming
"""
from __future__ import annotations

import structlog

from app.ai.tool.registry import ToolRegistry

logger = structlog.get_logger(__name__)

# ── 项目规范摘要（注入 system prompt）──────────────────────────────────────────

_BACKEND_STANDARDS = """\
若茗 PaaS 后端代码规范（FastAPI + SQLAlchemy 2.0 async + Pydantic v2）：

1. 模型层 (models.py)：
   - 继承 BaseModel（含 tenant_id、is_deleted、created_at、updated_at）
   - 使用 SQLAlchemy 2.0 Mapped 风格：`name: Mapped[str] = mapped_column(...)`
   - 表名 snake_case，类名 PascalCase

2. Schema (schemas.py)：
   - Create / Update / Info 三件套
   - `model_config = {"from_attributes": True}`（Pydantic v2）
   - Update 所有字段 Optional

3. 仓储层 (repository.py)：
   - 继承 BaseRepository，`_base_query` 方法做多租户过滤
   - 方法：get_by_id, create, soft_delete

4. 服务层 (service.py)：
   - `__init__(self, db, tenant_id)`，内部 `self.repo = XxxRepository(db, tenant_id)`
   - CRUD 方法：list / get / create / update / delete
   - `@audit_log(...)` 装饰器记录操作
   - 异常：`raise NotFoundException("xxx")`

5. 路由层 (router.py)：
   - `router = APIRouter()`
   - 依赖注入：`db: Annotated[AsyncSession, Depends(get_db)]`
   - 权限校验：`current_user: Annotated[SysUser, Depends(require_permissions("module:action"))]`
   - 统一响应：`return ok(data)` / `return ok(message="创建成功")`
   - 分页：`page_params: Annotated[PageParams, Depends()]`
"""

_FRONTEND_STANDARDS = """\
若茗 PaaS 前端代码规范（Vue3 + Element Plus + TypeScript + Pinia）：

1. API 封装 (api/*.ts)：
   - 使用统一 axios 实例，泛型响应类型 `ApiResponse<T>`
   - 函数式导出：`export const xxxApi = { list, create, update, remove }`

2. 页面 (views/*)：
   - 组合式 API：`<script setup lang="ts">`
   - Element Plus 组件：el-table + el-pagination + el-dialog + el-form
   - 搜索区 + 表格 + 分页 + 新增/编辑弹窗的标准布局

3. 类型定义 (types/index.d.ts)：
   - 接口类型集中管理：`interface XxxInfo { id: number; name: string; ... }`
   - 表单类型：`interface XxxForm { ... }`（不含 id、created_at）

4. 状态管理 (store/*.ts)：
   - Pinia store：`defineStore('xxx', () => { ... })`
   - ref + computed + actions
"""

_CODE_GENERATE_PROMPT = f"""你是若茗 PaaS 项目的资深开发工程师，请按照项目规范生成代码。

{_BACKEND_STANDARDS}

{_FRONTEND_STANDARDS}

要求：
1. 严格按照项目规范编写代码
2. 代码块使用 markdown 格式，标注语言和文件路径
3. 每个文件用单独的代码块，格式：```language 文件路径
4. 包含必要的注释和类型标注
5. 确保代码可直接用于若茗 PaaS 项目
"""


@ToolRegistry.register(
    "builtin:code_generate",
    name="代码生成",
    description=(
        "按若茗 PaaS 项目规范生成任意代码片段。"
        "输入：language（编程语言，如 python/typescript/vue/sql/shell），"
        "task（详细的代码需求描述），"
        "framework（可选，框架名，如 fastapi/vue3/element-plus/sqlalchemy），"
        "context（可选，已有相关代码或表结构，帮助生成更贴合的代码）。"
        "返回：markdown 格式代码块，含文件路径注释和说明。"
    ),
)
async def code_generate(
    language: str,
    task: str,
    framework: str = "",
    context: str = "",
) -> str:
    """
    生成任意代码片段工具。
    AI Agent 在用户要求写代码、生成接口、编写组件时调用此工具。
    生成后自动进行代码自检。
    """
    from app.ai.llm.providers.base import ChatMessage
    from app.ai.llm.service import LLMService
    from app.database import AsyncSessionFactory
    from app.ai.tool.builtin.code_checker import _check_code_internal

    user_msg = f"请用 {language} 语言"
    if framework:
        user_msg += f"（{framework} 框架）"
    user_msg += f"实现以下需求：\n\n{task}"
    if context:
        user_msg += f"\n\n参考上下文：\n{context}"

    try:
        async with AsyncSessionFactory() as safe_db:
            llm_svc = LLMService()
            result = await llm_svc.chat(
                messages=[
                    ChatMessage(role="system", content=_CODE_GENERATE_PROMPT),
                    ChatMessage(role="user", content=user_msg),
                ],
                model_config_id=None,
                db=safe_db,
                temperature=0.2,
                call_type="tool_code_generate",
                use_cache=False,
            )

        generated_code = result.content

        # 自动自检（只提取代码部分）
        self_check = await _check_code_internal(generated_code, language, focus="all")

        return f"{generated_code}\n\n---\n\n{self_check}"
    except Exception as e:
        logger.warning("code_generate_failed", error=str(e))
        return f"代码生成失败：{e}"


@ToolRegistry.register(
    "builtin:code_generate_crud",
    name="CRUD 模块生成",
    description=(
        "按若茗 PaaS 规范一次性生成完整 CRUD 模块（model/schemas/repository/service/router + api.ts/index.vue/FormDialog.vue/route.ts/migration）。"
        "输入：table_name（数据库表名，snake_case），"
        "module_name（模块名，如 customer_order），"
        "entity_name（可选，PascalCase 实体类名），"
        "page_title（可选，页面标题）。"
        "返回：每个文件的路径和内容预览，附带 module_name 可用于下载 ZIP。"
    ),
)
async def code_generate_crud(
    table_name: str,
    module_name: str,
    entity_name: str = "",
    page_title: str = "",
    preview_only: bool = True,
) -> str:
    """
    生成完整 CRUD 模块工具。
    复用 CodegenService.preview()，使用独立 session 隔离事务。
    """
    from app.database import AsyncSessionFactory
    from app.modules.codegen.schemas import GeneratePreviewRequest
    from app.modules.codegen.service import CodegenService

    # preview_only 参数保留用于工具描述语义（preview 模式不落盘，始终为预览）
    _ = preview_only

    # 自动推断 entity_name
    if not entity_name:
        parts = module_name.split("_")
        entity_name = "".join(p.capitalize() for p in parts)
    if not page_title:
        page_title = entity_name

    try:
        async with AsyncSessionFactory() as safe_db:
            svc = CodegenService(safe_db, tenant_id=None)
            request = GeneratePreviewRequest(
                table_name=table_name,
                module_name=module_name,
                entity_name=entity_name,
                page_title=page_title,
            )
            preview = await svc.preview(request)

        # 格式化输出
        lines = [
            f"## CRUD 模块生成结果\n",
            f"**表名**：{table_name}  |  **模块**：{module_name}  |  **实体**：{entity_name}\n",
        ]

        files = preview.get("files", [])
        for f in files:
            path = f.get("path", "")
            content = f.get("content", "")
            lang = f.get("language", "text")
            lines.append(f"### `{path}`\n")
            lines.append(f"```{lang} {path}")
            lines.append(content)
            lines.append("```\n")

        lines.append("---\n")
        lines.append(f"> 📦 共生成 {len(files)} 个文件。")
        lines.append(f"> 💾 如需下载 ZIP，请调用接口 `POST /api/v1/codegen/download-by-spec`，传入相同的 `table_name` 和 `module_name`。")

        return "\n".join(lines)
    except Exception as e:
        logger.warning("code_generate_crud_failed", error=str(e))
        return f"CRUD 模块生成失败：{e}\n\n请确认表名 `{table_name}` 在数据库中存在，或提供 column_configs。"
