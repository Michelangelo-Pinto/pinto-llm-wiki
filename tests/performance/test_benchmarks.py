"""Performance benchmarks for v3 services.

All benchmarks run inside the test-runner Docker container against the
running stack. Uses pytest-benchmark for accurate timing.

Targets (guidelines, not hard failures):
- OCR: single page < 3s, 5 pages < 15s
- Qdrant search: < 50ms single, < 200ms concurrent
- Embedding: < 100ms single, < 2s batch of 50
- Chunking: < 100ms for 10k chars
"""

import json
import os
from pathlib import Path

import pytest

TEST_DATA = Path("/data/test-data")
TEST_COLLECTION = "test_benchmarks"


@pytest.fixture(scope="session")
def bench_qdrant_url():
    return os.environ.get("QDRANT_URL", "http://qdrant-db:6334")


@pytest.fixture(scope="session", autouse=True)
def setup_bench_collection(bench_qdrant_url):
    """Ensure benchmark collection exists and is populated."""
    from qdrant_client import QdrantClient, models

    client = QdrantClient(url=bench_qdrant_url)
    try:
        client.create_collection(
            collection_name=TEST_COLLECTION,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            on_disk_payload=True,
        )
    except Exception:
        pass

    # Populate with 50 synthetic chunks for search benchmarks
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [
        f"Benchmark test document chunk number {i}. "
        f"This contains sample text about vector databases, semantic search, "
        f"and retrieval augmented generation for performance testing."
        for i in range(50)
    ]
    embeddings = model.encode(texts, normalize_embeddings=True)
    points = []
    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        points.append(models.PointStruct(
            id=i,
            vector=emb.tolist(),
            payload={"chunk_index": i, "text": text},
        ))
    client.upsert(collection_name=TEST_COLLECTION, points=points)
    yield
    try:
        client.delete_collection(collection_name=TEST_COLLECTION)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Qdrant Benchmarks
# ---------------------------------------------------------------------------


class TestQdrantLatency:
    def test_qdrant_search_single(self, bench_qdrant_url, benchmark):
        """Single Qdrant search query latency."""
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        client = QdrantClient(url=bench_qdrant_url)
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_vec = model.encode("vector database performance benchmarking", normalize_embeddings=True).tolist()

        def search():
            client.query_points(
                collection_name=TEST_COLLECTION,
                query=query_vec,
                limit=10,
            )

        benchmark(search)
        # Target: < 50ms

    def test_qdrant_collection_info(self, bench_qdrant_url, benchmark):
        """Benchmark collection info retrieval."""
        from qdrant_client import QdrantClient
        client = QdrantClient(url=bench_qdrant_url)

        def get_info():
            client.get_collection(TEST_COLLECTION)

        benchmark(get_info)

    @pytest.mark.benchmark(min_rounds=5)
    def test_qdrant_scroll_100(self, bench_qdrant_url, benchmark):
        """Benchmark scrolling 100 points."""
        from qdrant_client import QdrantClient
        client = QdrantClient(url=bench_qdrant_url)

        def scroll():
            client.scroll(collection_name=TEST_COLLECTION, limit=100)

        benchmark(scroll)


# ---------------------------------------------------------------------------
# Embedding Benchmarks
# ---------------------------------------------------------------------------


class TestEmbeddingLatency:
    def test_embedding_single_text(self, benchmark):
        """Single text embedding latency."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")

        def embed_single():
            model.encode("A single sentence for embedding performance testing.", normalize_embeddings=True)

        benchmark(embed_single)
        # Target: < 100ms (cold start excluded in rounds)

    def test_embedding_batch_50(self, benchmark):
        """Batch embedding 50 texts."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts = [
            f"Document chunk number {i} with enough text content to be a realistic "
            f"representation of what the ingestion pipeline actually processes."
            for i in range(50)
        ]

        def embed_batch():
            model.encode(texts, normalize_embeddings=True)

        benchmark(embed_batch)
        # Target: < 2s


# ---------------------------------------------------------------------------
# Chunking Benchmarks
# ---------------------------------------------------------------------------


class TestChunkingLatency:
    def test_chunking_10k_chars(self, benchmark):
        """Chunking a 10k character document."""
        from ingestion_pipeline.chunker import chunk_document

        text = (
            "This is a sample document about software engineering. "
            "It contains multiple sentences that will be chunked into smaller pieces. "
            * 100  # ~10k chars
        )

        def chunk():
            chunk_document(text, source_type="text")

        benchmark(chunk)
        # Target: < 100ms


# ---------------------------------------------------------------------------
# Ingestion Pipeline Benchmarks
# ---------------------------------------------------------------------------


class TestIngestionLatency:
    def test_ingest_single_text_file(self, benchmark):
        """Benchmark full ingestion of a single text file."""
        from ingestion_pipeline.tools import ingest_document

        test_file = TEST_DATA / "text" / "test.txt"
        if not test_file.exists():
            pytest.skip("Test data not found")

        def ingest():
            ingest_document(str(test_file), collection=TEST_COLLECTION, force=True)

        benchmark(ingest)
        # Target: < 5s for a single file
