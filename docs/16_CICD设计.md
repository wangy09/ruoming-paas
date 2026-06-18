# 16 CI/CD 设计

> 若茗 PaaS 的 CI/CD 体系采用**平台无关设计**：流水线逻辑统一，代码托管平台可在 GitHub / GitLab / 自建 Gitea 之间自由切换，切换成本极低。

---

## 1. 整体设计思路

### 核心原则

```
平台无关     → 流水线逻辑写在 Makefile / Shell 脚本中，CI 平台只负责触发和环境变量注入
环境隔离     → dev / staging / production 三套环境，代码分支与环境严格对应
镜像不可变   → 每次构建产出唯一 tag 的 Docker 镜像，部署只做镜像替换
密钥零泄露   → 所有密钥走 CI 平台的 Secret 管理，绝不写入代码
快速反馈     → PR/MR 阶段只做 lint + test（<3分钟），合并后才做构建+部署
```

### 分支与环境对应关系

```
feature/*  →  仅触发 PR 检查（lint + test）
develop    →  自动部署到 dev 环境
main       →  自动部署到 staging 环境
tag v*.*.*  →  手动审批后部署到 production 环境
```

---

## 2. 流水线统一脚本层（平台无关）

所有 CI 平台调用同一套 Makefile 命令，不把逻辑写进 CI YAML。

```makefile
# Makefile（项目根目录）

IMAGE_BACKEND  = registry.example.com/ruoming/backend
IMAGE_FRONTEND = registry.example.com/ruoming/frontend
GIT_SHA        = $(shell git rev-parse --short HEAD)
GIT_TAG        = $(shell git describe --tags --always)

# ─── 代码检查 ───────────────────────────────────────────
lint-backend:
	cd backend && ruff check . && mypy app/

lint-frontend:
	cd frontend && npm run lint

lint: lint-backend lint-frontend

# ─── 测试 ────────────────────────────────────────────────
test-backend:
	cd backend && pytest tests/ -v --cov=app --cov-report=xml

test-frontend:
	cd frontend && npm run test:unit

test: test-backend test-frontend

# ─── 构建镜像 ────────────────────────────────────────────
build-backend:
	docker build -t $(IMAGE_BACKEND):$(GIT_SHA) -t $(IMAGE_BACKEND):latest ./backend

build-frontend:
	docker build -t $(IMAGE_FRONTEND):$(GIT_SHA) -t $(IMAGE_FRONTEND):latest ./frontend

build: build-backend build-frontend

# ─── 推送镜像 ────────────────────────────────────────────
push:
	docker push $(IMAGE_BACKEND):$(GIT_SHA)
	docker push $(IMAGE_BACKEND):latest
	docker push $(IMAGE_FRONTEND):$(GIT_SHA)
	docker push $(IMAGE_FRONTEND):latest

# ─── 部署（通过 SSH 触发远端 deploy.sh）────────────────────
deploy-dev:
	ssh deploy@dev.example.com "cd /opt/ruoming && IMAGE_TAG=$(GIT_SHA) bash deploy.sh"

deploy-staging:
	ssh deploy@staging.example.com "cd /opt/ruoming && IMAGE_TAG=$(GIT_SHA) bash deploy.sh"

deploy-prod:
	ssh deploy@prod.example.com "cd /opt/ruoming && IMAGE_TAG=$(GIT_TAG) bash deploy.sh"

# ─── 数据库迁移（部署后执行）────────────────────────────────
migrate-dev:
	ssh deploy@dev.example.com "docker exec ruoming_backend alembic upgrade head"

migrate-staging:
	ssh deploy@staging.example.com "docker exec ruoming_backend alembic upgrade head"
```

### 远端服务器部署脚本

```bash
#!/bin/bash
# /opt/ruoming/deploy.sh（放在部署服务器上）
set -e

IMAGE_BACKEND="registry.example.com/ruoming/backend:${IMAGE_TAG}"
IMAGE_FRONTEND="registry.example.com/ruoming/frontend:${IMAGE_TAG}"

echo "==> Pulling images: ${IMAGE_TAG}"
docker pull "${IMAGE_BACKEND}"
docker pull "${IMAGE_FRONTEND}"

echo "==> Updating docker-compose..."
export BACKEND_IMAGE="${IMAGE_BACKEND}"
export FRONTEND_IMAGE="${IMAGE_FRONTEND}"

echo "==> Rolling update backend (zero-downtime)..."
docker compose up -d --no-deps --scale backend=2 backend
sleep 10
docker compose up -d --no-deps --scale backend=1 backend

echo "==> Updating frontend..."
docker compose up -d --no-deps frontend

echo "==> Running DB migrations..."
docker compose exec -T backend alembic upgrade head

echo "==> Deploy complete: ${IMAGE_TAG}"
```

