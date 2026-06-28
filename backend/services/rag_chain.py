"""
RAG Chain (LangGraph-based)
Full pipeline:
1. Multi-query retrieval
2. Parent-child context expansion
3. Reranking
4. Citation extraction
5. LLM answer generation (streaming via Ollama)

LangGraph StateGraph manages the flow.
"""
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator, TypedDict, Annotated
import httpx
from langgraph.graph import StateGraph, END
from services.multi_query import multi_query_search
from services.reranker import rerank
from services import vector_store
from services.conversation import build_memory_context
from config import settings

logger = logging.getLogger(__name__)

OLLAMA_GENERATE_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"

RAG_PROMPT = """You are an Enterprise AI Knowledge Assistant. Answer questions based on the provided document excerpts.

## Conversation History
{history}

## Retrieved Document Context
{context}

## Instructions
- Answer based ONLY on the provided context
- Be precise and cite specific documents
- If the answer is not in the context, say "I don't find this information in the uploaded documents"
- Format your answer clearly with bullet points or sections when appropriate

## Question
{question}

## Answer:"""


# ─── LangGraph State ──────────────────────────────────────────────────────────

class RAGState(TypedDict):
    query: str
    conversation_history: List[Dict]
    doc_filter: Optional[List[str]]
    user_id: Optional[str]          # ← for per-user chunk filtering
    retrieved_chunks: List[Dict]
    context_chunks: List[Dict]
    reranked_chunks: List[Dict]
    citations: List[Dict]
    prompt: str
    answer: str


# ─── LangGraph Nodes ──────────────────────────────────────────────────────────

async def retrieve_node(state: RAGState) -> RAGState:
    """Multi-query hybrid retrieval — filtered by user_id."""
    hits = await multi_query_search(
        query=state["query"],
        k=settings.RETRIEVAL_K,
        doc_filter=state.get("doc_filter"),
        user_id=state.get("user_id"),
    )
    state["retrieved_chunks"] = hits
    return state


def expand_to_parents_node(state: RAGState) -> RAGState:
    """Expand child chunks to their parent context."""
    expanded = []
    seen_parents = set()

    for chunk in state["retrieved_chunks"]:
        meta = chunk.get("metadata", {})
        parent_id = meta.get("parent_id")

        if parent_id and parent_id not in seen_parents:
            parent_text = vector_store.get_parent_text(parent_id)
            if parent_text:
                seen_parents.add(parent_id)
                expanded.append({
                    **chunk,
                    "text": parent_text,
                    "chunk_id": parent_id,
                    "is_parent": True,
                })
            else:
                expanded.append(chunk)
        elif not parent_id:
            expanded.append(chunk)

    state["context_chunks"] = expanded if expanded else state["retrieved_chunks"]
    return state


def rerank_node(state: RAGState) -> RAGState:
    """Rerank context chunks."""
    reranked = rerank(
        query=state["query"],
        chunks=state["context_chunks"],
        top_k=settings.RERANK_TOP_K,
    )
    state["reranked_chunks"] = reranked
    return state


def build_prompt_node(state: RAGState) -> RAGState:
    """Build RAG prompt with context and memory."""
    # Build context string with citations
    context_parts = []
    citations = []

    for i, chunk in enumerate(state["reranked_chunks"]):
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "Unknown")
        page = meta.get("page", 0)
        text = chunk["text"]

        context_parts.append(
            f"[{i+1}] Source: {filename} (Page {page})\n{text}"
        )
        citations.append({
            "index": i + 1,
            "document_id": meta.get("doc_id", ""),
            "filename": filename,
            "page": page,
            "chunk_text": text[:300] + ("..." if len(text) > 300 else ""),
            "score": round(chunk.get("score", 0.0), 4),
        })

    context_str = "\n\n---\n\n".join(context_parts)
    history_str = build_memory_context(state["conversation_history"])

    prompt = RAG_PROMPT.format(
        history=history_str or "No previous conversation.",
        context=context_str or "No relevant documents found.",
        question=state["query"],
    )

    state["prompt"] = prompt
    state["citations"] = citations
    return state


# ─── Build the LangGraph ──────────────────────────────────────────────────────

def build_rag_graph() -> StateGraph:
    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("expand_parents", expand_to_parents_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("build_prompt", build_prompt_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "expand_parents")
    graph.add_edge("expand_parents", "rerank")
    graph.add_edge("rerank", "build_prompt")
    graph.add_edge("build_prompt", END)

    return graph.compile()


_rag_graph = None


def get_rag_graph():
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = build_rag_graph()
    return _rag_graph


# ─── Streaming Generation ─────────────────────────────────────────────────────

async def run_rag_stream(
    query: str,
    conversation_history: List[Dict],
    doc_filter: Optional[List[str]] = None,
    user_id: Optional[str] = None,
) -> AsyncIterator[Dict]:
    """
    Run the full RAG pipeline and yield streaming events:
    - {"type": "status", "message": "..."}
    - {"type": "citation", "data": [...]}
    - {"type": "token", "content": "..."}
    - {"type": "done", "answer": "..."}
    - {"type": "error", "message": "..."}
    """
    try:
        # Phase 1: Run LangGraph pipeline (retrieval + reranking)
        yield {"type": "status", "message": "🔍 Searching documents..."}

        initial_state: RAGState = {
            "query": query,
            "conversation_history": conversation_history,
            "doc_filter": doc_filter,
            "user_id": user_id,
            "retrieved_chunks": [],
            "context_chunks": [],
            "reranked_chunks": [],
            "citations": [],
            "prompt": "",
            "answer": "",
        }

        graph = get_rag_graph()
        final_state = await graph.ainvoke(initial_state)

        yield {"type": "status", "message": "📚 Context retrieved, generating answer..."}
        yield {"type": "citation", "data": final_state["citations"]}

        # Phase 2: Streaming LLM generation via Ollama
        full_answer = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", OLLAMA_GENERATE_URL, json={
                "model": settings.LLM_MODEL,
                "prompt": final_state["prompt"],
                "stream": True,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096,
                }
            }) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                full_answer += token
                                yield {"type": "token", "content": token}
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

        yield {"type": "done", "answer": full_answer, "citations": final_state["citations"]}

    except Exception as e:
        logger.error(f"RAG pipeline error: {e}", exc_info=True)
        yield {"type": "error", "message": str(e)}
