"""
Chat API (user-scoped)
POST /api/chat/stream        - Streaming chat (SSE)
GET  /api/conversations      - List user's conversations
POST /api/conversations      - Create a new conversation
GET  /api/conversations/{id}/messages - Get messages
DELETE /api/conversations/{id}        - Delete conversation
GET  /api/sessions/{id}      - Get session state
PUT  /api/sessions/{id}      - Save session state
"""
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from database.db import get_db, Conversation, Message, User
from models.schemas import ConversationResponse, MessageResponse, ChatRequest, Citation
from services.rag_chain import run_rag_stream
from services.conversation import load_session, save_session, list_sessions
from services.auth import get_current_user

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


# ─── Session endpoints ────────────────────────────────────────────────────────

@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str, current_user: User = Depends(get_current_user)):
    return load_session(session_id)


@router.put("/api/sessions/{session_id}")
async def update_session(
    session_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
):
    existing = load_session(session_id)
    existing.update(data)
    save_session(session_id, existing)
    return existing


@router.get("/api/sessions")
async def get_all_sessions(current_user: User = Depends(get_current_user)):
    return list_sessions()


# ─── Conversation endpoints ───────────────────────────────────────────────────

@router.get("/api/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


@router.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(
    req: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=req.title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/api/conversations/{conv_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == current_user.id)
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    parsed = []
    for msg in messages:
        citations = None
        if msg.citations:
            try:
                citations = [Citation(**c) for c in json.loads(msg.citations)]
            except Exception:
                pass
        parsed.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            citations=citations,
            created_at=msg.created_at,
        ))
    return parsed


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == current_user.id)
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    await db.execute(delete(Message).where(Message.conversation_id == conv_id))
    await db.execute(delete(Conversation).where(Conversation.id == conv_id))
    await db.commit()
    return {"message": "Conversation deleted", "id": conv_id}


# ─── Streaming Chat endpoint ──────────────────────────────────────────────────

@router.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify conversation ownership
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == req.conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Load history
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == req.conversation_id)
        .order_by(Message.created_at.asc())
    )
    history = [{"role": m.role, "content": m.content} for m in result.scalars().all()]

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=req.conversation_id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)

    if conv.title == "New Conversation":
        conv.title = req.message[:60] + ("..." if len(req.message) > 60 else "")
        conv.updated_at = datetime.utcnow()

    await db.commit()

    # Pass user_id as doc_filter context so RAG only retrieves user's chunks
    user_doc_filter = req.document_filter or None

    async def event_stream():
        full_answer = ""
        final_citations = []

        async for event in run_rag_stream(
            query=req.message,
            conversation_history=history,
            doc_filter=user_doc_filter,
            user_id=current_user.id,
        ):
            if event["type"] == "token":
                full_answer += event["content"]
            elif event["type"] == "done":
                final_citations = event.get("citations", [])
            elif event["type"] == "citation":
                final_citations = event.get("data", [])

            yield f"data: {json.dumps(event)}\n\n"

        from database.db import AsyncSessionLocal
        async with AsyncSessionLocal() as save_db:
            asst_msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=req.conversation_id,
                role="assistant",
                content=full_answer,
                citations=json.dumps(final_citations) if final_citations else None,
            )
            save_db.add(asst_msg)
            conv_res = await save_db.execute(
                select(Conversation).where(Conversation.id == req.conversation_id)
            )
            conv2 = conv_res.scalar_one_or_none()
            if conv2:
                conv2.updated_at = datetime.utcnow()
            await save_db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
