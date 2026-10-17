"""
Weave — Explicit relationship mapping from source fields to graph edges.

This module defines the documented mapping from normalized source record
fields to FalkorDB graph relationships (edges).  Each mapping specifies:
  - source entity type
  - source field name
  - relationship type (Cypher relationship label)
  - target entity type(s)
  - direction

The relationship operations produced here are database-agnostic: they are
dicts describing (source_id, rel_type, target_id, properties) tuples that
can be consumed by any graph adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import (
    BaseRecord,
    CommitRecord,
    DecisionRecord,
    EntityType,
    IncidentRecord,
    IssueRecord,
    MessageRecord,
    PersonRecord,
    RepositoryRecord,
    ServiceRecord,
    TeamRecord,
)


# ---------------------------------------------------------------------------
# Relationship operation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RelationshipOp:
    """
    A single graph-relationship operation.

    source_id / target_id are canonical IDs.
    rel_type is the Cypher relationship label (e.g. "LED_TO").
    properties is an optional dict attached to the relationship.
    """
    source_id: str
    rel_type: str
    target_id: str
    properties: dict[str, Any] | None = None

    @property
    def stable_key(self) -> str:
        """Deterministic key for idempotency."""
        return f"{self.source_id}|{self.rel_type}|{self.target_id}"


# ---------------------------------------------------------------------------
# Documented mapping table
#
# Format: (source_entity_type, source_field) → (rel_type, direction)
#
# direction:
#   "forward"  → source_record  -[rel_type]-> referenced_entity
#   "reverse"  → referenced_entity -[rel_type]-> source_record
#
# The ontology directions follow docs/04_KNOWLEDGE_GRAPH.md §3.
# ---------------------------------------------------------------------------

RELATIONSHIP_MAP: list[dict[str, str]] = [
    # Incident
    {"entity": "Incident", "field": "related_issues",    "rel": "LED_TO",            "dir": "forward"},
    {"entity": "Incident", "field": "affected_services",  "rel": "AFFECTS",           "dir": "forward"},

    # Issue
    {"entity": "Issue",    "field": "affected_services",  "rel": "AFFECTS",           "dir": "forward"},
    {"entity": "Issue",    "field": "related_incidents",  "rel": "LED_TO",            "dir": "reverse"},
    {"entity": "Issue",    "field": "assignee",           "rel": "ASSIGNED_TO",       "dir": "forward"},

    # Decision
    {"entity": "Decision", "field": "affects",            "rel": "AFFECTS",           "dir": "forward"},
    {"entity": "Decision", "field": "introduces",         "rel": "INTRODUCES",        "dir": "forward"},
    {"entity": "Decision", "field": "participants",       "rel": "PARTICIPATED_IN",   "dir": "reverse"},
    {"entity": "Decision", "field": "approved_by",        "rel": "APPROVED",          "dir": "reverse"},
    {"entity": "Decision", "field": "supported_by",       "rel": "SUPPORTED_BY",      "dir": "forward"},
    {"entity": "Decision", "field": "implemented_by",     "rel": "IMPLEMENTED_BY",    "dir": "forward"},
    {"entity": "Decision", "field": "documented_in",      "rel": "DOCUMENTED_IN",     "dir": "forward"},

    # Commit
    {"entity": "Commit",   "field": "repository",         "rel": "BELONGS_TO",        "dir": "forward"},
    {"entity": "Commit",   "field": "changes",            "rel": "CHANGES",           "dir": "forward"},
    {"entity": "Commit",   "field": "author",             "rel": "AUTHORED",          "dir": "reverse"},
    {"entity": "Commit",   "field": "implements_decision","rel": "IMPLEMENTS_DECISION","dir": "forward"},
    {"entity": "Commit",   "field": "addresses",          "rel": "ADDRESSES",         "dir": "forward"},

    # Repository
    {"entity": "Repository","field": "service",           "rel": "IMPLEMENTS",        "dir": "forward"},

    # Service
    {"entity": "Service",  "field": "technologies",       "rel": "USES",              "dir": "forward"},
    {"entity": "Service",  "field": "depends_on",         "rel": "DEPENDS_ON",        "dir": "forward"},

    # Team
    {"entity": "Team",     "field": "members",            "rel": "MEMBER_OF",         "dir": "reverse"},
    {"entity": "Team",     "field": "owns_services",      "rel": "OWNS",              "dir": "forward"},

    # Person
    {"entity": "Person",   "field": "team",               "rel": "MEMBER_OF",         "dir": "forward"},

    # Message
    {"entity": "Message",  "field": "participants",       "rel": "WROTE",             "dir": "reverse"},

    # Document
    {"entity": "Document", "field": "describes",          "rel": "DESCRIBES",         "dir": "forward"},
]


# ---------------------------------------------------------------------------
# Relationship extraction
# ---------------------------------------------------------------------------

def extract_relationships(
    records: list[BaseRecord],
    chunks: list[Any] | None = None,
) -> list[RelationshipOp]:
    """
    Walk all records (and optional chunks) and produce a deduplicated list of RelationshipOps.

    Returns a stable-sorted list of relationship operations keyed by
    (source_id, rel_type, target_id).
    """
    seen: set[str] = set()
    ops: list[RelationshipOp] = []

    # Build a fast lookup: entity_type_name → list of mapping entries
    mapping_index: dict[str, list[dict[str, str]]] = {}
    for m in RELATIONSHIP_MAP:
        mapping_index.setdefault(m["entity"], []).append(m)

    for rec in records:
        entity_name = rec.entity_type.value
        mappings = mapping_index.get(entity_name, [])

        rec_dict = rec.model_dump()

        for m in mappings:
            field_name = m["field"]
            value = rec_dict.get(field_name)
            if value is None:
                continue

            # Normalize to list
            refs: list[str] = [value] if isinstance(value, str) else value
            refs = [r for r in refs if isinstance(r, str) and ":" in r]

            rel_type = m["rel"]
            direction = m["dir"]

            for ref_id in refs:
                if direction == "forward":
                    source_id = rec.id
                    target_id = ref_id
                elif direction == "reverse":
                    source_id = ref_id
                    target_id = rec.id
                else:
                    continue

                op = RelationshipOp(source_id=source_id, rel_type=rel_type, target_id=target_id)
                if op.stable_key not in seen:
                    seen.add(op.stable_key)
                    ops.append(op)

    # Process chunk relationships if chunks provided
    if chunks:
        chunk_rel_map = {
            "Issue": "FROM_ISSUE",
            "Message": "FROM_MESSAGE",
            "Commit": "FROM_COMMIT",
            "Document": "FROM_DOCUMENT",
        }
        for chunk in chunks:
            rel_type = chunk_rel_map.get(chunk.source_type, f"FROM_{chunk.source_type.upper()}")
            op = RelationshipOp(
                source_id=chunk.id,
                rel_type=rel_type,
                target_id=chunk.source_id,
            )
            if op.stable_key not in seen:
                seen.add(op.stable_key)
                ops.append(op)

    # Stable sort for determinism
    ops.sort(key=lambda o: o.stable_key)
    return ops

