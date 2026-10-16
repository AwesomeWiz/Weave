"""
Weave — Graph persistence adapter interface.

Defines a clean boundary between the ingestion pipeline (source parsing,
validation, normalization, relationship resolution) and the actual graph
database (FalkorDB).

Two implementations are provided:

1. ``InMemoryGraphAdapter`` — for testing and standalone validation.
2. ``FalkorDBGraphAdapter`` — for real graph persistence (requires Antony's
   FalkorDB setup to be available).

When Antony's graph layer is ready, either:
  - Use ``FalkorDBGraphAdapter`` directly, or
  - Replace it with a thin wrapper that delegates to Antony's seed/query module.

The adapter contract:
  - ``upsert_node(entity_type, canonical_id, properties)``
  - ``upsert_relationship(source_id, rel_type, target_id, properties)``
  - ``upsert_chunk(chunk_id, properties)``
  - ``node_count()`` / ``relationship_count()`` / ``chunk_count()``
  - ``clear()``
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class GraphAdapter(ABC):
    """Abstract persistence interface for graph operations."""

    @abstractmethod
    def upsert_node(self, entity_type: str, canonical_id: str, properties: dict[str, Any]) -> None:
        """Create or update a node identified by canonical_id."""

    @abstractmethod
    def upsert_relationship(
        self, source_id: str, rel_type: str, target_id: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Create or update a relationship between two canonical IDs."""

    @abstractmethod
    def upsert_chunk(self, chunk_id: str, properties: dict[str, Any]) -> None:
        """Create or update a Chunk node."""

    @abstractmethod
    def node_count(self) -> int:
        """Return the total number of entity nodes."""

    @abstractmethod
    def relationship_count(self) -> int:
        """Return the total number of relationships."""

    @abstractmethod
    def chunk_count(self) -> int:
        """Return the total number of chunk nodes."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all data (dev/demo use only)."""

    @abstractmethod
    def get_chunks_for_sources(self, source_ids: list[str]) -> list[dict[str, Any]]:
        """Retrieve persisted Chunk properties and relationships for given source canonical IDs."""



# ---------------------------------------------------------------------------
# In-memory adapter (for testing / standalone)
# ---------------------------------------------------------------------------

