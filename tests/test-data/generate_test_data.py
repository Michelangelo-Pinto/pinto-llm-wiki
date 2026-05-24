#!/usr/bin/env python3
"""Generate test documents for E2E and integration testing.

Creates: text PDF, scanned-like PDF, text DOCX, DOCX with embedded image,
markdown, plain text, and an image with text. All files are deterministic
and self-contained.
"""

import os
import sys
from pathlib import Path

# Ensure we can import required libraries (may need pip install)
BASE_DIR = Path(__file__).parent


def generate_text_pdf(output_path: str):
    """Generate a multi-page text-based PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open()
    
    # Page 1: Title and intro
    page1 = doc.new_page()
    page1.insert_text(fitz.Point(72, 72), "Test Document: Vector Databases", fontsize=18, fontname="helv")
    page1.insert_text(fitz.Point(72, 110), "A Technical Overview for Wiki Integration", fontsize=14, fontname="helv")
    page1.insert_text(fitz.Point(72, 160), "Abstract", fontsize=13, fontname="helv")
    
    abstract = (
        "Vector databases enable semantic search by storing numerical representations "
        "of documents called embeddings. These embeddings capture the semantic meaning "
        "of text, allowing retrieval based on conceptual similarity rather than exact "
        "keyword matching. This technology powers modern search engines, recommendation "
        "systems, and Retrieval-Augmented Generation (RAG) pipelines."
    )
    page1.insert_text(fitz.Point(72, 185), abstract, fontsize=11, fontname="helv")
    
    page1.insert_text(fitz.Point(72, 270), "Introduction", fontsize=13, fontname="helv")
    intro = (
        "Traditional search relies on keyword matching, which fails when users express "
        "concepts differently than authors. For example, a search for 'automobile' would "
        "miss documents about 'cars' even though they refer to the same concept.\n\n"
        "Vector databases solve this by converting text into high-dimensional vectors "
        "using embedding models. Similar concepts cluster together in vector space, "
        "enabling retrieval based on semantic proximity."
    )
    page1.insert_text(fitz.Point(72, 295), intro, fontsize=11, fontname="helv")

    # Page 2: Technical details
    page2 = doc.new_page()
    page2.insert_text(fitz.Point(72, 72), "Embedding Models", fontsize=13, fontname="helv")
    
    models_text = (
        "Popular embedding models include:\n\n"
        "1. all-MiniLM-L6-v2 (384 dimensions, 80MB)\n"
        "   A lightweight model by Sentence-Transformers, ideal for CPU deployment.\n"
        "   Produces 384-dimensional vectors with good semantic accuracy.\n\n"
        "2. text-embedding-3-small (1536 dimensions)\n"
        "   OpenAI's embedding model, API-based, higher accuracy but requires\n"
        "   network access and has per-token costs.\n\n"
        "3. bge-large-en-v1.5 (1024 dimensions)\n"
        "   BAAI's general-purpose embedding model, strong performance on MTEB\n"
        "   benchmarks, requires GPU for reasonable throughput."
    )
    page2.insert_text(fitz.Point(72, 100), models_text, fontsize=11, fontname="helv")

    page2.insert_text(fitz.Point(72, 400), "Indexing Strategies", fontsize=13, fontname="helv")
    indexing = (
        "Vector databases use approximate nearest neighbor (ANN) algorithms to "
        "efficiently search through millions of vectors. Common algorithms include:\n\n"
        "- HNSW (Hierarchical Navigable Small World): Graph-based, provides excellent\n"
        "  recall with logarithmic search complexity.\n"
        "- IVF (Inverted File Index): Clusters vectors into partitions, searches\n"
        "  only the most relevant clusters.\n"
        "- PQ (Product Quantization): Compresses vectors for memory efficiency\n"
        "  at the cost of some accuracy."
    )
    page2.insert_text(fitz.Point(72, 430), indexing, fontsize=11, fontname="helv")

    # Page 3: Practical applications
    page3 = doc.new_page()
    page3.insert_text(fitz.Point(72, 72), "Practical Applications", fontsize=13, fontname="helv")
    
    applications = (
        "1. Semantic Document Search\n"
        "   Replace keyword-based search with meaning-based retrieval. Users can\n"
        "   ask natural language questions and find relevant documents.\n\n"
        "2. Retrieval-Augmented Generation (RAG)\n"
        "   Augment LLM responses with relevant context retrieved from a vector\n"
        "   database, reducing hallucinations and grounding answers in facts.\n\n"
        "3. Recommendation Systems\n"
        "   Find similar items based on their vector representations. Used by\n"
        "   e-commerce platforms, streaming services, and social networks.\n\n"
        "4. Anomaly Detection\n"
        "   Detect unusual patterns by comparing new vectors against historical\n"
        "   clusters in vector space."
    )
    page3.insert_text(fitz.Point(72, 100), applications, fontsize=11, fontname="helv")

    page3.insert_text(fitz.Point(72, 400), "Conclusion", fontsize=13, fontname="helv")
    conclusion = (
        "Vector databases represent a fundamental shift in how we store and retrieve "
        "information. By operating on semantic meaning rather than surface-level "
        "keywords, they enable more intuitive and powerful search experiences. "
        "When combined with modern embedding models, they form the backbone of "
        "next-generation AI applications."
    )
    page3.insert_text(fitz.Point(72, 430), conclusion, fontsize=11, fontname="helv")

    doc.save(output_path)
    doc.close()
    print(f"Created text PDF: {output_path}")


def generate_scanned_like_pdf(output_path: str):
    """Generate a PDF page that simulates a scanned document by rendering text as an image.

    This creates a PDF where the page is an embedded image (like a scan),
    which requires OCR to extract text.
    """
    from PIL import Image, ImageDraw, ImageFont
    import fitz

    # Create an image with text (simulating a scanned page)
    img = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(img)

    # Try to use a system font, fall back to default
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.text((100, 80), "Company Annual Report 2025", fill="black", font=font_title)
    draw.text((100, 140), "Confidential - For Internal Use Only", fill="black", font=font_body)

    # Draw body text
    body_lines = [
        "Executive Summary",
        "",
        "This report summarizes the company's performance during the fiscal year 2025.",
        "Revenue grew by 15% year-over-year, reaching $450 million. Operating margins",
        "improved from 12% to 18% due to cost optimization initiatives implemented",
        "in Q2 2025.",
        "",
        "Key Highlights:",
        "- Launched three new product lines in the enterprise segment",
        "- Expanded operations to five new international markets",
        "- Achieved carbon neutrality across all data centers",
        "- Hired 500 new engineering staff members",
        "",
        "Financial Overview:",
        "Revenue: $450M (up 15% YoY)",
        "Operating Income: $81M (up 35% YoY)",
        "Net Income: $62M (up 28% YoY)",
        "EPS: $2.45 (up 22% YoY)",
        "",
        "The board of directors recommends a dividend of $0.85 per share,",
        "representing a 10% increase from the previous year.",
        "",
        "Prepared by: Finance Department",
        "Date: January 15, 2026",
    ]

    y = 200
    for line in body_lines:
        if line.startswith("-") or line.startswith("Revenue:") or line.startswith("Operating") or line.startswith("Net") or line.startswith("EPS"):
            draw.text((120, y), line, fill="black", font=font_body)
        elif line == "":
            pass  # skip empty lines
        else:
            draw.text((100, y), line, fill="black", font=font_body)
        y += 35

    # Save image temporarily
    img_path = str(Path(output_path).with_suffix(".png"))
    img.save(img_path)

    # Embed image in PDF
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
    page.insert_image(rect, filename=img_path)
    doc.save(output_path)
    doc.close()

    # Clean up temp image
    os.remove(img_path)
    print(f"Created scanned-like PDF: {output_path}")


def generate_text_docx(output_path: str):
    """Generate a text-only DOCX file."""
    from docx import Document

    doc = Document()
    doc.add_heading("Machine Learning Pipeline Documentation", level=1)

    doc.add_heading("Overview", level=2)
    doc.add_paragraph(
        "This document describes the machine learning pipeline architecture used "
        "for model training, evaluation, and deployment. The pipeline follows a "
        "modular design pattern that separates data ingestion, feature engineering, "
        "model training, and serving into independent components."
    )

    doc.add_heading("Data Ingestion Layer", level=2)
    doc.add_paragraph(
        "The data ingestion layer is responsible for reading raw data from various "
        "sources including PostgreSQL databases, Apache Kafka streams, and S3-compatible "
        "object storage. Data is validated against schema definitions before being "
        "passed to the feature engineering layer."
    )

    doc.add_heading("Feature Engineering", level=2)
    doc.add_paragraph(
        "Feature engineering transforms raw data into model-ready features through:"
    )
    features = [
        "Numerical scaling using StandardScaler or MinMaxScaler",
        "Categorical encoding via OneHotEncoder or TargetEncoder",
        "Text vectorization using TF-IDF or sentence embeddings",
        "Time-based feature extraction (day-of-week, month, quarter)",
        "Missing value imputation using median or model-based approaches",
    ]
    for f in features:
        doc.add_paragraph(f, style="List Bullet")

    doc.add_heading("Model Training", level=2)
    doc.add_paragraph(
        "The training module supports multiple model types organized by task:\n\n"
        "Classification: RandomForest, XGBoost, LightGBM, LogisticRegression\n"
        "Regression: LinearRegression, GradientBoosting, NeuralNetwork\n"
        "Clustering: KMeans, DBSCAN, HierarchicalClustering\n\n"
        "All models implement a common interface with fit(), predict(), and "
        "evaluate() methods. Hyperparameter optimization is performed using "
        "Optuna with Bayesian sampling."
    )

    doc.add_heading("Deployment Strategy", level=2)
    doc.add_paragraph(
        "Models are deployed as Docker containers behind a REST API. Each model "
        "version is tagged with a semantic version (e.g., v1.2.3) and stored in "
        "a model registry. The serving layer supports A/B testing by routing a "
        "configurable percentage of traffic to different model versions."
    )

    doc.save(output_path)
    print(f"Created text DOCX: {output_path}")


def generate_docx_with_images(output_path: str):
    """Generate a DOCX with text and an embedded image."""
    from docx import Document
    from docx.shared import Inches
    from PIL import Image, ImageDraw

    doc = Document()
    doc.add_heading("Network Architecture Diagram", level=1)
    
    doc.add_paragraph(
        "The following diagram illustrates the microservices architecture deployed "
        "across three availability zones. Each service communicates via gRPC with "
        "TLS mutual authentication."
    )

    # Create a simple diagram image
    img = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(img)
    
    # Draw boxes representing services
    services = [
        (50, 150, "API Gateway"),
        (250, 80, "Auth Service"),
        (250, 220, "User Service"),
        (450, 150, "Database"),
        (650, 80, "Cache (Redis)"),
        (650, 220, "Message Queue"),
    ]
    
    for x, y, name in services:
        draw.rectangle([x, y, x + 140, y + 50], outline="black", width=2)
        # Center text approximately
        draw.text((x + 10, y + 15), name, fill="black")

    # Draw arrows
    draw.line([(190, 175), (250, 105)], fill="black", width=2)
    draw.line([(190, 175), (250, 245)], fill="black", width=2)
    draw.line([(390, 105), (450, 175)], fill="black", width=2)
    draw.line([(390, 245), (450, 175)], fill="black", width=2)
    draw.line([(590, 175), (650, 105)], fill="black", width=2)
    draw.line([(590, 175), (650, 245)], fill="black", width=2)

    img_path = str(Path(output_path).parent / "temp_architecture.png")
    img.save(img_path)
    doc.add_picture(img_path, width=Inches(5))
    os.remove(img_path)

    doc.add_heading("Service Descriptions", level=2)
    
    doc.add_paragraph("API Gateway", style="List Bullet")
    doc.add_paragraph(
        "Routes external requests to internal services. Handles rate limiting, "
        "request validation, and response caching. Implemented with Envoy Proxy."
    )
    
    doc.add_paragraph("Auth Service", style="List Bullet")
    doc.add_paragraph(
        "Manages user authentication and authorization. Issues JWT tokens with "
        "configurable expiration. Integrates with OAuth2 providers including "
        "Google, GitHub, and Okta."
    )

    doc.add_paragraph("User Service", style="List Bullet")
    doc.add_paragraph(
        "Core user management: registration, profile updates, preferences storage. "
        "Emits events to message queue for downstream consumers (analytics, "
        "email notifications, audit logging)."
    )

    doc.save(output_path)
    print(f"Created DOCX with images: {output_path}")


def generate_markdown(output_path: str):
    """Generate a markdown file."""
    content = """# Software Engineering Best Practices

