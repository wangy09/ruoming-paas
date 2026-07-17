"""
若茗 PaaS - 权限路由（权限、角色、菜单）
Author: ruoming
"""
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.error_codes import PermErrCode
from app.core.exceptions import BusinessException, NotFoundException
from app.core.redis import get_redis
from app.core.response import ApiResponse, created, ok, paged
from app.database import get_db
from app.modules.permission.models import (
    SysPermission,
    SysRole,
    SysRolePermission,
)
from app.modules.permission.schemas import (
    PermissionCreate,
    PermissionUpdate,
    RoleCreate,
    RoleInfo,
    RolePermissionAssign,
    RoleUpdate,
)
from app.modules.permission.service import PermissionService

router = APIRouter()


@router.get(
    "/my/permissions",
    response_model=ApiResponse,
    summary="获取当前用户权限（前端初始化用）",
    description="返回当前用户的所有权限码、菜单树、按钮权限、列权限",
)
async def get_my_permissions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    svc = PermissionService(db, redis)

    # 超管拥有所有权限（包括所有菜单）
    if current_user.is_superplatform:
        data = await svc.get_all_menus()
        data["codes"] = ["*"]
        data["buttons"] = ["*"]
        data["is_superplatform"] = True
        return ok(data)

    data = await svc.get_user_full_permissions(current_user.id)
    return ok(data)


