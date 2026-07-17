#!/usr/bin/env python3
"""
直接通过数据库更新限流配置项的分类为 rate_limit

使用方式（在服务器上运行）：
  python scripts/update_rate_limit_db.py
"""
import asyncio


async def main():
    import os
    os.environ.setdefault("ENV_FOR_DYNACONF", "development")

    from app.database import AsyncSessionFactory
    from app.modules.config_center.service import ConfigCenterService

    config_items = [
        {"config_key": "rate_limit.enabled", "config_val": "true", "val_type": "bool", "config_type": "switch", "sort": 1},
        {"config_key": "rate_limit.global.default", "config_val": "100/minute", "val_type": "string", "config_type": "input", "sort": 2},
        {"config_key": "rate_limit.ip.default", "config_val": "300/minute", "val_type": "string", "config_type": "input", "sort": 3},
        {"config_key": "rate_limit.user.default", "config_val": "60/minute", "val_type": "string", "config_type": "input", "sort": 4},
        {"config_key": "rate_limit.tenant.default", "config_val": "500/minute", "val_type": "string", "config_type": "input", "sort": 5},
        {"config_key": "rate_limit.api.login", "config_val": "10/minute", "val_type": "string", "config_type": "input", "sort": 6},
        {"config_key": "rate_limit.api.register", "config_val": "5/minute", "val_type": "string", "config_type": "input", "sort": 7},
        {"config_key": "rate_limit.api.captcha", "config_val": "3/minute", "val_type": "string", "config_type": "input", "sort": 8},
        {"config_key": "rate_limit.ai.chat", "config_val": "30/minute", "val_type": "string", "config_type": "input", "sort": 9},
        {"config_key": "rate_limit.ai.agent", "config_val": "30/minute", "val_type": "string", "config_type": "input", "sort": 10},
    ]

    async with AsyncSessionFactory() as db:
        svc = ConfigCenterService(db)

        for item in config_items:
            try:
                await svc.set(
                    config_key=item["config_key"],
                    config_val=item["config_val"],
                    scope="global",
                    tenant_id=None,
                    app_key=None,
                    user_id=None,
                    val_type=item["val_type"],
                    is_encrypted=False,
                    category="rate_limit",
                    config_type=item["config_type"],
                    default_value=None,
                    options=None,
                    required=False,
                    regex=None,
                    min_value=None,
                    max_value=None,
                    sort=item["sort"],
                    status=1,
                    label="",
                    description="",
                    is_public=False,
                    changed_by=None,
                )
                print(f"✓ 更新成功: {item['config_key']} -> category=rate_limit, sort={item['sort']}")
            except Exception as e:
                print(f"✗ 更新失败 {item['config_key']}: {e}")

        await db.commit()

    print("\n所有限流配置项已更新到 rate_limit 分类")


if __name__ == "__main__":
    asyncio.run(main())