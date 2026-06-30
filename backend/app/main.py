"""
若茗 PaaS - FastAPI 应用入口
Author: ruoming
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.core.error_codes import SysErrCode
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.middleware.logging import RequestLoggingMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.middleware.tenant import TenantMiddleware

logger = structlog.get_logger(__name__)

# ── 限流器（slowapi）─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（启动 / 关闭）"""
    # ── 启动 ─────────────────────────────────────────────────────────
    setup_logging()
    logger.info(
        "app_starting",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )

    # 初始化 Redis
    from app.core.redis import get_redis_client
    redis = await get_redis_client()
    app.state.redis = redis

    # 验证数据库连接
    from app.database import engine
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
    logger.info("database_connected")

    # 启动 LLM 配置变更监听器（多 Worker 缓存失效）
    from app.ai.llm.service import LLMService
    await LLMService.start_invalidation_listener()

    # 注册内置工具（确保 ToolRegistry 单例初始化）
    import app.ai.tool.registry  # noqa: F401

    # 从数据库加载自定义工具到注册中心
    from app.ai.tool.router import load_custom_tools_from_db
    from app.database import AsyncSessionFactory
    async with AsyncSessionFactory() as _db:
        await load_custom_tools_from_db(_db)
    logger.info("custom_tools_loaded")

    yield

    # ── 关闭 ─────────────────────────────────────────────────────────
    from app.core.redis import close_redis
    from app.database import close_db

    await close_redis()
    await close_db()
    logger.info("app_shutdown")


# ── FastAPI 应用 ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="若茗 PaaS API",
    description="""
## 若茗 PaaS - 企业级 AI 应用开发底座

**Author**: ruoming  
**Version**: 2.0.0

### 功能模块
- **认证** - JWT 登录、Refresh Token 轮换、API Key
- **用户** - 用户 CRUD、角色分配
- **权限** - RBAC、角色继承、菜单/按钮/列权限
- **多租户** - 数据隔离、配额管理
- **审计** - 操作日志、登录日志、安全事件
- **AI** - LLM 网关、Agent、RAG 知识库
""",
    version=settings.APP_VERSION,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "认证", "description": "登录、Token 管理、登出"},
        {"name": "用户", "description": "用户 CRUD、角色分配"},
        {"name": "权限", "description": "角色、权限、菜单"},
        {"name": "租户", "description": "租户管理、配额"},
        {"name": "审计", "description": "操作日志、登录日志"},
        {"name": "消息中心", "description": "平台公告、用户消息"},
        {"name": "代码生成器", "description": "数据库表结构识别与 CRUD 代码生成"},
        {"name": "AI-模型管理", "description": "LLM 模型配置与连通性测试"},
        {"name": "AI-对话历史", "description": "对话会话与消息记录"},
        {"name": "AI-Agent管理", "description": "Agent 配置、执行与工作流编排"},
        {"name": "AI-知识库", "description": "知识库管理、文档上传与混合检索"},
        {"name": "AI-Prompt模板", "description": "Prompt 版本管理、发布与回滚"},
        {"name": "AI-工具管理", "description": "工具注册与调用"},
        {"name": "系统", "description": "健康检查、监控"},
    ],
)

# ── 限流扩展 ──────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 中间件（注意顺序：后注册的先执行）──────────────────────────────────────
# 1. RequestID（最先执行，为后续中间件提供 trace_id）
app.add_middleware(RequestIDMiddleware)

# 2. 请求日志（依赖 trace_id）
app.add_middleware(RequestLoggingMiddleware)

# 3. 租户解析（在认证之前解析租户）
app.add_middleware(TenantMiddleware)

# 4. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ── 全局异常处理器 ────────────────────────────────────────────────────────────


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一业务异常响应"""
    ctx = structlog.contextvars.get_contextvars()
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
            "trace_id": ctx.get("trace_id"),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic 校验错误响应"""
    ctx = structlog.contextvars.get_contextvars()
    errors = [
        {
            "field": ".".join(str(loc) for loc in e["loc"]),
            "msg": e["msg"],
            "type": e["type"],
        }
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": SysErrCode.VALIDATION_FAIL,
            "message": "参数校验失败",
            "data": {"errors": errors},
            "trace_id": ctx.get("trace_id"),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常兜底处理"""
    ctx = structlog.contextvars.get_contextvars()
    logger.exception("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": SysErrCode.SERVER_ERROR,
            "message": "服务器内部错误，请联系管理员",
            "data": None,
            "trace_id": ctx.get("trace_id"),
        },
    )


# ── 路由注册 ──────────────────────────────────────────────────────────────────
from app.modules.monitor.router import router as monitor_router
from app.modules.auth.router import router as auth_router
from app.modules.user.router import router as user_router
from app.modules.permission.router import router as permission_router
from app.modules.audit.router import router as audit_router
from app.modules.system.router import router as system_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.message.router import router as message_router
from app.modules.codegen.router import router as codegen_router

# 基础路由
app.include_router(auth_router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(user_router, prefix="/api/v1/users", tags=["用户"])
app.include_router(permission_router, prefix="/api/v1", tags=["权限"])
app.include_router(audit_router, prefix="/api/v1/audit", tags=["审计"])
app.include_router(system_router, prefix="/api/v1", tags=["系统管理"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["仪表盘"])
app.include_router(monitor_router, prefix="/api/v1/monitor", tags=["系统监控"])
app.include_router(message_router, prefix="/api/v1/messages", tags=["消息中心"])
app.include_router(codegen_router, prefix="/api/v1/codegen", tags=["代码生成器"])

# 提供前端权限初始化入口（无前缀，通过路由内部路径区分）
# GET /api/v1/my/permissions  -> permission_router
# GET /api/v1/permissions/tree -> permission_router
# GET/POST /api/v1/roles      -> permission_router

# 配置中心路由
from app.modules.config_center.router import router as config_center_router
app.include_router(config_center_router, prefix="/api/v1", tags=["配置中心"])

# M4 AI 路由
from app.ai.llm.router import router as llm_router
from app.ai.conversation.router import router as conversation_router
from app.ai.agent.router import router as agent_router
from app.ai.knowledge.router import router as knowledge_router
from app.ai.prompt.router import router as prompt_router
from app.ai.tool.router import router as tool_router

app.include_router(llm_router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(prompt_router, prefix="/api/v1")
app.include_router(tool_router, prefix="/api/v1")


# ── 健康检查 ──────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["系统"], summary="健康检查")
async def health_check() -> dict:
    """健康检查接口（无需认证，供 Docker / K8s 探针使用）"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }
