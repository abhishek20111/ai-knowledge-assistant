"""
Embedder Service
Uses nomic-embed-text via Ollama for generating embeddings.
Batched for efficiency.
"""
import logging
import httpx
from typing import List
from config import settings

logger = logging.getLogger(__name__)

EMBED_URL = f"{settings.OLLAMA_BASE_URL}/api/embed"


async def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Embed a list of texts using nomic-embed-text via Ollama."""
    all_embeddings = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Embedding batch {i // batch_size + 1} ({len(batch)} texts)")

            payload = {
                "model": settings.EMBED_MODEL,
                "input": batch,
            }
            response = await client.post(EMBED_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend(data["embeddings"])

    return all_embeddings


async def embed_query(text: str) -> List[float]:
    """Embed a single query string."""
    embeddings = await embed_texts([text])
    return embeddings[0]
