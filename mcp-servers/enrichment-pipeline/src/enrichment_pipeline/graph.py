"""LangGraph StateGraph for post-ingestion enrichment workflow."""

import logging
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from .nodes.chunk_enricher import enrich_chunks_heuristics
from .nodes.classifier import classify_document
from .nodes.pre_analysis import pre_enrichment_analysis, route_by_strategy
from .nodes.chunk_mapper import map_references_to_chunks
from .nodes.record_completion import record_completion
from .nodes.reference_extractor import extract_references
from .nodes.upsert import upsert_enriched_chunks

logger = logging.getLogger(__name__)


class EnrichmentState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    document_id: str
    source_file: str
    file_type: str
    collection: str
    chunks: List[Dict[str, Any]]
    enrichment_strategy: str
    classification: Optional[Dict[str, Any]]
    references: Optional[List[Dict[str, Any]]]
    enriched_chunks: Optional[List[Dict[str, Any]]]
    log_entries: List[Dict[str, Any]]
    llm_calls: int
    total_tokens: int
    status: str
    run_id: str


def route_after_classify(state: dict) -> str:
    """Route after classification: basic skips reference extraction."""
    if state.get("enrichment_strategy") == "basic":
        return "enrich"
    return "extract_refs"


def build_enrichment_graph():
    """Compile the enrichment LangGraph with conditional routing.

    Why LangGraph over LangChain chains:
    - Stateful multi-step workflow with branching (skip/basic/full/references_only)
    - Each node logs independently for industrial observability
    - Conditional edges map directly to enrichment strategies
    """
    workflow = StateGraph(EnrichmentState)

    workflow.add_node("pre_analysis", pre_enrichment_analysis)
    workflow.add_node("classify_document", classify_document)
    workflow.add_node("extract_references", extract_references)
    workflow.add_node("map_references", map_references_to_chunks)
    workflow.add_node("enrich_chunks", enrich_chunks_heuristics)
    workflow.add_node("upsert_enriched", upsert_enriched_chunks)
    workflow.add_node("record_completion", record_completion)

    workflow.set_entry_point("pre_analysis")

    workflow.add_conditional_edges(
        "pre_analysis",
        route_by_strategy,
        {
            "skip": "record_completion",
            "basic": "classify_document",
            "references_only": "extract_references",
            "full": "classify_document",
        },
    )

    workflow.add_conditional_edges(
        "classify_document",
        route_after_classify,
        {
            "enrich": "enrich_chunks",
            "extract_refs": "extract_references",
        },
    )

    workflow.add_edge("extract_references", "map_references")
    workflow.add_edge("map_references", "enrich_chunks")
    workflow.add_edge("enrich_chunks", "upsert_enriched")
    workflow.add_edge("upsert_enriched", "record_completion")
    workflow.add_edge("record_completion", END)

    return workflow.compile()


def run_enrichment(
    document_id: str,
    chunks: List[Dict[str, Any]],
    file_type: str = "unknown",
    source_file: str = "",
    collection: str = "documents",
) -> dict:
    """Execute the enrichment graph for one document."""
    graph = build_enrichment_graph()
    initial_state: EnrichmentState = {
        "document_id": document_id,
        "source_file": source_file,
        "file_type": file_type,
        "collection": collection,
        "chunks": chunks,
        "log_entries": [],
        "llm_calls": 0,
        "total_tokens": 0,
        "status": "pending",
        "run_id": str(uuid.uuid4()),
    }
    return graph.invoke(initial_state)
