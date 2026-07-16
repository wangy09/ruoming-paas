# 若茗 PaaS 开发底座用户手册

本手册面向基于若茗 PaaS 做二次开发、业务交付和平台管理的团队，先说明如何启动服务和开发模块，再介绍平台内置基础功能。

## 快速开始

在项目根目录启动开发环境：

```bash
bash scripts/start.sh dev
bash scripts/start.sh status
bash scripts/start.sh logs backend
bash scripts/start.sh stop
```

默认入口：

- 前端：`http://localhost:3000`
- API 文档：`http://localhost:8000/api/docs`
- 健康检查：`http://localhost:8000/api/health`
- 默认账号：`admin / ruoming@2024`

更新代码后看不到新菜单时，执行：

```bash
cd deploy
docker compose exec backend python /app/scripts/init_data.py
```

## 开发者指南

若茗 PaaS 是开发底座，开发者通常围绕“启动环境、加业务模块、接菜单权限、联调验证、交付上线”来使用平台。

### 目录约定

- `backend/app/modules/`：后端业务模块。
- `backend/alembic/versions/`：数据库迁移。
- `backend/scripts/init_data.py`：菜单、角色、权限、字典和种子数据。
- `frontend/src/views/`：前端页面。
- `frontend/src/api/`：接口封装。
- `frontend/src/types/`：类型定义。
- `docs/`：开发文档和用户手册。

### 新增业务模块

1. 设计数据表和接口，确认租户隔离、软删除、审计日志和数据权限。
2. 在 `backend/app/modules/<module>/` 下新增 `models.py`、`schemas.py`、`service.py`、`router.py`。
3. 注册 Router，接口统一使用 `/api/v1/` 前缀。
4. 新增 Alembic 迁移，创建表时显式包含基础字段。
5. 在 `frontend/src/api/` 增加接口封装。
6. 在 `frontend/src/views/` 新增页面。
7. 在 `backend/scripts/init_data.py` 或“菜单管理”中新增菜单和按钮权限。
8. 在“角色授权”中给角色分配权限，重新登录验证。

### 菜单权限

菜单由后端 `sys_permission` 驱动。

- `perm_type=menu`：控制页面是否出现在侧边栏。
- `perm_type=button`：控制新增、编辑、删除、导出等动作。
- `component=system/user/index` 对应 `frontend/src/views/system/user/index.vue`。

### 配置与集成

- 运行时开关、第三方地址、额度、密钥优先放到“配置中心”。
- 敏感配置必须加密和脱敏，公开配置只能返回非加密且 `is_public=true` 的值。
- 第三方系统优先接入“集成中心”，业务表只保存连接 ID，不重复保存密钥。
- 通讯录同步类能力应提供自检、预览、执行和同步日志。

### 异步任务

- 耗时任务优先使用 Celery 或计划任务。
- 计划任务统一进入“系统监控 / 计划任务”。
- 同一外部联系人同步连接使用 `func_name + kwargs.connection_id` 去重。
- 启用计划任务时，如果 `next_run_at` 为空，只初始化下一次执行时间，不立即执行。

### 代码生成

- 写入文件需要 `dev:codegen:write` 权限。
- 生成路径禁止绝对路径和 `..` 路径穿越。
- 默认跳过已存在文件，可手动选择覆盖。
- 生成结果会返回创建、覆盖、跳过和不可用文件数量。

### 开发验证

```bash
PYENV_VERSION=3.11.7 python -m py_compile backend/scripts/init_data.py
cd frontend && npm run type-check
git diff --check
```

更多开发说明请看：

- `docs/01_快速启动.md`
- `docs/当前功能清单.md`
- `docs/如何添加业务模块.md`
- `docs/07_API规范.md`
- `docs/08_前端架构.md`

## 登录与工作台

1. 打开平台地址，例如 `http://localhost:3000`。
2. 使用管理员提供的账号登录。初始化环境默认超管账号为 `admin`，默认密码为 `ruoming@2024`。
3. 首次登录后进入右上角用户菜单，维护个人资料并修改密码。

工作台展示当前用户可访问的常用入口、消息、公告、待关注事项和系统摘要。

- 点击“刷新首页”重新拉取数据。
- 点击“首页设置”调整首页模板、组件显示和常用入口。
- 常用入口会按当前账号菜单权限自动过滤。

## 平台内置基础功能

### 组织与账号

用于维护账号、角色、状态、部门、租户和外部联系人同步。

- 新增或编辑用户：维护用户名、昵称、手机号、邮箱、部门和状态。
- 分配角色：给用户授予租户管理员、普通用户或自定义角色。
- 同步用户：选择飞书、钉钉或企业微信连接，先执行自检和预览，再执行同步。
- 部门管理用于维护组织树。
- 租户管理用于维护租户、套餐、容量和状态。

### 权限中心

用于维护角色、菜单、按钮、列权限和数据范围。

- 先分配根菜单，再分配子菜单。
- 删除、导出、重置密码、写入生成文件等敏感操作应使用按钮权限控制。
- 组件路径对应 `frontend/src/views` 下的页面，例如 `system/user/index`。

### 平台配置

配置中心支持全局、租户、应用、用户四类作用域。加密配置在列表中脱敏，公开配置只返回已启用、非加密、`is_public=true` 的配置。

字典管理用于维护状态、类型、枚举值等下拉数据。

### 资源与集成

文件中心统一管理上传文件，支持上传、预览、下载、归档和删除。

集成中心配置飞书、钉钉、企业微信和自定义连接：

- 飞书通讯录同步或 OAuth：需要 `app_id`、`app_secret`。
- 钉钉通讯录同步或 OAuth：需要 `app_key`、`app_secret`。
- 企业微信通讯录同步：需要 `corp_id`、`corp_secret`。

### AI 管理

- AI 对话：直接与模型或 Agent 对话。
- 模型管理：先创建模型配置，再创建或绑定 Agent。
- Agent 管理：维护系统提示词、绑定模型、工具和工作流配置。
- 知识库：管理 RAG 文档和向量索引。
- Prompt 模板：维护可复用提示词和版本。
- 工具管理：维护 Agent 可调用工具。

### 消息与审计

- 平台公告：创建、编辑、发布公告，可按全部、部门或指定用户发送。
- 我的消息：查看当前账号收到的站内消息。
- 操作日志：记录关键操作、请求路径、操作者和执行结果。
- 登录日志：记录登录行为、安全事件、设备和浏览器信息。

### 系统监控

#### 服务监控

查看服务和资源运行状态。

#### 计划任务

统一管理定时任务和执行日志。

- 启用任务时，如果 `next_run_at` 为空，系统只初始化下一次执行时间，不会立即执行。
- 外部联系人同步任务使用 `func_name + kwargs.connection_id` 去重。
- 可手动立即执行任务并查看执行日志。

## 常见问题

### 看不到菜单

检查当前角色是否拥有根菜单和子菜单权限、菜单是否可见、权限缓存是否刷新。

### 配置改了但页面没变化

检查配置是否启用、是否公开、作用域是否正确。必要时在配置中心清缓存。

### Agent 无法使用

先确认模型管理中已有可用模型，再检查 Agent 是否绑定正确模型。

### 通讯录同步失败

先在集成中心测试连接，再在用户管理中执行同步自检。重点检查应用凭证、通讯录权限和部门可见范围。
