"""Validate Expert Finder's returned proof, never discover or rank people here."""

import re
from datetime import datetime

from weave_graph.experts import SCORES, TOPIC_RELATIONSHIPS

from .context import EvidenceContext, safe_url
from .context_v2 import validate_source_records
from .graph import GraphContractError
from .models import EvidenceGraph, ExpertData, ExpertInput, ExpertResult, Source

PREFIXES = {
    "Person": "person",
    "Team": "team",
    "Service": "service",
    "Technology": "tech",
    "Decision": "decision",
    "Issue": "issue",
    "Message": "message",
    "Commit": "commit",
    "Document": "doc",
    "Chunk": "chunk",
    "Repository": "repo",
    "Incident": "incident",
}
CONTRIBUTIONS = {
    "decision_approval": ("APPROVED", "Decision"),
    "decision_participation": ("PARTICIPATED_IN", "Decision"),
    "commit_authorship": ("AUTHORED", "Commit"),
    "issue_assignment": ("ASSIGNED_TO", "Issue"),
    "discussion_contribution": ("WROTE", "Message"),
}
FROM = {
    "Issue": "FROM_ISSUE",
    "Message": "FROM_MESSAGE",
    "Commit": "FROM_COMMIT",
    "Document": "FROM_DOCUMENT",
}


