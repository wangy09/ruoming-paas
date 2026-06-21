# 07 API 规范

## 1. URL 规范

```
/api/{version}/{module}/{resource}[/{id}][/{sub-resource}]

示例：
GET    /api/v1/users              用户列表
POST   /api/v1/users              新增用户
GET    /api/v1/users/{id}         用户详情
PUT    /api/v1/users/{id}         修改用户（全量）
PATCH  /api/v1/users/{id}         修改用户（部分）
DELETE /api/v1/users/{id}         删除用户
POST   /api/v1/users/{id}/enable  启用用户（动作类操作）

GET    /api/v1/ai/agents/{id}/conversations  Agent 对话列表
POST   /api/v1/ai/agents/{id}/run            运行 Agent
```

### 1.1 API 版本管理策略

| 场景 | 规则 |
|------|------|
| **版本格式** | URI 路径版本：`/api/v1/`、`/api/v2/`，不使用请求头版本 |
| **兼容期** | 新版本发布后，旧版本至少维护 **6 个月**，通过响应头 `Deprecation: true` 告知 |
| **破坏性变更** | 字段删除/类型变更/语义变更必须升版本号 |
| **非破坏性变更** | 新增字段/新增可选参数无需升版本 |
| **Open API** | 对外开放接口（`/api/open/v1/`）独立版本管理，需 API Key 认证 |

```python
# app/main.py —— 多版本路由注册
from app.api.v1 import router as v1_router
from app.api.v2 import router as v2_router   # 未来按需添加

app.include_router(v1_router, prefix="/api/v1")
# app.include_router(v2_router, prefix="/api/v2")  # v2 就绪后取消注释
```

---

## 2. 统一响应格式

```python
# app/core/response.py
from pydantic import BaseModel
from typing import TypeVar, Generic, Optional

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: int = 200           # 业务状态码（非 HTTP 状态码，见第3节错误码体系）
    message: str = "success"
    data: Optional[T] = None
    trace_id: str | None = None   # 链路 TraceID（兼容 request_id）

class PageData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int                # 总页数
    has_more: bool            # 是否还有更多（无限滚动场景）

# 快捷方法
def ok(data=None, message="success") -> ApiResponse:
    return ApiResponse(code=200, message=message, data=data)

def created(data=None) -> ApiResponse:
    return ApiResponse(code=201, message="created", data=data)

def error(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)
```

