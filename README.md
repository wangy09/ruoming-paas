# 若茗 PaaS

> **企业级 AI 应用开发底座** | Enterprise-grade AI PaaS Framework

**Author**: ruoming  
**Version**: v2.0.0 (MVP)  
**技术栈**: FastAPI + Vue3 + PostgreSQL + Redis + pgvector

---

## 产品定位

若茗 PaaS 是一套面向专业开发者的企业级 AI 应用开发底座。

**一句话定位**：企业级底座 + 原生 AI 能力，开发者只写业务代码。

| 对比维度 | 若茗 PaaS | Dify | RuoYi |
|---------|-----------|------|-------|
| AI + 企业底座 | ✅ 二合一原生集成 | AI 无企业底座 | 企业底座无 AI |
| 多租户 | ✅ 行级隔离，自动注入 | 工作区 | ❌ |
| 权限粒度 | ✅ 细粒度到按钮/列级 | 基础 | 菜单级 |
| 技术栈 | FastAPI + Vue3 | Python + React | Spring Boot |

---

## 快速启动

### 前置条件

- Docker & Docker Compose（推荐）
- （可选本地开发）Python 3.11+、Node.js 20+

### 一键启动（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/ruoming/ruoming-paas.git
cd ruoming-paas

# 2. 复制环境变量
cp backend/.env.example backend/.env.development
# 根据需要编辑 backend/.env.development（至少确认 SECRET_KEY）

# 3. 一键启动（自动检测首次初始化，完成数据库初始化）
bash scripts/start.sh dev
```

启动成功后访问：

| 服务 | 地址 |
|------|------|
| **前端管理台** | http://localhost:3000 |
| **后端 API** | http://localhost:8000 |
| **API 文档** | http://localhost:8000/api/docs |
| **健康检查** | http://localhost:8000/api/health |

### 默认账号

| 账号 | 密码 | 角色 |
|------|------|------|
| `admin` | `ruoming@2024` | 平台超级管理员 |

> ⚠️ **首次登录后请立即修改密码**

### 脚本命令

```bash
bash scripts/start.sh dev       # 启动开发环境
bash scripts/start.sh stop      # 停止开发环境
bash scripts/start.sh status    # 查看服务状态
bash scripts/start.sh logs      # 查看所有日志
bash scripts/start.sh logs backend   # 查看后端日志
bash scripts/start.sh logs frontend  # 查看前端日志
```

---

## 本地开发（不用 Docker）

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖（uv 加速）
pip install uv
uv pip install -e ".[dev]"

# 启动基础设施（PostgreSQL + Redis）
cd ../deploy && docker compose up postgres redis -d

# 数据库迁移
cd ../backend
APP_ENV=development alembic upgrade head

# 初始化种子数据（首次必须）
python scripts/init_data.py

# 启动开发服务器（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（热重载，代理到 localhost:8000）
npm run dev
# 访问 http://localhost:3000

# 构建生产版本
npm run build
# 产物在 dist/ 目录
```

---

## 生产部署

### 准备工作

```bash
# 1. 配置生产环境变量
cat > deploy/.env.production <<EOF
POSTGRES_USER=ruoming
POSTGRES_PASSWORD=<强随机密码>
POSTGRES_DB=ruoming_prod
REDIS_PASSWORD=<强随机密码>
SECRET_KEY=$(openssl rand -hex 32)
APP_VERSION=latest
EOF

# 2. 配置 SSL 证书（Let's Encrypt 或商业证书）
mkdir -p deploy/nginx/ssl
cp /path/to/fullchain.pem deploy/nginx/ssl/
cp /path/to/privkey.pem   deploy/nginx/ssl/

# 3. 修改域名（deploy/nginx/nginx.prod.conf 中的 server_name）
```

### 启动生产环境

```bash
bash scripts/start.sh prod
# 等价于：
# cd deploy && docker compose -f docker-compose.prod.yml up -d
```

### 生产环境架构

```
外部流量 (80/443)
    │
  Nginx (反向代理 + 静态文件)
    ├── /* → 前端 dist 静态文件（Vue3 SPA）
    ├── /api/* → Backend×2（least_conn 负载均衡）
    └── /api/v1/ai/*/stream → Backend（SSE 流式，300s 超时）
         │
    FastAPI backend (×2 副本)
         ├── PostgreSQL + pgvector
         └── Redis
```

---

## 项目结构

