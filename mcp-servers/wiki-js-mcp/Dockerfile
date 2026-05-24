FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 mcp \
    && useradd --uid 1000 --gid mcp --create-home mcp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /data /logs \
    && chown -R mcp:mcp /app /data /logs

USER mcp

EXPOSE 8000

VOLUME ["/data", "/logs"]

ENV WIKIJS_API_URL=http://wiki:3000 \
    WIKIJS_MCP_DB=/data/wikijs_mappings.db \
    LOG_FILE=/logs/wikijs_mcp.log \
    LOG_LEVEL=INFO \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_TRANSPORT=sse

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD bash -c 'echo > /dev/tcp/localhost/8000' 2>/dev/null || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "wiki_mcp_server.server"]
