# AI 助手三大功能实现计划

## Context

用户希望 AI 助手具备三大能力：**写代码（含下载）**、**错误检测**、**反馈记录（含管理后台）**。当前 AI 助手已有浮动面板、Agent 调用（SSE 流式）、知识库 RAG、导航工具，工具注册机制（`ToolRegistry`）成熟，代码生成器（`codegen`）有完整 Jinja2 模板。本计划在现有架构上扩展，不引入新依赖。

---

## 功能1：写代码（含下载）

### 后端

**新建** `backend/app/ai/tool/builtin/__init__.py` + `code_writer.py`，注册两个工具：

| 工具 ID | 用途 | 参数 |
|---|---|---|
| `builtin:code_generate` | 生成任意代码片段 | `language`, `task`, `framework=""`, `context=""` |
| `builtin:code_generate_crud` | 生成完整 CRUD 模块 | `table_name`, `module_name`, `entity_name=""`, `page_title=""`, `preview_only=True` |

- `code_generate`：内部调 `LLMService().chat()`，system prompt 注入项目规范（FastAPI + Repository + Pydantic / Vue3 + Element Plus + TS），`temperature=0.2`
- `code_generate_crud`：复用 `CodegenService.preview()`（用 `AsyncSessionFactory` 独立 session 隔离事务），返回各文件路径 + 内容预览
- 生成后自动调 `_check_code_internal`（功能2）做自检，结果附在代码后

**修改** `backend/app/modules/codegen/router.py`：新增 `POST /codegen/download-by-spec` 端点，按生成规格直接下载 ZIP（无需保存配置）

**修改** `backend/app/main.py`：lifespan 中 `import app.ai.tool.builtin` 触发注册

### 前端

**新建** `frontend/src/utils/markdown.ts`：`createEnhancedMd()` 工厂，覆盖 markdown-it `fence` 渲染规则，在每个代码块外包裹工具栏（语言标签 + 复制按钮 + 下载按钮）

**修改** `AiAssistant/index.vue` 和 `chat/index.vue`：
- 替换 `new MarkdownIt()` 为 `createEnhancedMd()`
- 添加 click 事件委托：复制用 `navigator.clipboard`，下载用 `Blob + URL.createObjectURL`
- 追加 `.code-block-toolbar` / `.code-btn` 样式

---

## 功能2：错误检测

### 后端

**新建** `backend/app/ai/tool/builtin/code_checker.py`，注册工具：

| 工具 ID | 用途 | 参数 |
|---|---|---|
| `builtin:code_check` | 代码静态审查 | `code`, `language`, `focus="all"`, `context=""` |

- 内部调 `LLMService().chat()`，`temperature=0`，system prompt 要求 JSON 结构化输出
- 输出按严重级别分类：`critical` / `warning` / `info`，每条含行号、问题描述、修复建议、修复代码
- 抽取 `_check_code_internal(code, language)` 内部函数，供 `code_generate` 末尾自检调用
- JSON 解析失败时降级为纯文本返回

### 前端

无需新页面，检测结果通过 markdown 自然渲染，代码块复用功能1的复制/下载按钮。

---

## 功能3：反馈记录（含管理后台）

### 数据模型

**修改** `backend/app/ai/conversation/models.py`，追加 `AiMessageFeedback`（继承 `BaseModel`）：
- `message_id`, `conversation_id`, `agent_id`, `user_id`（索引）
- `rating`（1=赞 / -1=踩）, `feedback_content`, `tags`（JSONB）, `message_snapshot`
- `status`（pending/resolved/ignored）, `reply`, `replied_by`, `replied_at`
- 唯一约束：`(message_id, user_id)` —— 一条消息一个用户只能反馈一次

**新建** Alembic migration 文件

### 后端 API

**新建** `backend/app/ai/feedback/` 模块（`schemas.py` / `service.py` / `router.py`）：

| 端点 | 用途 | 权限 |
|---|---|---|
| `POST /ai/feedback` | 用户提交反馈 | 登录 |
| `GET /ai/feedback/me` | 我的反馈列表 | 登录 |
| `GET /ai/feedback` | 管理后台列表（含筛选） | `ai:feedback:view` |
| `GET /ai/feedback/stats` | 统计（点赞率/趋势/标签分布） | `ai:feedback:view` |
| `PUT /ai/feedback/{id}` | 处理反馈（回复/改状态） | `ai:feedback:reply` |
| `DELETE /ai/feedback/{id}` | 删除反馈 | `ai:feedback:delete` |

**修改** `backend/app/main.py`：注册 `feedback_router`

### 前端 - 用户端

