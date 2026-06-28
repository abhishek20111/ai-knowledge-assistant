import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"
    EMBED_MODEL: str = "nomic-embed-text"

    # ChromaDB
    CHROMA_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
    CHROMA_COLLECTION: str = "enterprise_rag"

    # SQLite
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rag.db')}"

    # Upload
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    MAX_FILE_SIZE_MB: int = 50

    # Sessions
    SESSIONS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions")

    # RAG config
    PARENT_CHUNK_SIZE: int = 1024
    CHILD_CHUNK_SIZE: int = 256
    CHUNK_OVERLAP: int = 50
    RETRIEVAL_K: int = 20
    RERANK_TOP_K: int = 5
    MULTI_QUERY_COUNT: int = 3
    MEMORY_WINDOW: int = 5

    # JWT Authentication
    JWT_SECRET_KEY: str = "enterprise-rag-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"

settings = Settings()
