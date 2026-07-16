# ================================================================
# 若茗 PaaS - 后端 Dockerfile
# Author: ruoming
# ================================================================

# ── 构建阶段 ──────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 安装系统依赖
RUN sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|http://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g; s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（快速依赖安装工具）
RUN pip install --no-cache-dir uv

# 复制依赖文件
COPY pyproject.toml README.md ./

# 安装生产依赖
RUN uv pip install --system --no-cache -e .

# ── 运行阶段 ──────────────────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security

# 安装运行时系统依赖
RUN sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|http://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g; s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 创建上传目录
RUN mkdir -p uploads logs

# 非 root 用户运行（安全）
RUN useradd -m -u 1000 ruoming && chown -R ruoming:ruoming /app
USER ruoming

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
