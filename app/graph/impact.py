from typing import Any

from .client import GraphClient


def impact_analysis(
    client: GraphClient,
    entity_id: str,
    max_depth: int = 2,
) -> dict[str, Any]:
    """
    Analyze the services affected by a change to a service or technology.

    DEPENDS_ON direction:
        A -[:DEPENDS_ON]-> B means A depends on B.

    When B changes, its dependents are discovered by traversing
    DEPENDS_ON relationships in reverse, while preserving the original
    direction of graph edges in the response.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    warnings: list[str] = []

    def empty_response(message: str) -> dict[str, Any]:
        return {
            "data": {
                "entity": None,
                "direct_impact": [],
                "indirect_impact": [],
                "related_issues": [],
                "related_incidents": [],
            },
            "sources": [],
            "nodes": [],
            "edges": [],
            "warnings": [message],
        }

    def add_node(
        entity_type: str,
        properties: dict[str, Any],
    ) -> None:
        entity_node_id = properties.get("id")
        if not entity_node_id:
            return

        node = {
            "id": entity_node_id,
            "type": entity_type,
            "label": properties.get(
                "title",
                properties.get("name", entity_node_id),
            ),
            "properties": properties,
        }

        if not any(item["id"] == entity_node_id for item in nodes):
            nodes.append(node)

    def add_edge(
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        edge_id = f"{source_id}|{relationship_type}|{target_id}"

        if any(item["id"] == edge_id for item in edges):
            return

        edges.append(
            {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "type": relationship_type,
                "properties": properties or {},
            }
        )

    def fetch_properties(node: Any) -> dict[str, Any]:
        return dict(node.properties)

    def fetch_label(node: Any) -> str:
        labels = node.labels
        return labels[0] if labels else "Unknown"

    def fetch_entity(entity_identifier: str) -> dict[str, Any] | None:
        result = client.execute(
            """
            MATCH (n {id: $entity_id})
            RETURN n
            LIMIT 1
            """,
            {"entity_id": entity_identifier},
        )

        if not result.result_set:
            return None

        node = result.result_set[0][0]
        properties = fetch_properties(node)
        add_node(fetch_label(node), properties)
        return {
            "id": properties.get("id"),
            "type": fetch_label(node),
            "label": properties.get(
                "title",
                properties.get("name", properties.get("id")),
            ),
            "properties": properties,
        }

    if not isinstance(max_depth, int) or isinstance(max_depth, bool):
        return empty_response("max_depth must be an integer between 1 and 3.")

    if not 1 <= max_depth <= 3:
        return empty_response("max_depth must be between 1 and 3.")

    entity = fetch_entity(entity_id)

    if entity is None:
        return empty_response(f"No graph entity found with ID {entity_id}.")

    entity_type = entity["type"]

    if entity_type not in {"Service", "Technology"}:
        return empty_response(
            "Impact analysis supports Service and Technology entities only."
        )

    # ---------------------------------------------------------------
    # 1. Discover services directly affected by the entity.
    # ---------------------------------------------------------------

    service_depths: dict[str, int] = {}
    service_paths: dict[str, list[str]] = {}
    service_path_edges: dict[str, list[dict[str, str]]] = {}

    if entity_type == "Service":
        service_depths[entity_id] = 0
        service_paths[entity_id] = [entity_id]
        service_path_edges[entity_id] = []

    elif entity_type == "Technology":
        technology_result = client.execute(
            """
            MATCH (s:Service)-[r:USES]->(t:Technology {id: $entity_id})
            RETURN s, r, t
            ORDER BY s.id
            """,
            {"entity_id": entity_id},
        )

        for service_node, relationship, technology_node in (
            technology_result.result_set
        ):
            service = fetch_properties(service_node)
            technology = fetch_properties(technology_node)
            service_id = service.get("id")
            technology_id = technology.get("id")

            if not service_id or not technology_id:
                continue

            add_node("Service", service)
            add_node("Technology", technology)
            add_edge(
                service_id,
                "USES",
                technology_id,
                dict(relationship.properties),
            )

            service_depths[service_id] = 1
            service_paths[service_id] = [entity_id, service_id]
            service_path_edges[service_id] = [
                {
                    "source": service_id,
                    "type": "USES",
                    "target": technology_id,
                }
            ]

    # ---------------------------------------------------------------
    # 2. Traverse reverse DEPENDS_ON relationships.
    #
    # For A -> B, A depends on B. Therefore, if B changes, A is
    # affected. The traversal begins at B and discovers incoming edges.
    # ---------------------------------------------------------------

    frontier = set(service_depths)

    visited = set(frontier)

    while frontier:
        next_frontier: set[str] = set()

        for dependency_id in sorted(frontier):
            current_depth = service_depths[dependency_id]

            if current_depth >= max_depth:
                continue

            dependency_result = client.execute(
                """
                MATCH (dependent:Service)-[r:DEPENDS_ON]->
                      (dependency:Service {id: $dependency_id})
                RETURN dependent, r, dependency
                ORDER BY dependent.id
                """,
                {"dependency_id": dependency_id},
            )

            for dependent_node, relationship, dependency_node in (
                dependency_result.result_set
            ):
                dependent = fetch_properties(dependent_node)
                dependency = fetch_properties(dependency_node)

                dependent_id = dependent.get("id")
                actual_dependency_id = dependency.get("id")

                if not dependent_id or not actual_dependency_id:
                    continue

                add_node("Service", dependent)
                add_node("Service", dependency)

                # Preserve the actual stored edge direction:
                # dependent -> dependency.
                add_edge(
                    dependent_id,
                    "DEPENDS_ON",
                    actual_dependency_id,
                    dict(relationship.properties),
                )

                candidate_depth = current_depth + 1

                # Keep only the shortest discovered path for each service.
                if dependent_id in visited:
                    continue

                visited.add(dependent_id)
                service_depths[dependent_id] = candidate_depth

                previous_path = service_paths.get(dependency_id, [entity_id])
                service_paths[dependent_id] = previous_path + [dependent_id]

                previous_edges = service_path_edges.get(
                    dependency_id,
                    [],
                )

                service_path_edges[dependent_id] = previous_edges + [
                    {
                        "source": dependent_id,
                        "type": "DEPENDS_ON",
                        "target": actual_dependency_id,
                    }
                ]

                next_frontier.add(dependent_id)

        frontier = next_frontier

    # ---------------------------------------------------------------
    # 3. Gather ownership, issues, and incidents for impacted services.
    # ---------------------------------------------------------------

    impact_items: dict[str, dict[str, Any]] = {}

    for service_id, depth in sorted(
        service_depths.items(),
        key=lambda item: (item[1], item[0]),
    ):
        service_result = client.execute(
            """
            MATCH (s:Service {id: $service_id})
            RETURN s
            LIMIT 1
            """,
            {"service_id": service_id},
        )

        if not service_result.result_set:
            continue

        service = fetch_properties(service_result.result_set[0][0])
        add_node("Service", service)

        owners: list[dict[str, Any]] = []
        related_issues: list[dict[str, Any]] = []
        related_incidents: list[dict[str, Any]] = []

        owner_result = client.execute(
            """
            MATCH (team:Team)-[r:OWNS]->(s:Service {id: $service_id})
            RETURN team, r, s
            ORDER BY team.id
            """,
            {"service_id": service_id},
        )

        for team_node, relationship, service_node in owner_result.result_set:
            team = fetch_properties(team_node)
            team_id = team.get("id")

            if not team_id:
                continue

            add_node("Team", team)
            add_edge(
                team_id,
                "OWNS",
                service_id,
                dict(relationship.properties),
            )

            owners.append(
                {
                    "id": team_id,
                    "name": team.get("name", team.get("title", team_id)),
                }
            )

        issue_result = client.execute(
            """
            MATCH (issue:Issue)-[r:AFFECTS]->(s:Service {id: $service_id})
            RETURN issue, r, s
            ORDER BY issue.id
            """,
            {"service_id": service_id},
        )

        for issue_node, relationship, service_node in issue_result.result_set:
            issue = fetch_properties(issue_node)
            issue_id = issue.get("id")

            if not issue_id:
                continue

            add_node("Issue", issue)
            add_edge(
                issue_id,
                "AFFECTS",
                service_id,
                dict(relationship.properties),
            )

            issue_item = {
                "id": issue_id,
                "title": issue.get("title", issue_id),
                "properties": issue,
                "service_id": service_id,
            }

            related_issues.append(issue_item)

        incident_result = client.execute(
            """
            MATCH (incident:Incident)-[r:AFFECTS]->(s:Service {id: $service_id})
            RETURN incident, r, s
            ORDER BY incident.id
            """,
            {"service_id": service_id},
        )

        for incident_node, relationship, service_node in (
            incident_result.result_set
        ):
            incident = fetch_properties(incident_node)
            incident_id = incident.get("id")

            if not incident_id:
                continue

            add_node("Incident", incident)
            add_edge(
                incident_id,
                "AFFECTS",
                service_id,
                dict(relationship.properties),
            )

            related_incidents.append(
                {
                    "id": incident_id,
                    "title": incident.get("title", incident_id),
                    "properties": incident,
                    "service_id": service_id,
                }
            )

        # Also include incidents linked to an issue affecting this service.
        for issue_item in related_issues:
            linked_incident_result = client.execute(
                """
                MATCH (incident:Incident)-[r:LED_TO]->
                      (issue:Issue {id: $issue_id})
                RETURN incident, r, issue
                ORDER BY incident.id
                """,
                {"issue_id": issue_item["id"]},
            )

            for incident_node, relationship, issue_node in (
                linked_incident_result.result_set
            ):
                incident = fetch_properties(incident_node)
                incident_id = incident.get("id")

                if not incident_id:
                    continue

                add_node("Incident", incident)
                add_edge(
                    incident_id,
                    "LED_TO",
                    issue_item["id"],
                    dict(relationship.properties),
                )

                if not any(
                    item["id"] == incident_id
                    for item in related_incidents
                ):
                    related_incidents.append(
                        {
                            "id": incident_id,
                            "title": incident.get("title", incident_id),
                            "properties": incident,
                            "service_id": service_id,
                        }
                    )

        impact_items[service_id] = {
            "service_id": service_id,
            "service": service,
            "impact_depth": depth,
            "impact_type": (
                "direct" if depth == 1 else "indirect" if depth > 1 else "target"
            ),
            "path": service_paths.get(service_id, [entity_id]),
            "path_edges": service_path_edges.get(service_id, []),
            "owners": owners,
            "related_issues": related_issues,
            "related_incidents": related_incidents,
        }

    # ---------------------------------------------------------------
    # 4. Gather evidence chunks for real related sources.
    # ---------------------------------------------------------------

    source_ids = sorted(
        {
            item["id"]
            for impact in impact_items.values()
            for item in (
                impact["related_issues"] + impact["related_incidents"]
            )
        }
    )

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

        seen_sources: set[tuple[str, str]] = set()

        for chunk_node, relationship_type, source_id in chunk_result.result_set:
            chunk = fetch_properties(chunk_node)
            chunk_id = chunk.get("id")

            if not chunk_id:
                continue

            add_node("Chunk", chunk)
            add_edge(
                chunk_id,
                relationship_type,
                source_id,
            )

            pair = (source_id, chunk_id)

            if pair in seen_sources:
                continue

            seen_sources.add(pair)

            sources.append(
                {
                    "id": source_id,
                    "chunk_id": chunk_id,
                    "title": chunk.get("title"),
                    "text": chunk.get("text"),
                    "url": chunk.get("url"),
                }
            )

    # ---------------------------------------------------------------
    # 5. Assemble direct and indirect impact results.
    # ---------------------------------------------------------------

    direct_impact = []
    indirect_impact = []
    all_related_issues: dict[str, dict[str, Any]] = {}
    all_related_incidents: dict[str, dict[str, Any]] = {}

    for service_id, item in impact_items.items():
        depth = item["impact_depth"]

        if depth == 1:
            direct_impact.append(item)
        elif depth > 1:
            indirect_impact.append(item)

        for issue in item["related_issues"]:
            all_related_issues[issue["id"]] = issue

        for incident in item["related_incidents"]:
            all_related_incidents[incident["id"]] = incident

    direct_impact.sort(key=lambda item: item["service_id"])
    indirect_impact.sort(
        key=lambda item: (item["impact_depth"], item["service_id"])
    )

    if not direct_impact and not indirect_impact:
        warnings.append("No dependent services were found for this entity.")

    return {
        "data": {
            "entity": entity,
            "direct_impact": direct_impact,
            "indirect_impact": indirect_impact,
            "related_issues": list(all_related_issues.values()),
            "related_incidents": list(all_related_incidents.values()),
        },
        "sources": sources,
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }