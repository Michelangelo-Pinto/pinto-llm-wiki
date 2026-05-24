FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ita \
    libtesseract-dev libleptonica-dev \
    libgl1-mesa-glx libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    fastmcp>=3.0.0 \
    qdrant-client>=1.17.0 \
    sentence-transformers>=3.0.0 \
    PyMuPDF>=1.24.0 \
    python-docx>=1.1.0 \
    pytesseract>=0.3.10 \
    Pillow>=10.0.0 \
    sqlalchemy>=2.0.0

# Pre-download the embedding model to eliminate cold start delay on first call
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

RUN useradd -m -u 1000 mcp && mkdir -p /data /app && chown -R mcp:mcp /data /app
WORKDIR /app
COPY src/ /app/src/
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8002
ENV PYTHONUNBUFFERED=1
USER mcp
CMD ["python", "-m", "ingestion_pipeline.server"]
