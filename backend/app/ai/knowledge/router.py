"""
若茗 PaaS - 知识库路由
/api/v1/ai/knowledge
Author: ruoming
"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseInfo,
    KnowledgeBaseUpdate,
    KnowledgeDocInfo,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.ai.knowledge.service import KnowledgeService
from app.config import settings
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import AppException, NotFoundException
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/knowledge", tags=["AI-知识库"])


@router.get("", response_model=ApiResponse[PageData[KnowledgeBaseInfo]], summary="知识库列表")
async def list_knowledge_bases(
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    items, total = await svc.get_list(current_user.tenant_id, current_user.id, page_params)
    return paged(items=[KnowledgeBaseInfo.model_validate(i) for i in items], total=total, params=page_params)


@router.post("", response_model=ApiResponse[KnowledgeBaseInfo], summary="创建知识库", status_code=201)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("ai:kb:create")),
):
    svc = KnowledgeService(db)
    kb = await svc.create(data, current_user.tenant_id, current_user.id)
    return created(KnowledgeBaseInfo.model_validate(kb))


@router.put("/{kb_id}", response_model=ApiResponse[KnowledgeBaseInfo], summary="修改知识库")
async def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:update")),
):
    svc = KnowledgeService(db)
    kb = await svc.update(kb_id, data)
    return ok(KnowledgeBaseInfo.model_validate(kb))


@router.delete("/{kb_id}", response_model=ApiResponse, summary="删除知识库")
async def delete_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:delete")),
):
    svc = KnowledgeService(db)
    await svc.delete(kb_id)
    return ok(message="删除成功")


# ── 文档管理 ──────────────────────────────────────────────────────────────────

@router.get("/{kb_id}/docs", response_model=ApiResponse[PageData[KnowledgeDocInfo]], summary="文档列表")
async def list_documents(
    kb_id: int,
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    items, total = await svc.list_documents(kb_id, page_params)
    return paged(items=[KnowledgeDocInfo.model_validate(i) for i in items], total=total, params=page_params)


@router.post("/{kb_id}/docs", response_model=ApiResponse[KnowledgeDocInfo], summary="上传文档", status_code=201)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(..., description="文档文件（支持 txt/md/pdf/docx/html）"),
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    # 文件大小限制
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_size_bytes:
        raise AppException(status_code=413, message=f"文件超过最大上传限制（{settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 文件类型校验
    filename = file.filename or "untitled"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    allowed_doc_exts = {"txt", "md", "pdf", "docx", "doc", "html", "htm", "csv"}
    if ext not in allowed_doc_exts:
        raise AppException(status_code=415, message=f"不支持的文档类型：{ext}")

    svc = KnowledgeService(db)
    doc = await svc.upload_document(kb_id, filename, content, source_type="file")
    return created(KnowledgeDocInfo.model_validate(doc))


@router.put("/{kb_id}/docs/{doc_id}", response_model=ApiResponse, summary="更新文档（增量）")
async def update_document(
    kb_id: int,
    doc_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    content = await file.read()
    svc = KnowledgeService(db)
    result = await svc.update_document(kb_id, doc_id, content)
    return ok(result)


@router.delete("/{kb_id}/docs/{doc_id}", response_model=ApiResponse, summary="删除文档（含向量清理）")
async def delete_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:delete")),
):
    svc = KnowledgeService(db)
    await svc.delete_document(kb_id, doc_id)
    return ok(message="删除成功")


# ── 检索测试 ──────────────────────────────────────────────────────────────────

@router.post("/{kb_id}/search", response_model=ApiResponse[list[KnowledgeSearchResult]], summary="知识库检索测试")
async def search_knowledge_base(
    kb_id: int,
    data: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    results = await svc.search(
        kb_id=kb_id,
        query=data.query,
        top_k=data.top_k,
        retrieval_type=data.retrieval_type,
    )
    return ok([KnowledgeSearchResult(**r) for r in results])
