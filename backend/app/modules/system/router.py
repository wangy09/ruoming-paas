"""
若茗 PaaS - 系统路由
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import BusinessException, NotFoundException
from app.core.response import ApiResponse, created, ok
from app.database import get_db
from app.modules.permission.models import SysRoleDept
from app.modules.system.models import SysDept, SysDictType, SysDictItem
from app.modules.user.models import SysUser
from app.modules.system.schemas import DeptCreate, DeptInfo, DeptUpdate, DictTypeCreate, DictTypeUpdate, DictTypeWithItems, DictTypeInfo, DictItemCreate, DictItemUpdate, DictItemInfo, DictCodeResult
from app.modules.system.service import DictService

router = APIRouter()


@router.get("/system/demo-mode", response_model=ApiResponse, summary="获取演示模式状态")
async def get_demo_mode() -> ApiResponse:
    """获取系统是否处于演示模式（无需认证，前端初始化时调用）"""
    return ok({"demo_mode": settings.DEMO_MODE})


def _build_ancestors(parent: SysDept | None) -> str:
    """构建祖级列表"""
    if not parent:
        return "0"
    return f"{parent.ancestors},{parent.id}" if parent.ancestors else f"0,{parent.id}"


def _build_tree(depts: list[SysDept], parent_id: int = 0) -> list[dict]:
    """递归构建部门树"""
    children = [d for d in depts if d.parent_id == parent_id]
    children.sort(key=lambda x: x.sort)

    result = []
    for dept in children:
        node = {
            "id": dept.id,
            "parent_id": dept.parent_id,
            "name": dept.name,
            "ancestors": dept.ancestors,
            "level": dept.level,
            "sort": dept.sort,
            "leader": dept.leader,
            "phone": dept.phone,
            "email": dept.email,
            "status": dept.status,
            "tenant_id": dept.tenant_id,
            "remark": dept.remark,
            "children": _build_tree(depts, dept.id),
        }
        result.append(node)
    return result


@router.get("/depts/tree", response_model=ApiResponse, summary="获取部门树")
async def get_dept_tree(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当前租户/平台的部门树"""
    query = select(SysDept).where(SysDept.is_deleted == False)  # noqa: E712
    if not current_user.is_superplatform:
        query = query.where(SysDept.tenant_id == current_user.tenant_id)
    query = query.order_by(SysDept.sort)

    result = await db.execute(query)
    depts = list(result.scalars().all())

    tree = _build_tree(depts)
    return ok(tree)


