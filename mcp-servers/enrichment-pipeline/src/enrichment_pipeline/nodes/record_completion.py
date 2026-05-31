"""Record enrichment completion in SQLite."""

import uuid

from ..db import EnrichmentRun, get_db, serialize_logs
from ..logger import StepTimer


def record_completion(state: dict) -> dict:
    """Persist enrichment run metadata and mark status completed."""
    document_id = state["document_id"]
    run_id = state.get("run_id") or str(uuid.uuid4())

    with StepTimer(state, "record_completion", document_id) as timer:
        db = get_db()
        try:
            total_duration = sum(
                e.get("duration_ms", 0) for e in state.get("log_entries", [])
            )
            run = EnrichmentRun(
                run_id=run_id,
                document_id=document_id,
                strategy=state.get("enrichment_strategy", "unknown"),
                status="completed" if state.get("enrichment_strategy") != "skip" else "skipped",
                llm_calls=state.get("llm_calls", 0),
                total_tokens=state.get("total_tokens", 0),
                duration_ms=total_duration,
                log_entries=serialize_logs(state.get("log_entries", [])),
            )
            db.add(run)
            db.commit()
            timer.extra["run_id"] = run_id
        except Exception as e:
            db.rollback()
            timer.extra["db_error"] = str(e)
        finally:
            db.close()

        state["status"] = "completed"
        state["run_id"] = run_id

    return state
