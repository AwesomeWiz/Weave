"""
Weave — Dataset loader.

Loads the NovaPay source files from disk, parses them into typed Pydantic
records, and reads associated assets (ADR-7 markdown, aliases).

This module handles only *loading and parsing*.  Validation, relationship
extraction, chunk generation, and persistence are in separate modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    BaseRecord,
    ChunkRecord,
    CommitRecord,
    DecisionRecord,
    DocumentRecord,
    ENTITY_MODEL_MAP,
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


# ---------------------------------------------------------------------------
# File layout
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "novapay"

# Mapping: relative path → entity_type
_FILE_ENTITY_MAP: list[tuple[str, EntityType]] = [
    ("people.json", EntityType.Person),
    ("teams.json", EntityType.Team),
    ("services.json", EntityType.Service),
    ("technologies.json", EntityType.Technology),
    ("incidents.json", EntityType.Incident),
    ("decisions.json", EntityType.Decision),
    ("documents.json", EntityType.Document),
    ("github/repositories.json", EntityType.Repository),
    ("github/commits.json", EntityType.Commit),
    ("jira/issues.json", EntityType.Issue),
    ("slack/messages.json", EntityType.Message),
]

_DOCS_METADATA: dict[str, dict[str, Any]] = {
    "ADR-7.md": {
        "id": "doc:ADR-7",
        "title": "ADR-7: Redis Caching for Payment Service",
        "doc_type": "ADR",
        "updated_at": "2026-05-20T10:00:00Z",
        "url": "https://docs.novapay.example/adrs/ADR-7",
        "describes": ["service:payment-service"],
    },
    "architecture-overview.md": {
        "id": "doc:architecture-overview",
        "title": "NovaPay Core Architecture Overview",
        "doc_type": "architecture",
        "updated_at": "2026-05-01T12:00:00Z",
        "url": "https://docs.novapay.example/architecture/overview",
        "describes": ["service:payment-service"],
    },
    "runbook-payment-latency.md": {
        "id": "doc:runbook-payment-latency",
        "title": "Runbook: Payment Service Latency & Degradation",
        "doc_type": "runbook",
        "updated_at": "2026-05-22T10:00:00Z",
        "url": "https://docs.novapay.example/runbooks/payment-latency",
        "describes": ["service:payment-service"],
    },
}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_records(data_dir: Path | None = None) -> tuple[list[BaseRecord], dict[str, str]]:
    """
    Load all source records and return (records, source_file_map).

    source_file_map maps record ID → source filename for error reporting.
    """
    base = data_dir or DEFAULT_DATA_DIR
    records: list[BaseRecord] = []
    source_file_map: dict[str, str] = {}
    loaded_ids: set[str] = set()

    for rel_path, entity_type in _FILE_ENTITY_MAP:
        fpath = base / rel_path
        if not fpath.exists():
            continue
        raw: list[dict[str, Any]] = json.loads(fpath.read_text(encoding="utf-8"))
        model_cls = ENTITY_MODEL_MAP[entity_type]
        for item in raw:
            rec = model_cls.model_validate(item)
            records.append(rec)
            source_file_map[rec.id] = rel_path
            loaded_ids.add(rec.id)

    # Documents from docs/ directory (markdown assets)
    docs_dir = base / "docs"
    if docs_dir.exists():
        for doc_filename, meta in _DOCS_METADATA.items():
            doc_path = docs_dir / doc_filename
            if doc_path.exists() and meta["id"] not in loaded_ids:
                doc_rec = DocumentRecord(
                    id=meta["id"],
                    source="docs",
                    entity_type=EntityType.Document,
                    title=meta["title"],
                    doc_type=meta.get("doc_type"),
                    content=doc_path.read_text(encoding="utf-8"),
                    updated_at=meta.get("updated_at"),
                    url=meta.get("url"),
                    describes=meta.get("describes", []),
                )
                records.append(doc_rec)
                source_file_map[doc_rec.id] = f"docs/{doc_filename}"
                loaded_ids.add(doc_rec.id)

    return records, source_file_map


def load_aliases(data_dir: Path | None = None) -> dict[str, str]:
    """Load the alias map from aliases.json."""
    base = data_dir or DEFAULT_DATA_DIR
    alias_path = base / "aliases.json"
    if not alias_path.exists():
        return {}
    return json.loads(alias_path.read_text(encoding="utf-8"))


def load_adr_content(data_dir: Path | None = None) -> str | None:
    """Load raw ADR-7 markdown content for chunk generation."""
    base = data_dir or DEFAULT_DATA_DIR
    adr_path = base / "docs" / "ADR-7.md"
    if not adr_path.exists():
        return None
    return adr_path.read_text(encoding="utf-8")
