"""Bounded, evidence-backed expert discovery for the Weave graph."""

from __future__ import annotations

import re
from typing import Any

from weave_data.loader import load_aliases

from .client import GraphClient

# Scores express this tool's transparent ranking policy, not an objective
# measure of expertise.  An evidence item is counted once per person/category/
# entity, even if traversal finds the same graph edge more than once.
SCORES = {
    "team_ownership": 4,
    "decision_approval": 5,
    "decision_participation": 3,
    "commit_authorship": 4,
    "issue_assignment": 3,
    "discussion_contribution": 2,
}

TOPIC_RELATIONSHIPS = [
    "AFFECTS",
    "INTRODUCES",
    "USES",
    "CHANGES",
    "IMPLEMENTS_DECISION",
    "ADDRESSES",
    "SUPPORTED_BY",
    "IMPLEMENTED_BY",
    "DOCUMENTED_IN",
    "DESCRIBES",
]
PERSON_EVIDENCE = {
    "APPROVED": "decision_approval",
    "PARTICIPATED_IN": "decision_participation",
    "AUTHORED": "commit_authorship",
    "WROTE": "discussion_contribution",
}
STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "best",
    "can",
    "contact",
    "expert",
    "find",
    "for",
    "has",
    "in",
    "is",
    "knows",
    "me",
    "most",
    "of",
    "on",
    "the",
    "to",
    "who",
    "with",
}
TOPIC_CANDIDATE_CAP = 20
NEIGHBORHOOD_CAP = 100
PERSON_EVIDENCE_CAP = 100
ISSUE_ASSIGNMENT_CAP = 100
OWNERSHIP_CAP = 100
CHUNK_CAP = 100


