"""
BM25 Sparse Search
Uses rank-bm25 for keyword-based retrieval.
Index is rebuilt in memory from ChromaDB child chunks.
"""
import logging
import pickle
import os
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from config import settings

logger = logging.getLogger(__name__)

INDEX_PATH = os.path.join(settings.CHROMA_PATH, "bm25_index.pkl")

# In-memory BM25 state
_bm25: Optional[BM25Okapi] = None
_corpus: List[Dict] = []   # [{chunk_id, text, metadata}, ...]


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def build_index(chunks: List[Dict]) -> None:
    """Build BM25 index from list of chunk dicts."""
    global _bm25, _corpus
    _corpus = chunks
    tokenized = [_tokenize(c["text"]) for c in chunks]
    _bm25 = BM25Okapi(tokenized)
    _save_index()
    logger.info(f"BM25 index built with {len(chunks)} chunks")


def add_to_index(new_chunks: List[Dict]) -> None:
    """Add new chunks to the BM25 index (rebuild)."""
    global _corpus
    _corpus.extend(new_chunks)
    build_index(_corpus)


def remove_from_index(doc_id: str) -> None:
    """Remove all chunks for a doc and rebuild."""
    global _corpus
    _corpus = [c for c in _corpus if c.get("metadata", {}).get("doc_id") != doc_id]
    if _corpus:
        build_index(_corpus)
    else:
        global _bm25
        _bm25 = None
        _save_index()


def search(query: str, k: int = 20, doc_filter: Optional[List[str]] = None) -> List[Dict]:
    """BM25 keyword search."""
    global _bm25, _corpus
    if _bm25 is None or not _corpus:
        return []

    tokenized_query = _tokenize(query)
    scores = _bm25.get_scores(tokenized_query)

    hits = []
    for idx, score in enumerate(scores):
        if score > 0:
            chunk = _corpus[idx]
            meta = chunk.get("metadata", {})
            if doc_filter and meta.get("doc_id") not in doc_filter:
                continue
            hits.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "metadata": meta,
                "score": float(score),
                "search_type": "sparse",
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:k]


def _save_index():
    try:
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({"corpus": _corpus}, f)
    except Exception as e:
        logger.warning(f"Could not save BM25 index: {e}")


def load_index():
    """Load BM25 index from disk on startup."""
    global _bm25, _corpus
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, "rb") as f:
                data = pickle.load(f)
            _corpus = data.get("corpus", [])
            if _corpus:
                tokenized = [_tokenize(c["text"]) for c in _corpus]
                _bm25 = BM25Okapi(tokenized)
                logger.info(f"BM25 index loaded: {len(_corpus)} chunks")
        except Exception as e:
            logger.warning(f"Could not load BM25 index: {e}")
            _corpus = []
            _bm25 = None