@router.get(
    "/permissions/tree",
    response_model=ApiResponse,
    summary="获取权限树（管理端）",
)
async def get_permission_tree(
    current_user=Depends(require_permissions("system:permission:view")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    from sqlalchemy import select
    from app.modules.permission.models import SysPermission

    result = await db.execute(
        select(SysPermission)
        .where(SysPermission.is_deleted == False)  # noqa: E712
        .order_by(SysPermission.sort)
    )
    perms = list(result.scalars().all())

    # 构建树形结构
    perm_map = {p.id: {
        "id": p.id,
        "parent_id": p.parent_id,
        "name": p.name,
        "code": p.code,
        "type": p.perm_type,
        "path": p.path,
        "component": p.component,
        "icon": p.icon,
        "sort": p.sort,
        "is_visible": p.is_visible,
        "is_cache": p.is_cache,
        "is_external": p.is_external,
        "is_system": p.is_system,
        "resource": p.resource,
        "method": p.method,
        "children": [],
    } for p in perms}

    tree = []
    for perm in perm_map.values():
        if perm["parent_id"] == 0:
            tree.append(perm)
        elif perm["parent_id"] in perm_map:
            perm_map[perm["parent_id"]]["children"].append(perm)

    # 按 sort 排序
    def sort_tree(nodes):
        nodes.sort(key=lambda x: x["sort"])
        for node in nodes:
            sort_tree(node["children"])

    sort_tree(tree)
    return ok(tree)


# ── 角色管理 ──────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=ApiResponse, summary="角色列表")
async def list_roles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    keyword: str | None = Query(default=None),
    current_user=Depends(require_permissions("system:role:view")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    from sqlalchemy import func, or_

    tenant_id = current_user.tenant_id
    query = select(SysRole).where(SysRole.is_deleted == False)  # noqa: E712

    if not current_user.is_superplatform:
        query = query.filter(
            (SysRole.tenant_id == tenant_id) | (SysRole.tenant_id.is_(None))
        )
    if keyword:
        query = query.where(
            or_(SysRole.name.ilike(f"%{keyword}%"), SysRole.code.ilike(f"%{keyword}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(SysRole.sort).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    roles = list(result.scalars().all())

    return paged(
        items=[RoleInfo.model_validate(r) for r in roles],
        total=total, page=page, page_size=page_size,
    )


import json

@router.post("/roles", response_model=ApiResponse[RoleInfo], summary="创建角色", status_code=201)
async def create_role(
    data: RoleCreate,
    current_user=Depends(require_permissions("system:role:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RoleInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id

    # 校验 code 唯一（租户内唯一）
    exists = await db.execute(
        select(SysRole.id).where(
            SysRole.code == data.code,
            SysRole.tenant_id == tenant_id,
            SysRole.is_deleted == False,  # noqa: E712
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessException(PermErrCode.ROLE_CODE_EXISTS, f"角色标识 '{data.code}' 已存在")
    role = SysRole(
        name=data.name,
        code=data.code,
        description=data.description,
        parent_id=data.parent_id,
        data_scope=data.data_scope,
        data_scope_depts=json.dumps(data.data_scope_depts) if data.data_scope_depts else None,
        dashboard_template=data.dashboard_template,
        sort=data.sort,
        tenant_id=tenant_id,
        status=1,
        remark=data.remark,
    )
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return ApiResponse(code=201, message="创建成功", data=RoleInfo.model_validate(role))


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleInfo], summary="更新角色")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user=Depends(require_permissions("system:role:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RoleInfo]:
    from sqlalchemy import or_

    conditions = [SysRole.id == role_id, SysRole.is_deleted == False]
    if not current_user.is_superplatform:
        conditions.append(SysRole.tenant_id == current_user.tenant_id)

    result = await db.execute(select(SysRole).where(*conditions))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException("角色")

    update_data = data.model_dump(exclude_unset=True)
    if "data_scope_depts" in update_data:
        update_data["data_scope_depts"] = json.dumps(update_data["data_scope_depts"]) if update_data["data_scope_depts"] else None

    for k, v in update_data.items():
        setattr(role, k, v)
    await db.flush()
    await db.refresh(role)
    return ok(RoleInfo.model_validate(role))


@router.delete("/roles/{role_id}", response_model=ApiResponse, summary="删除角色")
async def delete_role(
    role_id: int,
    current_user=Depends(require_permissions("system:role:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    conditions = [SysRole.id == role_id, SysRole.is_deleted == False]
    if not current_user.is_superplatform:
        conditions.append(SysRole.tenant_id == current_user.tenant_id)

    result = await db.execute(select(SysRole).where(*conditions))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException("角色")

    children = await db.execute(
        select(SysRole.id).where(SysRole.parent_id == role_id, SysRole.is_deleted == False)  # noqa: E712
    )
    if children.scalar_one_or_none():
        raise BusinessException(
            PermErrCode.CANNOT_DELETE_ROLE_WITH_CHILDREN,
            "请先删除或转移子角色",
        )

    role.is_deleted = True
    await db.flush()
    return ok(message="删除成功")


@router.get("/roles/{role_id}/permissions", response_model=ApiResponse, summary="获取角色已分配的权限")
async def get_role_permissions(
    role_id: int,
    current_user=Depends(require_permissions("system:role:view")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(SysRolePermission.permission_id)
        .where(SysRolePermission.role_id == role_id)
    )
    permission_ids = [row[0] for row in result.all()]
    return ok({"permission_ids": permission_ids})
@router.post("/roles/{role_id}/permissions", response_model=ApiResponse, summary="给角色分配权限")
async def assign_role_permissions(
    role_id: int,
    data: RolePermissionAssign,
    current_user=Depends(require_permissions("system:role:assign_perm")),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse:
    role_result = await db.execute(
        select(SysRole).where(SysRole.id == role_id, SysRole.is_deleted == False)  # noqa: E712
    )
    if not role_result.scalar_one_or_none():
        raise NotFoundException("角色")

    # 删除旧权限关联，再插入新的（全量替换）
    await db.execute(delete(SysRolePermission).where(SysRolePermission.role_id == role_id))
    for perm_id in data.permission_ids:
        db.add(SysRolePermission(role_id=role_id, permission_id=perm_id))
    await db.flush()

    # 清除角色下所有用户的权限缓存
    perm_svc = PermissionService(db, redis)
    await perm_svc.invalidate_role_users_cache(role_id)

    return ok(message="权限分配成功")


# ── 权限项管理 ────────────────────────────────────────────────────────────────

@router.post("/permissions", response_model=ApiResponse, summary="新增权限项", status_code=201)
async def create_permission(
    data: PermissionCreate,
    current_user=Depends(require_permissions("system:permission:create")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    # 校验 code 唯一
    exists = await db.execute(
        select(SysPermission.id).where(
            SysPermission.code == data.code, SysPermission.is_deleted == False  # noqa: E712
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessException(
            PermErrCode.PERMISSION_CODE_EXISTS,
            f"权限标识 '{data.code}' 已存在",
        )

    perm = SysPermission(**data.model_dump())
    db.add(perm)
    await db.flush()
    await db.refresh(perm)
    return ApiResponse(code=201, message="创建成功", data={"id": perm.id, "code": perm.code})


@router.put("/permissions/{perm_id}", response_model=ApiResponse, summary="更新权限项")
async def update_permission(
    perm_id: int,
    data: PermissionUpdate,
    current_user=Depends(require_permissions("system:permission:update")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(SysPermission).where(
            SysPermission.id == perm_id, SysPermission.is_deleted == False  # noqa: E712
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise NotFoundException("权限项")

    # 如果更新 code，需要检查是否与其他权限重复
    if data.code and data.code != perm.code:
        exists = await db.execute(
            select(SysPermission.id).where(
                SysPermission.code == data.code, SysPermission.is_deleted == False  # noqa: E712
            )
        )
        if exists.scalar_one_or_none():
            raise BusinessException(
                PermErrCode.PERMISSION_CODE_EXISTS,
                f"权限标识 '{data.code}' 已存在",
            )

    update_data = data.model_dump(exclude_none=True)
    for k, v in update_data.items():
        setattr(perm, k, v)
    await db.flush()
    await db.refresh(perm)
    return ok(message="更新成功", data={"id": perm.id, "code": perm.code})


@router.delete("/permissions/{perm_id}", response_model=ApiResponse, summary="删除权限项")
async def delete_permission(
    perm_id: int,
    current_user=Depends(require_permissions("system:permission:delete")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    result = await db.execute(
        select(SysPermission).where(
            SysPermission.id == perm_id, SysPermission.is_deleted == False  # noqa: E712
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise NotFoundException("权限项")

    perm.is_deleted = True
    await db.flush()
    return ok(message="删除成功")
