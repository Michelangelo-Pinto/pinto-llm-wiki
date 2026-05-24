FROM python:3.12-slim

# Install system dependencies for sentence-transformers native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
# sentence-transformers provides the all-MiniLM-L6-v2 embedding model (384-dim)
# which is shared with the ingestion pipeline and matches Qdrant's default config.
RUN pip install --no-cache-dir \
    fastmcp>=3.0.0 \
    qdrant-client>=1.17.0 \
    sentence-transformers>=3.0.0 \
    httpx>=0.27.0

# Pre-download the embedding model to eliminate cold start delay on first call
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    mkdir -p /data /app && \
    chown -R mcp:mcp /data /app

WORKDIR /app
COPY src/ /app/src/

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8001
ENV PYTHONUNBUFFERED=1

USER mcp

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://localhost:${MCP_PORT}/sse || exit 1

CMD ["python", "-m", "qdrant_mcp.server"]