---

## 3. 方案一：GitHub Actions

> 适合：代码可以放在 GitHub（公开开源 or 私有仓库均可）

### 文件结构

```
.github/
└── workflows/
    ├── pr-check.yml      ← PR 检查（lint + test）
    ├── deploy-dev.yml    ← develop 分支自动部署 dev
    ├── deploy-staging.yml ← main 分支自动部署 staging
    └── release.yml       ← tag 触发，手动审批后部署 production
```

### PR 检查（pr-check.yml）

```yaml
name: PR Check

on:
  pull_request:
    branches: [develop, main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: ruoming_test
          POSTGRES_USER: ruoming
          POSTGRES_PASSWORD: testpassword
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install backend deps
        run: cd backend && pip install -r requirements.txt

      - name: Lint backend
        run: make lint-backend

      - name: Test backend
        env:
          DATABASE_URL: postgresql+asyncpg://ruoming:testpassword@localhost:5432/ruoming_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET: test_secret_min_32_characters_here
        run: make test-backend

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend deps
        run: cd frontend && npm ci

      - name: Lint & test frontend
        run: make lint-frontend && make test-frontend

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: backend/coverage.xml
```

### 部署到 dev（deploy-dev.yml）

```yaml
name: Deploy Dev

on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: dev        # GitHub Environments 隔离 secret

    steps:
      - uses: actions/checkout@v4

      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: registry.example.com
          username: ${{ secrets.REGISTRY_USER }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Build & Push
        run: make build push

      - name: Deploy to dev
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEV_HOST }}
          username: deploy
          key: ${{ secrets.DEV_SSH_KEY }}
          script: |
            cd /opt/ruoming
            IMAGE_TAG=$(git rev-parse --short ${{ github.sha }}) bash deploy.sh
```

### 生产发布（release.yml）

```yaml
name: Release to Production

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Login & Build & Push
        run: |
          echo ${{ secrets.REGISTRY_PASSWORD }} | docker login registry.example.com -u ${{ secrets.REGISTRY_USER }} --password-stdin
          make build push

  deploy-prod:
    needs: build
    runs-on: ubuntu-latest
    environment: production    # 配置 required reviewers，需要人工审批
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to production
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_HOST }}
          username: deploy
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/ruoming
            IMAGE_TAG=${{ github.ref_name }} bash deploy.sh
```

> **GitHub Environments 审批**：在仓库 Settings → Environments → production，配置 `Required reviewers`，生产部署必须人工点击 Approve 才会执行。

---

## 4. 方案二：GitLab CI/CD

> 适合：想完全自主管理代码仓库，自建 GitLab 或使用 GitLab.com

### 文件结构

```
.gitlab-ci.yml   ← 单文件，用 stages 划分阶段
```

### .gitlab-ci.yml

