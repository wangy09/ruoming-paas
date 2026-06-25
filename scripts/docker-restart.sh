# 1. 删除旧容器和数据库卷
cd /Users/wangyan/Documents/Projects/01_Working/RuoMingPaas/deploy
docker-compose down -v

# 2. 重新启动（会自动执行所有迁移）
docker-compose up -d

# 3. 等待启动完成后执行初始化脚本
docker exec -it ruoming_backend python /app/scripts/init_data.py
docker exec -it ruoming_backend python /app/scripts/seed_agents.py