"""
Weave — Exact Source Retrieval Interface.

Provides deterministic source resolution by canonical source ID, returning
structured evidence directly from dataset/graph chunks and canonical records.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

from .chunks import generate_chunks
from .graph_adapter import GraphAdapter
from .loader import load_adr_content, load_records
from .models import BaseRecord, ChunkRecord


class SourceRecord(BaseModel):
    """
    Retrieved source evidence record.

    Attributes
    ----------
    id:
        Canonical entity ID (e.g., 'issue:PAY-42', 'doc:ADR-7').
    type:
        Entity/source type (e.g., 'Issue', 'Document', 'Commit', 'Message').
    title:
        Human-readable title of the source.
    snippet:
        Verbatim text snippet from stored chunks (never fabricated).
    url:
        Optional web URL for the source if available.
    chunk_ids:
        List of contributing chunk IDs for this source.
    """
    id: str
    type: str
    title: str
    snippet: str
    url: Optional[str] = None
    chunk_ids: list[str] = Field(default_factory=list)


def find_sources(
    source_ids: Iterable[str] | None,
    data_dir: Path | None = None,
    chunks: list[ChunkRecord] | None = None,
    records: list[BaseRecord] | None = None,
    adapter: GraphAdapter | None = None,
) -> list[SourceRecord]:
    """
    Deterministic retrieval interface resolving canonical source IDs to structured evidence.

    Supports both local-data mode (default) and graph-backed mode (when adapter is provided).

    Parameters
    ----------
    source_ids:
        Iterable of canonical entity IDs (e.g., ['issue:PAY-42', 'doc:ADR-7']).
    data_dir:
        Optional path to NovaPay data directory.
    chunks:
        Optional pre-generated list of ChunkRecord objects.
    records:
        Optional pre-loaded list of BaseRecord objects.
    adapter:
        Optional GraphAdapter instance (InMemoryGraphAdapter or FalkorDBGraphAdapter).
        When provided, queries persisted Chunk nodes and their FROM_* relationships directly.

    Returns
    -------
    list[SourceRecord]:
        Deduplicated source records matching the requested IDs.
        Returns [] if source_ids is empty or no requested IDs exist.
    """
    if not source_ids:
        return []

    # Clean and deduplicate source_ids while preserving order
    cleaned_ids: list[str] = []
    seen_ids: set[str] = set()
    for sid in source_ids:
        if not sid or not isinstance(sid, str):
            continue
        sid_clean = sid.strip()
        if not sid_clean or sid_clean in seen_ids:
            continue
        seen_ids.add(sid_clean)
        cleaned_ids.append(sid_clean)

    if not cleaned_ids:
        return []

    # ------------------------------------------------------------------
    # 1. Graph-backed mode (when adapter is supplied)
    # ------------------------------------------------------------------
    if adapter is not None:
        # An explicitly supplied adapter is authoritative.  In particular, do
        # not catch an adapter/query failure and substitute local files: that
        # could return stale or unrelated evidence in a deployed service.
        retrieved = adapter.get_chunks_for_sources(cleaned_ids)
        chunks_by_source: dict[str, list[dict[str, Any]]] = {}
        for c in retrieved:
            chunks_by_source.setdefault(c["source_id"], []).append(c)

        results: list[SourceRecord] = []
        for sid in cleaned_ids:
            source_chunks = chunks_by_source.get(sid, [])
            if not source_chunks:
                continue

            sorted_chunks = sorted(source_chunks, key=lambda c: (c.get("chunk_index", 0), c.get("id", "")))
            chunk_ids = [c["id"] for c in sorted_chunks]
            snippet = "\n\n".join(c["text"].strip() for c in sorted_chunks if c.get("text"))
            first_chunk = sorted_chunks[0]

            results.append(SourceRecord(
                id=sid,
                type=first_chunk.get("source_type", ""),
                title=first_chunk.get("title", sid),
                snippet=snippet,
                url=first_chunk.get("url"),
                chunk_ids=chunk_ids,
            ))
        return results

    # ------------------------------------------------------------------
    # 2. Local fallback mode (when adapter is None)
    # ------------------------------------------------------------------
    if chunks is None or records is None:
        rec_list, _ = load_records(data_dir)
        adr_content = load_adr_content(data_dir)
        chk_list = generate_chunks(rec_list, adr_content)
    else:
        rec_list = records
        chk_list = chunks

    # Build index of chunks by source_id: source_id -> list[ChunkRecord]
    chunks_by_source_local: dict[str, list[ChunkRecord]] = {}
    for chk in chk_list:
        chunks_by_source_local.setdefault(chk.source_id, []).append(chk)

    # Build index of records by id: id -> BaseRecord
    records_by_id: dict[str, BaseRecord] = {r.id: r for r in rec_list}

    results = []

    for sid_clean in cleaned_ids:
        source_chunks_local = chunks_by_source_local.get(sid_clean, [])
        source_rec = records_by_id.get(sid_clean)

        # Only return evidence if stored in the dataset/chunks
        if not source_chunks_local and not source_rec:
            continue

        # Extract type, title, and url
        source_type = ""
        title = ""
        url = None

        if source_chunks_local:
            source_type = source_chunks_local[0].source_type
            title = source_chunks_local[0].title or sid_clean
            url = source_chunks_local[0].url
        elif source_rec:
            source_type = source_rec.entity_type.value
            title = getattr(source_rec, "title", None) or getattr(source_rec, "name", None) or sid_clean
            url = getattr(source_rec, "url", None)

        # Combine text snippets from all contributing chunks
        if source_chunks_local:
            sorted_chunks_local = sorted(source_chunks_local, key=lambda c: (c.chunk_index, c.id))
            chunk_ids = [c.id for c in sorted_chunks_local]
            snippet = "\n\n".join(c.text.strip() for c in sorted_chunks_local if c.text)
        else:
            chunk_ids = []
            snippet = getattr(source_rec, "summary", None) or getattr(source_rec, "description", None) or ""

        results.append(SourceRecord(
            id=sid_clean,
            type=source_type,
            title=title,
            snippet=snippet,
            url=url,
            chunk_ids=chunk_ids,
        ))

    return results