def _same_timestamp(first, second):
    if first is None or second is None:
        return first is second
    try:
        return datetime.fromisoformat(first.replace("Z", "+00:00")) == datetime.fromisoformat(second.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False


def build_expert_context(
    result: ExpertResult, records: list[Source], query: ExpertInput
) -> tuple[EvidenceContext, ExpertData]:
    data, warnings = result.data.model_copy(deep=True), list(result.warnings)
    if data.query != query.query or len(data.experts) > query.limit:
        raise GraphContractError("Expert request/result mismatch")
    nodes, edges = {}, {}
    for node in result.nodes:
        prefix = PREFIXES.get(node.type)
        if (
            not prefix
            or not re.fullmatch(re.escape(prefix) + r":[A-Za-z0-9][A-Za-z0-9:/._-]*", node.id)
            or node.properties.get("id") != node.id
            or node.label != node.properties.get("title", node.properties.get("name", node.id))
            or (node.id in nodes and nodes[node.id] != node)
        ):
            raise GraphContractError("Invalid canonical expert node")
        nodes[node.id] = node
    for edge in result.edges:
        if (
            edge.source not in nodes
            or edge.target not in nodes
            or not edge.type
            or (edge.id in edges and edges[edge.id] != edge)
        ):
            raise GraphContractError("Invalid expert relationship")
        edges[edge.id] = edge
    graph = EvidenceGraph(nodes=list(nodes.values()), edges=list(edges.values()))
    relations = {(e.source, e.type, e.target) for e in graph.edges}
    topic_ids = set()
    for topic in data.topics:
        if (
            topic.id in topic_ids
            or nodes.get(topic.id) != topic
            or topic.type
            not in {"Service", "Technology", "Decision", "Issue", "Document", "Message"}
        ):
            raise GraphContractError("Invalid resolved expert topic")
        topic_ids.add(topic.id)
    if len(topic_ids) != 1:
        if data.experts or result.sources or edges or set(nodes) != topic_ids:
            raise GraphContractError("Ranked evidence without one resolved topic")
        message = (
            "Topic resolution is ambiguous; specify one canonical topic. No experts were ranked."
            if topic_ids
            else "No graph topic matched the query. No experts were ranked."
        )
        return EvidenceContext(graph, [], "insufficient_evidence", message, warnings, False), data
    if data.scoring != SCORES:
        raise GraphContractError("Expert scoring policy differs from the graph tool")

    # Check relevance using only the returned neighborhood, within the tool's
    # documented two expansions. This validates proofs; it cannot find new experts.
    relevant = set(topic_ids)
    for _ in range(2):
        relevant |= {
            id
            for s, r, t in relations
            if r in TOPIC_RELATIONSHIPS and (s in relevant or t in relevant)
            for id in (s, t)
        }
    ownership_services = {id for id in topic_ids if nodes[id].type == "Service"}
    ownership_services |= {
        s for s, r, t in relations if r == "USES" and t in topic_ids and nodes[s].type == "Service"
    }
    ranked_ids, evidence_entities = set(), set()
    for expert in data.experts:
        person = nodes.get(expert.person.id)
        if (
            person is None
            or person.type != "Person"
            or person.id in ranked_ids
            or expert.person.name != person.properties.get("name", person.id)
            or expert.person.role != person.properties.get("role")
        ):
            raise GraphContractError("Expert identity conflicts with graph")
        ranked_ids.add(person.id)
        seen = set()
        for evidence in expert.evidence:
            entity = nodes.get(evidence.entity_id)
            key = (evidence.category, evidence.entity_id)
            if (
                key in seen
                or entity is None
                or entity.type != evidence.entity_type
                or entity.id not in relevant
            ):
                raise GraphContractError("Unrelated or duplicated expert evidence")
            seen.add(key)
            evidence_entities.add(entity.id)
            actual = [(e.source, e.type, e.target) for e in evidence.path]
            if evidence.category == "team_ownership":
                if (
                    entity.type != "Service"
                    or entity.id not in ownership_services
                    or len(actual) != 2
                    or actual[0][0:2] != (person.id, "MEMBER_OF")
                    or nodes.get(actual[0][2]) is None
                    or nodes[actual[0][2]].type != "Team"
                    or actual[1] != (actual[0][2], "OWNS", entity.id)
                ):
                    raise GraphContractError("Team ownership is not personal ownership")
            else:
                relationship, kind = CONTRIBUTIONS[evidence.category]
                expected = (
                    (entity.id, relationship, person.id)
                    if evidence.category == "issue_assignment"
                    else (person.id, relationship, entity.id)
                )
                if entity.type != kind or actual != [expected]:
                    raise GraphContractError(
                        "Expert contribution has the wrong person or direction"
                    )
            if any(step not in relations for step in actual):
                raise GraphContractError("Expert proof path is absent from the returned graph")
        expected_ownership = [e for e in expert.evidence if e.category == "team_ownership"]
        expected_history = [e for e in expert.evidence if e.category != "team_ownership"]

        def identity(e):
            return e.model_dump(exclude={"source_ids"})

        if (
            sorted(map(identity, expert.ownership), key=str)
            != sorted(map(identity, expected_ownership), key=str)
            or sorted(map(identity, expert.historical_contributions), key=str)
            != sorted(map(identity, expected_history), key=str)
            or expert.ownership_classification
            != (
                "team_membership_with_team_owned_service"
                if expected_ownership
                else "no_current_ownership_evidence"
            )
            or expert.score != sum(SCORES[e.category] for e in expert.evidence)
            or [(e.category, e.entity_id) for e in expert.evidence] != sorted(seen)
            or expert.ranking_reasons
            != [f"{e.category.replace('_', ' ')}: {e.entity_id}" for e in expert.evidence]
        ):
            raise GraphContractError("Expert score, reasons or ownership conflicts with its proof")
    if data.experts != sorted(data.experts, key=lambda e: (-e.score, e.person.id)):
        raise GraphContractError("Expert ranking order differs from graph scores")

    refs = {}
    for ref in result.sources:
        chunk, parent = nodes.get(ref.chunk_id), nodes.get(ref.id)
        if (
            chunk is None
            or chunk.type != "Chunk"
            or parent is None
            or parent.type not in FROM
            or parent.id not in relevant
            or (ref.chunk_id, FROM[parent.type], parent.id) not in relations
            or chunk.properties.get("source_id") != ref.id
            or chunk.properties.get("source_type") != parent.type
            or any(
                getattr(ref, field) != chunk.properties.get(field)
                for field in ("title", "text", "url")
            )
            or (ref.chunk_id in refs and refs[ref.chunk_id] != ref)
        ):
            raise GraphContractError("Invalid expert source/chunk reference")
        refs[ref.chunk_id] = ref
    validate_source_records(records)
    requested = {ref.id for ref in refs.values()}
    sources = {}
    for source in records:
        if source.id not in requested:
            continue
        parent, chunk_ids = nodes.get(source.id), source.metadata.get("chunk_ids")
        if (
            parent is None
            or source.type != parent.type
            or source.metadata.get("source_id") != source.id
            or source.metadata.get("source_type") != parent.type
            or set(source.entity_ids) != {source.id}
            or not isinstance(chunk_ids, list)
            or not chunk_ids
            or any(not isinstance(id, str) for id in chunk_ids)
            or len(set(chunk_ids)) != len(chunk_ids)
        ):
            continue
        chunks = [nodes.get(id) for id in chunk_ids]
        if any(
            c is None
            or c.type != "Chunk"
            or c.id not in refs
            or refs[c.id].id != parent.id
            or type(c.properties.get("chunk_index")) is not int
            or c.properties["chunk_index"] < 0
            or not isinstance(c.properties.get("text"), str)
            or not c.properties["text"].strip()
            for c in chunks
        ):
            continue
        chunks.sort(key=lambda c: (c.properties["chunk_index"], c.id))
        first = chunks[0].properties
        if (source.title != first.get("title") or source.url != first.get("url")
                or not _same_timestamp(source.timestamp, first.get("timestamp"))):
            continue
        metadata_chunks = source.metadata.get("chunks")
        if metadata_chunks is not None:
            if (not isinstance(metadata_chunks, list)
                    or any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in metadata_chunks)
                    or len(metadata_chunks) != len(chunks)
                    or {row.get("id") for row in metadata_chunks} != set(chunk_ids)):
                continue
            if any(any(row.get(field) != nodes[row["id"]].properties.get(field)
                       for field in ("source_id", "source_type", "chunk_index", "title", "url"))
                   or not _same_timestamp(row.get("timestamp"), nodes[row["id"]].properties.get("timestamp"))
                   for row in metadata_chunks):
                continue
        excerpt = "\n\n".join(c.properties["text"].strip() for c in chunks)
        if source.snippet != excerpt or {c.id for c in chunks} != {
            r.chunk_id for r in refs.values() if r.id == source.id
        }:
            continue
        sources[source.id] = source.model_copy(
            update={"snippet": source.snippet[:1600], "url": safe_url(source.url)}
        )

    missing = False
    for expert in data.experts:
        for evidence in expert.evidence:
            # Approval/participation may cite only an actual Decision -> Source
            # relationship followed by the separately verified Chunk -> Source.
            related = (
                {evidence.entity_id}
                if evidence.entity_type in FROM
                else {
                    t
                    for s, r, t in relations
                    if s == evidence.entity_id
                    and r in {"SUPPORTED_BY", "DOCUMENTED_IN", "IMPLEMENTED_BY"}
                    and nodes[t].type in FROM
                }
            )
            evidence.source_ids = sorted(related & sources.keys())
            if evidence.category != "team_ownership" and not evidence.source_ids:
                missing = True
        lookup = {(e.category, e.entity_id): e.source_ids for e in expert.evidence}
        for evidence in expert.ownership + expert.historical_contributions:
            evidence.source_ids = lookup[(evidence.category, evidence.entity_id)]
    if requested - sources.keys() or missing:
        warnings.append(
            "Some expert contributions lack retrieved matching source/chunk provenance; rankings remain graph-backed only."
        )
    # Top-k is never exhaustive, even when no query cap was reached.
    lines = [
        f"Expert Finder for {data.topics[0].label} ({data.topics[0].id}). "
        f"Showing up to {query.limit} ranked people from bounded retrieved evidence; this is not an exhaustive expertise directory."
    ]
    for index, expert in enumerate(data.experts, 1):
        ownership = (
            "Team member of a team that owns the service; personal ownership is not established."
            if expert.ownership
            else "No current personal ownership evidence was returned."
        )
        lines.append(
            f"{index}. {expert.person.name} ({expert.person.id}), ranking score {expert.score}. {ownership}"
        )
        for evidence in expert.evidence:
            path = "; ".join(f"{e.source} —{e.type}→ {e.target}" for e in evidence.path)
            citations = " ".join(f"[{id}]" for id in evidence.source_ids)
            lines.append(
                f"{evidence.category.replace('_', ' ')}: {evidence.entity_id}. "
                f"Retrieved directed proof: {path}. {citations}".strip()
            )
    if not data.experts:
        lines.append(
            "No person-level evidence was returned for this topic; this does not establish that no experts exist."
        )
    lines.append(
        "Scores reflect the graph tool's fixed weighting policy, not an objective measure of expertise. "
        "Historical contribution does not establish current personal ownership."
    )
    if missing:
        lines.append(
            "Missing evidence: textual provenance is incomplete for some historical contributions."
        )
    if warnings:
        # All warnings must remain visible even after hosted presentation choices.
        lines.append("Evidence limitations: " + " ".join(warnings))
    status = (
        "supported"
        if data.experts and not warnings and not missing
        else "partially_supported"
        if data.experts
        else "insufficient_evidence"
    )
    return EvidenceContext(
        graph,
        list(sources.values()),
        status,
        "\n\n".join(lines),
        list(dict.fromkeys(warnings)),
        False,
    ), data