### 2.1 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "admin",
    "nickname": "管理员"
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 2.2 分页响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "pages": 5
  }
}
```

### 2.3 错误响应示例

```json
{
  "code": 40300,
  "message": "缺少权限: system:user:delete",
  "data": null,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 3. 业务错误码规范（分级体系）

错误码采用 **5位数字**，按首位数字分为两大类：

```
1xxxx   系统级错误（框架/基础设施层抛出）
2xxxx   业务级错误（业务逻辑层抛出，含具体业务含义）
```

> 与 HTTP 状态码的关系：`code` 是业务错误码，HTTP 状态码独立设置（4xx/5xx）。前端优先判断 `code`，`code=200` 表示成功（无论 HTTP 状态码）。

### 3.1 系统级错误码（1xxxx）

| 错误码 | HTTP 状态 | 含义 |
|--------|---------|------|
| `10000` | 200 | 成功 |
| `10001` | 400 | 参数缺失或格式错误 |
| `10002` | 422 | 字段校验失败（附 `data` 字段详细错误） |
| `10100` | 401 | 未登录或 Token 无效 |
| `10101` | 401 | Token 已过期，请使用 Refresh Token 刷新 |
| `10102` | 401 | Refresh Token 无效或已轮换 |
| `10200` | 403 | 无操作权限（缺少 permission） |
| `10201` | 403 | IP 被封禁 |
| `10202` | 403 | 账号已被锁定（登录失败次数过多） |
| `10203` | 403 | 租户已过期或被禁用 |
| `10300` | 404 | 资源不存在 |
| `10400` | 429 | 请求过于频繁（限流） |
| `10401` | 429 | 租户 API 配额已耗尽 |
| `10402` | 429 | 租户 AI Token 配额已耗尽 |
| `10500` | 500 | 服务器内部错误 |
| `10501` | 500 | 数据库操作失败 |
| `10502` | 503 | 依赖服务不可用（AI 模型/OSS 等） |

### 3.2 业务级错误码（2xxxx）

按模块分段，各模块维护自己的错误码段：

| 模块 | 错误码段 | 示例 |
|------|---------|------|
| 用户/认证 | `21000–21099` | `21001` 用户名已存在，`21002` 旧密码错误 |
| 租户 | `21100–21199` | `21101` 租户码已被使用，`21102` 用户数已达上限 |
| 权限 | `21200–21299` | `21201` 不能删除有子项的角色 |
| AI | `22000–22099` | `22001` 知识库文件解析失败，`22002` Agent 执行超时 |
| 文件 | `23000–23099` | `23001` 文件类型不允许，`23002` 文件大小超限 |
| 导入 | `24000–24099` | `24001` 模板格式错误，`24002` 数据行校验失败 |

```python
# app/core/error_codes.py —— 错误码常量（系统级）
class SysErrCode:
    SUCCESS           = 10000
    PARAM_ERROR       = 10001
    VALIDATION_FAIL   = 10002
    UNAUTHORIZED      = 10100
    TOKEN_EXPIRED     = 10101
    REFRESH_INVALID   = 10102
    FORBIDDEN         = 10200
    IP_BANNED         = 10201
    ACCOUNT_LOCKED    = 10202
    TENANT_DISABLED   = 10203
    NOT_FOUND         = 10300
    RATE_LIMITED      = 10400
    QUOTA_API         = 10401
    QUOTA_AI_TOKEN    = 10402
    SERVER_ERROR      = 10500
    DB_ERROR          = 10501
    SERVICE_UNAVAIL   = 10502

# app/modules/user/error_codes.py —— 业务错误码（用户模块）
class UserErrCode:
    USERNAME_EXISTS   = 21001
    WRONG_PASSWORD    = 21002
    USER_NOT_FOUND    = 21003
```

---

## 4. 全局异常处理

```python
# app/core/exceptions.py
from app.core.error_codes import SysErrCode

class AppException(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status

class AuthException(AppException):
    def __init__(self, message="未登录或 Token 无效", code=SysErrCode.UNAUTHORIZED):
        super().__init__(code=code, message=message, http_status=401)

class TokenExpiredException(AppException):
    def __init__(self):
        super().__init__(code=SysErrCode.TOKEN_EXPIRED, message="Token 已过期，请刷新", http_status=401)

class PermissionException(AppException):
    def __init__(self, message="无操作权限"):
        super().__init__(code=SysErrCode.FORBIDDEN, message=message, http_status=403)

class NotFoundException(AppException):
    def __init__(self, resource="资源"):
        super().__init__(code=SysErrCode.NOT_FOUND, message=f"{resource}不存在", http_status=404)

class ValidationException(AppException):
    def __init__(self, message="参数校验失败", details=None):
        super().__init__(code=SysErrCode.VALIDATION_FAIL, message=message, http_status=422)
        self.details = details

class QuotaExceededError(AppException):
    def __init__(self, message="配额已耗尽", code=SysErrCode.QUOTA_API):
        super().__init__(code=code, message=message, http_status=429)


# app/main.py 注册异常处理器
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
            "trace_id": structlog.contextvars.get_contextvars().get("trace_id")
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(l) for l in e["loc"]), "msg": e["msg"]}
              for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"code": SysErrCode.VALIDATION_FAIL, "message": "参数校验失败", "data": errors}
    )
```

---

## 5. 分页与筛选规范

### 5.1 分页参数（统一标准）

```python
# app/core/utils/pagination.py
from pydantic import BaseModel, Field

class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=200, description="每页数量，最大 200")
    order_by: str = Field(default="created_at", description="排序字段名（白名单校验）")
    order_dir: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
```

**请求示例：**
```
GET /api/v1/users?page=2&page_size=20&order_by=created_at&order_dir=desc
```

**响应包含分页元信息：**
```json
{
  "code": 10000,
  "data": {
    "items": [...],
    "total": 100,
    "page": 2,
    "page_size": 20,
    "pages": 5,
    "has_more": true
  }
}
```

### 5.2 筛选参数规范

| 场景 | 参数格式 | 示例 |
|------|---------|------|
| 精确匹配 | `field=value` | `status=1` |
| 模糊搜索 | `keyword=xxx`（统一字段名） | `keyword=张三` |
| 范围筛选 | `field_gte` / `field_lte` | `created_at_gte=2024-01-01` |
| 多值筛选 | `field=v1,v2,v3`（逗号分隔） | `status=1,2` |
| 时间范围 | `start_date` / `end_date` | `start_date=2024-01-01` |

> **安全注意**：`order_by` 字段必须经过白名单校验，禁止直接拼入 SQL，防止注入。

---

## 6. 流式响应（AI SSE）

```python
# AI 对话流式推送
@router.post("/chat")
async def chat_stream(request: ChatRequest, current_user = Depends(get_current_user)):
    async def event_generator():
        async for chunk in llm_service.stream_chat(request.messages):
            data = json.dumps({"type": "content", "content": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        # 结束标记
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # 关闭 Nginx 缓冲
        }
    )
```

---

## 7. API 文档配置

```python
# app/main.py
app = FastAPI(
    title="RuoMingSaaS API",
    description="企业级 SaaS 框架 API 文档",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "认证", "description": "登录、Token 管理、验证码"},
        {"name": "用户", "description": "用户 CRUD"},
        {"name": "权限", "description": "角色、权限、菜单"},
        {"name": "字典", "description": "字典类型、字典项管理"},
        {"name": "AI-LLM", "description": "大模型管理"},
        {"name": "AI-Agent", "description": "Agent 管理与运行"},
        {"name": "AI-知识库", "description": "知识库管理"},
    ]
)
```
