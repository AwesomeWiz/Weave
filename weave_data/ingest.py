"""
Weave — Ingestion pipeline orchestrator.

Executes the full ingestion pipeline:

  1. Load source files
  2. Validate schemas and references
  3. Normalize records and timestamps
  4. Build canonical ID registry
  5. Resolve all references
  6. Produce normalized entities and relationship operations
  7. Create text chunks
  8. Persist through the graph adapter
  9. Return ingestion statistics and errors

All steps are independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .chunks import generate_chunks
from .graph_adapter import FalkorDBGraphAdapter, GraphAdapter, InMemoryGraphAdapter
from .loader import load_aliases, load_adr_content, load_records
from .models import BaseRecord, ChunkRecord
from .relationships import RelationshipOp, extract_relationships
from .validation import ValidationResult, validate_dataset


# ---------------------------------------------------------------------------
# Ingestion result
# ---------------------------------------------------------------------------

@dataclass
class IngestionResult:
    status: str = "pending"
    records_processed: int = 0
    nodes_created_or_updated: int = 0
    relationships_processed: int = 0
    chunks_created_or_updated: int = 0
    errors: list[str] = field(default_factory=list)
    validation: ValidationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "records_processed": self.records_processed,
            "nodes_created_or_updated": self.nodes_created_or_updated,
            "relationships_processed": self.relationships_processed,
            "chunks_created_or_updated": self.chunks_created_or_updated,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_ingestion(
    data_dir: Path | None = None,
    adapter: GraphAdapter | None = None,
) -> IngestionResult:
    """
    Execute the full ingestion pipeline.

    Parameters
    ----------
    data_dir:
        Path to the NovaPay data directory.  Defaults to ``data/novapay/``.
    adapter:
        Graph persistence adapter. If None, uses FalkorDB. In-memory persistence
        must be explicitly supplied; database failure never selects it.

    Returns
    -------
    IngestionResult with counts and errors.
    """
    result = IngestionResult()

    # ------------------------------------------------------------------
    # 1. Load
    # ------------------------------------------------------------------
    try:
        records, source_file_map = load_records(data_dir)
        aliases = load_aliases(data_dir)
        adr_content = load_adr_content(data_dir)
    except Exception as exc:
        result.status = "failed"
        result.errors.append(f"Load error: {exc}")
        return result

    result.records_processed = len(records)

    # ------------------------------------------------------------------
    # 2. Validate
    # ------------------------------------------------------------------
    validation = validate_dataset(records, aliases, source_file_map)
    result.validation = validation

    if not validation.ok:
        result.status = "failed"
        result.errors = [str(e) for e in validation.errors]
        return result

    # ------------------------------------------------------------------
    # 3. Chunks
    # ------------------------------------------------------------------
    chunks = generate_chunks(records, adr_content)

    # ------------------------------------------------------------------
    # 4. Relationships (including chunk-to-source relationships)
    # ------------------------------------------------------------------
    rel_ops = extract_relationships(records, chunks=chunks)

    # ------------------------------------------------------------------
    # 5. Persist
    # ------------------------------------------------------------------
    try:
        if adapter is None:
            adapter = _create_adapter()
        _persist_nodes(adapter, records)
        result.nodes_created_or_updated = len(records)

        _persist_chunks(adapter, chunks)
        result.chunks_created_or_updated = len(chunks)

        _persist_relationships(adapter, rel_ops)
        result.relationships_processed = len(rel_ops)

        result.status = "success"
    except Exception as exc:
        result.status = "failed"
        result.errors.append(f"Persistence error: {exc}")

    return result


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _create_adapter(
    host: str | None = None,
    port: int | None = None,
    graph_name: str | None = None,
    *,
    in_memory: bool = False,
) -> GraphAdapter:
    """Memory is explicit. Configuration and connection failures propagate."""
    if in_memory:
        return InMemoryGraphAdapter()
    return FalkorDBGraphAdapter(host=host, port=port, graph_name=graph_name)


def _persist_nodes(adapter: GraphAdapter, records: list[BaseRecord]) -> None:
    for rec in records:
        props = rec.model_dump(mode="json")
        # Remove meta fields that are part of the schema, not node properties
        props.pop("entity_type", None)
        props.pop("source", None)
        # Convert datetime objects to ISO strings
        for key, val in list(props.items()):
            if val is None:
                props.pop(key)
        adapter.upsert_node(rec.entity_type.value, rec.id, props)


def _persist_relationships(adapter: GraphAdapter, rel_ops: list[RelationshipOp]) -> None:
    for op in rel_ops:
        adapter.upsert_relationship(op.source_id, op.rel_type, op.target_id, op.properties)


def _persist_chunks(adapter: GraphAdapter, chunks: list[ChunkRecord]) -> None:
    for chunk in chunks:
        props = chunk.model_dump(mode="json")
        for key, val in list(props.items()):
            if val is None:
                props.pop(key)
        adapter.upsert_chunk(chunk.id, props)


# ---------------------------------------------------------------------------
# Convenience: prepare-only (no persistence)
# ---------------------------------------------------------------------------

def prepare_ingestion(
    data_dir: Path | None = None,
) -> tuple[list[BaseRecord], list[RelationshipOp], list[ChunkRecord], dict[str, str], ValidationResult]:
    """
    Run the ingestion pipeline up to but NOT including persistence.

    Returns (records, relationship_ops, chunks, aliases, validation_result).

    Useful for Antony's integration: he can consume the prepared records
    and relationship ops directly.
    """
    records, source_file_map = load_records(data_dir)
    aliases = load_aliases(data_dir)
    adr_content = load_adr_content(data_dir)

    validation = validate_dataset(records, aliases, source_file_map)

    chunks = generate_chunks(records, adr_content)
    rel_ops = extract_relationships(records, chunks=chunks)

    return records, rel_ops, chunks, aliases, validation



# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="weave_data.ingest",
        description="Weave — Data & Ingestion pipeline for FalkorDB Company Brain",
    )
    parser.add_argument(
        "--in-memory", action="store_true",
        help="Explicit offline development run; does not persist to FalkorDB",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to the NovaPay data directory (default: data/novapay/)",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate and prepare records, relationships, and chunks without persisting to graph",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="FalkorDB host (default: env FALKORDB_HOST or localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="FalkorDB port (default: env FALKORDB_PORT or 6379)",
    )
    parser.add_argument(
        "--graph",
        default=None,
        help="FalkorDB graph name (default: env FALKORDB_GRAPH or novapay)",
    )

    args = parser.parse_args()

    if args.prepare_only:
        records, rel_ops, chunks, aliases, validation = prepare_ingestion(data_dir=args.data_dir)
        payload = {
            "mode": "prepare_only",
            "validation_passed": validation.ok,
            "validation_errors": [str(e) for e in validation.errors],
            "records_count": len(records),
            "relationships_count": len(rel_ops),
            "chunks_count": len(chunks),
            "aliases_count": len(aliases),
            "canonical_ids": [r.id for r in records],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("=" * 60)
            print(" Weave Ingestion Pipeline - Prepare-Only Mode")
            print("=" * 60)
            print(f"Validation:    {'[PASSED]' if validation.ok else '[FAILED]'}")
            if not validation.ok:
                for err in validation.errors:
                    print(f"  - Error: {err}")
            print(f"Entities:      {len(records)} canonical records")
            print(f"Relationships: {len(rel_ops)} edges extracted")
            print(f"Text Chunks:   {len(chunks)} retrieval chunks")
            print(f"Aliases:       {len(aliases)} alias mappings")
            print("=" * 60)
        return 0 if validation.ok else 1

    # Full ingestion run
    adapter = None
    try:
        adapter = _create_adapter(host=args.host, port=args.port, graph_name=args.graph,
                                  in_memory=args.in_memory)
        result = run_ingestion(data_dir=args.data_dir, adapter=adapter)
    except Exception:
        result = IngestionResult(status="failed", errors=[
            "FalkorDB adapter unavailable. Check database configuration; no in-memory fallback was used."
        ])

    if args.json:
        print(json.dumps({**result.to_dict(), "persistence": type(adapter).__name__ if adapter else "unavailable"}, indent=2))
    else:
        print("=" * 60)
        print(" Weave Ingestion Pipeline - Full Run")
        print("=" * 60)
        print(f"Status:        {result.status.upper()}")
        print(f"Nodes:         {result.nodes_created_or_updated}")
        print(f"Relationships: {result.relationships_processed}")
        print(f"Chunks:        {result.chunks_created_or_updated}")
        if result.errors:
            print("Errors:")
            for err in result.errors:
                print(f"  - {err}")
        print(f"Persistence:   {type(adapter).__name__ if adapter else 'unavailable'}")
        print("=" * 60)

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
