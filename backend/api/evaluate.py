"""
RAG Evaluation API
POST /api/evaluate  — Score a RAG response using Ollama as judge (no OpenAI needed)

Metrics:
  faithfulness   (0-1): Is the answer grounded in the provided context?
  relevance      (0-1): Does the answer actually address the question?
  context_recall (0-1): Does the context contain enough info to answer?
"""
import json
import logging
import httpx
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.auth import get_current_user
from database.db import User
from config import settings

router = APIRouter(prefix="/api/evaluate", tags=["evaluation"])
logger = logging.getLogger(__name__)

GENERATE_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"


class EvalRequest(BaseModel):
    question: str
    answer: str
    contexts: List[str]


class EvalResponse(BaseModel):
    faithfulness: float
    relevance: float
    context_recall: float
    overall: float
    feedback: str


async def _ask_judge(prompt: str) -> str:
    """Ask qwen2.5:7b to evaluate and return raw response."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(GENERATE_URL, json={
                "model": settings.LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            })
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"Judge LLM failed: {e}")
        return ""


def _extract_score(text: str) -> float:
    """Extract first number (0-10) from judge response and normalize to 0-1."""
    import re
    matches = re.findall(r'\b([0-9](?:\.[0-9]+)?|10)\b', text)
    for m in matches:
        val = float(m)
        if 0 <= val <= 10:
            return round(val / 10.0, 2)
    return 0.5   # neutral fallback


@router.post("", response_model=EvalResponse)
async def evaluate(
    req: EvalRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate a RAG response using the local LLM as a judge.
    Returns faithfulness, relevance, and context_recall scores (0-1).
    """
    context_str = "\n\n---\n\n".join(req.contexts[:5])

    # ── Faithfulness ─────────────────────────────────────────────────────────
    faith_prompt = f"""You are an objective evaluator. Rate whether the answer is supported by the context.

Context:
{context_str}

Answer:
{req.answer}

Score the faithfulness from 0 to 10:
- 10: Every claim in the answer is explicitly supported by the context
- 5:  Some claims are supported, others are not
- 0:  The answer contradicts or ignores the context completely

Reply with ONLY a number from 0 to 10."""

    faith_raw = await _ask_judge(faith_prompt)
    faithfulness = _extract_score(faith_raw)

    # ── Relevance ─────────────────────────────────────────────────────────────
    rel_prompt = f"""You are an objective evaluator. Rate whether the answer addresses the question.

Question:
{req.question}

Answer:
{req.answer}

Score the relevance from 0 to 10:
- 10: The answer directly and completely addresses the question
- 5:  The answer partially addresses the question
- 0:  The answer is completely off-topic

Reply with ONLY a number from 0 to 10."""

    rel_raw = await _ask_judge(rel_prompt)
    relevance = _extract_score(rel_raw)

    # ── Context Recall ─────────────────────────────────────────────────────────
    recall_prompt = f"""You are an objective evaluator. Rate whether the context contains enough information to answer the question.

Question:
{req.question}

Context:
{context_str}

Score from 0 to 10:
- 10: The context contains all the information needed to fully answer the question
- 5:  The context is partially relevant
- 0:  The context is completely unrelated to the question

Reply with ONLY a number from 0 to 10."""

    recall_raw = await _ask_judge(recall_prompt)
    context_recall = _extract_score(recall_raw)

    overall = round((faithfulness + relevance + context_recall) / 3.0, 2)

    # Simple textual feedback
    if overall >= 0.8:
        feedback = "Excellent RAG response — highly faithful, relevant, and well-supported."
    elif overall >= 0.6:
        feedback = "Good response — mostly faithful and relevant with minor gaps."
    elif overall >= 0.4:
        feedback = "Moderate response — some faithfulness or relevance issues."
    else:
        feedback = "Poor response — low faithfulness or relevance. Consider improving retrieval."

    logger.info(
        f"[eval] user={current_user.username} faithfulness={faithfulness} "
        f"relevance={relevance} context_recall={context_recall} overall={overall}"
    )

    return EvalResponse(
        faithfulness=faithfulness,
        relevance=relevance,
        context_recall=context_recall,
        overall=overall,
        feedback=feedback,
    )
