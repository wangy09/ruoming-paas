# ================================================================
# 若茗 PaaS - 前端 Dockerfile（多阶段构建）
# Author: ruoming
# ================================================================

# ── 依赖安装阶段 ────────────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

# 仅复制依赖文件，利用 Docker 缓存层
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# ── 构建阶段 ────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 构建参数（运行时注入 API 地址）
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ── 生产阶段（纯静态文件，用 Nginx 托管）────────────────────────
FROM nginx:1.25-alpine AS runner

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 开发配置（用于独立运行前端容器）
COPY nginx.standalone.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