## Code Review Guidelines

### Before Submitting
- [ ] All tests pass locally
- [ ] No commented-out code
- [ ] No debug logging statements
- [ ] Documentation updated for public API changes

### During Review
- Focus on logic errors, not formatting (let the linter handle that)
- Verify edge cases are handled (null inputs, empty collections, timeouts)
- Check that error messages are actionable
- Ensure new code has corresponding tests

## Testing Strategy

### Test Pyramid
```
      /\\
     /E2E\\
    /------\\
   /Integration\\
  /------------\\
 /  Unit Tests   \\
/________________\\
```

1. **Unit Tests**: Test individual functions in isolation. Fast, reliable, many.
2. **Integration Tests**: Test interactions between modules. Moderate speed.
3. **E2E Tests**: Test complete user workflows. Slow, brittle, few.

### Test Naming Convention
```
test_<unit>_<scenario>_<expected_behavior>
```

Examples:
- `test_user_create_with_valid_email_returns_201`
- `test_user_create_with_duplicate_email_returns_409`
- `test_search_empty_query_returns_400`

## Git Workflow

### Branch Naming
- `feature/<ticket-id>-<short-description>`
- `fix/<ticket-id>-<short-description>`
- `chore/<short-description>`

### Commit Messages
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: feat, fix, docs, style, refactor, test, chore

