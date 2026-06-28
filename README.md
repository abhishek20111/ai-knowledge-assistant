# 🧠 Enterprise AI Knowledge Assistant

> **Talk to your company documents using AI** — Upload PDFs, Word files, Excel sheets, and images. Ask anything in plain English and get accurate answers with source citations, powered by a fully local AI stack with zero API costs.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B35)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-7B2D8B)
![Ollama](https://img.shields.io/badge/Ollama-Local_AI-000000)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 📸 What It Does

```
┌─────────────────────────────────────────────────────────┐
│  🧠 KnowledgeAI  │ 💬 Chats │ 📄 Docs │ ⬆️ Upload      │
├──────────────────┼──────────────────────────────────────┤
│                  │                                      │
│  📋 HR Policy    │  You: What is the leave policy?      │
│  📊 Q3 Report    │                                      │
│  📝 Contract     │  🧠 AI: According to the HR Policy   │
│                  │  document (Page 4), employees are    │
│  🔍 Filter chat  │  entitled to 21 days of paid leave   │
│  to this doc     │  annually...                         │
│                  │                                      │
│  ─────────────── │  📎 Sources                          │
│  Docs: 3         │  [1] HR_Policy.pdf — p.4             │
│  Chunks: 847     │  [2] Employee_Handbook.pdf — p.12    │
│  Chats: 5        │                                      │
└──────────────────┴──────────────────────────────────────┘
```

---

## ✨ Features

### 🔍 Advanced Retrieval (What Makes It Enterprise-Grade)

| Feature | Description |
|---------|-------------|
| **Hybrid Search** | Dense vector search (ChromaDB) + sparse BM25 keyword search, fused with Reciprocal Rank Fusion |
| **Parent-Child Chunking** | Small 256-token child chunks indexed; 1024-token parent chunks returned for richer context |
| **Multi-Query Expansion** | LLM generates 3 alternative phrasings → more recall, fewer missed results |
| **Cross-Encoder Reranking** | FlashRank re-scores all retrieved chunks → picks the most relevant 5 |
| **Metadata Filtering** | Filter chat to only search within specific documents |
| **Conversation Memory** | Last 5 turns of chat injected into the prompt automatically |
| **Citations** | Every answer shows source filename, page number, and chunk preview |

### 📄 Document Support

| Format | Parser | Notes |
|--------|--------|-------|
| **PDF** | PyMuPDF | Text + tables, page-aware |
| **DOCX** | python-docx | Full Word document support |
| **XLSX** | openpyxl | Sheet data as structured text |
| **Images** | EasyOCR | JPG, PNG, GIF, BMP, TIFF, WEBP |

### ⚡ Streaming & Real-Time

- **LangGraph pipeline** — explicit state machine: Retrieve → Expand → Rerank → Generate
- **Server-Sent Events (SSE)** — streams tokens word-by-word to the browser in real time
- **Persistent sessions** — chat history survives browser refresh (`sessions/*.json`)
- **Background ingestion** — files appear instantly; processing happens asynchronously

---

## 🛠️ Libraries & Tools — Full Breakdown

> Understanding what each library does and WHY it was chosen.

### 🧠 AI / LLM Layer

| Library | Version | Role | Why This Choice |
|---------|---------|------|----------------|
| **[Ollama](https://ollama.com)** | v0.30+ | Local LLM inference engine | Runs models (qwen2.5:7b, nomic-embed-text) 100% locally — no OpenAI API key needed, no cost, no data leaves your machine |
| **[LangChain](https://python.langchain.com)** | 0.3 | LLM abstraction layer | Provides unified interface for calling Ollama, building prompts, and text splitting. Used for `langchain-ollama` chat wrapper and text splitters |
| **[LangGraph](https://langchain-ai.github.io/langgraph)** | 0.2 | RAG pipeline state machine | Converts the RAG pipeline into an explicit graph of nodes (Retrieve → Expand → Rerank → Prompt). Makes the pipeline debuggable, pausable, and extensible |
| **[langchain-ollama](https://pypi.org/project/langchain-ollama)** | 0.2 | Ollama ↔ LangChain bridge | Allows calling Ollama's `qwen2.5:7b` and `nomic-embed-text` models through LangChain's standard interface |

**Models Used:**

| Model | Size | Purpose | Where It Runs |
|-------|------|---------|--------------|
| `qwen2.5:7b` | 4.7 GB | Answer generation, multi-query expansion | GPU + RAM (hybrid on GTX 1650) |
| `nomic-embed-text` | 274 MB | Text → 768-dim vector embeddings | GPU |

---

### 🗄️ Vector Storage & Search

| Library | Version | Role | Why This Choice |
|---------|---------|------|----------------|
| **[ChromaDB](https://www.trychroma.com)** | 0.5.23 | Vector store — stores and searches embeddings | Lightweight, embedded, no separate server required. Supports metadata filtering and persistent storage |
| **[rank-bm25](https://pypi.org/project/rank-bm25)** | 0.2.2 | Sparse BM25 keyword search index | Classic probabilistic retrieval — catches exact keywords, names, codes that vector search might miss |
| **[FlashRank](https://github.com/PrithivirajDamodaran/FlashRank)** | 0.2.9 | Cross-encoder reranking | Uses `ms-marco-MiniLM-L-12-v2` to re-score retrieved chunks more accurately than vector similarity. Runs on CPU only — ideal for 4GB VRAM setup |

**How Hybrid Search Works (Reciprocal Rank Fusion):**
```
Query: "What is the leave policy?"
         ↓
┌─────────────────────┐    ┌─────────────────────┐
│   ChromaDB Dense    │    │    BM25 Sparse       │
│  (semantic meaning) │    │  (keyword matching)  │
│  1. chunk_A (0.92)  │    │  1. chunk_B (8.3)    │
│  2. chunk_B (0.88)  │    │  2. chunk_A (7.1)    │
│  3. chunk_C (0.75)  │    │  3. chunk_D (6.8)    │
└─────────────────────┘    └─────────────────────┘
              ↓  Reciprocal Rank Fusion  ↓
         Combined + deduplicated ranking
         → top 20 results → FlashRank reranks → top 5
```

---

### 🌐 Web Framework & API

| Library | Version | Role | Why This Choice |
|---------|---------|------|----------------|
| **[FastAPI](https://fastapi.tiangolo.com)** | 0.115 | REST API framework | Async-native, automatic Swagger docs at `/docs`, built-in Pydantic validation, excellent for SSE streaming |
| **[Uvicorn](https://www.uvicorn.org)** | 0.32 | ASGI web server | High-performance async server that runs FastAPI |
| **[Pydantic](https://docs.pydantic.dev)** | 2.x | Data validation & schemas | All request/response bodies validated automatically — catches bad inputs before they reach logic |
| **[python-multipart](https://pypi.org/project/python-multipart)** | 0.0.12 | File upload handling | Required for FastAPI's `UploadFile` to work with multipart form data |
| **[python-dotenv](https://pypi.org/project/python-dotenv)** | 1.0 | Environment config | Loads `.env` file into settings automatically |

---

### 🗃️ Database (Metadata Storage)

| Library | Version | Role | Why This Choice |
|---------|---------|------|----------------|
| **[SQLAlchemy](https://www.sqlalchemy.org)** | 2.0 | Async ORM for SQLite | Manages Documents, Conversations, Messages tables with full async support |
| **[aiosqlite](https://aiosqlite.omnilib.dev)** | 0.20 | Async SQLite driver | Makes SQLite work with FastAPI's async event loop without blocking |

**Database Tables:**
```
documents        → tracks uploaded files (id, filename, status, page_count, chunk_count)
conversations    → chat sessions (id, title, created_at)
messages         → individual messages (id, conversation_id, role, content, citations JSON)
```

---

### 📄 Document Processing

| Library | Version | Role | Why This Choice |
|---------|---------|------|----------------|
| **[PyMuPDF](https://pymupdf.readthedocs.io)** | 1.24 | PDF parsing | Fastest Python PDF library; extracts text page by page with accurate layout |
| **[python-docx](https://python-docx.readthedocs.io)** | 1.1 | Word document parsing | Official .docx reader; handles paragraphs, tables, headers |
| **[openpyxl](https://openpyxl.readthedocs.io)** | 3.1 | Excel (.xlsx) parsing | Reads sheets, rows, columns and converts to text representation |
| **[EasyOCR](https://github.com/JaidedAI/EasyOCR)** | 1.7 | Image OCR (text extraction) | Supports 80+ languages; works on JPG/PNG/etc. without Tesseract install |

**Document Processing Pipeline:**
```
File Upload
    ↓
detect type (pdf/docx/xlsx/image)
    ↓
extract raw text per page (PyMuPDF / python-docx / openpyxl / EasyOCR)
    ↓
Parent-Child Chunking
    ├── Parent: 1024 tokens, overlap 50   (for context)
    └── Child:   256 tokens, overlap 50   (for indexing)
    ↓
Embed child chunks (nomic-embed-text via Ollama)
    ↓
Store in ChromaDB (children + parents)
Store in BM25 index (children)
Update SQLite (status = "ready")
```

---

### 🔧 Utilities & Infrastructure

| Library | Version | Role |
|---------|---------|------|
| **[httpx](https://www.python-httpx.org)** | 0.27 | Async HTTP client — used for Ollama API streaming |
| **[aiofiles](https://github.com/Tinche/aiofiles)** | 24.1 | Async file I/O — reading/writing session JSON files |
| **[langchain-text-splitters](https://pypi.org/project/langchain-text-splitters)** | 0.3 | `RecursiveCharacterTextSplitter` for parent-child chunking |
| **[langsmith](https://smith.langchain.com)** | 0.2 | LangChain tracing (optional) |
| **[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings)** | 2.x | `Settings` class that reads from `.env` file |
| **[torch + torchvision](https://pytorch.org)** | 2.12 | Required by EasyOCR for neural net inference |
| **[onnxruntime](https://onnxruntime.ai)** | 1.27 | Required by ChromaDB and FlashRank for running ONNX models |
| **[scipy + scikit-image](https://scipy.org)** | latest | Image preprocessing for EasyOCR |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        UPLOAD FLOW                             │
│                                                                │
│  File Upload → Document Processor → Parent-Child Chunker       │
│      ↓              (PyMuPDF /           (LangChain splitter)  │
│  FastAPI             docx/xlsx/OCR)            ↓              │
│  BackgroundTask                        nomic-embed-text        │
│                                        (Ollama embeddings)     │
│                                              ↓                 │
│                              ┌───────────────┴──────────────┐  │
│                              │ ChromaDB (child vectors)     │  │
│                              │ ChromaDB (parent texts)      │  │
│                              │ BM25 Index (rank-bm25)       │  │
│                              │ SQLite (metadata)            │  │
│                              └──────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                         QUERY FLOW (LangGraph)                 │
│                                                                │
│  User Question (Browser → FastAPI SSE endpoint)                │
│      ↓                                                         │
│  ┌─────────────────── LangGraph StateGraph ────────────────┐  │
│  │                                                          │  │
│  │  Node 1: RETRIEVE                                        │  │
│  │    └─ Multi-Query: qwen2.5:7b generates 3 variants       │  │
│  │    └─ Dense Search: ChromaDB cosine similarity           │  │
│  │    └─ Sparse Search: BM25 keyword matching               │  │
│  │    └─ RRF Fusion: merge + deduplicate → top 20           │  │
│  │            ↓                                             │  │
│  │  Node 2: EXPAND_PARENTS                                  │  │
│  │    └─ Child chunk → look up parent context               │  │
│  │            ↓                                             │  │
│  │  Node 3: RERANK                                          │  │
│  │    └─ FlashRank (ms-marco-MiniLM-L-12-v2) → top 5       │  │
│  │            ↓                                             │  │
│  │  Node 4: BUILD_PROMPT                                    │  │
│  │    └─ Inject: context + citations + memory (last 5 turns)│  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│      ↓                                                         │
│  Ollama (qwen2.5:7b) → streaming via /api/generate             │
│      ↓                                                         │
│  FastAPI SSE → tokens sent word-by-word to browser             │
│      ↓                                                         │
│  Browser JS renders answer + citation cards in real-time       │
└────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
enterprise-rag/
│
├── 🖥️  backend/                    Python FastAPI backend
│   ├── main.py                    Entry point — FastAPI app, CORS, lifespan
│   ├── config.py                  All settings via pydantic-settings
│   ├── requirements.txt           All Python dependencies
│   │
│   ├── api/
│   │   ├── chat.py                SSE streaming chat + conversations + sessions
│   │   └── documents.py           Upload, list, delete, stats endpoints
│   │
│   ├── database/
│   │   └── db.py                  SQLite models: Documents, Conversations, Messages
│   │
│   ├── models/
│   │   └── schemas.py             Pydantic request/response schemas
│   │
│   └── services/
│       ├── rag_chain.py           ⭐ LangGraph state machine (full pipeline)
│       ├── hybrid_search.py       ChromaDB + BM25 → RRF fusion
│       ├── multi_query.py         qwen2.5:7b query expansion (3 variants)
│       ├── reranker.py            FlashRank cross-encoder reranking
│       ├── vector_store.py        ChromaDB operations (child + parent)
│       ├── bm25_store.py          rank-bm25 index (persist + load)
│       ├── chunker.py             Parent-child chunking (1024/256 tokens)
│       ├── embedder.py            nomic-embed-text via Ollama HTTP API
│       ├── document_processor.py  PyMuPDF + python-docx + openpyxl + EasyOCR
│       └── conversation.py        Session JSON persistence + memory context
│
├── 🌐  frontend/                   Pure HTML/CSS/Vanilla JS — no framework
│   ├── index.html                 App shell: sidebar + chat panel + upload modal
│   ├── css/styles.css             Dark glassmorphism design system (24KB)
│   └── js/
│       ├── app.js                 Bootstrap, session restore, health check
│       ├── chat.js                SSE stream handler, markdown render, citations
│       ├── documents.js           Document list, filter chips, status polling
│       ├── upload.js              Drag & drop, upload progress, status tracking
│       └── api.js                 Centralized API client with SSE support
│
├── 📦  venv/                       Python 3.12 virtual environment
├── 💾  chroma_db/                  ChromaDB persistent storage (auto-created)
├── 📁  uploads/                    Uploaded files (auto-created)
├── 📝  sessions/                   Session JSON files (auto-created)
├── 🗄️  rag.db                      SQLite database (auto-created)
│
├── 🚀  start.bat                   One-click startup (checks Ollama, starts server)
├── 📦  install.bat                 Creates venv + installs all dependencies
├── 🙈  .gitignore                  Excludes venv, DB, uploads, sessions
└── 📖  README.md                   This file
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Download |
|------|---------|---------|
| **Python** | 3.12 only (NOT 3.13 or 3.14 — native extensions incompatible) | [python.org](https://www.python.org/downloads/release/python-31210/) |
| **Ollama** | Latest | [ollama.com](https://ollama.com) |
| **Git** | Any | [git-scm.com](https://git-scm.com) |

> ⚠️ **Python 3.12 is required.** Python 3.13/3.14 breaks `pydantic-core` and `tokenizers` due to PyO3 native binary incompatibility.

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/yourusername/enterprise-rag.git
cd enterprise-rag
```

---

### Step 2 — Install Dependencies

**Windows — double-click `install.bat`**

Or manually:
```bat
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

> First install takes 5–10 minutes — includes PyTorch (123 MB), EasyOCR, ChromaDB, etc.

---

### Step 3 — Download AI Models

```bash
ollama pull qwen2.5:7b          # 4.7 GB — one-time download (resumes if interrupted)
ollama pull nomic-embed-text    # 274 MB — embedding model
```

> Models are cached in `~/.ollama/models/` — only downloaded once.

---

### Step 4 — Start the App

**Windows — double-click `start.bat`** ← Easiest

Or manually:
```bat
venv\Scripts\activate
python backend\main.py
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser ✅

Also see **[http://localhost:8000/docs](http://localhost:8000/docs)** for Swagger API explorer.

---

### Step 5 — Use It

1. **⬆️ Upload** — drag & drop any PDF, Word, Excel, or image file
2. **Wait** for ✓ Ready status (5–60 seconds depending on file size)
3. **💬 New Conversation** — create a chat
4. **Type your question** — e.g. *"Summarize this contract"* or *"Who are the parties involved?"*
5. Watch the answer stream in real-time with source citations 🎉

---

## ⚙️ Configuration

Edit [`backend/config.py`](backend/config.py):

```python
# AI Models
LLM_MODEL    = "qwen2.5:7b"        # Swap to qwen2.5:14b for better quality (needs 8GB+ VRAM)
EMBED_MODEL  = "nomic-embed-text"  # 768-dim dense embeddings

# RAG Tuning
RETRIEVAL_K       = 20   # Initial chunk retrieval count
RERANK_TOP_K      = 5    # Chunks sent to LLM after reranking
MULTI_QUERY_COUNT = 3    # LLM query variants generated
MEMORY_WINDOW     = 5    # Conversation turns kept in memory
PARENT_CHUNK_SIZE = 1024 # Parent chunk token size
CHILD_CHUNK_SIZE  = 256  # Child chunk token size (indexed)
CHUNK_OVERLAP     = 50   # Overlap between consecutive chunks

# Limits
MAX_FILE_SIZE_MB  = 50
```

---

## 🔌 API Reference

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload document (multipart/form-data, field: `file`) |
| `GET` | `/api/documents` | List all documents with status |
| `DELETE` | `/api/documents/{id}` | Delete document + all its vectors |
| `GET` | `/api/documents/stats` | Collection stats (chunk counts) |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/stream` | **Streaming SSE chat** |
| `GET` | `/api/conversations` | List all conversations |
| `POST` | `/api/conversations` | Create a new conversation |
| `GET` | `/api/conversations/{id}/messages` | Get full message history |
| `DELETE` | `/api/conversations/{id}` | Delete conversation + messages |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sessions/{id}` | Get UI session state |
| `PUT` | `/api/sessions/{id}` | Save UI session state |

### Chat Request Body

```json
{
  "conversation_id": "uuid-string",
  "message": "What is the leave policy?",
  "document_filter": ["doc-id-1"]
}
```

### SSE Event Stream Format

```
data: {"type": "status",   "message": "🔍 Searching documents..."}
data: {"type": "status",   "message": "📚 Context retrieved, generating answer..."}
data: {"type": "citation", "data": [{"filename": "...", "page": 4, "score": 0.92}]}
data: {"type": "token",    "content": "According"}
data: {"type": "token",    "content": " to"}
data: {"type": "done",     "answer": "...", "citations": [...]}
data: [DONE]
```

---

## 🖥️ Hardware Requirements & Model Guide

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16 GB |
| **VRAM** | 4 GB | 8 GB |
| **Storage** | 10 GB free | 20 GB |
| **CPU** | 4 cores | 8 cores |

> **Tested on:** Intel Core i5-10300H, 16 GB RAM, GTX 1650 (4 GB VRAM)

### Model Selection

| Model | Size | VRAM Needed | Speed | Quality |
|-------|------|------------|-------|---------|
| `qwen2.5:7b` **(default)** | 4.7 GB | 4–5 GB | ~8 tok/s | ⭐⭐⭐⭐ |
| `qwen2.5:14b` | 9 GB | 8+ GB | ~4 tok/s | ⭐⭐⭐⭐⭐ |
| `llama3.2:3b` | 2 GB | 2–3 GB | ~20 tok/s | ⭐⭐⭐ |

> If VRAM < model size, Ollama automatically offloads remaining layers to RAM (slower but still works).

---

## 🧩 Full Tech Stack Reference

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | HTML5 + CSS3 + Vanilla JS | — | UI — glassmorphism dark design |
| **Web Framework** | FastAPI | 0.115 | REST API + SSE streaming |
| **ASGI Server** | Uvicorn | 0.32 | Async HTTP server |
| **Data Validation** | Pydantic v2 | 2.x | Request/response schemas |
| **AI Orchestration** | LangChain | 0.3 | LLM wrappers, text splitters |
| **Pipeline Engine** | LangGraph | 0.2 | RAG state machine |
| **LLM** | qwen2.5:7b via Ollama | — | Answer generation, query expansion |
| **Embeddings** | nomic-embed-text via Ollama | — | 768-dim dense vectors |
| **Vector Store** | ChromaDB | 0.5.23 | Dense semantic search |
| **Keyword Search** | rank-bm25 | 0.2.2 | Sparse BM25 retrieval |
| **Reranker** | FlashRank (ms-marco-MiniLM-L-12-v2) | 0.2.9 | Cross-encoder reranking |
| **PDF Parser** | PyMuPDF (fitz) | 1.24 | Page-aware PDF extraction |
| **Word Parser** | python-docx | 1.1 | .docx parsing |
| **Excel Parser** | openpyxl | 3.1 | .xlsx sheet parsing |
| **OCR** | EasyOCR | 1.7 | Image text extraction |
| **Database ORM** | SQLAlchemy (async) | 2.0 | Documents, conversations, messages |
| **SQLite Driver** | aiosqlite | 0.20 | Async SQLite for FastAPI |
| **HTTP Client** | httpx | 0.27 | Async calls to Ollama API |
| **Deep Learning** | PyTorch | 2.12 | Backend for EasyOCR |
| **ML Runtime** | ONNX Runtime | 1.27 | ChromaDB + FlashRank model inference |

---

## 🐛 Known Issues & Fixes

### ChromaDB telemetry error (harmless)
```
ERROR chromadb.telemetry.product.posthog: capture() takes 1 positional argument but 3 were given
```
**This is a ChromaDB analytics bug — not your app.** Completely harmless, ignore it.

### First-time model downloads during use
- **EasyOCR**: Downloads ~1.5 GB neural net models on first image upload
- **FlashRank**: Downloads `ms-marco-MiniLM-L-12-v2` (21 MB) on first chat
- **ChromaDB**: Downloads `all-MiniLM-L6-v2` (79 MB) on first vector query  
These are one-time downloads cached locally.

### Python version
```bash
# Must be Python 3.12
py -3.12 --version   # Python 3.12.x ✅
# NOT 3.13 or 3.14 — pydantic-core PyO3 bindings incompatible
```

### Ollama not found in PATH
Open a **new terminal window** after installing Ollama. PATH updates only take effect in new sessions.

---

## 📝 Resume Description

> **Enterprise RAG Platform** — Built a full-stack AI document intelligence system using Python FastAPI + LangGraph. Implemented advanced Hybrid Retrieval combining ChromaDB dense vector search with BM25 sparse keyword search, fused via Reciprocal Rank Fusion. Features Parent-Child Chunking (1024/256 tokens), Multi-Query Expansion via LLM, and Cross-Encoder Reranking with FlashRank. Delivers real-time streaming answers via Server-Sent Events with source citations. Runs 100% locally using Ollama (qwen2.5:7b + nomic-embed-text) with zero API costs.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">
  Built with Python · FastAPI · LangGraph · ChromaDB · Ollama · qwen2.5:7b
</div>
