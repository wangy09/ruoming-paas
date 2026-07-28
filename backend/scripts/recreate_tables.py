"""
若茗 PaaS - 数据库结构初始化
首次启动时执行，创建所有表结构。

用法：
  python recreate_tables.py           # 仅创建不存在的表（安全，生产可用）
  python recreate_tables.py --force   # 强制删除并重建所有表（⚠️ 会丢失所有数据）

设计说明：
  本脚本是 app.database.init_db() 的命令行入口，不维护独立的模型导入列表。
  所有模型注册统一在 app.database._import_models_for_metadata() 中维护。
  新增业务模块时只需更新该函数，此脚本无需修改。
"""
import asyncio
import argparse
import sys

sys.path.insert(0, '/app')


async def recreate_tables(force: bool = False) -> None:
    from app.database import _write_engine, Base, init_db, _import_models_for_metadata

    if force:
        print("⚠️  Force mode: 删除所有表...")
        _import_models_for_metadata()
        async with _write_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ 所有表已删除")

    await init_db()
    print("✅ 表结构初始化完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化数据库表结构")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制删除并重建所有表（⚠️ 会丢失所有数据，仅开发环境使用）",
    )
    args = parser.parse_args()
    asyncio.run(recreate_tables(force=args.force))
