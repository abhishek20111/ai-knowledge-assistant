"""
Multi-Query Retrieval
Uses LLM to generate alternative phrasings of the query.
Searches with all queries → deduplicates → merges.
"""
import logging
import httpx
import json
from typing import List, Dict, Any, Optional
from services.hybrid_search import hybrid_search
from config import settings

logger = logging.getLogger(__name__)

GENERATE_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"

MULTI_QUERY_PROMPT = """You are an AI assistant helping with enterprise document search.
Generate {count} different search queries to find information about the following topic.
Each query should approach the topic from a different angle.
Return ONLY a JSON array of strings, nothing else.

Topic: {query}

Example output:
["query 1", "query 2", "query 3"]"""


async def generate_alternative_queries(query: str, count: int = None) -> List[str]:
    """Use LLM to generate alternative query phrasings."""
    if count is None:
        count = settings.MULTI_QUERY_COUNT

    prompt = MULTI_QUERY_PROMPT.format(query=query, count=count)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GENERATE_URL, json={
                "model": settings.LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            })
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "").strip()

            # Extract JSON array
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                queries = json.loads(raw[start:end])
                return [q for q in queries if isinstance(q, str)]
    except Exception as e:
        logger.warning(f"Multi-query generation failed: {e}")

    return [query]  # fallback to original


async def multi_query_search(
    query: str,
    k: int = None,
    doc_filter: Optional[List[str]] = None,
) -> List[Dict]:
    """
    1. Generate N alternative queries
    2. Search with each
    3. Deduplicate by chunk_id
    4. Return merged & deduplicated results
    """
    if k is None:
        k = settings.RETRIEVAL_K

    alt_queries = await generate_alternative_queries(query)
    all_queries = list(dict.fromkeys([query] + alt_queries))  # original first, dedup
    logger.info(f"Multi-query search with {len(all_queries)} queries: {all_queries}")

    seen_ids = set()
    merged = []

    for q in all_queries:
        hits = await hybrid_search(q, k=k, doc_filter=doc_filter)
        for hit in hits:
            cid = hit["chunk_id"]
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged.append(hit)

    # Sort by RRF/score
    merged.sort(key=lambda x: x.get("rrf_score", x.get("score", 0)), reverse=True)
    return merged[:k]