## Docker Best Practices

1. Use multi-stage builds to minimize image size
2. Never run as root inside containers
3. Use specific version tags, not `latest`
4. One process per container
5. Store persistent data in volumes, not container filesystem
6. Use `.dockerignore` to exclude unnecessary files
"""
    Path(output_path).write_text(content)
    print(f"Created markdown: {output_path}")


def generate_text_file(output_path: str):
    """Generate a plain text file."""
    content = """SYSTEM CONFIGURATION REFERENCE
===============================

Database Configuration
---------------------
Host: db.internal.example.com
Port: 5432
Database: production_main
Pool Size: 20
Connection Timeout: 30s
SSL Mode: require

Cache Configuration
-------------------
Type: Redis Cluster
Nodes: redis-1:6379, redis-2:6379, redis-3:6379
Max Memory: 4GB per node
Eviction Policy: allkeys-lru
Connection Pool: 50

Logging Configuration
---------------------
Level: INFO
Format: JSON
Output: stdout + /var/log/app/app.log
Rotation: Daily, keep 30 days

API Configuration
-----------------
Rate Limit: 1000 requests/minute
Max Request Size: 10MB
CORS Origins: https://app.example.com, https://admin.example.com
Authentication: JWT Bearer Token
Token Expiry: 3600 seconds

