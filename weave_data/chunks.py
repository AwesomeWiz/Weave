"""
Weave — Source chunk generation.

Creates retrieval-ready text chunks from source records.  Each chunk
preserves provenance (source_id, source_type, chunk_index, title, text,
timestamp).

One chunk per short source is sufficient for the hackathon dataset.
Embeddings are not generated here.
"""

from __future__ import annotations

from .models import (
    BaseRecord,
    ChunkRecord,
    CommitRecord,
    DocumentRecord,
    IssueRecord,
    MessageRecord,
)
from .relationships import RelationshipOp


def generate_chunks(
    records: list[BaseRecord],
    adr_content: str | None = None,
) -> list[ChunkRecord]:
    """
    Generate retrieval chunks for text-bearing source records.

    Parameters
    ----------
    records:
        All parsed entity records.
    adr_content:
        Optional raw markdown content of ADR-7.  If provided, a chunk is
        created for it even though Document records may not carry inline
        content in the JSON files.
    """
    chunks: list[ChunkRecord] = []

    for rec in records:
        if isinstance(rec, IssueRecord) and rec.description:
            chunks.append(ChunkRecord(
                id=f"chunk:{rec.id}:0",
                source_id=rec.id,
                source_type="Issue",
                chunk_index=0,
                title=rec.title,
                text=rec.description,
                timestamp=rec.created_at,
                url=rec.url,
            ))

        elif isinstance(rec, MessageRecord):
            chunks.append(ChunkRecord(
                id=f"chunk:{rec.id}:0",
                source_id=rec.id,
                source_type="Message",
                chunk_index=0,
                title=f"Thread: {rec.thread_id or rec.channel or rec.id}",
                text=rec.text,
                timestamp=rec.timestamp,
                url=rec.url,
            ))

        elif isinstance(rec, CommitRecord):
            chunks.append(ChunkRecord(
                id=f"chunk:{rec.id}:0",
                source_id=rec.id,
                source_type="Commit",
                chunk_index=0,
                title=rec.message.split("\n", 1)[0],
                text=rec.message,
                timestamp=rec.timestamp,
                url=rec.url,
            ))

        elif isinstance(rec, DocumentRecord):
            text = (adr_content if rec.id == "doc:ADR-7" and adr_content else rec.content)
            if text:
                chunks.append(ChunkRecord(
                    id=f"chunk:{rec.id}:0",
                    source_id=rec.id,
                    source_type="Document",
                    chunk_index=0,
                    title=rec.title,
                    text=text,
                    timestamp=rec.updated_at,
                    url=rec.url,
                ))

    # Stable sort by chunk ID
    chunks.sort(key=lambda c: c.id)
    return chunks


def extract_chunk_relationships(chunks: list[ChunkRecord]) -> list[RelationshipOp]:
    """
    Produce directed graph relationships linking Chunk nodes to their source nodes:
      (Chunk)-[:FROM_ISSUE]->(Issue)
      (Chunk)-[:FROM_MESSAGE]->(Message)
      (Chunk)-[:FROM_COMMIT]->(Commit)
      (Chunk)-[:FROM_DOCUMENT]->(Document)
    """
    rel_map = {
        "Issue": "FROM_ISSUE",
        "Message": "FROM_MESSAGE",
        "Commit": "FROM_COMMIT",
        "Document": "FROM_DOCUMENT",
    }
    ops: list[RelationshipOp] = []
    for chunk in chunks:
        rel_type = rel_map.get(chunk.source_type, f"FROM_{chunk.source_type.upper()}")
        ops.append(RelationshipOp(
            source_id=chunk.id,
            rel_type=rel_type,
            target_id=chunk.source_id,
        ))
    ops.sort(key=lambda o: o.stable_key)
    return ops

