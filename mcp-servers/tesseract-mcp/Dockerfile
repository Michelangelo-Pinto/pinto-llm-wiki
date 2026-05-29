FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ita \
    libtesseract-dev libleptonica-dev \
    libgl1-mesa-glx libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    fastmcp>=3.0.0 \
    pytesseract>=0.3.10 \
    PyMuPDF>=1.24.0 \
    Pillow>=10.0.0 \
    opencv-python-headless>=4.9.0
RUN useradd -m -u 1000 mcp && mkdir -p /data /app && chown -R mcp:mcp /data /app
WORKDIR /app
COPY src/ /app/src/
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8003
ENV PYTHONPATH=/app/src
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV PYTHONUNBUFFERED=1
USER mcp
CMD ["python", "-m", "tesseract_mcp.server"]