Monitoring
----------
Health Check: GET /health (every 30s)
Metrics: Prometheus endpoint at :9090/metrics
Alerts: PagerDuty integration for ERROR-level logs
Tracing: Jaeger with 1% sampling rate

This document is auto-generated. Do not edit manually.
Last updated: 2026-05-23T14:30:00Z
"""
    Path(output_path).write_text(content)
    print(f"Created text file: {output_path}")


def generate_image_with_text(output_path: str):
    """Generate a PNG image with text that OCR should recognize."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except (OSError, IOError):
        font = ImageFont.load_default()

    lines = [
        "INVOICE #2026-0042",
        "Date: May 15, 2026",
        "Due Date: June 15, 2026",
        "",
        "Bill To:",
        "Acme Corporation",
        "123 Main Street",
        "San Francisco, CA 94105",
        "",
        "Description                    Qty    Unit Price    Total",
        "-------------------------------------------------------",
        "Cloud Storage (AWS S3)         500GB    $0.023/GB    $11.50",
        "Compute (EC2 t3.medium)        720hrs   $0.042/hr     $30.24",
        "Database (RDS PostgreSQL)      30days   $0.50/day     $15.00",
        "Load Balancer                  1unit    $18.00/mo     $18.00",
        "-------------------------------------------------------",
        "                                    Subtotal:          $74.74",
        "                                    Tax (8.5%):        $6.35",
        "                                    Total Due:         $81.09",
        "",
        "Payment Terms: Net 30",
        "Please include invoice number with payment.",
    ]

    y = 20
    for line in lines:
        draw.text((30, y), line, fill="black", font=font)
        y += 24

    img.save(output_path)
    print(f"Created image with text: {output_path}")


def main():
    """Generate all test documents."""
    os.makedirs(BASE_DIR / "pdf", exist_ok=True)
    os.makedirs(BASE_DIR / "docx", exist_ok=True)
    os.makedirs(BASE_DIR / "markdown", exist_ok=True)
    os.makedirs(BASE_DIR / "text", exist_ok=True)
    os.makedirs(BASE_DIR / "images", exist_ok=True)
    os.makedirs(BASE_DIR / "mixed", exist_ok=True)

    generate_text_pdf(str(BASE_DIR / "pdf" / "test_text.pdf"))
    generate_scanned_like_pdf(str(BASE_DIR / "pdf" / "test_scanned.pdf"))
    generate_text_docx(str(BASE_DIR / "docx" / "test_text.docx"))
    generate_docx_with_images(str(BASE_DIR / "docx" / "test_with_images.docx"))
    generate_markdown(str(BASE_DIR / "markdown" / "test.md"))
    generate_text_file(str(BASE_DIR / "text" / "test.txt"))
    generate_image_with_text(str(BASE_DIR / "images" / "test_scan.png"))

    # Mixed directory for batch testing: copy markdown and text files
    import shutil
    shutil.copy(BASE_DIR / "markdown" / "test.md", BASE_DIR / "mixed" / "readme.md")
    shutil.copy(BASE_DIR / "text" / "test.txt", BASE_DIR / "mixed" / "config.txt")

    print("\nAll test documents generated successfully!")
    print(f"Files are in: {BASE_DIR}")
    print("\nTo use with Docker, mount this directory at /data/test-data")


if __name__ == "__main__":
    main()
