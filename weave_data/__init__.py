"""Weave — Data & Ingestion Package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chunks import extract_chunk_relationships, generate_chunks
    from .graph_adapter import FalkorDBGraphAdapter, GraphAdapter, InMemoryGraphAdapter
    from .ingest import IngestionResult, prepare_ingestion, run_ingestion
    from .loader import load_adr_content, load_aliases, load_records
    from .models import (
        BaseRecord,
        ChunkRecord,
        CommitRecord,
        DecisionRecord,
        DocumentRecord,
        EntityType,
        IncidentRecord,
        IssueRecord,
        MessageRecord,
        PersonRecord,
        RepositoryRecord,
        ServiceRecord,
        TeamRecord,
        TechnologyRecord,
    )
    from .relationships import RelationshipOp, extract_relationships
    from .retrieval import SourceRecord, find_sources
    from .validation import ValidationError, ValidationResult, validate_dataset

_EXPORTS = {
    "generate_chunks": ".chunks",
    "extract_chunk_relationships": ".chunks",
    "FalkorDBGraphAdapter": ".graph_adapter",
    "GraphAdapter": ".graph_adapter",
    "InMemoryGraphAdapter": ".graph_adapter",
    "IngestionResult": ".ingest",
    "prepare_ingestion": ".ingest",
    "run_ingestion": ".ingest",
    "load_adr_content": ".loader",
    "load_aliases": ".loader",
    "load_records": ".loader",
    "BaseRecord": ".models",
    "ChunkRecord": ".models",
    "CommitRecord": ".models",
    "DecisionRecord": ".models",
    "DocumentRecord": ".models",
    "EntityType": ".models",
    "IncidentRecord": ".models",
    "IssueRecord": ".models",
    "MessageRecord": ".models",
    "PersonRecord": ".models",
    "RepositoryRecord": ".models",
    "ServiceRecord": ".models",
    "TeamRecord": ".models",
    "TechnologyRecord": ".models",
    "RelationshipOp": ".relationships",
    "extract_relationships": ".relationships",
    "SourceRecord": ".retrieval",
    "find_sources": ".retrieval",
    "ValidationError": ".validation",
    "ValidationResult": ".validation",
    "validate_dataset": ".validation",
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    if name in _EXPORTS:
        import importlib
        module = importlib.import_module(_EXPORTS[name], __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
