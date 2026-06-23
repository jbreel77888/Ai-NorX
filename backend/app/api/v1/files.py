"""
Files API - upload and manage files.
"""
import logging
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth.deps import get_current_user
from app.core.storage import r2_storage
from app.db import get_db
from app.db.models import User, Document, KnowledgeBase
from app.rag import parse_document, process_document, is_supported, get_file_extension

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class FileResponse(BaseModel):
    id: str
    name: str
    file_type: str
    file_size: int
    storage_url: str
    indexing_status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    document_count: int
    total_size_mb: float
    created_at: datetime

    class Config:
        from_attributes = True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Knowledge Bases
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    name: str = Form(...),
    description: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base."""
    # Get or create default knowledge base for user
    kb = KnowledgeBase(
        tenant_id=user.tenant_id,
        name=name,
        description=description,
        owner_id=user.id,
        is_public=False,
    )
    db.add(kb)
    await db.flush()
    await db.refresh(kb)

    return KnowledgeBaseResponse(
        id=str(kb.id),
        name=kb.name,
        description=kb.description,
        document_count=0,
        total_size_mb=0.0,
        created_at=kb.created_at,
    )


@router.get("/knowledge-bases", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's knowledge bases."""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.tenant_id == user.tenant_id, KnowledgeBase.owner_id == user.id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    kbs = result.scalars().all()

    # Auto-create default KB if none exists
    if not kbs:
        default_kb = KnowledgeBase(
            tenant_id=user.tenant_id,
            name="ملفاتي",
            description="مكتبة الملفات الافتراضية",
            owner_id=user.id,
        )
        db.add(default_kb)
        await db.flush()
        await db.refresh(default_kb)
        kbs = [default_kb]

    return [
        KnowledgeBaseResponse(
            id=str(kb.id),
            name=kb.name,
            description=kb.description,
            document_count=kb.document_count,
            total_size_mb=kb.total_size_mb,
            created_at=kb.created_at,
        )
        for kb in kbs
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# File Upload
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    knowledge_base_id: str = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file, parse it, and index it for RAG.

    Supported formats: PDF, DOCX, TXT, MD, CSV, JSON, HTML, XLSX, PPTX
    Max size: 10MB
    """
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    if not is_supported(file.filename):
        raise HTTPException(
            400,
            f"Unsupported file type: {get_file_extension(file.filename)}. "
            f"Supported: PDF, DOCX, TXT, MD, CSV, JSON, HTML, XLSX, PPTX"
        )

    # Read file data
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")

    if not file_data:
        raise HTTPException(400, "Empty file")

    # Get or create knowledge base
    if knowledge_base_id:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == UUID(knowledge_base_id),
                KnowledgeBase.tenant_id == user.tenant_id,
                KnowledgeBase.owner_id == user.id,
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(404, "Knowledge base not found")
    else:
        # Get or create default KB
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == user.tenant_id,
                KnowledgeBase.owner_id == user.id,
            ).order_by(KnowledgeBase.created_at.asc()).limit(1)
        )
        kb = result.scalar_one_or_none()
        if not kb:
            kb = KnowledgeBase(
                tenant_id=user.tenant_id,
                name="ملفاتي",
                description="مكتبة الملفات الافتراضية",
                owner_id=user.id,
            )
            db.add(kb)
            await db.flush()
            await db.refresh(kb)

    # 1. Upload to R2
    try:
        upload_result = await r2_storage.upload_file(
            file_data=file_data,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
    except Exception as e:
        logger.error(f"R2 upload failed: {e}")
        raise HTTPException(500, f"File storage failed: {e}")

    # 2. Parse document
    try:
        parsed = await parse_document(file_data, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        raise HTTPException(500, f"File parsing failed: {e}")

    # 3. Create document record
    from app.rag.embeddings import compute_hash
    doc = Document(
        tenant_id=user.tenant_id,
        knowledge_base_id=kb.id,
        name=file.filename,
        source="upload",
        file_type=get_file_extension(file.filename),
        file_size=len(file_data),
        content=parsed["text"],
        content_hash=compute_hash(parsed["text"]),
        storage_url=upload_result["key"],
        indexing_status="indexing",
        chunk_count=0,
        doc_metadata={
            "page_count": parsed.get("page_count", 1),
            "char_count": parsed.get("char_count", len(parsed["text"])),
            "truncated": parsed.get("truncated", False),
            "r2_key": upload_result["key"],
        },
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # 4. Index the document (chunk + embed + store)
    try:
        result = await process_document(
            text=parsed["text"],
            tenant_id=user.tenant_id,
            document_id=doc.id,
            knowledge_base_id=kb.id,
            db_session=db,
        )

        doc.chunk_count = result["chunk_count"]
        doc.indexing_status = "indexed"
        kb.document_count += 1
        kb.total_size_mb += len(file_data) / (1024 * 1024)
        await db.flush()

    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        doc.indexing_status = "failed"
        doc.doc_metadata["error"] = str(e)
        await db.flush()

    await db.refresh(doc)

    return FileResponse(
        id=str(doc.id),
        name=doc.name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        storage_url=doc.storage_url,
        indexing_status=doc.indexing_status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )


@router.get("/documents", response_model=List[FileResponse])
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's documents."""
    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == user.tenant_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        FileResponse(
            id=str(d.id),
            name=d.name,
            file_type=d.file_type or "",
            file_size=d.file_size,
            storage_url=d.storage_url or "",
            indexing_status=d.indexing_status,
            chunk_count=d.chunk_count,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == user.tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete from R2
    if doc.storage_url:
        await r2_storage.delete_file(doc.storage_url)

    await db.delete(doc)