**新建** `frontend/src/components/AiAssistant/FeedbackDialog.vue`：评分（赞/踩）+ 标签多选（回答错误/信息过时/格式混乱/有害内容/其他）+ 内容 textarea

**修改** `AiAssistant/index.vue` 和 `chat/index.vue`：
- 消息数据结构加 `feedback_rating?` / `feedback_id?`
- AI 消息气泡下方加 👍/👎 按钮
- 点击调用 `feedbackApi.create`，点踩弹 `FeedbackDialog`

### 前端 - 管理后台

**新建** `frontend/src/views/ai/feedback/index.vue`：
- 顶部统计卡片：总数/点赞/点踩/点赞率/待处理
- 筛选区：评分/状态/Agent/日期范围
- 表格：消息快照/评分/反馈内容/用户/Agent/时间/状态
- 详情抽屉：完整消息 + 回复 + 状态流转

**修改** `frontend/src/api/ai.ts`：追加 `feedbackApi`
**修改** `frontend/src/types/index.d.ts`：追加 `FeedbackInfo` / `FeedbackStats` 类型
**修改** `AiAssistant/index.vue` 的 `allNavRoutes`：添加 `{ path: '/ai/feedback', label: '反馈管理', keywords: ['反馈', 'feedback'] }`

### 权限注册

在 `permission` 表新增菜单：`/ai/feedback`（code: `ai:feedback:view`）+ 按钮（`ai:feedback:reply`、`ai:feedback:delete`），通过 init_data.py 或手动添加。

---

## 文件清单

### 新建（12 个）

| 文件 | 说明 |
|---|---|
| `backend/app/ai/tool/builtin/__init__.py` | 触发内置工具注册 |
| `backend/app/ai/tool/builtin/code_writer.py` | code_generate + code_generate_crud 工具 |
| `backend/app/ai/tool/builtin/code_checker.py` | code_check 工具 + _check_code_internal |
| `backend/app/ai/feedback/__init__.py` | 模块初始化 |
| `backend/app/ai/feedback/schemas.py` | FeedbackCreate/Update/Info/Stats |
| `backend/app/ai/feedback/service.py` | FeedbackService |
| `backend/app/ai/feedback/router.py` | 反馈 API |
| `backend/migrations/versions/<rev>_add_ai_feedback.py` | Alembic migration |
| `frontend/src/utils/markdown.ts` | createEnhancedMd() |
| `frontend/src/components/AiAssistant/FeedbackDialog.vue` | 反馈弹窗 |
| `frontend/src/views/ai/feedback/index.vue` | 反馈管理后台 |

### 修改（7 个）

| 文件 | 改动 |
|---|---|
| `backend/app/ai/conversation/models.py` | 追加 AiMessageFeedback |
| `backend/app/modules/codegen/router.py` | 追加 download-by-spec 端点 |
| `backend/app/main.py` | 注册 builtin 工具 + feedback_router |
| `frontend/src/api/ai.ts` | 追加 feedbackApi |
| `frontend/src/types/index.d.ts` | 追加反馈类型 |
| `frontend/src/components/AiAssistant/index.vue` | markdown 增强 + 反馈按钮 + 导航路由 |
| `frontend/src/views/ai/chat/index.vue` | markdown 增强 + 反馈按钮 |

---

## 实现顺序

1. **后端工具**（功能1+2）：`builtin/code_writer.py` + `code_checker.py` → `main.py` 注册
2. **前端代码块增强**：`utils/markdown.ts` → 修改两个 vue 文件
3. **后端反馈**（功能3）：模型 + migration + feedback 模块 → `main.py` 注册
4. **前端反馈用户端**：`FeedbackDialog.vue` → 修改两个 vue 文件
5. **前端反馈管理后台**：`views/ai/feedback/index.vue` + API + 类型
6. **权限注册**：permission 表 + allNavRoutes

---

## 验证

1. **写代码**：AI 助手中输入"帮我写一个 FastAPI 用户登录接口"，AI 调用 `code_generate` 工具，返回符合项目规范的代码，代码块右上角有复制和下载按钮
2. **CRUD 生成**：输入"帮我生成一个客户管理模块，表名 customer"，AI 调用 `code_generate_crud`，返回多个文件预览
3. **错误检测**：粘贴一段有 SQL 注入风险的代码，AI 调用 `code_check`，返回分类问题列表
4. **自检**：生成的代码末尾自动附带"自检结果"段落
5. **反馈**：AI 回复下方点踩，弹出反馈对话框，提交后在管理后台 `/ai/feedback` 可看到记录
6. **统计**：管理后台顶部卡片显示点赞率，筛选功能正常