def find_expert(
    client: GraphClient,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Rank people whose persisted graph relationships support *query*.

    The tool resolves at most 20 domain-topic candidates, expands the selected
    topic neighborhood twice (at most 100 directed edges per expansion), and
    never treats a historical contribution as personal service ownership. A
    cap warning means the returned ranking is evidence-backed but may not be
    exhaustive.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    warnings: list[str] = []

    def response(
        experts: list[dict[str, Any]], topics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "data": {
                "query": query if isinstance(query, str) else None,
                "topics": topics,
                "experts": experts,
                "scoring": dict(SCORES),
            },
            "sources": sources,
            "nodes": nodes,
            "edges": edges,
            "warnings": warnings,
        }

    if not isinstance(query, str) or not query.strip():
        warnings.append("query must be a non-empty string.")
        return response([], [])
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        warnings.append("limit must be an integer between 1 and 10.")
        return response([], [])

    def props(node: Any) -> dict[str, Any]:
        return dict(node.properties)

    def label(node: Any) -> str:
        labels = node.labels
        return labels[0] if labels else "Unknown"

    def add_node(node: Any) -> dict[str, Any] | None:
        properties = props(node)
        entity_id = properties.get("id")
        if not entity_id:
            return None
        item = {
            "id": entity_id,
            "type": label(node),
            "label": properties.get("title", properties.get("name", entity_id)),
            "properties": properties,
        }
        if not any(existing["id"] == entity_id for existing in nodes):
            nodes.append(item)
        return item

    def add_edge(source_node: Any, relationship: Any, target_node: Any) -> None:
        source = add_node(source_node)
        target = add_node(target_node)
        if source is None or target is None:
            return
        relationship_type = getattr(relationship, "relation", None) or getattr(
            relationship, "type", None
        )
        if not relationship_type:
            # FalkorDB relationship objects expose ``relation``; this fallback
            # makes the contract explicit for compatible client doubles.
            relationship_type = dict(relationship.properties).get("type")
        if not relationship_type:
            return
        edge_id = f"{source['id']}|{relationship_type}|{target['id']}"
        if any(edge["id"] == edge_id for edge in edges):
            return
        edges.append(
            {
                "id": edge_id,
                "source": source["id"],
                "target": target["id"],
                "type": relationship_type,
                "properties": dict(relationship.properties),
            }
        )

    def warn_if_capped(result: Any, cap: int, label_text: str) -> None:
        if len(result.result_set) >= cap:
            warnings.append(
                f"{label_text} may be incomplete because the query reached "
                f"its cap of {cap} rows."
            )

    normalized = query.casefold().strip()
    terms = [
        term for term in re.findall(r"[\w-]+", normalized) if term not in STOP_WORDS
    ]
    # A two-token phrase is enough for "Payment Service" while avoiding a
    # full natural-language string being required to match an entity label.
    phrases = [" ".join(terms[index : index + 2]) for index in range(len(terms) - 1)]
    alias_ids = {
        canonical_id
        for alias, canonical_id in load_aliases().items()
        if alias in normalized
    }
    candidates = sorted(set(terms + phrases + [normalized, *alias_ids]))[:12]

    topic_result = client.execute(
        """
        MATCH (topic)
        WHERE (topic:Service OR topic:Technology OR topic:Decision OR
               topic:Issue OR topic:Document OR topic:Message)
          AND (
              topic.id IN $candidate_ids OR
              any(candidate IN $candidates WHERE
                  toLower(coalesce(topic.name, '')) CONTAINS candidate OR
                  toLower(coalesce(topic.title, '')) CONTAINS candidate OR
                  toLower(coalesce(topic.key, '')) = candidate
              )
          )
        RETURN topic
        ORDER BY topic.id
        LIMIT 20
        """,
        {"candidate_ids": candidates, "candidates": candidates},
    )
    warn_if_capped(topic_result, TOPIC_CANDIDATE_CAP, "Topic resolution")
    resolved_topics: list[tuple[dict[str, Any], int]] = []
    for row in topic_result.result_set:
        node = add_node(row[0])
        if node is None:
            continue
        searchable = " ".join(
            str(node["properties"].get(field, ""))
            for field in ("id", "name", "title", "key")
        ).casefold()
        # A single incidental substring (for example, "service") is not a
        # confident resolution. Exact canonical/name/title/key matches are
        # accepted; otherwise require a multi-word phrase.
        exact_values = {
            str(node["properties"].get(field, "")).casefold()
            for field in ("id", "name", "title", "key")
        }
        if node["id"].casefold() in alias_ids or exact_values & set(candidates):
            match_score = 3
        else:
            match_score = max(
                (
                    len(candidate.split())
                    for candidate in candidates
                    if len(candidate.split()) >= 2 and candidate in searchable
                ),
                default=0,
            )
        resolved_topics.append((node, match_score))
    requested_types = {
        term.capitalize()
        for term in terms
        if term.capitalize()
        in {"Service", "Technology", "Decision", "Issue", "Document", "Message"}
    }
    typed_topics = [
        item for item in resolved_topics if item[0]["type"] in requested_types
    ]
    if len(requested_types) == 1 and typed_topics:
        resolved_topics = typed_topics
    best_match = max((score for _, score in resolved_topics), default=0)
    topic_nodes = [
        node for node, score in resolved_topics if score == best_match and score > 0
    ]
    if not topic_nodes:
        nodes.clear()
        warnings.append("No graph topic matched the query.")
        return response([], [])
    selected_topic_ids = {node["id"] for node in topic_nodes}
    nodes[:] = [node for node in nodes if node["id"] in selected_topic_ids]
    if len(topic_nodes) > 1:
        warnings.append(
            "Topic resolution is ambiguous: " + ", ".join(sorted(selected_topic_ids))
        )
        return response([], topic_nodes)

    topic_ids = selected_topic_ids
    evidence_ids = set(topic_ids)
    ownership_service_ids = {
        node["id"] for node in topic_nodes if node["type"] == "Service"
    }
    # Expand the topic neighborhood only twice, and retain real directed edges.
    for _ in range(2):
        neighborhood = client.execute(
            """
            MATCH (source)-[relationship]->(target)
            WHERE (source.id IN $entity_ids OR target.id IN $entity_ids)
              AND type(relationship) IN $relationship_types
            RETURN source, relationship, target
            ORDER BY source.id, type(relationship), target.id
            LIMIT 100
            """,
            {
                "entity_ids": sorted(evidence_ids),
                "relationship_types": TOPIC_RELATIONSHIPS,
            },
        )
        warn_if_capped(
            neighborhood,
            NEIGHBORHOOD_CAP,
            "Topic evidence traversal",
        )
        discovered: set[str] = set()
        for source_node, relationship, target_node in neighborhood.result_set:
            add_edge(source_node, relationship, target_node)
            relationship_type = getattr(relationship, "relation", None) or getattr(
                relationship, "type", None
            )
            source_properties = props(source_node)
            target_properties = props(target_node)
            # For a technology request, the services directly using that
            # technology are relevant owner teams.  Do not broaden owner
            # evidence through later, incidental neighborhood expansion.
            if relationship_type == "USES":
                if (
                    source_properties.get("id") in topic_ids
                    and label(target_node) == "Service"
                ):
                    ownership_service_ids.add(target_properties["id"])
                if (
                    target_properties.get("id") in topic_ids
                    and label(source_node) == "Service"
                ):
                    ownership_service_ids.add(source_properties["id"])
            for node in (source_node, target_node):
                node_id = props(node).get("id")
                if node_id:
                    discovered.add(node_id)
        new_ids = discovered - evidence_ids
        if not new_ids:
            break
        evidence_ids.update(new_ids)

    candidates_by_person: dict[str, dict[str, Any]] = {}

    def add_evidence(
        person_node: Any, category: str, entity_node: Any, path: list[dict[str, str]]
    ) -> None:
        person = add_node(person_node)
        entity = add_node(entity_node)
        if person is None or entity is None:
            return
        person_id = person["id"]
        item = candidates_by_person.setdefault(
            person_id,
            {
                "person": {
                    "id": person_id,
                    "name": person["properties"].get("name", person_id),
                    "role": person["properties"].get("role"),
                },
                "evidence": [],
                "ownership": [],
                "historical_contributions": [],
            },
        )
        key = (category, entity["id"])
        if any(
            (entry["category"], entry["entity_id"]) == key for entry in item["evidence"]
        ):
            return
        evidence = {
            "category": category,
            "entity_id": entity["id"],
            "entity_type": entity["type"],
            "path": path,
        }
        item["evidence"].append(evidence)
        if category == "team_ownership":
            item["ownership"].append(evidence)
        else:
            item["historical_contributions"].append(evidence)

    direct_evidence = client.execute(
        """
        MATCH (person:Person)-[relationship]->(entity)
        WHERE entity.id IN $entity_ids
          AND type(relationship) IN $relationship_types
        RETURN person, relationship, entity
        ORDER BY person.id, type(relationship), entity.id
        LIMIT 100
        """,
        {
            "entity_ids": sorted(evidence_ids),
            "relationship_types": sorted(PERSON_EVIDENCE),
        },
    )
    warn_if_capped(
        direct_evidence,
        PERSON_EVIDENCE_CAP,
        "Person evidence retrieval",
    )
    for person_node, relationship, entity_node in direct_evidence.result_set:
        relationship_type = getattr(relationship, "relation", None) or getattr(
            relationship, "type", None
        )
        category = PERSON_EVIDENCE.get(relationship_type)
        if not category:
            continue
        add_edge(person_node, relationship, entity_node)
        person_id = props(person_node).get("id")
        entity_id = props(entity_node).get("id")
        if person_id and entity_id:
            add_evidence(
                person_node,
                category,
                entity_node,
                [{"source": person_id, "type": relationship_type, "target": entity_id}],
            )

    issue_assignments = client.execute(
        """
        MATCH (issue:Issue)-[relationship:ASSIGNED_TO]->(person:Person)
        WHERE issue.id IN $entity_ids
        RETURN issue, relationship, person
        ORDER BY person.id, issue.id
        LIMIT 100
        """,
        {"entity_ids": sorted(evidence_ids)},
    )
    warn_if_capped(
        issue_assignments,
        ISSUE_ASSIGNMENT_CAP,
        "Issue assignment retrieval",
    )
    for issue_node, relationship, person_node in issue_assignments.result_set:
        add_edge(issue_node, relationship, person_node)
        issue_id = props(issue_node).get("id")
        person_id = props(person_node).get("id")
        if issue_id and person_id:
            add_evidence(
                person_node,
                "issue_assignment",
                issue_node,
                [{"source": issue_id, "type": "ASSIGNED_TO", "target": person_id}],
            )

    ownership = client.execute(
        """
        MATCH (person:Person)-[membership:MEMBER_OF]->(team:Team)-[owns:OWNS]->(service:Service)
        WHERE service.id IN $entity_ids
        RETURN person, membership, team, owns, service
        ORDER BY person.id, team.id, service.id
        LIMIT 100
        """,
        {"entity_ids": sorted(ownership_service_ids)},
    )
    warn_if_capped(ownership, OWNERSHIP_CAP, "Team ownership retrieval")
    for person_node, membership, team_node, owns, service_node in ownership.result_set:
        add_edge(person_node, membership, team_node)
        add_edge(team_node, owns, service_node)
        person_id = props(person_node).get("id")
        team_id = props(team_node).get("id")
        service_id = props(service_node).get("id")
        if person_id and team_id and service_id:
            add_evidence(
                person_node,
                "team_ownership",
                service_node,
                [
                    {"source": person_id, "type": "MEMBER_OF", "target": team_id},
                    {"source": team_id, "type": "OWNS", "target": service_id},
                ],
            )

    source_ids = sorted(
        {
            evidence["entity_id"]
            for candidate in candidates_by_person.values()
            for evidence in candidate["evidence"]
            if evidence["entity_type"] in {"Commit", "Issue", "Message", "Document"}
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
            {"source_ids": source_ids},
        )
        warn_if_capped(
            chunk_result,
            CHUNK_CAP,
            "Evidence provenance retrieval",
        )
        provenance_source_ids: set[str] = set()
        for chunk_node, relationship, source_node in chunk_result.result_set:
            add_edge(chunk_node, relationship, source_node)
            chunk = props(chunk_node)
            source = props(source_node)
            chunk_id, source_id = chunk.get("id"), source.get("id")
            if (
                chunk_id
                and source_id
                and not any(item["chunk_id"] == chunk_id for item in sources)
            ):
                provenance_source_ids.add(source_id)
                sources.append(
                    {
                        "id": source_id,
                        "chunk_id": chunk_id,
                        "title": chunk.get("title"),
                        "text": chunk.get("text"),
                        "url": chunk.get("url"),
                    }
                )
        missing_provenance = set(source_ids) - provenance_source_ids
        if missing_provenance:
            warnings.append(
                "Missing provenance chunks for expert evidence: "
                + ", ".join(sorted(missing_provenance))
            )

    experts: list[dict[str, Any]] = []
    for person_id, candidate in candidates_by_person.items():
        evidence = sorted(
            candidate["evidence"],
            key=lambda item: (item["category"], item["entity_id"]),
        )
        score = sum(SCORES[item["category"]] for item in evidence)
        candidate["score"] = score
        candidate["evidence"] = evidence
        candidate["ranking_reasons"] = [
            f"{item['category'].replace('_', ' ')}: {item['entity_id']}"
            for item in evidence
        ]
        candidate["ownership_classification"] = (
            "team_membership_with_team_owned_service"
            if candidate["ownership"]
            else "no_current_ownership_evidence"
        )
        experts.append(candidate)
    experts.sort(key=lambda item: (-item["score"], item["person"]["id"]))
    experts = experts[:limit]
    if not experts:
        warnings.append("No person-level evidence was found for the matched topic.")
    return response(experts, topic_nodes)
