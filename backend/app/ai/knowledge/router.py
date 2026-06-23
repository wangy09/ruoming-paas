"""
若茗 PaaS - 知识库路由
/api/v1/ai/knowledge
Author: ruoming
"""
import hashlib

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseInfo,
    KnowledgeBaseUpdate,
    KnowledgeDocInfo,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadPartRequest,
)
from app.ai.knowledge.service import KnowledgeService
from app.config import settings
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import AppException, NotFoundException
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.storage.factory import get_storage
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
    return paged(items=[KnowledgeBaseInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


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
    return paged(items=[KnowledgeDocInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


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


@router.get("/{kb_id}/docs/{doc_id}", response_model=ApiResponse[KnowledgeDocInfo], summary="文档详情")
async def get_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    doc = await svc.get_document(kb_id, doc_id)
    return ok(KnowledgeDocInfo.model_validate(doc))


@router.get("/{kb_id}/stats", response_model=ApiResponse, summary="知识库统计")
async def get_knowledge_base_stats(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    stats = await svc.get_stats(kb_id)
    return ok(stats)


@router.post("/{kb_id}/docs/{doc_id}/reindex", response_model=ApiResponse, summary="重新索引文档")
async def reindex_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    svc = KnowledgeService(db)
    result = await svc.reindex_document(kb_id, doc_id)
    return ok(result)


@router.post("/{kb_id}/reindex", response_model=ApiResponse, summary="重新索引全部文档")
async def reindex_all_documents(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    svc = KnowledgeService(db)
    result = await svc.reindex_all_documents(kb_id)
    return ok(result)


@router.get("/{kb_id}/tasks", response_model=ApiResponse, summary="任务列表")
async def list_knowledge_tasks(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    tasks = await svc.list_tasks(kb_id)
    return ok(tasks)


@router.get("/{kb_id}/tasks/{task_id}", response_model=ApiResponse, summary="任务状态")
async def get_task_status(
    kb_id: int,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = KnowledgeService(db)
    status = await svc.get_task_status(kb_id, task_id)
    return ok(status)


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


# ── 文件下载/预览 ─────────────────────────────────────────────────────────────

@router.get("/{kb_id}/docs/{doc_id}/download", summary="下载/预览文档原文件")
async def download_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """从配置的存储后端下载文档原文件"""
    from app.ai.knowledge.models import AiKnowledgeDoc

    doc = await db.get(AiKnowledgeDoc, doc_id)
    if not doc or doc.is_deleted or doc.kb_id != kb_id:
        raise NotFoundException(f"文档 ID={doc_id} 不存在")
    if not doc.storage_key or not doc.storage_backend:
        raise AppException(code=500, message="文档未配置存储信息（历史数据）")

    storage = get_storage()
    try:
        content = await storage.get(doc.storage_key)
    except Exception as e:
        raise AppException(code=500, message=f"读取文件失败：{e}")

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.name}"',
        },
    )


# ── 分片上传 ────────────────────────────────────────────────────────────────

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per part


@router.post("/{kb_id}/upload/init", response_model=ApiResponse[UploadInitResponse], summary="初始化分片上传")
async def init_multipart_upload(
    kb_id: int,
    data: UploadInitRequest,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    """初始化分片上传，返回 upload_id 和已上传分片列表（断点续传）"""
    import uuid
    from datetime import datetime, timedelta

    from app.ai.knowledge.models import AiKnowledgeUploadPart

    # 检查是否已有相同 hash 的完整文档
    svc = KnowledgeService(db)
    kb = await svc.get_by_id(kb_id)

    # 查询是否有未完成的分片上传（断点续传）
    existing_parts = await db.execute(
        select(AiKnowledgeUploadPart)
        .where(AiKnowledgeUploadPart.upload_id != None)
        .where(AiKnowledgeUploadPart.kb_id == kb_id)
        .where(AiKnowledgeUploadPart.file_hash == data.file_hash)
        .where(AiKnowledgeUploadPart.expires_at > datetime.now())
    )
    parts = existing_parts.scalars().all()

    if parts:
        # 已有未完成上传，返回已上传分片列表
        upload_id = parts[0].upload_id
        uploaded_numbers = [p.part_number for p in parts]
        return ok(UploadInitResponse(
            upload_id=upload_id,
            part_size=CHUNK_SIZE,
            uploaded_parts=uploaded_numbers,
        ))

    # 新上传
    upload_id = str(uuid.uuid4())
    return ok(UploadInitResponse(
        upload_id=upload_id,
        part_size=CHUNK_SIZE,
        uploaded_parts=[],
    ))


@router.post("/{kb_id}/upload/part", summary="上传分片")
async def upload_part(
    kb_id: int,
    upload_id: str = File(...),
    part_number: int = File(...),
    part_hash: str = File(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    """上传单个分片"""
    from datetime import datetime, timedelta

    from app.ai.knowledge.models import AiKnowledgeUploadPart

    content = await file.read()

    # 校验分片 hash
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != part_hash:
        raise AppException(code=400, message=f"分片 hash 不匹配：期望 {part_hash}，实际 {actual_hash}")

    # 存储分片
    storage = get_storage()
    storage_key = f"upload_parts/{upload_id}/{part_number}"
    stored = await storage.put(storage_key, content)

    # 记录分片信息
    part = AiKnowledgeUploadPart(
        upload_id=upload_id,
        kb_id=kb_id,
        filename=file.filename or "unknown",
        file_hash="",  # 完整文件 hash 在 complete 时填
        part_number=part_number,
        part_size=len(content),
        part_hash=part_hash,
        storage_key=stored.key,
        expires_at=datetime.now() + timedelta(hours=24),
    )
    db.add(part)
    await db.commit()

    return ok({"part_number": part_number, "etag": part_hash})


@router.post("/{kb_id}/upload/complete", response_model=ApiResponse[KnowledgeDocInfo], summary="完成分片上传")
async def complete_multipart_upload(
    kb_id: int,
    data: UploadCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:kb:upload")),
):
    """合并所有分片，创建文档并触发索引"""
    import hashlib
    from datetime import datetime

    from app.ai.knowledge.models import AiKnowledgeUploadPart

    # 获取所有分片
    parts_result = await db.execute(
        select(AiKnowledgeUploadPart)
        .where(AiKnowledgeUploadPart.upload_id == data.upload_id)
        .where(AiKnowledgeUploadPart.kb_id == kb_id)
        .order_by(AiKnowledgeUploadPart.part_number)
    )
    parts = parts_result.scalars().all()

    if not parts:
        raise AppException(code=400, message="未找到分片记录")

    # 校验分片完整性
    if len(parts) != len(data.part_hashes):
        raise AppException(code=400, message=f"分片数量不匹配：期望 {len(data.part_hashes)}，实际 {len(parts)}")

    for i, part in enumerate(parts):
        if part.part_hash != data.part_hashes[i]:
            raise AppException(code=400, message=f"分片 {i+1} hash 不匹配")

    # 合并分片
    storage = get_storage()
    full_content = b""
    for part in parts:
        chunk = await storage.get(part.storage_key)
        full_content += chunk

    # 计算完整文件 hash
    full_hash = hashlib.sha256(full_content).hexdigest()

    # 创建文档
    svc = KnowledgeService(db)
    doc = await svc.upload_document(
        kb_id=kb_id,
        filename=parts[0].filename,
        file_content=full_content,
        source_type="multipart_upload",
    )

    # 清理分片记录
    for part in parts:
        await db.delete(part)
    await db.commit()

    return created(KnowledgeDocInfo.model_validate(doc))
