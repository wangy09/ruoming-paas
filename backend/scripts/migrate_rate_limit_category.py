#!/usr/bin/env python3
"""
迁移脚本：将 rate_limit.* 配置项的分类更新为 rate_limit

运行方式：
  cd backend && python scripts/migrate_rate_limit_category.py
"""
import asyncio


async def main():
    import os
    os.environ.setdefault("ENV_FOR_DYNACONF", "development")

    from app.database import AsyncSessionFactory
    from sqlalchemy import text

    async with AsyncSessionFactory() as db:
        # 更新 rate_limit.* 配置项的分类为 rate_limit
        result = await db.execute(
            text("""
                UPDATE sys_config 
                SET category = 'rate_limit'
                WHERE config_key LIKE 'rate_limit.%'
                  AND category != 'rate_limit'
            """)
        )
        updated = result.rowcount
        await db.commit()

    print(f"已更新 {updated} 条限流配置项的分类为 rate_limit")


if __name__ == "__main__":
    asyncio.run(main())