```
RuoMingPaas/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 应用入口
│   │   ├── config.py           # 全局配置（Pydantic Settings）
│   │   ├── database.py         # 数据库连接
│   │   ├── core/               # 核心基础设施
│   │   │   ├── security.py     # JWT、密码哈希、AES 加密
│   │   │   ├── deps.py         # 依赖注入（认证、权限）
│   │   │   ├── exceptions.py   # 类型化异常体系
│   │   │   ├── response.py     # 统一响应格式
│   │   │   ├── base_model.py   # ORM 基类
│   │   │   ├── base_repository.py  # 多租户感知 Repository
│   │   │   └── middleware/     # 中间件（RequestID/日志/租户）
│   │   ├── modules/            # 业务模块
│   │   │   ├── auth/           # 认证（JWT、Refresh Token、API Key）
│   │   │   ├── user/           # 用户管理
│   │   │   ├── permission/     # RBAC 权限（角色继承、菜单/按钮/列）
│   │   │   ├── tenant/         # 多租户（配额、套餐）
│   │   │   ├── audit/          # 审计日志
│   │   │   └── config_center/  # 配置中心（四级分层）
│   │   └── ai/                 # AI 能力模块
│   │       ├── llm/            # LLM 网关（多供应商路由）
│   │       ├── agent/          # Agent 编排
│   │       ├── knowledge/      # 知识库 RAG（pgvector）
│   │       └── prompt/         # Prompt 版本管理
│   ├── Dockerfile              # 多阶段构建
│   ├── migrations/             # Alembic 数据库迁移
│   ├── scripts/                # 运维脚本（init_data.py 等）
│   └── tests/                  # 测试（pytest）
├── frontend/                   # Vue3 管理后台
│   ├── src/
│   │   ├── main.ts             # 应用入口
│   │   ├── App.vue
│   │   ├── api/                # 按模块分层 API（auth/user/ai 等）
│   │   ├── store/              # Pinia（auth/permission/app）
│   │   ├── router/             # 动态路由 + 导航守卫
│   │   ├── layouts/            # 主布局（侧边栏+标签页+Header）
│   │   ├── directives/         # v-permission 权限指令
│   │   ├── utils/              # request.ts（Axios+Token刷新）
│   │   └── views/              # 页面
│   │       ├── login/          # 登录页（租户代码+账密）
│   │       ├── dashboard/      # 仪表盘（ECharts统计图表）
│   │       ├── system/         # 系统管理
│   │       │   ├── user/       # 用户管理（CRUD+角色分配）
│   │       │   ├── role/       # 角色管理（CRUD+权限树）
│   │       │   ├── permission/ # 权限管理（树形CRUD）
│   │       │   └── tenant/     # 租户管理（CRUD+用量）
│   │       ├── ai/             # AI 管理
│   │       │   ├── model/      # 模型管理（多供应商+连通测试）
│   │       │   ├── agent/      # Agent管理（卡片式）
│   │       │   ├── knowledge/  # 知识库（文档上传+检索测试）
│   │       │   ├── conversation/ # 对话历史（Markdown渲染）
│   │       │   └── prompt/     # Prompt模板（版本管理+预览）
│   │       └── audit/          # 审计
│   │           ├── logs/       # 操作审计（before/after对比）
│   │           └── login/      # 登录日志
│   ├── Dockerfile              # 多阶段构建（Node构建 + Nginx托管）
│   └── vite.config.ts
├── deploy/                     # 部署配置
│   ├── docker-compose.yml      # 本地开发（Vite Dev Server）
│   ├── docker-compose.prod.yml # 生产部署（Nginx + 双后端实例）
│   ├── nginx/
│   │   └── nginx.prod.conf     # Nginx 生产配置（SSE/SSL/缓存/限流）
│   └── init-db.sql             # 数据库初始化 SQL
├── scripts/
│   └── start.sh                # 一键启动脚本
└── docs/                       # 设计文档（21份）
```

---

## 核心特性

### 后端

| 特性 | 实现方式 |
|------|---------|
| **多租户行级隔离** | Repository 基类自动注入 `tenant_id`，无需手写 WHERE |
| **JWT + Refresh Token** | Access Token 15min，Refresh Token 7天，自动续期 |
| **RBAC 细粒度权限** | 菜单权限 + 按钮权限 + 列权限，前端 v-permission 指令配合 |
| **AI 多供应商路由** | OpenAI / Azure / 通义千问 / Gemini 统一接口，熔断重试 |
| **RAG 知识库** | pgvector 向量检索，支持文档分片和语义搜索 |
| **审计日志** | 自动记录 before/after 数据快照，追踪所有写操作 |
| **四级配置中心** | 平台 → 租户 → 应用 → 用户，下层覆盖上层 |

### 前端

| 特性 | 实现方式 |
|------|---------|
| **动态路由** | 登录后按权限码过滤 asyncRoutes，超管全部可见 |
| **Token 自动刷新** | Axios 拦截器队列，并发请求只刷新一次 |
| **v-permission 指令** | `<el-button v-permission="'user:create'">` 无权限 DOM 移除 |
| **多标签页** | TabsBar 支持关闭/关闭其他/关闭全部，affix 固定 |
| **暗色模式** | VueUse `useDark`，CSS 变量注入 |
| **ECharts 按需加载** | 只注册用到的组件，减少包体积 |
| **Markdown 渲染** | 对话历史用 markdown-it 渲染 AI 回复 |

---

## API 接口

| 模块 | 接口前缀 |
|------|---------|
| 认证 | `POST /api/v1/auth/login` |
| 用户管理 | `/api/v1/users/` |
| 权限/角色/菜单 | `/api/v1/permissions/` |
| 租户管理 | `/api/v1/tenants/` |
| AI 模型 | `/api/v1/ai/models/` |
| Agent | `/api/v1/ai/agents/` |
| 知识库 | `/api/v1/ai/knowledge/` |
| 对话 | `/api/v1/ai/conversations/` |
| 审计日志 | `/api/v1/audit/` |
| API 文档 | `/api/docs` |
| 健康检查 | `/api/health` |

---

## 版本里程碑

| 版本 | 状态 | 内容 |
|------|------|------|
| v1.0（文档期） | ✅ 完成 | 21 份设计文档 |
| **v2.0（MVP）** | ✅ **完成** | 后端全模块 + Vue3 管理台 + Docker 一键部署 |
| v3.0（完整版） | ⬜ 计划中 | 代码生成器 + 示例项目 + 测试覆盖率 ≥ 80% |
| v4.0（生态版） | ⬜ 计划中 | 插件市场 + 云托管 |

---

## 开发规范

- **后端**：Python 3.11+，`ruff` 格式化，所有函数必须有类型注解
- **前端**：Vue3 + TypeScript，ESLint + Prettier，组合式 API（`<script setup>`）
- **Commit**：遵循 Conventional Commits（`feat:` / `fix:` / `docs:` ...）
- **数据库变更**：必须通过 `alembic revision --autogenerate` 生成迁移文件
- **测试覆盖率**：核心模块 API 层目标 ≥ 80%

---

*© 2024 ruoming. All rights reserved.*
