"""
Documents API
POST /api/documents/upload  - Upload and process a document
GET  /api/documents          - List all documents
DELETE /api/documents/{id}   - Delete a document
GET  /api/documents/stats    - Collection stats
"""
import os
import uuid
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from database.db import get_db, Document
from models.schemas import DocumentResponse
from services.document_processor import process_document, get_file_type
from services.chunker import create_parent_child_chunks
from services.embedder import embed_texts
from services import vector_store, bm25_store
from config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "xlsx", "image"}
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def _ingest_document(doc_id: str, file_path: str, filename: str, db: AsyncSession):
    """Background task: process, chunk, embed, store."""
    try:
        # 1. Parse document
        pages = await process_document(file_path, filename)
        page_count = len(pages)

        # 2. Parent-child chunking
        parent_chunks, child_chunks = create_parent_child_chunks(pages, doc_id, filename)

        # 3. Embed child chunks
        child_texts = [c["text"] for c in child_chunks]
        embeddings = await embed_texts(child_texts)

        # 4. Store in ChromaDB
        await vector_store.add_chunks(child_chunks, parent_chunks, embeddings)

        # 5. Add to BM25 index
        bm25_entries = [
            {"chunk_id": c["chunk_id"], "text": c["text"], "metadata": c["metadata"]}
            for c in child_chunks
        ]
        bm25_store.add_to_index(bm25_entries)

        # 6. Update DB
        async with db as session:
            result = await session.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "ready"
                doc.page_count = page_count
                doc.chunk_count = len(child_chunks)
                await session.commit()

        logger.info(f"Document {filename} ingested: {page_count} pages, {len(child_chunks)} chunks")

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
):
    # Validate file type
    file_type = get_file_type(file.filename)
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type. Allowed: PDF, DOCX, XLSX, Images")

    # Validate size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(413, f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    # Save file
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}_{Path(file.filename).name}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # Create DB record
    doc = Document(
        id=doc_id,
        filename=safe_name,
        original_filename=file.filename,
        file_type=file_type,
        file_size=len(content),
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Start background ingestion
    from database.db import AsyncSessionLocal
    background_tasks.add_task(_ingest_document, doc_id, file_path, file.filename, AsyncSessionLocal())

    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove from vector store & BM25
    await vector_store.delete_document_chunks(doc_id)
    bm25_store.remove_from_index(doc_id)

    # Remove file
    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove from DB
    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted", "id": doc_id}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document))
    docs = result.scalars().all()
    chroma_stats = vector_store.get_collection_stats()
    return {
        "total_documents": len(docs),
        "ready_documents": sum(1 for d in docs if d.status == "ready"),
        "processing_documents": sum(1 for d in docs if d.status == "processing"),
        **chroma_stats,
    }
