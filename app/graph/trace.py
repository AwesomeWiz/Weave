from typing import Any

from .client import GraphClient


def trace_decision(
    client: GraphClient,
    service_id: str = "service:payment-service",
    technology_id: str = "tech:redis",
) -> dict[str, Any]:
    """
    Trace an accepted decision connecting a service to a technology.

    Returns decision details, graph nodes and directed edges, supporting
    evidence, canonical source IDs, and chunk provenance.

    All returned relationships are retrieved from the persisted graph.
    No synthetic relationships are created.
    """

    def node_properties(node: Any) -> dict[str, Any]:
        """Convert a FalkorDB node into a JSON-friendly dictionary."""
        return dict(node.properties)

    def node_type(node: Any) -> str:
        """Return the node's graph label."""
        labels = node.labels
        return labels[0] if labels else "Unknown"

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    evidence_nodes: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Find the decision connecting the requested service and technology.
    # ------------------------------------------------------------------
    result = client.execute(
        """
        MATCH (d:Decision)-[:AFFECTS]->(s:Service {id: $service_id})
        MATCH (d)-[:INTRODUCES]->(t:Technology {id: $technology_id})
        RETURN d, s, t
        """,
        {
            "service_id": service_id,
            "technology_id": technology_id,
        },
    )

    if not result.result_set:
        return {
            "data": {
                "decision": None,
                "decision_status": None,
                "rationale": None,
            },
            "sources": [],
            "nodes": [],
            "edges": [],
            "warnings": [
                "No decision found for the requested service and technology."
            ],
        }

    decision_node, service_node, technology_node = result.result_set[0]

    decision = node_properties(decision_node)
    service = node_properties(service_node)
    technology = node_properties(technology_node)

    decision_id = decision.get("id")

    if not decision_id:
        return {
            "data": {
                "decision": decision,
                "decision_status": decision.get("status"),
                "rationale": decision.get("summary"),
            },
            "sources": [],
            "nodes": [],
            "edges": [],
            "warnings": ["The decision node has no canonical ID."],
        }

    # ------------------------------------------------------------------
    # 2. Add the primary decision, service, and technology nodes.
    # ------------------------------------------------------------------
    for entity_type, properties in (
        ("Decision", decision),
        ("Service", service),
        ("Technology", technology),
    ):
        entity_id = properties.get("id")

        nodes.append(
            {
                "id": entity_id,
                "type": entity_type,
                "label": properties.get(
                    "title",
                    properties.get("name", entity_id),
                ),
                "properties": properties,
            }
        )

    # These relationships were matched in the first query.
    edges.extend(
        [
            {
                "id": f"{decision_id}|AFFECTS|{service['id']}",
                "source": decision_id,
                "target": service["id"],
                "type": "AFFECTS",
                "properties": {},
            },
            {
                "id": f"{decision_id}|INTRODUCES|{technology['id']}",
                "source": decision_id,
                "target": technology["id"],
                "type": "INTRODUCES",
                "properties": {},
            },
        ]
    )

    # ------------------------------------------------------------------
    # 3. Retrieve actual additional graph paths.
    # ------------------------------------------------------------------
    # Payment Service -> Redis.
    uses_result = client.execute(
        """
        MATCH (s:Service {id: $service_id})
              -[r:USES]->
              (t:Technology {id: $technology_id})
        RETURN s, r, t
        """,
        {
            "service_id": service_id,
            "technology_id": technology_id,
        },
    )

    if uses_result.result_set:
        for source_node, relationship, target_node in uses_result.result_set:
            source = node_properties(source_node)
            target = node_properties(target_node)

            edges.append(
                {
                    "id": (
                        f"{source['id']}|USES|{target['id']}"
                    ),
                    "source": source["id"],
                    "target": target["id"],
                    "type": "USES",
                    "properties": dict(relationship.properties),
                }
            )
    else:
        warnings.append(
            f"Missing USES relationship from {service_id} to {technology_id}."
        )

    # Incident INC-17 -> Issue PAY-42.
    # Preserve this as a real persisted edge, not an inferred relationship.
    incident_id = "incident:INC-17"
    issue_id = "issue:PAY-42"

    incident_result = client.execute(
        """
        MATCH (i:Incident {id: $incident_id})
              -[r:LED_TO]->
              (issue:Issue {id: $issue_id})
        RETURN i, r, issue
        """,
        {
            "incident_id": incident_id,
            "issue_id": issue_id,
        },
    )

    if incident_result.result_set:
        for incident_node, relationship, issue_node in incident_result.result_set:
            incident = node_properties(incident_node)
            issue = node_properties(issue_node)

            nodes.append(
                {
                    "id": incident["id"],
                    "type": "Incident",
                    "label": incident.get("title", incident["id"]),
                    "properties": incident,
                }
            )

            edges.append(
                {
                    "id": f"{incident['id']}|LED_TO|{issue['id']}",
                    "source": incident["id"],
                    "target": issue["id"],
                    "type": "LED_TO",
                    "properties": dict(relationship.properties),
                }
            )
    else:
        warnings.append(
            f"Missing LED_TO relationship from {incident_id} to {issue_id}."
        )

    # ------------------------------------------------------------------
    # 4. Retrieve the decision's actual supporting graph relationships.
    # ------------------------------------------------------------------
    evidence_result = client.execute(
        """
        MATCH (d:Decision {id: $decision_id})-[r]->(e)
        WHERE type(r) IN [
            'SUPPORTED_BY',
            'IMPLEMENTED_BY',
            'DOCUMENTED_IN'
        ]
        RETURN type(r), e
        ORDER BY type(r), e.id
        """,
        {"decision_id": decision_id},
    )

    source_ids: list[str] = []

    for relationship_type, evidence_node in evidence_result.result_set:
        properties = node_properties(evidence_node)
        evidence_id = properties.get("id")

        if not evidence_id:
            warnings.append(
                f"Found a {relationship_type} target without a canonical ID."
            )
            continue

        evidence_type = node_type(evidence_node)

        nodes.append(
            {
                "id": evidence_id,
                "type": evidence_type,
                "label": properties.get(
                    "title",
                    properties.get("name", evidence_id),
                ),
                "properties": properties,
            }
        )

        edges.append(
            {
                "id": f"{decision_id}|{relationship_type}|{evidence_id}",
                "source": decision_id,
                "target": evidence_id,
                "type": relationship_type,
                "properties": {},
            }
        )

        source_ids.append(evidence_id)

        evidence_nodes.append(
            {
                "id": evidence_id,
                "type": evidence_type,
                "relationship": relationship_type,
                "properties": properties,
            }
        )

    # ------------------------------------------------------------------
    # 5. Check rationale provenance against the retrieved source paths.
    # ------------------------------------------------------------------
    # These are the sources required by the current Phase 1 scenario.
    # This is a validation check, not a substitute for graph retrieval.
    required_rationale_sources = {
        "issue:PAY-42",
        "message:payment-perf-7",
        "doc:ADR-7",
    }

    linked_source_ids = set(source_ids)

    missing_rationale_sources = (
        required_rationale_sources - linked_source_ids
    )

    if missing_rationale_sources:
        warnings.append(
            "Missing decision rationale relationships for: "
            + ", ".join(sorted(missing_rationale_sources))
        )

    # ------------------------------------------------------------------
    # 6. Retrieve chunks through actual Chunk -> Source relationships.
    # ------------------------------------------------------------------
    if source_ids:
        chunk_result = client.execute(
            """
            MATCH (c:Chunk)-[r]->(source)
            WHERE source.id IN $source_ids
              AND type(r) IN [
                  'FROM_ISSUE',
                  'FROM_MESSAGE',
                  'FROM_COMMIT',
                  'FROM_DOCUMENT'
              ]
            RETURN c, type(r), source.id
            ORDER BY source.id, c.id
            """,
            {"source_ids": source_ids},
        )

        for chunk_node, relationship_type, source_id in chunk_result.result_set:
            properties = node_properties(chunk_node)
            chunk_id = properties.get("id")

            if not chunk_id:
                warnings.append(
                    f"Found a chunk linked to {source_id} without a canonical ID."
                )
                continue

            chunks.append(
                {
                    "id": chunk_id,
                    "source_id": source_id,
                    "relationship": relationship_type,
                    "title": properties.get("title"),
                    "text": properties.get("text"),
                    "url": properties.get("url"),
                }
            )

            nodes.append(
                {
                    "id": chunk_id,
                    "type": "Chunk",
                    "label": properties.get("title", chunk_id),
                    "properties": properties,
                }
            )

            # Preserve the persisted direction: Chunk -> Source.
            edges.append(
                {
                    "id": f"{chunk_id}|{relationship_type}|{source_id}",
                    "source": chunk_id,
                    "target": source_id,
                    "type": relationship_type,
                    "properties": {},
                }
            )

    # ------------------------------------------------------------------
    # 7. Verify that the required rationale sources have linked chunks.
    # ------------------------------------------------------------------
    chunk_source_ids = {
        chunk["source_id"]
        for chunk in chunks
    }

    missing_chunk_sources = (
        required_rationale_sources - chunk_source_ids
    )

    if missing_chunk_sources:
        warnings.append(
            "Missing linked evidence chunks for: "
            + ", ".join(sorted(missing_chunk_sources))
        )

    if not decision.get("summary"):
        warnings.append(
            f"Decision {decision_id} has no persisted rationale summary."
        )

    if decision.get("status") != "accepted":
        warnings.append(
            f"Decision {decision_id} is not marked as accepted."
        )

    # ------------------------------------------------------------------
    # 8. Return the existing trace structure.
    # ------------------------------------------------------------------
    # Deduplicate nodes and edges while preserving order.
    unique_nodes = list(
        {node["id"]: node for node in reversed(nodes)}.values()
    )
    unique_nodes.reverse()

    unique_edges = list(
        {edge["id"]: edge for edge in reversed(edges)}.values()
    )
    unique_edges.reverse()

    return {
        "data": {
            "decision": decision,
            "decision_status": decision.get("status"),
            "rationale": decision.get("summary"),
            "service": service,
            "technology": technology,
            "evidence": evidence_nodes,
        },
        "sources": [
            {
                "id": chunk["source_id"],
                "chunk_id": chunk["id"],
                "title": chunk["title"],
                "text": chunk["text"],
                "url": chunk["url"],
            }
            for chunk in chunks
        ],
        "nodes": unique_nodes,
        "edges": unique_edges,
        "warnings": warnings,
    }
