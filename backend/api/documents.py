"""
Documents API (user-scoped)
POST /api/documents/upload  - Upload and process a document
GET  /api/documents          - List current user's documents
DELETE /api/documents/{id}   - Delete a document (must own it)
GET  /api/documents/stats    - Stats for current user's collection
"""
import os
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from database.db import get_db, Document, User
from models.schemas import DocumentResponse
from services.document_processor import process_document, get_file_type
from services.chunker import create_parent_child_chunks
from services.embedder import embed_texts
from services import vector_store, bm25_store
from services.auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "xlsx", "image"}
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def _ingest_document(doc_id: str, file_path: str, filename: str, user_id: str, db):
    """Background task: process, chunk, embed, store — tagged to user_id."""
    try:
        pages = await process_document(file_path, filename)
        page_count = len(pages)

        parent_chunks, child_chunks = create_parent_child_chunks(pages, doc_id, filename)

        # Tag every chunk with user_id for filtering
        for c in child_chunks:
            c["metadata"]["user_id"] = user_id
        for p in parent_chunks:
            p["metadata"]["user_id"] = user_id

        child_texts = [c["text"] for c in child_chunks]
        embeddings = await embed_texts(child_texts)

        await vector_store.add_chunks(child_chunks, parent_chunks, embeddings)

        bm25_entries = [
            {"chunk_id": c["chunk_id"], "text": c["text"], "metadata": c["metadata"]}
            for c in child_chunks
        ]
        bm25_store.add_to_index(bm25_entries)

        async with db as session:
            result = await session.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "ready"
                doc.page_count = page_count
                doc.chunk_count = len(child_chunks)
                await session.commit()

        logger.info(f"[user:{user_id}] Ingested {filename}: {page_count}p, {len(child_chunks)} chunks")

    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}", exc_info=True)
        try:
            async with db as session:
                result = await session.execute(select(Document).where(Document.id == doc_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "error"
                    doc.error_msg = str(e)[:500]
                    await session.commit()
        except Exception:
            pass


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_type = get_file_type(file.filename)
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported file type. Allowed: PDF, DOCX, XLSX, Images")

    content = await file.read()
    if len(content) / (1024 * 1024) > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(413, f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}_{Path(file.filename).name}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=safe_name,
        original_filename=file.filename,
        file_type=file_type,
        file_size=len(content),
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    from database.db import AsyncSessionLocal
    background_tasks.add_task(
        _ingest_document, doc_id, file_path, file.filename, current_user.id, AsyncSessionLocal()
    )
    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    await vector_store.delete_document_chunks(doc_id)
    bm25_store.remove_from_index(doc_id)

    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted", "id": doc_id}


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id)
    )
    docs = result.scalars().all()
    chroma_stats = vector_store.get_collection_stats()
    return {
        "total_documents": len(docs),
        "ready_documents": sum(1 for d in docs if d.status == "ready"),
        "processing_documents": sum(1 for d in docs if d.status == "processing"),
        **chroma_stats,
    }
