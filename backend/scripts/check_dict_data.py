import asyncio
import sys
sys.path.insert(0, '.')

from app.database import AsyncSessionFactory
from app.modules.system.models import SysDictType, SysDictItem
from app.modules.permission.models import SysPermission


async def check_data():
    async with AsyncSessionFactory() as db:
        types = await db.execute(SysDictType.__table__.select())
        print('=== 字典类型 ===')
        for t in types.scalars().all():
            print(f'  {t.id}: {t.name} ({t.code})')

        items = await db.execute(SysDictItem.__table__.select())
        print('=== 字典项数量 ===')
        print(f'  总数: {len(list(items.scalars().all()))}')

        perms = await db.execute(SysPermission.__table__.select().where(SysPermission.code.like('%dict%')))
        print('=== 字典管理菜单权限 ===')
        for p in perms.scalars().all():
            print(f'  {p.code}: {p.name} (type: {p.perm_type})')


if __name__ == '__main__':
    asyncio.run(check_data())
