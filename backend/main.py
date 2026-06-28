"""
Enterprise AI Knowledge Assistant — FastAPI Main Application
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.db import init_db
from services import bm25_store
from api.documents import router as docs_router
from api.chat import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown lifecycle."""
    logger.info("🚀 Starting Enterprise RAG Backend...")

    # Init database
    await init_db()
    logger.info("✅ Database initialized")

    # Load BM25 index from disk
    bm25_store.load_index()
    logger.info("✅ BM25 index loaded")

    logger.info("✅ Backend ready at http://localhost:8000")
    yield

    logger.info("👋 Shutting down...")


app = FastAPI(
    title="Enterprise AI Knowledge Assistant",
    description="Advanced RAG with Hybrid Search, LangGraph Streaming, and Citations",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(docs_router)
app.include_router(chat_router)

# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Enterprise RAG Backend"}

# Serve frontend static files
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
