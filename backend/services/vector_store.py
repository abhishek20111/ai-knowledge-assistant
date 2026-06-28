"""
ChromaDB Vector Store
Stores CHILD chunks for embedding-based search.
Stores PARENT chunks in a separate collection for context retrieval.
"""
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings

logger = logging.getLogger(__name__)

_client: Optional[chromadb.PersistentClient] = None
_child_col = None   # child chunks (searched)
_parent_col = None  # parent chunks (retrieved for context)


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _client


def get_child_collection():
    global _child_col
    if _child_col is None:
        client = get_client()
        _child_col = client.get_or_create_collection(
            name=f"{settings.CHROMA_COLLECTION}_child",
            metadata={"hnsw:space": "cosine"}
        )
    return _child_col


def get_parent_collection():
    global _parent_col
    if _parent_col is None:
        client = get_client()
        _parent_col = client.get_or_create_collection(
            name=f"{settings.CHROMA_COLLECTION}_parent",
            metadata={"hnsw:space": "cosine"}
        )
    return _parent_col


async def add_chunks(
    child_chunks: List[Dict],
    parent_chunks: List[Dict],
    embeddings: List[List[float]],
) -> None:
    """Add child chunks with embeddings, and parent chunks without embeddings."""
    child_col = get_child_collection()
    parent_col = get_parent_collection()

    # Add child chunks (with embeddings)
    if child_chunks and embeddings:
        child_col.add(
            ids=[c["chunk_id"] for c in child_chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in child_chunks],
            metadatas=[c["metadata"] for c in child_chunks],
        )

    # Add parent chunks (stored for text retrieval, no embeddings needed)
    if parent_chunks:
        # Store in batches of 500
        batch_size = 500
        for i in range(0, len(parent_chunks), batch_size):
            batch = parent_chunks[i:i + batch_size]
            parent_col.add(
                ids=[p["chunk_id"] for p in batch],
                documents=[p["text"] for p in batch],
                metadatas=[p["metadata"] for p in batch],
            )

    logger.info(f"Added {len(child_chunks)} child + {len(parent_chunks)} parent chunks")


async def similarity_search(
    query_embedding: List[float],
    k: int = 20,
    doc_filter: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> List[Dict]:
    """Dense vector similarity search on child chunks, filtered by user."""
    child_col = get_child_collection()

    # Build ChromaDB `where` filter — user_id always applied if provided
    conditions = []
    if user_id:
        conditions.append({"user_id": {"$eq": user_id}})
    if doc_filter:
        conditions.append({"doc_id": {"$in": doc_filter}})

    if len(conditions) > 1:
        where = {"$and": conditions}
    elif len(conditions) == 1:
        where = conditions[0]
    else:
        where = None

    count = child_col.count()
    if count == 0:
        return []

    results = child_col.query(
        query_embeddings=[query_embedding],
        n_results=min(k, count),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            hits.append({
                "chunk_id": chunk_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": 1.0 - results["distances"][0][i],
                "search_type": "dense",
            })
    return hits


def get_parent_text(parent_id: str) -> Optional[str]:
    """Retrieve parent chunk text by ID."""
    parent_col = get_parent_collection()
    try:
        result = parent_col.get(ids=[parent_id], include=["documents"])
        if result["documents"]:
            return result["documents"][0]
    except Exception:
        pass
    return None


async def delete_document_chunks(doc_id: str) -> None:
    """Delete all chunks belonging to a document."""
    child_col = get_child_collection()
    parent_col = get_parent_collection()
    child_col.delete(where={"doc_id": doc_id})
    parent_col.delete(where={"doc_id": doc_id})
    logger.info(f"Deleted all chunks for doc_id={doc_id}")


def get_collection_stats() -> Dict:
    child_col = get_child_collection()
    parent_col = get_parent_collection()
    return {
        "child_chunks": child_col.count(),
        "parent_chunks": parent_col.count(),
    }