```yaml
stages:
  - check
  - build
  - deploy-dev
  - deploy-staging
  - deploy-prod

variables:
  IMAGE_BACKEND: $CI_REGISTRY_IMAGE/backend
  IMAGE_FRONTEND: $CI_REGISTRY_IMAGE/frontend
  DOCKER_DRIVER: overlay2

# ─── 模板（减少重复）────────────────────────────────────────
.ssh-deploy: &ssh-deploy
  before_script:
    - eval $(ssh-agent -s)
    - echo "$DEPLOY_SSH_KEY" | ssh-add -
    - mkdir -p ~/.ssh && ssh-keyscan $DEPLOY_HOST >> ~/.ssh/known_hosts

# ─── PR/MR 检查 ──────────────────────────────────────────────
lint-test:
  stage: check
  image: python:3.11
  services:
    - postgres:15
    - redis:7-alpine
  variables:
    POSTGRES_DB: ruoming_test
    POSTGRES_USER: ruoming
    POSTGRES_PASSWORD: testpassword
    DATABASE_URL: postgresql+asyncpg://ruoming:testpassword@postgres:5432/ruoming_test
    REDIS_URL: redis://redis:6379/0
    JWT_SECRET: test_secret_min_32_characters_here
  script:
    - pip install -r backend/requirements.txt
    - make lint-backend test-backend
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "develop"
    - if: $CI_COMMIT_BRANCH == "main"
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: backend/coverage.xml

# ─── 构建镜像 ─────────────────────────────────────────────────
build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - make build push
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+/

# ─── 部署 dev ─────────────────────────────────────────────────
deploy-dev:
  stage: deploy-dev
  <<: *ssh-deploy
  variables:
    DEPLOY_HOST: $DEV_HOST
    DEPLOY_SSH_KEY: $DEV_SSH_KEY
  script:
    - ssh deploy@$DEV_HOST "cd /opt/ruoming && IMAGE_TAG=$CI_COMMIT_SHORT_SHA bash deploy.sh"
  environment:
    name: development
    url: https://dev.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"

# ─── 部署 staging ──────────────────────────────────────────────
deploy-staging:
  stage: deploy-staging
  <<: *ssh-deploy
  variables:
    DEPLOY_HOST: $STAGING_HOST
    DEPLOY_SSH_KEY: $STAGING_SSH_KEY
  script:
    - ssh deploy@$STAGING_HOST "cd /opt/ruoming && IMAGE_TAG=$CI_COMMIT_SHORT_SHA bash deploy.sh"
  environment:
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# ─── 部署 production（需要手动触发）────────────────────────────
deploy-prod:
  stage: deploy-prod
  <<: *ssh-deploy
  variables:
    DEPLOY_HOST: $PROD_HOST
    DEPLOY_SSH_KEY: $PROD_SSH_KEY
  script:
    - ssh deploy@$PROD_HOST "cd /opt/ruoming && IMAGE_TAG=$CI_COMMIT_TAG bash deploy.sh"
  environment:
    name: production
    url: https://app.example.com
  when: manual         # 必须人工点击触发
  allow_failure: false
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+/
```

---

## 5. 方案三：自建 Gitea + Gitea Actions

> 适合：**完全私有化部署**，代码不出内网，适合对数据安全要求高的场景

### 为什么选 Gitea

| | Gitea | GitLab CE |
|---|---|---|
| 资源占用 | 极低（~100MB RAM） | 高（~4GB RAM） |
| 部署复杂度 | 单二进制文件 | 多服务 |
| Gitea Actions 兼容性 | 兼容 GitHub Actions YAML | 独立语法 |
| 适用场景 | 小团队、低预算、内网隔离 | 中大团队，需要完整 DevOps 套件 |

### Gitea 部署（Docker Compose 追加）

```yaml
# 追加到 deploy/docker-compose.infra.yml
services:
  gitea:
    image: gitea/gitea:1.21
    environment:
      USER_UID: 1000
      USER_GID: 1000
      GITEA__database__DB_TYPE: postgres
      GITEA__database__HOST: postgres:5432
      GITEA__database__NAME: gitea
      GITEA__database__USER: ruoming
      GITEA__database__PASSWD: ${POSTGRES_PASSWORD}
    volumes:
      - gitea_data:/data
    ports:
      - "3000:3000"   # Web UI
      - "2222:22"     # SSH

  # Gitea Actions Runner（执行 CI 任务的 Agent）
  gitea-runner:
    image: gitea/act_runner:latest
    environment:
      GITEA_INSTANCE_URL: http://gitea:3000
      GITEA_RUNNER_REGISTRATION_TOKEN: ${GITEA_RUNNER_TOKEN}
      GITEA_RUNNER_NAME: ruoming-runner
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - runner_data:/data
    depends_on:
      - gitea

volumes:
  gitea_data:
  runner_data:
```

### Gitea Actions YAML（与 GitHub Actions 几乎一致）

```yaml
# .gitea/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [develop, main]
  create:
    tags:
      - 'v*'

jobs:
  check:
    runs-on: ubuntu-latest    # Gitea Runner 标签
    steps:
      - uses: actions/checkout@v4
      - run: make lint test

  deploy:
    needs: check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & Push
        run: make build push
        env:
          REGISTRY_USER: ${{ secrets.REGISTRY_USER }}
          REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Deploy
        run: make deploy-dev   # 或根据分支判断
        env:
          DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
```

> **优势**：Gitea Actions 语法与 GitHub Actions 高度兼容，日后想迁移到 GitHub 只需复制 YAML 文件，改极少配置。

---

## 6. 镜像仓库选择

| 选项 | 说明 | 适用场景 |
|------|------|---------|
| **GitHub Container Registry** | `ghcr.io`，与 GitHub Actions 无缝集成，免费私有包 | 代码在 GitHub 时首选 |
| **GitLab Registry** | 每个项目自带，与 GitLab CI 无缝集成 | 代码在 GitLab 时首选 |
| **自建 Harbor** | 企业级镜像仓库，支持镜像扫描、签名、权限管理 | 完全私有化时推荐 |
| **阿里云 / 腾讯云 ACR** | 国内网络友好，免费额度够用 | 服务器在国内时推荐 |

