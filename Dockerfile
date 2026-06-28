# ─── Build Stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Runtime Stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install libgomp (required by LightGBM/ONNX in some packages)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app source
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create runtime directories
RUN mkdir -p uploads sessions chroma_db

WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "main.py"]
