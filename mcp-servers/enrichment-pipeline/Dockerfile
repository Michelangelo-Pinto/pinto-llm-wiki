FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    fastmcp>=3.0.0 \
    qdrant-client>=1.17.0 \
    langgraph>=0.2.0 \
    langchain-core>=0.3.0 \
    langchain-openai>=0.2.0 \
    sqlalchemy>=2.0.0 \
    pyyaml>=6.0
RUN useradd -m -u 1000 mcp && mkdir -p /data /app && chown -R mcp:mcp /data /app
WORKDIR /app
COPY src/ /app/src/
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8004
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
USER mcp
CMD ["python", "-m", "enrichment_pipeline.server"]
