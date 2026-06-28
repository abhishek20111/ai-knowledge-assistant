"""
Hybrid Search Service
Combines dense (ChromaDB) + sparse (BM25) results
using Reciprocal Rank Fusion (RRF).
"""
from typing import List, Dict, Any, Optional
from services import vector_store, bm25_store
from services.embedder import embed_query
from config import settings


async def hybrid_search(
    query: str,
    k: int = None,
    doc_filter: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> List[Dict]:
    """
    Hybrid search: dense + sparse → RRF fusion.
    Returns fused results sorted by RRF score.
    """
    if k is None:
        k = settings.RETRIEVAL_K

    # 1. Dense search (ChromaDB)
    query_embedding = await embed_query(query)
    dense_hits = await vector_store.similarity_search(
        query_embedding, k=k, doc_filter=doc_filter, user_id=user_id
    )

    # 2. Sparse search (BM25)
    sparse_hits = bm25_store.search(query, k=k, doc_filter=doc_filter, user_id=user_id)

    # 3. RRF fusion
    fused = _reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
    return fused[:k]


def _reciprocal_rank_fusion(
    dense_hits: List[Dict],
    sparse_hits: List[Dict],
    k: int = 60,
) -> List[Dict]:
    """
    RRF score = Σ 1/(k + rank_i)
    k=60 is standard RRF constant (not retrieval k).
    """
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict] = {}

    def _add_hits(hits, weight=1.0):
        for rank, hit in enumerate(hits):
            cid = hit["chunk_id"]
            rrf_score = weight / (k + rank + 1)
            scores[cid] = scores.get(cid, 0.0) + rrf_score
            if cid not in chunk_map:
                chunk_map[cid] = hit

    _add_hits(dense_hits, weight=1.0)
    _add_hits(sparse_hits, weight=1.0)

    # Merge and sort
    results = []
    for cid, score in sorted(scores.items(), key=lambda x: -x[1]):
        hit = dict(chunk_map[cid])
        hit["rrf_score"] = score
        hit["score"] = score
        results.append(hit)
    return results
