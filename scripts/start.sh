#!/usr/bin/env bash
# ================================================================
# 若茗 PaaS - 一键启动脚本
# 用法：bash scripts/start.sh [dev|prod|stop|status|logs]
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $*"; }

# ── 检查前置依赖 ─────────────────────────────────────────────────
check_deps() {
    log_step "检查前置依赖..."
    local missing=()
    command -v docker   &>/dev/null || missing+=("docker")
    command -v docker   &>/dev/null && docker compose version &>/dev/null || \
        { command -v docker-compose &>/dev/null || missing+=("docker-compose"); }

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "缺少依赖：${missing[*]}"
        log_error "请先安装 Docker Desktop：https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    log_info "依赖检查通过 ✓"
}

# ── 判断 compose 命令 ────────────────────────────────────────────
compose_cmd() {
    if docker compose version &>/dev/null 2>&1; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

# ── 开发环境启动 ─────────────────────────────────────────────────
start_dev() {
    log_step "启动开发环境..."

    # 检查 .env 文件
    if [[ ! -f "$PROJECT_ROOT/backend/.env.development" ]]; then
        log_warn "未找到 backend/.env.development，从 example 复制..."
        if [[ -f "$PROJECT_ROOT/backend/.env.example" ]]; then
            cp "$PROJECT_ROOT/backend/.env.example" "$PROJECT_ROOT/backend/.env.development"
            log_warn "请编辑 backend/.env.development 填写 SECRET_KEY 等配置后重新运行"
            exit 0
        else
            log_error "未找到 backend/.env.example，请手动创建 backend/.env.development"
            exit 1
        fi
    fi

    cd "$DEPLOY_DIR"
    $(compose_cmd) up -d

    log_step "等待服务健康（最长 90 秒）..."
    local retries=18
    while [[ $retries -gt 0 ]]; do
        if curl -sf http://localhost:8000/api/health &>/dev/null; then
            break
        fi
        sleep 5
        ((retries--))
    done

    if [[ $retries -eq 0 ]]; then
        log_warn "后端健康检查超时，请查看日志："
        $(compose_cmd) logs --tail=50 backend
        exit 1
    fi

    # 检查是否需要初始化数据库
    log_step "检查数据库初始化状态..."
    local user_count
    user_count=$($(compose_cmd) exec -T backend python -c \
        "import asyncio; from app.database import AsyncSessionLocal; from sqlalchemy import text; \
        async def f(): \
            async with AsyncSessionLocal() as s: \
                r = await s.execute(text('SELECT COUNT(*) FROM sys_user WHERE is_superplatform = true')); return r.scalar() \
        print(asyncio.run(f()))" 2>/dev/null || echo "0")

    if [[ "$user_count" == "0" ]]; then
        log_step "首次启动，初始化种子数据..."
        $(compose_cmd) exec backend python /app/scripts/init_data.py
        log_info "种子数据初始化完成 ✓"
    fi

    echo ""
    echo "════════════════════════════════════════════════"
    log_info "🚀 若茗 PaaS 开发环境启动成功！"
    echo "════════════════════════════════════════════════"
    echo ""
    echo "  前端管理台：  http://localhost:3000"
    echo "  后端 API：    http://localhost:8000"
    echo "  API 文档：    http://localhost:8000/api/docs"
    echo "  健康检查：    http://localhost:8000/api/health"
    echo ""
    echo "  默认账号：admin / ruoming@2024"
    echo "  ⚠️  首次使用后请立即修改密码！"
    echo ""
}

# ── 生产环境启动 ─────────────────────────────────────────────────
start_prod() {
    log_step "启动生产环境..."

    if [[ ! -f "$DEPLOY_DIR/.env.production" ]]; then
        log_error "未找到 deploy/.env.production，请先配置生产环境变量"
        cat <<'EOF'
# 需要配置的变量：
POSTGRES_USER=ruoming
POSTGRES_PASSWORD=<强密码>
POSTGRES_DB=ruoming_prod
REDIS_PASSWORD=<强密码>
SECRET_KEY=<64位随机字符串>
APP_VERSION=latest
EOF
        exit 1
    fi

    cd "$DEPLOY_DIR"
    $(compose_cmd) -f docker-compose.prod.yml build --no-cache

    log_step "启动生产数据库与缓存..."
    $(compose_cmd) -f docker-compose.prod.yml up -d postgres redis

    log_step "初始化生产数据库结构..."
    $(compose_cmd) -f docker-compose.prod.yml run --rm backend python -c \
        "import asyncio; from app.database import init_db; asyncio.run(init_db())"

    log_step "初始化生产种子数据..."
    $(compose_cmd) -f docker-compose.prod.yml run --rm backend python /app/scripts/init_data.py

    log_step "启动生产应用服务..."
    $(compose_cmd) -f docker-compose.prod.yml up -d

    log_step "等待服务启动..."
    sleep 10
    $(compose_cmd) -f docker-compose.prod.yml ps

    log_info "生产环境启动完成 ✓"
    log_info "访问：http://your-domain.com"
}

# ── 停止服务 ─────────────────────────────────────────────────────
stop_services() {
    local env="${1:-dev}"
    cd "$DEPLOY_DIR"
    if [[ "$env" == "prod" ]]; then
        log_step "停止生产环境..."
        $(compose_cmd) -f docker-compose.prod.yml down
    else
        log_step "停止开发环境..."
        $(compose_cmd) down
    fi
    log_info "服务已停止 ✓"
}

# ── 查看状态 ─────────────────────────────────────────────────────
show_status() {
    cd "$DEPLOY_DIR"
    echo ""
    log_info "=== 开发环境服务状态 ==="
    $(compose_cmd) ps
}

# ── 查看日志 ─────────────────────────────────────────────────────
show_logs() {
    local service="${2:-}"
    cd "$DEPLOY_DIR"
    if [[ -n "$service" ]]; then
        $(compose_cmd) logs -f --tail=100 "$service"
    else
        $(compose_cmd) logs -f --tail=50
    fi
}

# ── 主入口 ───────────────────────────────────────────────────────
main() {
    local cmd="${1:-dev}"

    check_deps

    case "$cmd" in
        dev)      start_dev ;;
        prod)     start_prod ;;
        stop)     stop_services "${2:-dev}" ;;
        status)   show_status ;;
        logs)     show_logs "$@" ;;
        *)
            echo "用法：bash scripts/start.sh [命令]"
            echo ""
            echo "命令："
            echo "  dev       启动开发环境（默认）"
            echo "  prod      启动生产环境"
            echo "  stop      停止开发环境"
            echo "  stop prod 停止生产环境"
            echo "  status    查看服务状态"
            echo "  logs      查看所有日志"
            echo "  logs backend  查看后端日志"
            exit 1
            ;;
    esac
}

main "$@"
