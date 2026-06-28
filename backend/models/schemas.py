from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# ─── Document schemas ─────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str
    error_msg: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Chat schemas ──────────────────────────────────────────────────────────────

class Citation(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_text: str
    score: float

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    document_filter: Optional[List[str]] = None   # filter by doc ids

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: List[Citation]

# ─── Conversation schemas ──────────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: Optional[List[Citation]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Chunk schemas (internal) ─────────────────────────────────────────────────

class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    page: int
    text: str
    chunk_type: str = "child"   # "parent" or "child"
    parent_id: Optional[str] = None
