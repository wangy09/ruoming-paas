#!/bin/bash
# ================================================================
# 若茗 PaaS - 版本切换与灰度发布脚本
# Author: ruoming
# 用法：
#   ./deploy.sh deploy <version>      # 部署指定版本
#   ./deploy.sh rollback              # 回滚到上一版本
#   ./deploy.sh status                # 查看当前状态
#   ./deploy.sh canary <percent>      # 灰度发布（按百分比）
# ================================================================

set -euo pipefail

# ── 配置 ──────────────────────────────────────────────────────────
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
PROD_COMPOSE_FILE="${PROD_COMPOSE_FILE:-deploy/docker-compose.prod.yml}"
NGINX_CONF="${NGINX_CONF:-deploy/nginx/nginx.prod.conf}"
VERSION_FILE="${VERSION_FILE:-deploy/.current_version}"
MAX_KEEP_VERSIONS="${MAX_KEEP_VERSIONS:-5}"

# ── 辅助函数 ──────────────────────────────────────────────────────
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }
log_success() { echo "[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

check_command() {
    if ! command -v "$1" &>/dev/null; then
        log_error "命令不存在: $1"
        exit 1
    fi
}

wait_for_health() {
    local url="$1"
    local max_attempts="${2:-30}"
    local attempt=1

    log_info "等待服务就绪: $url"
    while [ "$attempt" -le "$max_attempts" ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log_success "服务就绪 (尝试 $attempt 次)"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "服务就绪超时 (尝试 $max_attempts 次)"
    return 1
}

# ── 部署新版本 ──────────────────────────────────────────────────
do_deploy() {
    local version="${1:?请指定版本号}"

    log_info "部署版本: $version"

    # 1. 保存当前版本
    local current_version=""
    if [ -f "$VERSION_FILE" ]; then
        current_version=$(cat "$VERSION_FILE")
        echo "$current_version" > "${VERSION_FILE}.prev"
    fi

    # 2. 更新版本文件
    echo "$version" > "$VERSION_FILE"

    # 3. 构建并启动新容器
    log_info "构建新版本镜像..."
    APP_VERSION="$version" $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" build backend celery_worker task_scheduler

    log_info "停止旧服务..."
    $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" stop backend celery_worker task_scheduler

    log_info "启动新服务..."
    $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" up -d backend celery_worker task_scheduler

    # 4. 健康检查
    if wait_for_health "http://localhost/api/health" 60; then
        log_success "部署成功: $version"
        log_info "旧版本: ${current_version:-N/A}"
    else
        log_error "新版本健康检查失败，准备回滚..."
        if [ -n "$current_version" ]; then
            do_rollback
        else
            log_error "无可用回滚版本，请手动处理"
        fi
        exit 1
    fi

    # 5. 清理旧镜像
    cleanup_old_images
}

# ── 回滚版本 ──────────────────────────────────────────────────
do_rollback() {
    log_info "开始回滚..."

    if [ ! -f "${VERSION_FILE}.prev" ]; then
        log_error "没有可用的回滚版本"
        exit 1
    fi

    local prev_version
    prev_version=$(cat "${VERSION_FILE}.prev")
    log_info "回滚到版本: $prev_version"

    # 停止当前服务
    $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" stop backend celery_worker task_scheduler

    # 使用旧版本启动
    APP_VERSION="$prev_version" $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" up -d backend celery_worker task_scheduler

    # 更新版本文件
    echo "$prev_version" > "$VERSION_FILE"

    # 健康检查
    if wait_for_health "http://localhost/api/health" 60; then
        log_success "回滚成功: $prev_version"
    else
        log_error "回滚后健康检查失败"
        exit 1
    fi
}

# ── 灰度发布 ──────────────────────────────────────────────────
do_canary() {
    local percent="${1:?请指定灰度百分比 (1-99)}"

    if [ "$percent" -lt 1 ] || [ "$percent" -gt 99 ]; then
        log_error "灰度百分比必须在 1-99 之间"
        exit 1
    fi

    log_info "开始灰度发布 (${percent}%)"

    # 1. 获取新版本
    if [ -f "$VERSION_FILE" ]; then
        local canary_version
        canary_version=$(cat "$VERSION_FILE")
        log_info "灰度版本: $canary_version"
    fi

    # 2. 启动灰度实例
    local canary_port=8081
    log_info "启动灰度实例 (端口: $canary_port)..."

    # 修改 nginx 配置，添加灰度分流
    local canary_config="${NGINX_CONF}.canary"
    cp "$NGINX_CONF" "$canary_config"

    # 在 nginx 配置中添加灰度规则
    cat >> "$canary_config" <<EOF

    # === 灰度发布配置 (${percent}%) ===
    split_clients "\${cookie_route}" \$backend_upstream {
        ${percent}%    backend_canary;
        *               backend_main;
    }

    map \$http_cookie \$cookie_route {
        default        "";
        "~canary=1"    "1";
    }
EOF

    log_info "灰度配置已生成: $canary_config"
    log_warn "请手动完成以下步骤："
    echo "  1. 使用灰度配置重新加载 Nginx: nginx -s reload"
    echo "  2. 灰度实例启动后，设置 canary=1 Cookie 测试"
    echo "  3. 验证通过后，逐步扩大灰度比例"
    echo "  4. 全量发布后，移除灰度配置"
}

# ── 查看状态 ──────────────────────────────────────────────────
do_status() {
    echo "=== 若茗 PaaS 部署状态 ==="
    echo ""

    echo "当前版本:"
    if [ -f "$VERSION_FILE" ]; then
        echo "  $(cat "$VERSION_FILE")"
    else
        echo "  未记录"
    fi

    echo ""
    echo "上一版本:"
    if [ -f "${VERSION_FILE}.prev" ]; then
        echo "  $(cat "${VERSION_FILE}.prev")"
    else
        echo "  无"
    fi

    echo ""
    echo "服务状态:"
    $DOCKER_COMPOSE -f "$PROD_COMPOSE_FILE" ps

    echo ""
    echo "健康检查:"
    local health
    health=$(curl -sf "http://localhost/api/health" 2>/dev/null || echo "unreachable")
    echo "  $health"
}

# ── 清理旧镜像 ──────────────────────────────────────────────────
cleanup_old_images() {
    log_info "清理旧镜像..."

    # 保留最近的 N 个版本镜像
    local images
    images=$(docker images --filter "reference=ruoming-paas-backend:*" --format "{{.Repository}}:{{.Tag}} {{.ID}}" 2>/dev/null | wc -l)

    if [ "$images" -gt "$MAX_KEEP_VERSIONS" ]; then
        log_info "镜像数量 ($images) 超过保留限制 ($MAX_KEEP_VERSIONS)，清理旧镜像"

        docker images --filter "reference=ruoming-paas-backend:*" --format "{{.Repository}}:{{.Tag}} {{.ID}}" 2>/dev/null | \
            tail -n +"$((MAX_KEEP_VERSIONS + 1))" | \
            awk '{print $2}' | \
            xargs -r docker rmi -f 2>/dev/null || true
    fi
}

# ── 主入口 ──────────────────────────────────────────────────
check_command docker
check_command curl

case "${1:-}" in
    deploy)
        do_deploy "${2:-}"
        ;;
    rollback)
        do_rollback
        ;;
    canary)
        do_canary "${2:-50}"
        ;;
    status)
        do_status
        ;;
    *)
        echo "用法: $0 {deploy|rollback|canary|status} [参数]"
        echo ""
        echo "  deploy <version>   部署指定版本"
        echo "  rollback           回滚到上一版本"
        echo "  canary <percent>   灰度发布 (默认 50%)"
        echo "  status             查看当前部署状态"
        exit 1
esac
