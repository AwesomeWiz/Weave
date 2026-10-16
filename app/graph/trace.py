from typing import Any

from app.graph.client import GraphClient


def trace_decision(
    client: GraphClient,
    service_id: str = "service:payment-service",
    technology_id: str = "tech:redis",
) -> dict[str, Any]:
    """
    Trace the accepted decision connecting a service to a technology.

    Returns decision details, graph nodes and edges, and supporting
    evidence with canonical source IDs and chunk provenance.
    """

    # Find the decision affecting this service and introducing this technology.
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
            "error": "No decision found for the requested service and technology.",
        }

    decision_node, service_node, technology_node = result.result_set[0]

    def node_properties(node: Any) -> dict[str, Any]:
        """Convert a FalkorDB node into a JSON-friendly dictionary."""
        return dict(node.properties)

    decision = node_properties(decision_node)
    service = node_properties(service_node)
    technology = node_properties(technology_node)

    decision_id = decision.get("id")

    # Retrieve the decision's supporting records and implementation/documentation.
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

    evidence_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    nodes = [
        {
            "id": decision.get("id"),
            "type": "Decision",
            "label": decision.get("title", decision.get("id")),
            "properties": decision,
        },
        {
            "id": service.get("id"),
            "type": "Service",
            "label": service.get("name", service.get("id")),
            "properties": service,
        },
        {
            "id": technology.get("id"),
            "type": "Technology",
            "label": technology.get("name", technology.get("id")),
            "properties": technology,
        },
    ]

    edges.extend(
        [
            {
                "id": f"{decision['id']}|AFFECTS|{service['id']}",
                "source": decision["id"],
                "target": service["id"],
                "type": "AFFECTS",
                "properties": {},
            },
            {
                "id": f"{decision['id']}|INTRODUCES|{technology['id']}",
                "source": decision["id"],
                "target": technology["id"],
                "type": "INTRODUCES",
                "properties": {},
            },
        ]
    )

    source_ids: list[str] = []

    for relationship_type, evidence_node in evidence_result.result_set:
        properties = node_properties(evidence_node)
        evidence_id = properties.get("id")

        if not evidence_id:
            continue

        evidence_type = evidence_node.labels[0] if evidence_node.labels else "Unknown"

        nodes.append(
            {
                "id": evidence_id,
                "type": evidence_type,
                "label": properties.get("title", properties.get("name", evidence_id)),
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

    # Find evidence chunks linked to the supporting source records.
    chunks: list[dict[str, Any]] = []

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

            edges.append(
                {
                    "id": f"{chunk_id}|{relationship_type}|{source_id}",
                    "source": chunk_id,
                    "target": source_id,
                    "type": relationship_type,
                    "properties": {},
                }
            )

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
        "nodes": nodes,
        "edges": edges,
    }