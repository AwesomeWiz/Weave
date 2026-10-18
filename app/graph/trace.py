from typing import Any

from .client import GraphClient


def trace_decision(
    client: GraphClient,
    service_id: str = "service:payment-service",
    technology_id: str = "tech:redis",
    *,
    include_relationship_paths: bool = False,
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

    # Incidents are only relevant when they lead to an Issue that the selected
    # decision actually supports.  This deliberately does not name a fixture
    # incident or issue: every returned edge is discovered from the decision.
    incident_result = client.execute(
        """
        MATCH (d:Decision {id: $decision_id})-[:SUPPORTED_BY]->(issue:Issue)
        MATCH (i:Incident)-[r:LED_TO]->(issue)
        RETURN i, r, issue
        ORDER BY i.id, issue.id
        LIMIT 20
        """,
        {"decision_id": decision_id},
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
            "No incident-to-issue relationship was returned for the selected "
            "decision's supporting issues."
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

    # The decision's implementation can establish the current architecture
    # only when all three directed relationships are present.  Query the
    # complete bounded path, rather than connecting individually returned
    # nodes in application code.
    implementation_path_result = client.execute(
        """
        MATCH (d:Decision {id: $decision_id})-[implemented:IMPLEMENTED_BY]->
              (commit:Commit)-[changes:CHANGES]->
              (service:Service {id: $service_id})-[uses:USES]->
              (technology:Technology {id: $technology_id})
        RETURN d, implemented, commit, changes, service, uses, technology
        ORDER BY commit.id
        LIMIT 20
        """,
        {
            "decision_id": decision_id,
            "service_id": service_id,
            "technology_id": technology_id,
        },
    )

    implementation_path_edges: list[list[dict[str, str]]] = []
    for (
        path_decision,
        implemented_relationship,
        commit_node,
        changes_relationship,
        path_service,
        uses_relationship,
        path_technology,
    ) in implementation_path_result.result_set:
        path_nodes = (
            (path_decision, "Decision"),
            (commit_node, "Commit"),
            (path_service, "Service"),
            (path_technology, "Technology"),
        )
        valid_nodes = []
        for path_node, fallback_type in path_nodes:
            properties = node_properties(path_node)
            node_id = properties.get("id")
            if not node_id:
                valid_nodes = []
                break
            valid_nodes.append((node_id, fallback_type, properties))
            nodes.append(
                {
                    "id": node_id,
                    "type": node_type(path_node),
                    "label": properties.get(
                        "title", properties.get("name", node_id)
                    ),
                    "properties": properties,
                }
            )
        if not valid_nodes:
            warnings.append(
                "An implementation path was returned with a node lacking a canonical ID."
            )
            continue

        path_steps = []
        for source, relationship, target in (
            (path_decision, implemented_relationship, commit_node),
            (commit_node, changes_relationship, path_service),
            (path_service, uses_relationship, path_technology),
        ):
            source_id = node_properties(source)["id"]
            target_id = node_properties(target)["id"]
            relationship_type = (
                getattr(relationship, "relation", None)
                or getattr(relationship, "type", None)
            )
            if not relationship_type:
                warnings.append(
                    "An implementation path relationship had no returned type."
                )
                path_steps = []
                break
            edge = {
                "id": f"{source_id}|{relationship_type}|{target_id}",
                "source": source_id,
                "target": target_id,
                "type": relationship_type,
                "properties": dict(relationship.properties),
            }
            edges.append(edge)
            path_steps.append(
                {"source": source_id, "type": relationship_type, "target": target_id}
            )
        if path_steps:
            implementation_path_edges.append(path_steps)

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

    response = {
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
    if include_relationship_paths:
        node_ids = {node["id"] for node in unique_nodes if node.get("id")}
        edge_signatures = {
            (edge["source"], edge["type"], edge["target"])
            for edge in unique_edges
        }

        def verified_path(path_id: str, steps: list[dict[str, str]]):
            """Return an ordered path only when every returned edge is real."""
            if not steps or any(
                step["source"] not in node_ids
                or step["target"] not in node_ids
                or
                (step["source"], step["type"], step["target"])
                not in edge_signatures
                for step in steps
            ):
                return None
            if any(
                current["target"] != following["source"]
                for current, following in zip(steps, steps[1:])
            ):
                return None
            return {"id": path_id, "steps": steps}

        ordered_paths = []
        single_edge_paths = (
            ("incident_to_investigation", "LED_TO", "incident:"),
            ("decision_to_investigation", "SUPPORTED_BY", "issue:"),
            ("decision_to_discussion", "SUPPORTED_BY", "message:"),
            ("decision_to_documentation", "DOCUMENTED_IN", "doc:"),
        )
        for path_id, relationship_type, target_prefix in single_edge_paths:
            matches = [
                {"source": edge["source"], "type": edge["type"], "target": edge["target"]}
                for edge in unique_edges
                if edge["type"] == relationship_type
                and (
                    (path_id == "incident_to_investigation" and edge["source"].startswith(target_prefix))
                    or (path_id != "incident_to_investigation" and edge["source"] == decision_id
                        and edge["target"].startswith(target_prefix))
                )
            ]
            for index, step in enumerate(matches):
                path = verified_path(
                    path_id if len(matches) == 1 else f"{path_id}:{index + 1}", [step]
                )
                if path:
                    ordered_paths.append(path)
        for index, steps in enumerate(implementation_path_edges):
            path = verified_path(
                "decision_to_current_architecture"
                if len(implementation_path_edges) == 1
                else f"decision_to_current_architecture:{index + 1}",
                steps,
            )
            if path:
                ordered_paths.append(path)
        response["data"]["relationship_paths"] = ordered_paths
    return response
