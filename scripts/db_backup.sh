#!/bin/bash
# ================================================================
# 若茗 PaaS - 数据库备份脚本
# Author: ruoming
# 用法：
#   ./backup.sh                    # 立即备份
#   ./backup.sh --schedule         # 定时备份（需配合 crontab）
#   ./backup.sh --restore <file>   # 从备份恢复
# ================================================================

set -euo pipefail

# ── 配置 ──────────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-./postgres-backup}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ruoming_dev}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_COMPRESS="${BACKUP_COMPRESS:-gzip}"  # gzip | zstd | none
NOTIFY_WEBHOOK="${NOTIFY_WEBHOOK:-}"       # 可选：备份完成后通知

# ── 函数 ──────────────────────────────────────────────────────────
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }

check_db_password() {
    if [ -z "$DB_PASSWORD" ]; then
        log_error "未设置数据库密码，请通过环境变量 DB_PASSWORD 指定"
        log_error "示例: DB_PASSWORD=your_password $0 $*"
        exit 1
    fi
}

send_notification() {
    local status="$1"
    local message="$2"
    if [ -n "$NOTIFY_WEBHOOK" ]; then
        curl -s -X POST "$NOTIFY_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"status\": \"$status\", \"message\": \"$message\", \"time\": \"$(date -Iseconds)\"}" \
            2>/dev/null || true
    fi
}

# ── 立即备份 ──────────────────────────────────────────────────────
do_backup() {
    check_db_password "backup"

    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${BACKUP_DIR}/${DB_NAME}_${timestamp}.sql"

    log_info "开始备份数据库: ${DB_NAME}"
    mkdir -p "$BACKUP_DIR"

    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        --encoding=UTF8 \
        --file="$backup_file" \
        2>&1

    if [ ! -f "$backup_file" ] || [ ! -s "$backup_file" ]; then
        log_error "备份文件为空或不存在"
        rm -f "$backup_file"
        send_notification "failed" "备份失败：文件为空"
        exit 1
    fi

    # 压缩
    case "$BACKUP_COMPRESS" in
        gzip)
            gzip -9 "$backup_file"
            backup_file="${backup_file}.gz"
            ;;
        zstd)
            zstd -9 "$backup_file" -o "${backup_file}.zst"
            rm "$backup_file"
            backup_file="${backup_file}.zst"
            ;;
    esac

    local size
    size=$(du -h "$backup_file" | cut -f1)
    log_info "备份完成: ${backup_file} (大小: ${size})"

    # 清理旧备份
    cleanup_old_backups

    send_notification "success" "备份完成: ${backup_file} (${size})"
}

# ── 清理旧备份 ────────────────────────────────────────────────────
cleanup_old_backups() {
    log_info "清理 ${BACKUP_RETENTION_DAYS} 天前的备份..."
    local deleted
    deleted=$(find "$BACKUP_DIR" -name "*.sql*" -mtime +"$BACKUP_RETENTION_DAYS" -delete -print | wc -l)
    if [ "$deleted" -gt 0 ]; then
        log_info "已清理 ${deleted} 个过期备份"
    fi
}

# ── 恢复备份 ──────────────────────────────────────────────────────
do_restore() {
    check_db_password "restore"

    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi

    log_warn "警告：此操作将覆盖数据库 ${DB_NAME}，请确认！"
    read -r -p "输入 YES 确认恢复: " confirm
    if [ "$confirm" != "YES" ]; then
        log_info "已取消恢复操作"
        exit 0
    fi

    log_info "开始恢复备份: $backup_file"

    # 先终止现有连接
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
        2>/dev/null || true

    # 重建数据库
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
        -c "CREATE DATABASE ${DB_NAME};" \
        2>&1

    # 恢复数据
    case "$backup_file" in
        *.gz)
            gunzip -c "$backup_file" | PGPASSWORD="$DB_PASSWORD" psql \
                -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" 2>&1
            ;;
        *.zst)
            zstd -d -c "$backup_file" | PGPASSWORD="$DB_PASSWORD" psql \
                -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" 2>&1
            ;;
        *)
            PGPASSWORD="$DB_PASSWORD" psql \
                -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -f "$backup_file" 2>&1
            ;;
    esac

    if [ $? -eq 0 ]; then
        log_info "恢复完成"
        send_notification "success" "数据库恢复完成"
    else
        log_error "恢复失败"
        send_notification "failed" "数据库恢复失败"
        exit 1
    fi
}

# ── 列出备份 ──────────────────────────────────────────────────────
list_backups() {
    echo "可用备份文件:"
    echo "================"
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        ls -lhS "$BACKUP_DIR"/*.sql* 2>/dev/null | awk '{
            printf "%-10s %-20s %s\n", $5, $6" "$7" "$8, $9
        }'
    else
        echo "  无备份文件"
    fi
}

# ── 主入口 ────────────────────────────────────────────────────────
case "${1:-}" in
    --restore)
        if [ -z "${2:-}" ]; then
            echo "用法: $0 --restore <backup_file>"
            exit 1
        fi
        do_restore "$2"
        ;;
    --list)
        list_backups
        ;;
    *)
        do_backup
        ;;
esac
