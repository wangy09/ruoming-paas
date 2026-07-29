# 1. 删除旧容器和数据库卷（完全重置）
cd /Users/wangyan/Documents/Projects/01_Working/RuoMingPaas/deploy
docker-compose down -v

# 2. 重新启动
docker-compose up -d

# 3. 等待服务启动
sleep 20

# 4. 初始化表结构（--force 强制重建）
docker exec ruoming_backend python /app/scripts/recreate_tables.py --force

# 5. 初始化种子数据
docker exec ruoming_backend python /app/scripts/init_data.py

# 6. 初始化 Agent 种子数据（可选）
docker exec ruoming_backend python /app/scripts/seed_agents.py


# 注意：日常重启只需执行 docker-compose down && docker-compose up -d
# 表结构和数据初始化脚本会在首次启动时由 start.sh 自动执行（幂等）