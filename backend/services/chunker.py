"""
Parent-Child Chunker
- Parent chunks: larger context (1024 tokens ≈ chars)
- Child chunks: smaller, embedded (256 tokens ≈ chars)
On retrieval: find child → return parent context
"""
import uuid
from typing import List, Dict, Any
from config import settings


def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into chunks by character count with overlap."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start = end - overlap
    return chunks


def create_parent_child_chunks(
    pages: List[Dict[str, Any]],
    doc_id: str,
    filename: str,
) -> tuple[List[Dict], List[Dict]]:
    """
    Returns (parent_chunks, child_chunks)
    Each parent chunk contains multiple child chunks.
    child.metadata["parent_id"] links to parent.
    """
    parent_chunks = []
    child_chunks = []

    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]
        metadata = page_data.get("metadata", {})

        # Create parent chunks from the page
        parent_texts = _split_text(
            text,
            settings.PARENT_CHUNK_SIZE * 4,   # 4 chars ≈ 1 token
            settings.CHUNK_OVERLAP * 4
        )

        for p_idx, parent_text in enumerate(parent_texts):
            parent_id = f"{doc_id}_p{page_num}_{p_idx}"
            parent_chunks.append({
                "chunk_id": parent_id,
                "doc_id": doc_id,
                "filename": filename,
                "page": page_num,
                "text": parent_text,
                "chunk_type": "parent",
                "parent_id": None,
                "metadata": {
                    **metadata,
                    "chunk_id": parent_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": page_num,
                    "chunk_type": "parent",
                }
            })

            # Create child chunks from each parent
            child_texts = _split_text(
                parent_text,
                settings.CHILD_CHUNK_SIZE * 4,
                settings.CHUNK_OVERLAP * 4
            )
            for c_idx, child_text in enumerate(child_texts):
                child_id = f"{parent_id}_c{c_idx}"
                child_chunks.append({
                    "chunk_id": child_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": page_num,
                    "text": child_text,
                    "chunk_type": "child",
                    "parent_id": parent_id,
                    "metadata": {
                        **metadata,
                        "chunk_id": child_id,
                        "doc_id": doc_id,
                        "filename": filename,
                        "page": page_num,
                        "chunk_type": "child",
                        "parent_id": parent_id,
                    }
                })

    return parent_chunks, child_chunks