### 自建 Harbor（完全私有化）

```yaml
# docker-compose.infra.yml 追加
harbor:
  image: goharbor/harbor-core:v2.10.0
  # Harbor 官方推荐使用 harbor-installer 脚本部署
  # https://goharbor.io/docs/latest/install-config/
```

> 实际推荐用 Harbor 官方 installer 脚本部署，而不是手写 compose：
> ```bash
> wget https://github.com/goharbor/harbor/releases/download/v2.10.0/harbor-offline-installer-v2.10.0.tgz
> tar xzf harbor-offline-installer-v2.10.0.tgz
> cd harbor && cp harbor.yml.tmpl harbor.yml
> # 修改 hostname 和密码后执行：
> sudo ./install.sh
> ```

---

## 7. 密钥管理规范

**绝对禁止**写入代码仓库的内容：

```
❌ 数据库密码
❌ Redis 密码
❌ JWT Secret
❌ 大模型 API Key
❌ SSH 私钥
❌ 镜像仓库密码
```

**正确做法**：

| 平台 | 密钥存储位置 |
|------|------------|
| GitHub | Settings → Secrets and variables → Actions |
| GitLab | Settings → CI/CD → Variables（勾选 Masked + Protected）|
| Gitea | Settings → Secrets |
| 生产服务器 | `/opt/ruoming/.env`（权限 600，仅 deploy 用户可读）|

### SSH 部署密钥配置

```bash
# 生成专用部署密钥（不要复用个人 SSH 密钥）
ssh-keygen -t ed25519 -C "ruoming-ci-deploy" -f ~/.ssh/ruoming_deploy -N ""

# 公钥放到服务器（仅允许执行 deploy.sh）
echo 'command="/opt/ruoming/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-ed25519 AAAA...' >> ~/.ssh/authorized_keys

# 私钥放入 CI 平台的 Secret（DEPLOY_SSH_KEY）
cat ~/.ssh/ruoming_deploy
```

---

## 8. 完整流水线总览

```
开发者 push feature/xxx
        │
        ▼
    PR / MR 创建
        │
        ▼
  ┌─── PR Check ───────────────────────┐
  │  lint-backend (ruff + mypy)        │  < 3 分钟
  │  test-backend (pytest + coverage)  │
  │  lint-frontend (eslint)            │
  │  test-frontend (vitest)            │
  └────────────────────────────────────┘
        │ 通过后允许合并
        ▼
  merge to develop
        │
        ▼
  ┌─── Auto Deploy Dev ────────────────┐
  │  build backend image               │  ~ 5 分钟
  │  build frontend image              │
  │  push to registry                  │
  │  ssh → deploy.sh (dev)             │
  │  alembic upgrade head              │
  └────────────────────────────────────┘
        │
        ▼
  merge to main
        │
        ▼
  ┌─── Auto Deploy Staging ────────────┐
  │  build & push images               │  ~ 5 分钟
  │  ssh → deploy.sh (staging)         │
  └────────────────────────────────────┘
        │
        ▼
  git tag v1.2.0
        │
        ▼
  ┌─── Release to Production ──────────┐
  │  build & push images (tag)         │
  │  ⏸ 等待人工 Approve               │
  │  ssh → deploy.sh (prod)            │
  │  alembic upgrade head              │
  │  健康检查通过 → 完成               │
  └────────────────────────────────────┘
```

---

## 9. 选型建议

| 你的情况 | 推荐方案 |
|---------|---------|
| 代码可以放在 GitHub，追求最省事 | **GitHub Actions + GHCR** |
| 要求代码完全私有，有独立服务器 | **Gitea + Gitea Actions + Harbor** |
| 团队 > 5 人，需要完整 DevOps 功能（MR 审查、Wiki、Issue） | **自建 GitLab + GitLab CI** |
| 现在不确定，想保留切换空间 | **从 GitHub 开始，Makefile 封装逻辑，随时可迁移** |

> **若茗 PaaS 当前阶段推荐**：从 GitHub Actions 开始，Makefile 封装所有构建/部署逻辑。等到有私有化需求时，只需搭一个 Gitea，复制 YAML 文件改几行配置即可完成迁移，成本极低。

---

*返回 [文档首页](./README.md)*
