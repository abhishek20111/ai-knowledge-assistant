@echo off
title Enterprise AI Knowledge Assistant — Setup & Start
color 0B
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║      Enterprise AI Knowledge Assistant                  ║
echo  ║      Advanced RAG Platform  ^|  LangGraph + Ollama       ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set ROOT=%~dp0
set VENV=%ROOT%venv
set BACKEND=%ROOT%backend
set PYTHON=%VENV%\Scripts\python.exe
set PIP=%VENV%\Scripts\pip.exe
:: Python 3.12 required (3.14 is NOT supported by PyO3-based packages)
set PY312=C:\Users\white\AppData\Local\Programs\Python\Python312\python.exe

:: ── Step 1: Check Python ──────────────────────────────────────
echo [1/5] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found. Install from https://python.org
    pause & exit /b 1
)
echo  OK ^| Python found

:: ── Step 2: Create venv if missing ───────────────────────────
echo [2/5] Checking virtual environment...
if not exist "%VENV%\Scripts\activate.bat" (
    echo  Creating venv...
    python -m venv "%VENV%"
    if %errorlevel% neq 0 (
        echo  ERROR: Failed to create venv
        pause & exit /b 1
    )
    echo  OK ^| venv created at %VENV%
) else (
    echo  OK ^| venv already exists
)

:: ── Step 3: Install dependencies ─────────────────────────────
echo [3/5] Checking Python dependencies...
"%PYTHON%" -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing packages into venv (this takes a few minutes)...
    "%PIP%" install -r "%BACKEND%\requirements.txt" --quiet
    if %errorlevel% neq 0 (
        echo  ERROR: pip install failed. Check your internet connection.
        pause & exit /b 1
    )
    echo  OK ^| All packages installed
) else (
    echo  OK ^| Dependencies already installed
)

:: ── Step 4: Check Ollama ──────────────────────────────────────
echo [4/5] Checking Ollama...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo  WARNING: Ollama not found. Install from https://ollama.com
    echo  Then run: ollama pull qwen2.5:7b ^&^& ollama pull nomic-embed-text
    pause & exit /b 1
)

:: Start Ollama service if not running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %errorlevel% neq 0 (
    echo  Starting Ollama service...
    start /B "" ollama serve
    timeout /t 4 /nobreak >nul
) else (
    echo  OK ^| Ollama already running
)

:: Pull models if missing
ollama list 2>&1 | find "qwen2.5" >nul
if %errorlevel% neq 0 (
    echo  Pulling qwen2.5:7b model [~4.7 GB, one-time download]...
    ollama pull qwen2.5:7b
)
ollama list 2>&1 | find "nomic-embed-text" >nul
if %errorlevel% neq 0 (
    echo  Pulling nomic-embed-text model [~274 MB]...
    ollama pull nomic-embed-text
)
echo  OK ^| Models ready

:: ── Step 5: Start backend ─────────────────────────────────────
echo [5/5] Starting backend...
echo.
echo  ┌─────────────────────────────────────────┐
echo  │  App URL : http://localhost:8000         │
echo  │  API Docs: http://localhost:8000/docs    │
echo  └─────────────────────────────────────────┘
echo.

start "RAG Backend" cmd /k "title RAG Backend ^| http://localhost:8000 && cd /d %BACKEND% && %PYTHON% main.py"

timeout /t 3 /nobreak >nul
start "" "http://localhost:8000"

echo  Backend started! Browser opening...
echo  Close the 'RAG Backend' window to stop the server.
echo.
pause