class InMemoryGraphAdapter(GraphAdapter):
    """
    Dictionary-backed adapter for testing idempotency and ingestion logic
    without a running FalkorDB instance.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}          # id → {type, ...props}
        self._relationships: dict[str, dict[str, Any]] = {}  # stable_key → {src, rel, tgt, props}
        self._chunks: dict[str, dict[str, Any]] = {}         # id → props

    def upsert_node(self, entity_type: str, canonical_id: str, properties: dict[str, Any]) -> None:
        if not canonical_id or not str(canonical_id).strip():
            raise ValueError("canonical_id must be a non-empty string")
        self._nodes[canonical_id] = {"entity_type": entity_type, "id": canonical_id, **properties}

    def upsert_relationship(
        self, source_id: str, rel_type: str, target_id: str, properties: dict[str, Any] | None = None
    ) -> None:
        if source_id not in self._nodes or target_id not in self._nodes:
            missing = [nid for nid in (source_id, target_id) if nid not in self._nodes]
            raise ValueError(
                f"Cannot create relationship {source_id} -[:{rel_type}]-> {target_id}: "
                f"missing endpoint node(s) {missing}"
            )
        key = f"{source_id}|{rel_type}|{target_id}"
        self._relationships[key] = {
            "source_id": source_id,
            "rel_type": rel_type,
            "target_id": target_id,
            "properties": properties or {},
        }

    def upsert_chunk(self, chunk_id: str, properties: dict[str, Any]) -> None:
        if not chunk_id or not str(chunk_id).strip():
            raise ValueError("chunk_id must be a non-empty string")
        props = {"id": chunk_id, **properties}
        self._chunks[chunk_id] = props
        self._nodes[chunk_id] = {"entity_type": "Chunk", **props}

    def node_count(self) -> int:
        return sum(1 for n in self._nodes.values() if n.get("entity_type") != "Chunk")

    def relationship_count(self) -> int:
        return len(self._relationships)

    def chunk_count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._nodes.clear()
        self._relationships.clear()
        self._chunks.clear()

    # Inspection helpers (test-only)
    def get_node(self, canonical_id: str) -> dict[str, Any] | None:
        return self._nodes.get(canonical_id)

    def get_relationship(self, source_id: str, rel_type: str, target_id: str) -> dict[str, Any] | None:
        return self._relationships.get(f"{source_id}|{rel_type}|{target_id}")

    def all_nodes(self) -> dict[str, dict[str, Any]]:
        return dict(self._nodes)

    def all_relationships(self) -> dict[str, dict[str, Any]]:
        return dict(self._relationships)

    def get_chunks_for_sources(self, source_ids: list[str]) -> list[dict[str, Any]]:
        if not source_ids:
            return []
        source_set = set(source_ids)
        allowed_rels = {"FROM_ISSUE", "FROM_MESSAGE", "FROM_COMMIT", "FROM_DOCUMENT"}
        matching: list[dict[str, Any]] = []
        for rel in self._relationships.values():
            src_chunk_id = rel["source_id"]  # chunk id
            tgt_source_id = rel["target_id"]  # source id
            rel_type = rel["rel_type"]
            if tgt_source_id in source_set and rel_type in allowed_rels:
                chunk_props = self._chunks.get(src_chunk_id, {})
                matching.append({
                    "source_id": tgt_source_id,
                    "rel_type": rel_type,
                    "id": chunk_props.get("id", src_chunk_id),
                    "source_type": chunk_props.get("source_type", rel_type.replace("FROM_", "").capitalize()),
                    "chunk_index": chunk_props.get("chunk_index", 0),
                    "title": chunk_props.get("title", ""),
                    "text": chunk_props.get("text", ""),
                    "timestamp": chunk_props.get("timestamp"),
                    "url": chunk_props.get("url"),
                })
        matching.sort(key=lambda x: (x["chunk_index"], x["id"]))
        return matching



# ---------------------------------------------------------------------------
# FalkorDB adapter (integration-ready)
# ---------------------------------------------------------------------------

class FalkorDBGraphAdapter(GraphAdapter):
    """
    FalkorDB adapter using MERGE-based upserts for idempotent ingestion.

    Requires:
      - ``falkordb`` Python package
      - Environment variables: FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH

    This adapter is intentionally thin.  When Antony's graph layer is
    available, integrate through this interface or replace it.

    ASSUMPTION (for Antony):
      - The FalkorDB instance is running and accessible.
      - Node labels match EntityType values (Person, Service, Decision, …).
      - Canonical IDs are stored in a property called ``id``.
      - Relationships use the labels from relationships.py RELATIONSHIP_MAP.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        graph_name: str | None = None,
    ) -> None:
        try:
            from falkordb import FalkorDB as FalkorDBClient
        except ImportError:
            raise ImportError(
                "The 'falkordb' package is required for FalkorDBGraphAdapter. "
                "Install it with: pip install falkordb"
            )

        self._host = host or os.environ.get("FALKORDB_HOST", "localhost")
        self._port = port or int(os.environ.get("FALKORDB_PORT", "6379"))
        self._graph_name = graph_name or os.environ.get("FALKORDB_GRAPH", "novapay")

        self._client = FalkorDBClient(host=self._host, port=self._port)
        self._graph = self._client.select_graph(self._graph_name)

    def upsert_node(self, entity_type: str, canonical_id: str, properties: dict[str, Any]) -> None:
        if not canonical_id or not str(canonical_id).strip():
            raise ValueError("canonical_id must be a non-empty string")
        props = {k: v for k, v in properties.items() if v is not None}
        props["id"] = canonical_id
        set_clause = ", ".join(f"n.{k} = ${k}" for k in props)
        query = f"MERGE (n:{entity_type} {{id: $id}}) SET {set_clause}"
        self._graph.query(query, props)

    def upsert_relationship(
        self, source_id: str, rel_type: str, target_id: str, properties: dict[str, Any] | None = None
    ) -> None:
        props = properties or {}
        set_clause = ""
        param_props = {}
        if props:
            param_props = {f"prop_{k}": v for k, v in props.items() if v is not None}
            if param_props:
                set_clause = " SET " + ", ".join(f"r.{k} = $prop_{k}" for k in props if props[k] is not None)
        query = (
            f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b){set_clause} "
            f"RETURN a.id, b.id"
        )
        params = {"source_id": source_id, "target_id": target_id, **param_props}
        result = self._graph.query(query, params)
        if not getattr(result, "result_set", None):
            raise ValueError(
                f"Failed to upsert relationship {source_id} -[:{rel_type}]-> {target_id}: "
                f"one or both endpoints not found in graph."
            )

    def upsert_chunk(self, chunk_id: str, properties: dict[str, Any]) -> None:
        if not chunk_id or not str(chunk_id).strip():
            raise ValueError("chunk_id must be a non-empty string")
        props = {k: v for k, v in properties.items() if v is not None}
        props["id"] = chunk_id
        set_clause = ", ".join(f"n.{k} = ${k}" for k in props)
        query = f"MERGE (n:Chunk {{id: $id}}) SET {set_clause}"
        self._graph.query(query, props)

    def node_count(self) -> int:
        try:
            result = self._graph.query("MATCH (n) WHERE NOT n:Chunk RETURN count(n) AS c")
            return result.result_set[0][0]
        except Exception:
            result = self._graph.query("MATCH (n) RETURN count(n) AS c")
            return result.result_set[0][0]

    def relationship_count(self) -> int:
        result = self._graph.query("MATCH ()-[r]->() RETURN count(r) AS c")
        return result.result_set[0][0]

    def chunk_count(self) -> int:
        result = self._graph.query("MATCH (n:Chunk) RETURN count(n) AS c")
        return result.result_set[0][0]

    def clear(self) -> None:
        self._graph.query("MATCH (n) DETACH DELETE n")

    def get_chunks_for_sources(self, source_ids: list[str]) -> list[dict[str, Any]]:
        if not source_ids:
            return []
        query = (
            "MATCH (c:Chunk)-[r]->(s) "
            "WHERE s.id IN $source_ids AND type(r) IN ['FROM_ISSUE', 'FROM_MESSAGE', 'FROM_COMMIT', 'FROM_DOCUMENT'] "
            "RETURN s.id AS source_id, type(r) AS rel_type, c.id AS id, "
            "c.source_type AS source_type, c.chunk_index AS chunk_index, "
            "c.title AS title, c.text AS text, c.timestamp AS timestamp, c.url AS url "
            "ORDER BY c.chunk_index ASC"
        )
        result = self._graph.query(query, {"source_ids": source_ids})
        records: list[dict[str, Any]] = []
        if hasattr(result, "result_set") and result.result_set:
            cols = ["source_id", "rel_type", "id", "source_type", "chunk_index", "title", "text", "timestamp", "url"]
            for row in result.result_set:
                records.append(dict(zip(cols, row)))
        return records


