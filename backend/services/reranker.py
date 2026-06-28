"""
FlashRank Cross-Encoder Reranker
Reranks retrieved chunks using a cross-encoder model.
Runs on CPU only — perfect for GTX 1650 setup.
"""
import logging
from typing import List, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from flashrank import Ranker
            _reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank")
            logger.info("FlashRank reranker loaded")
        except Exception as e:
            logger.warning(f"FlashRank not available: {e}")
            _reranker = None
    return _reranker


def rerank(query: str, chunks: List[Dict], top_k: int = None) -> List[Dict]:
    """
    Rerank chunks using FlashRank cross-encoder.
    Falls back to original order if reranker unavailable.
    """
    if top_k is None:
        top_k = settings.RERANK_TOP_K

    if not chunks:
        return []

    ranker = get_reranker()
    if ranker is None:
        logger.warning("Reranker unavailable, using score-based sorting")
        return chunks[:top_k]

    try:
        from flashrank import RerankRequest
        passages = [{"id": i, "text": c["text"]} for i, c in enumerate(chunks)]
        request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(request)

        reranked = []
        for r in results[:top_k]:
            idx = r["id"]
            chunk = dict(chunks[idx])
            # Cast to Python float — FlashRank returns numpy float32
            # which is NOT JSON serializable
            score = float(r["score"])
            chunk["rerank_score"] = score
            chunk["score"] = score
            reranked.append(chunk)
        return reranked
    except Exception as e:
        logger.warning(f"Reranking failed: {e}, falling back to original order")
        return chunks[:top_k]
