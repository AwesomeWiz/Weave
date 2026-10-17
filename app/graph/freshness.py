"""Evidence-backed knowledge freshness review candidates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .client import GraphClient

ENTITY_CAP = 2
DOCUMENT_CAP = 50
EVENT_CAP = 50
CHUNK_CAP = 100


def find_stale_knowledge(client: GraphClient, entity: str) -> dict[str, Any]:
    """Find documents that may merit review after later changes to a service.

    A review candidate is not a claim that documentation is wrong. It is a
    document with a comparable ``updated_at`` timestamp older than an accepted
    decision, architecture-changing commit, or incident affecting the same
    persisted Service node.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    warnings: list[str] = []

    def response(
        resolved_entity: dict[str, Any] | None,
        review_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "data": {
                "entity": resolved_entity,
                "review_candidates": review_candidates,
            },
            "sources": sources,
            "nodes": nodes,
            "edges": edges,
            "warnings": warnings,
        }

    if not isinstance(entity, str) or not entity.strip():
        warnings.append("entity must be a non-empty string.")
        return response(None, [])

    def properties(node: Any) -> dict[str, Any]:
        return dict(node.properties)

    def node_label(node: Any) -> str:
        labels = node.labels
        return labels[0] if labels else "Unknown"

    def relationship_type(relationship: Any) -> str | None:
        return (
            getattr(relationship, "relation", None)
            or getattr(relationship, "type", None)
            or dict(relationship.properties).get("type")
        )

    def add_node(node: Any) -> dict[str, Any] | None:
        props = properties(node)
        node_id = props.get("id")
        if not node_id:
            return None
        item = {
            "id": node_id,
            "type": node_label(node),
            "label": props.get("title", props.get("name", node_id)),
            "properties": props,
        }
        if not any(existing["id"] == node_id for existing in nodes):
            nodes.append(item)
        return item

    def add_edge(source_node: Any, relationship: Any, target_node: Any) -> None:
        source = add_node(source_node)
        target = add_node(target_node)
        rel_type = relationship_type(relationship)
        if source is None or target is None or not rel_type:
            return
        edge_id = f"{source['id']}|{rel_type}|{target['id']}"
        if any(existing["id"] == edge_id for existing in edges):
            return
        edges.append(
            {
                "id": edge_id,
                "source": source["id"],
                "target": target["id"],
                "type": rel_type,
                "properties": dict(relationship.properties),
            }
        )

    def warn_if_capped(result: Any, cap: int, query_name: str) -> None:
        if len(result.result_set) >= cap:
            warnings.append(
                f"{query_name} may be incomplete because the query reached its "
                f"cap of {cap} rows."
            )

    def parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    entity_result = client.execute(
        """
        MATCH (entity)
        WHERE entity.id = $entity
           OR toLower(coalesce(entity.name, '')) = $normalized_entity
           OR toLower(coalesce(entity.title, '')) = $normalized_entity
        RETURN entity
        ORDER BY entity.id
        LIMIT 2
        """,
        {"entity": entity.strip(), "normalized_entity": entity.casefold().strip()},
    )
    warn_if_capped(entity_result, ENTITY_CAP, "Entity resolution")
    resolved = [add_node(row[0]) for row in entity_result.result_set]
    resolved = [item for item in resolved if item is not None]
    if not resolved:
        warnings.append(f"No graph entity found for {entity.strip()}.")
        return response(None, [])
    if len(resolved) > 1:
        warnings.append(
            "Entity resolution is ambiguous: "
            + ", ".join(sorted(item["id"] for item in resolved))
        )
        return response(None, [])
    resolved_entity = resolved[0]
    if resolved_entity["type"] != "Service":
        warnings.append("Knowledge freshness currently supports Service entities only.")
        return response(resolved_entity, [])

    service_id = resolved_entity["id"]
    document_paths: dict[str, dict[str, Any]] = {}

    describes_result = client.execute(
        """
        MATCH (document:Document)-[relationship:DESCRIBES]->(service:Service {id: $service_id})
        RETURN document, relationship, service
        ORDER BY document.id
        LIMIT 50
        """,
        {"service_id": service_id},
    )
    warn_if_capped(describes_result, DOCUMENT_CAP, "Document discovery")
    for document_node, relationship, service_node in describes_result.result_set:
        add_edge(document_node, relationship, service_node)
        document = add_node(document_node)
        if document:
            document_paths[document["id"]] = {
                "document": document,
                "service_id": service_id,
                "path": [
                    {
                        "source": document["id"],
                        "type": "DESCRIBES",
                        "target": service_id,
                    }
                ],
            }

    documented_result = client.execute(
        """
        MATCH (decision:Decision)-[documented:DOCUMENTED_IN]->(document:Document)
        MATCH (decision)-[affects:AFFECTS]->(service:Service {id: $service_id})
        RETURN decision, documented, document, affects, service
        ORDER BY document.id, decision.id
        LIMIT 50
        """,
        {"service_id": service_id},
    )
    warn_if_capped(documented_result, DOCUMENT_CAP, "Decision documentation discovery")
    for (
        decision_node,
        documented,
        document_node,
        affects,
        service_node,
    ) in documented_result.result_set:
        add_edge(decision_node, documented, document_node)
        add_edge(decision_node, affects, service_node)
        document = add_node(document_node)
        decision = add_node(decision_node)
        if document and decision:
            document_paths.setdefault(
                document["id"],
                {
                    "document": document,
                    "service_id": service_id,
                    "path": [
                        {
                            "source": decision["id"],
                            "type": "DOCUMENTED_IN",
                            "target": document["id"],
                        },
                        {
                            "source": decision["id"],
                            "type": "AFFECTS",
                            "target": service_id,
                        },
                    ],
                },
            )

    if not document_paths:
        warnings.append(
            "No documents were found describing or documenting this service."
        )
        return response(resolved_entity, [])

    event_rows: list[tuple[str, Any, list[dict[str, str]]]] = []
    decision_result = client.execute(
        """
        MATCH (decision:Decision {status: 'accepted'})-[relationship:AFFECTS]->(service:Service {id: $service_id})
        RETURN decision, relationship, service
        ORDER BY decision.decided_at, decision.id
        LIMIT 50
        """,
        {"service_id": service_id},
    )
    warn_if_capped(decision_result, EVENT_CAP, "Decision retrieval")
    for decision_node, relationship, service_node in decision_result.result_set:
        add_edge(decision_node, relationship, service_node)
        decision = add_node(decision_node)
        if decision:
            event_rows.append(
                (
                    "decision",
                    decision,
                    [
                        {
                            "source": decision["id"],
                            "type": "AFFECTS",
                            "target": service_id,
                        }
                    ],
                )
            )

    commit_result = client.execute(
        """
        MATCH (commit:Commit {architecture_change: true})-[relationship:CHANGES]->(service:Service {id: $service_id})
        RETURN commit, relationship, service
        ORDER BY commit.timestamp, commit.id
        LIMIT 50
        """,
        {"service_id": service_id},
    )
    warn_if_capped(commit_result, EVENT_CAP, "Architecture-changing commit retrieval")
    for commit_node, relationship, service_node in commit_result.result_set:
        add_edge(commit_node, relationship, service_node)
        commit = add_node(commit_node)
        if commit:
            event_rows.append(
                (
                    "commit",
                    commit,
                    [{"source": commit["id"], "type": "CHANGES", "target": service_id}],
                )
            )

    incident_result = client.execute(
        """
        MATCH (incident:Incident)-[relationship:AFFECTS]->(service:Service {id: $service_id})
        RETURN incident, relationship, service
        ORDER BY incident.started_at, incident.id
        LIMIT 50
        """,
        {"service_id": service_id},
    )
    warn_if_capped(incident_result, EVENT_CAP, "Incident retrieval")
    for incident_node, relationship, service_node in incident_result.result_set:
        add_edge(incident_node, relationship, service_node)
        incident = add_node(incident_node)
        if incident:
            event_rows.append(
                (
                    "incident",
                    incident,
                    [
                        {
                            "source": incident["id"],
                            "type": "AFFECTS",
                            "target": service_id,
                        }
                    ],
                )
            )

    timestamp_fields = {
        "decision": "decided_at",
        "commit": "timestamp",
        "incident": "started_at",
    }
    candidates: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for document_id, document_item in sorted(document_paths.items()):
        document = document_item["document"]
        updated_at = document["properties"].get("updated_at")
        document_time = parse_timestamp(updated_at)
        if document_time is None:
            warnings.append(
                f"Document {document_id} has no comparable updated_at timestamp."
            )
            continue
        triggers: list[dict[str, Any]] = []
        for event_type, event, event_path in event_rows:
            timestamp_field = timestamp_fields[event_type]
            event_timestamp = event["properties"].get(timestamp_field)
            event_time = parse_timestamp(event_timestamp)
            if event_time is None:
                warnings.append(
                    f"{event_type.capitalize()} {event['id']} has no comparable "
                    f"{timestamp_field} timestamp."
                )
                continue
            if event_time <= document_time:
                continue
            trigger = {
                "type": event_type,
                "id": event["id"],
                "timestamp": event_timestamp,
                "affected_entity_id": service_id,
                "path": event_path,
            }
            triggers.append(trigger)
            # Current ingestion defines chunk provenance for commits and
            # documents, but not Decisions or Incidents. Keep graph-only
            # event evidence rather than claiming unavailable chunks exist.
            if event_type == "commit":
                source_ids.add(event["id"])
        if triggers:
            triggers.sort(key=lambda item: (item["timestamp"], item["id"]))
            source_ids.add(document_id)
            candidates.append(
                {
                    "document": document,
                    "document_id": document_id,
                    "updated_at": updated_at,
                    "affected_entity_id": service_id,
                    "document_path": document_item["path"],
                    "triggers": triggers,
                    "reason": "Later graph-linked changes affect the same service; review may be warranted.",
                }
            )

    if source_ids:
        chunk_result = client.execute(
            """
            MATCH (chunk:Chunk)-[relationship]->(source)
            WHERE source.id IN $source_ids
              AND type(relationship) IN ['FROM_ISSUE', 'FROM_MESSAGE', 'FROM_COMMIT', 'FROM_DOCUMENT']
            RETURN chunk, relationship, source
            ORDER BY source.id, chunk.id
            LIMIT 100
            """,
            {"source_ids": sorted(source_ids)},
        )
        warn_if_capped(chunk_result, CHUNK_CAP, "Evidence provenance retrieval")
        returned_source_ids: set[str] = set()
        for chunk_node, relationship, source_node in chunk_result.result_set:
            add_edge(chunk_node, relationship, source_node)
            chunk = properties(chunk_node)
            source = properties(source_node)
            chunk_id, source_id = chunk.get("id"), source.get("id")
            if chunk_id and source_id:
                returned_source_ids.add(source_id)
                if not any(item["chunk_id"] == chunk_id for item in sources):
                    sources.append(
                        {
                            "id": source_id,
                            "chunk_id": chunk_id,
                            "title": chunk.get("title"),
                            "text": chunk.get("text"),
                            "url": chunk.get("url"),
                        }
                    )
        missing_provenance = source_ids - returned_source_ids
        if missing_provenance:
            warnings.append(
                "Missing provenance chunks for freshness evidence: "
                + ", ".join(sorted(missing_provenance))
            )

    if not candidates:
        warnings.append("No later comparable change events require document review.")
    return response(resolved_entity, candidates)
