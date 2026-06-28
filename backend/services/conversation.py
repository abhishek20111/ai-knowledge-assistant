"""
Conversation Memory & Session Manager
- Persistent conversation history stored in SQLite
- Session UI state persisted in sessions/{session_id}.json
- LangChain conversation buffer (windowed) for prompt injection
"""
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger(__name__)

os.makedirs(settings.SESSIONS_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(settings.SESSIONS_DIR, f"{session_id}.json")


def load_session(session_id: str) -> Dict:
    """Load session UI state from JSON file."""
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load session {session_id}: {e}")
    return {
        "session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
        "active_conversation_id": None,
        "document_filter": [],
    }


def save_session(session_id: str, data: Dict) -> None:
    """Save session UI state to JSON file."""
    path = _session_path(session_id)
    data["updated_at"] = datetime.utcnow().isoformat()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Could not save session {session_id}: {e}")


def list_sessions() -> List[Dict]:
    """List all session files."""
    sessions = []
    for fname in os.listdir(settings.SESSIONS_DIR):
        if fname.endswith(".json"):
            sid = fname[:-5]
            data = load_session(sid)
            sessions.append(data)
    return sessions


def build_memory_context(messages: List[Dict], window: int = None) -> str:
    """
    Build a conversation history string for injection into RAG prompt.
    Uses last N turns (windowed memory).
    """
    if window is None:
        window = settings.MEMORY_WINDOW

    # Take last window*2 messages (user+assistant pairs)
    recent = messages[-(window * 2):]

    if not recent:
        return ""

    lines = []
    for msg in recent:
        role = "Human" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        # Truncate long messages to 200 chars for context efficiency
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{role}: {content}")

    return "\n".join(lines)
