#!/bin/bash
# ================================================================
# 若茗 PaaS - 日志轮转脚本
# Author: ruoming
# 用法：
#   ./log_rotate.sh                  # 立即轮转
#   ./log_rotate.sh --check          # 仅检查日志大小
#   ./log_rotate.sh --compress       # 压缩旧日志
#
# 配合 crontab 使用：
#   0 2 * * * /path/to/log_rotate.sh  # 每天凌晨 2 点执行
# ================================================================

set -euo pipefail

# ── 配置 ──────────────────────────────────────────────────────────
LOG_DIR="${LOG_DIR:-./logs}"
MAX_LOG_SIZE_MB="${MAX_LOG_SIZE_MB:-100}"
MAX_LOG_AGE_DAYS="${MAX_LOG_AGE_DAYS:-30}"
BACKUP_SUFFIX="${BACKUP_SUFFIX:-.old}"
COMPRESS_AFTER_DAYS="${COMPRESS_AFTER_DAYS:-1}"

# ── 函数 ──────────────────────────────────────────────────────────
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }

# ── 检查日志目录 ────────────────────────────────────────────────
check_logs() {
    if [ ! -d "$LOG_DIR" ]; then
        log_warn "日志目录不存在: $LOG_DIR"
        return 0
    fi

    echo "日志文件统计:"
    echo "=============="
    echo "文件数: $(find "$LOG_DIR" -name "*.log*" -type f 2>/dev/null | wc -l)"
    echo "总大小: $(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)"
    echo ""

    echo "超过 ${MAX_LOG_SIZE_MB}MB 的日志文件:"
    find "$LOG_DIR" -name "*.log" -type f -size +"${MAX_LOG_SIZE_MB}"M -exec ls -lh {} \; 2>/dev/null || echo "  无"
    echo ""

    echo "超过 ${MAX_LOG_AGE_DAYS} 天的日志文件:"
    find "$LOG_DIR" -name "*.log*" -type f -mtime +"${MAX_LOG_AGE_DAYS}" 2>/dev/null | head -20 || echo "  无"
}

# ── 轮转日志 ──────────────────────────────────────────────────
rotate_logs() {
    log_info "开始日志轮转..."

    if [ ! -d "$LOG_DIR" ]; then
        log_warn "日志目录不存在，创建: $LOG_DIR"
        mkdir -p "$LOG_DIR"
        return 0
    fi

    local rotated=0
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')

    # 轮转超过大小限制的日志
    while IFS= read -r logfile; do
        if [ -z "$logfile" ]; then
            continue
        fi

        local basename
        basename=$(basename "$logfile")
        local rotated_name="${logfile}.${timestamp}${BACKUP_SUFFIX}"

        # 重命名当前日志
        mv "$logfile" "$rotated_name"

        # 创建新的空日志文件
        touch "$logfile"

        # 输出轮转信息
        local size
        size=$(du -h "$rotated_name" | cut -f1)
        log_info "轮转: ${basename} -> $(basename "$rotated_name") (${size})"

        # 立即压缩（可选）
        if command -v gzip &>/dev/null; then
            gzip "$rotated_name"
            log_info "压缩: $(basename "$rotated_name").gz"
        fi

        rotated=$((rotated + 1))
    done < <(find "$LOG_DIR" -name "*.log" -type f -size +"${MAX_LOG_SIZE_MB}"M 2>/dev/null)

    # 清理过期日志
    local deleted
    deleted=$(find "$LOG_DIR" -name "*.log*" -type f -mtime +"${MAX_LOG_AGE_DAYS}" -delete -print 2>/dev/null | wc -l)
    if [ "$deleted" -gt 0 ]; then
        log_info "清理 ${deleted} 个过期日志文件 (>${MAX_LOG_AGE_DAYS}天)"
    fi

    # 压缩较旧的未压缩日志
    if command -v gzip &>/dev/null; then
        local compressed
        compressed=$(find "$LOG_DIR" -name "*.log*${BACKUP_SUFFIX}" -type f -mtime +"${COMPRESS_AFTER_DAYS}" ! -name "*.gz" -exec gzip {} \; -print 2>/dev/null | wc -l)
        if [ "$compressed" -gt 0 ]; then
            log_info "压缩 ${compressed} 个旧日志文件"
        fi
    fi

    if [ "$rotated" -eq 0 ]; then
        log_info "无需轮转的日志文件"
    else
        log_info "轮转完成，共处理 ${rotated} 个文件"
    fi
}

# ── 主入口 ──────────────────────────────────────────────────────
case "${1:-}" in
    --check)
        check_logs
        ;;
    *)
        rotate_logs
        check_logs
        ;;
esac
