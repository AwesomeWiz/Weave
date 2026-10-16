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
    ("github/repositories.json", EntityType.Repository),
    ("github/commits.json", EntityType.Commit),
    ("jira/issues.json", EntityType.Issue),
    ("slack/messages.json", EntityType.Message),
]


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

    # ADR-7 as a Document record (if the markdown exists)
    adr_path = base / "docs" / "ADR-7.md"
    if adr_path.exists():
        doc_rec = DocumentRecord(
            id="doc:ADR-7",
            source="docs",
            entity_type=EntityType.Document,
            title="ADR-7: Redis Caching for Payment Service",
            doc_type="ADR",
            content=adr_path.read_text(encoding="utf-8"),
            updated_at="2026-05-20T10:00:00Z",
            url="https://docs.novapay.example/adrs/ADR-7",
        )
        records.append(doc_rec)
        source_file_map[doc_rec.id] = "docs/ADR-7.md"

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