@router.get("/depts/options", response_model=ApiResponse, summary="获取部门下拉选项（树形）")
async def get_dept_options(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取部门下拉选项（用于角色自定义数据权限选择）"""
    query = select(SysDept).where(SysDept.is_deleted == False, SysDept.status == 1)  # noqa: E712
    if not current_user.is_superplatform:
        query = query.where(SysDept.tenant_id == current_user.tenant_id)
    query = query.order_by(SysDept.sort)

    result = await db.execute(query)
    depts = list(result.scalars().all())
    tree = _build_tree(depts)
    return ok(tree)


@router.get("/depts/{dept_id}", response_model=ApiResponse, summary="获取部门详情")
async def get_dept(
    dept_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    conditions = [SysDept.id == dept_id, SysDept.is_deleted == False]
    if not current_user.is_superplatform:
        conditions.append(SysDept.tenant_id == current_user.tenant_id)

    result = await db.execute(select(SysDept).where(*conditions))
    dept = result.scalar_one_or_none()
    if not dept:
        raise NotFoundException("部门")

    return ok(DeptInfo.model_validate(dept))


@router.post("/depts", response_model=ApiResponse, summary="创建部门", status_code=201)
async def create_dept(
    data: DeptCreate,
    current_user=Depends(require_permissions("system:dept:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id

    # 校验同级部门名称唯一
    exists = await db.execute(
        select(SysDept.id).where(
            SysDept.parent_id == data.parent_id,
            SysDept.name == data.name,
            SysDept.is_deleted == False,  # noqa: E712
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessException(code=400, message=f"部门 '{data.name}' 已存在")

    # 获取父部门信息
    parent = None
    level = 1
    ancestors = "0"
    if data.parent_id > 0:
        result = await db.execute(
            select(SysDept).where(SysDept.id == data.parent_id, SysDept.is_deleted == False)  # noqa: E712
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise NotFoundException("父部门")
        level = parent.level + 1
        ancestors = _build_ancestors(parent)

    dept = SysDept(
        name=data.name,
        parent_id=data.parent_id,
        ancestors=ancestors,
        level=level,
        sort=data.sort,
        leader=data.leader,
        phone=data.phone,
        email=data.email,
        status=data.status,
        tenant_id=tenant_id,
        remark=data.remark,
    )
    db.add(dept)
    await db.flush()
    await db.refresh(dept)

    return ApiResponse(code=201, message="创建成功", data=DeptInfo.model_validate(dept))


@router.put("/depts/{dept_id}", response_model=ApiResponse, summary="更新部门")
async def update_dept(
    dept_id: int,
    data: DeptUpdate,
    current_user=Depends(require_permissions("system:dept:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    conditions = [SysDept.id == dept_id, SysDept.is_deleted == False]
    if not current_user.is_superplatform:
        conditions.append(SysDept.tenant_id == current_user.tenant_id)

    result = await db.execute(select(SysDept).where(*conditions))
    dept = result.scalar_one_or_none()
    if not dept:
        raise NotFoundException("部门")

    if data.parent_id is not None:
        if data.parent_id == dept_id:
            raise BusinessException(code=400, message="不能将部门设为自己的子部门")
        if dept.ancestors and str(dept_id) in dept.ancestors.split(","):
            raise BusinessException(code=400, message="不能将部门移动到自己的子部门下")

        if data.parent_id > 0:
            parent_conditions = [SysDept.id == data.parent_id, SysDept.is_deleted == False]
            if not current_user.is_superplatform:
                parent_conditions.append(SysDept.tenant_id == current_user.tenant_id)

            parent_result = await db.execute(select(SysDept).where(*parent_conditions))
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise NotFoundException("父部门")
            dept.ancestors = _build_ancestors(parent)
            dept.level = parent.level + 1
        else:
            dept.ancestors = "0"
            dept.level = 1

    for k, v in data.model_dump(exclude_none=True).items():
        setattr(dept, k, v)

    await db.flush()

    if data.parent_id is not None and data.parent_id > 0:
        await _update_children_ancestors(db, dept_id, dept.ancestors or "", dept.level)

    return ok(DeptInfo.model_validate(dept))


async def _update_children_ancestors(
    db: AsyncSession, dept_id: int, ancestors: str, level: int
) -> None:
    """递归更新子部门的 ancestors 和 level"""
    result = await db.execute(
        select(SysDept).where(SysDept.parent_id == dept_id, SysDept.is_deleted == False)  # noqa: E712
    )
    children = list(result.scalars().all())

    for child in children:
        child.ancestors = f"{ancestors},{dept_id}"
        child.level = level + 1
        await _update_children_ancestors(db, child.id, child.ancestors or "", child.level)


@router.delete("/depts/{dept_id}", response_model=ApiResponse, summary="删除部门")
async def delete_dept(
    dept_id: int,
    current_user=Depends(require_permissions("system:dept:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    # 检查是否有子部门
    children = await db.execute(
        select(SysDept.id).where(
            SysDept.parent_id == dept_id, SysDept.is_deleted == False  # noqa: E712
        )
    )
    if children.scalar_one_or_none():
        raise BusinessException(code=400, message="请先删除子部门")

    # 检查是否有用户
    users = await db.execute(
        select(SysUser.id).where(
            SysUser.dept_id == dept_id, SysUser.is_deleted == False  # noqa: E712
        )
    )
    if users.scalar_one_or_none():
        raise BusinessException(code=400, message="该部门下有用户，无法删除")

    # 逻辑删除
    result = await db.execute(
        select(SysDept).where(SysDept.id == dept_id, SysDept.is_deleted == False)  # noqa: E712
    )
    dept = result.scalar_one_or_none()
    if dept:
        dept.is_deleted = True
        await db.flush()

    return ok(message="删除成功")


# ============ 字典类型 API ============

@router.get("/dict/types", response_model=ApiResponse, summary="获取字典类型列表")
async def get_dict_types(
    keyword: str | None = Query(default=None, description="关键字搜索（名称/编码）"),
    status: int | None = Query(default=None, description="状态筛选"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    service = DictService(db)
    types = await service.get_dict_types(tenant_id, keyword, status)
    return ok([DictTypeInfo.model_validate(t) for t in types])


@router.get("/dict/types/{type_id}", response_model=ApiResponse, summary="获取字典类型详情（含字典项）")
async def get_dict_type(
    type_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    dict_type, items = await service.get_dict_type_with_items(type_id)
    if not dict_type:
        raise NotFoundException("字典类型")
    result = DictTypeWithItems(
        **DictTypeInfo.model_validate(dict_type).dict(),
        items=[DictItemInfo.model_validate(i) for i in items],
    )
    return ok(result)


@router.post("/dict/types", response_model=ApiResponse, summary="创建字典类型", status_code=201)
async def create_dict_type(
    data: DictTypeCreate,
    current_user=Depends(require_permissions("system:dict:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    service = DictService(db)

    exists = await db.execute(
        select(SysDictType.id).where(
            SysDictType.code == data.code,
            SysDictType.is_deleted == False,
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessException(code=400, message=f"字典类型编码 '{data.code}' 已存在")

    dict_type = await service.create_dict_type(data, tenant_id)
    return created(DictTypeInfo.model_validate(dict_type))


@router.put("/dict/types/{type_id}", response_model=ApiResponse, summary="更新字典类型")
async def update_dict_type(
    type_id: int,
    data: DictTypeUpdate,
    current_user=Depends(require_permissions("system:dict:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    dict_type = await service.update_dict_type(type_id, data)
    if not dict_type:
        raise NotFoundException("字典类型")
    return ok(DictTypeInfo.model_validate(dict_type))


@router.delete("/dict/types/{type_id}", response_model=ApiResponse, summary="删除字典类型")
async def delete_dict_type(
    type_id: int,
    current_user=Depends(require_permissions("system:dict:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    success = await service.delete_dict_type(type_id)
    if not success:
        raise NotFoundException("字典类型")
    return ok(message="删除成功")


# ============ 字典项 API ============

@router.get("/dict/items", response_model=ApiResponse, summary="获取字典项列表")
async def get_dict_items(
    type_id: int = Query(..., description="字典类型 ID"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    items = await service.get_dict_items(type_id)
    return ok([DictItemInfo.model_validate(i) for i in items])


@router.post("/dict/items", response_model=ApiResponse, summary="创建字典项", status_code=201)
async def create_dict_item(
    data: DictItemCreate,
    current_user=Depends(require_permissions("system:dict:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)

    exists = await db.execute(
        select(SysDictItem.id).where(
            SysDictItem.type_id == data.type_id,
            SysDictItem.value == data.value,
            SysDictItem.is_deleted == False,
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessException(code=400, message=f"字典值 '{data.value}' 已存在")

    dict_item = await service.create_dict_item(data)
    return created(DictItemInfo.model_validate(dict_item))


@router.put("/dict/items/{item_id}", response_model=ApiResponse, summary="更新字典项")
async def update_dict_item(
    item_id: int,
    data: DictItemUpdate,
    current_user=Depends(require_permissions("system:dict:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    dict_item = await service.update_dict_item(item_id, data)
    if not dict_item:
        raise NotFoundException("字典项")
    return ok(DictItemInfo.model_validate(dict_item))


@router.delete("/dict/items/{item_id}", response_model=ApiResponse, summary="删除字典项")
async def delete_dict_item(
    item_id: int,
    current_user=Depends(require_permissions("system:dict:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    service = DictService(db)
    success = await service.delete_dict_item(item_id)
    if not success:
        raise NotFoundException("字典项")
    return ok(message="删除成功")


# ============ 前端使用 API ============

@router.get("/dict/code/{code}", response_model=ApiResponse, summary="根据编码获取字典项")
async def get_dict_by_code(
    code: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    service = DictService(db)
    dict_type, items = await service.get_dict_by_code(code, tenant_id)
    if not dict_type:
        return ok(DictCodeResult(code=code, name="", items=[]))
    return ok(DictCodeResult(
        code=dict_type.code,
        name=dict_type.name,
        items=[DictItemInfo.model_validate(i) for i in items],
    ))
