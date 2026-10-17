"""Independently validate returned review proofs; never discover new findings."""
import re
from datetime import datetime

from .context import EvidenceContext, safe_url
from .context_v2 import validate_source_records
from .graph import GraphContractError
from .models import EvidenceGraph, FreshnessData, FreshnessInput, FreshnessResult, Source

REASON = "Later graph-linked changes affect the same service; review may be warranted."
PREFIXES = {"Service": "service", "Document": "doc", "Decision": "decision",
            "Commit": "commit", "Incident": "incident", "Chunk": "chunk",
            "Technology": "tech", "Person": "person", "Team": "team", "Issue": "issue",
            "Message": "message", "Repository": "repo"}
EVENTS = {"decision": ("Decision", "decided_at", "AFFECTS"),
          "commit": ("Commit", "timestamp", "CHANGES"),
          "incident": ("Incident", "started_at", "AFFECTS")}
FROM = {"Document": "FROM_DOCUMENT", "Commit": "FROM_COMMIT"}


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except ValueError:
        return None


def _same_time(first, second):
    return first == second or (timestamp(first) is not None and timestamp(first) == timestamp(second))


def _sources(result, records, nodes, relations, expected, warnings):
    refs = {}
    for ref in result.sources:
        chunk, parent = nodes.get(ref.chunk_id), nodes.get(ref.id)
        if (chunk is None or chunk.type != "Chunk" or parent is None
                or parent.type not in FROM or parent.id not in expected
                or (chunk.id, FROM[parent.type], parent.id) not in relations
                or chunk.properties.get("source_id") != parent.id
                or chunk.properties.get("source_type") != parent.type
                or any(getattr(ref, f) != chunk.properties.get(f) for f in ("title", "text", "url"))
                or (ref.chunk_id in refs and refs[ref.chunk_id] != ref)):
            raise GraphContractError("Invalid freshness source/chunk reference")
        refs[ref.chunk_id] = ref
    validate_source_records(records)
    sources = {}
    for source in records:
        parent, ids = nodes.get(source.id), source.metadata.get("chunk_ids")
        if (source.id not in expected or parent is None or source.type != parent.type
                or source.metadata.get("source_id") != source.id
                or source.metadata.get("source_type") != parent.type
                or set(source.entity_ids) != {source.id}
                or not isinstance(ids, list) or not ids
                or any(not isinstance(id, str) for id in ids) or len(set(ids)) != len(ids)):
            continue
        chunks = [nodes.get(id) for id in ids]
        if any(c is None or c.type != "Chunk" or c.id not in refs or refs[c.id].id != source.id
               or type(c.properties.get("chunk_index")) is not int or c.properties["chunk_index"] < 0
               or not isinstance(c.properties.get("text"), str) or not c.properties["text"].strip()
               for c in chunks):
            continue
        chunks.sort(key=lambda c: (c.properties["chunk_index"], c.id))
        first = chunks[0].properties
        if (source.title != first.get("title") or source.url != first.get("url")
                or not _same_time(source.timestamp, first.get("timestamp"))
                or not _same_time(source.timestamp, parent.properties.get(
                    "updated_at" if parent.type == "Document" else "timestamp"))
                or source.snippet != "\n\n".join(c.properties["text"].strip() for c in chunks)
                or set(ids) != {r.chunk_id for r in refs.values() if r.id == source.id}):
            continue
        rows = source.metadata.get("chunks")
        if rows is not None:
            if (not isinstance(rows, list) or len(rows) != len(ids)
                    or any(not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in rows)
                    or {r["id"] for r in rows} != set(ids)):
                continue
            if any(any(r.get(f) != nodes[r["id"]].properties.get(f)
                       for f in ("source_id", "source_type", "chunk_index", "title", "url"))
                   or not _same_time(r.get("timestamp"), nodes[r["id"]].properties.get("timestamp"))
                   for r in rows):
                continue
        if len(source.snippet) > 1600:
            warnings.append(f"Source excerpt for {source.id} was truncated to 1600 characters; inspect the original source for full context.")
        sources[source.id] = source.model_copy(update={"snippet": source.snippet[:1600], "url": safe_url(source.url)})
    return sources


def build_freshness_context(result: FreshnessResult, records: list[Source], query: FreshnessInput
                            ) -> tuple[EvidenceContext, FreshnessData]:
    data, warnings = result.data.model_copy(deep=True), list(result.warnings)
    nodes, edges = {}, {}
    for node in result.nodes:
        prefix = PREFIXES.get(node.type)
        if (not prefix or not re.fullmatch(re.escape(prefix) + r":[A-Za-z0-9][A-Za-z0-9:/._-]*", node.id)
                or node.properties.get("id") != node.id
                or node.label != node.properties.get("title", node.properties.get("name", node.id))
                or (node.id in nodes and nodes[node.id] != node)):
            raise GraphContractError("Invalid canonical freshness node")
        nodes[node.id] = node
    for edge in result.edges:
        if (edge.source not in nodes or edge.target not in nodes
                or edge.id != f"{edge.source}|{edge.type}|{edge.target}"
                or (edge.id in edges and edges[edge.id] != edge)):
            raise GraphContractError("Invalid freshness relationship")
        edges[edge.id] = edge
    graph = EvidenceGraph(nodes=list(nodes.values()), edges=list(edges.values()))
    relations = {(e.source, e.type, e.target) for e in graph.edges}

    def matches(node):
        return node.id == query.entity or any(
            str(node.properties.get(f, "")).casefold() == query.entity.casefold() for f in ("name", "title"))

    entity = data.entity
    if entity is None or entity.type != "Service":
        if (data.review_candidates or edges or result.sources
                or any(not matches(n) for n in nodes.values())
                or (entity is not None and (nodes.get(entity.id) != entity or len(nodes) != 1))):
            raise GraphContractError("Freshness evidence without a resolved service")
        return EvidenceContext(graph, [], "insufficient_evidence",
                               "No unambiguous supported service target was resolved. "
                               "Specify an exact service name or canonical ID; no review findings were established.",
                               warnings, False), data
    if nodes.get(entity.id) != entity or not matches(entity):
        raise GraphContractError("Freshness target differs from request")
    expected, seen = set(), set()
    for finding in data.review_candidates:
        doc = nodes.get(finding.document_id)
        updated = timestamp(finding.updated_at)
        if (doc is None or doc.type != "Document" or doc != finding.document
                or finding.document_id in seen or finding.affected_entity_id != entity.id
                or finding.updated_at != doc.properties.get("updated_at") or updated is None
                or finding.reason != REASON):
            raise GraphContractError("Invalid document review assertion")
        seen.add(doc.id)
        path = [(p.source, p.type, p.target) for p in finding.document_path]
        valid = path == [(doc.id, "DESCRIBES", entity.id)]
        if len(path) == 2:
            decision = nodes.get(path[0][0])
            valid = (decision is not None and decision.type == "Decision"
                     and path == [(decision.id, "DOCUMENTED_IN", doc.id), (decision.id, "AFFECTS", entity.id)])
        if not valid or any(p not in relations for p in path):
            raise GraphContractError("Document is not linked to the requested service")
        expected.add(doc.id)
        triggers = set()
        for trigger in finding.triggers:
            kind, field, relation = EVENTS[trigger.type]
            event = nodes.get(trigger.id)
            when = timestamp(trigger.timestamp)
            path = [(p.source, p.type, p.target) for p in trigger.path]
            if (event is None or event.type != kind or trigger.id in triggers
                    or trigger.affected_entity_id != entity.id
                    or trigger.timestamp != event.properties.get(field)
                    or when is None or when <= updated
                    or (kind == "Decision" and event.properties.get("status") != "accepted")
                    or (kind == "Commit" and event.properties.get("architecture_change") is not True)
                    or path != [(event.id, relation, entity.id)] or path[0] not in relations):
                raise GraphContractError("Later change lacks a comparable directed graph proof")
            triggers.add(event.id)
            if kind == "Commit":
                expected.add(event.id)
    # Missing timestamps outside findings still limit completeness; never infer order.
    for node in graph.nodes:
        field = {"Document": "updated_at", "Decision": "decided_at", "Commit": "timestamp",
                 "Incident": "started_at"}.get(node.type)
        if field and timestamp(node.properties.get(field)) is None:
            warnings.append(f"{node.id} has no comparable {field} timestamp; temporal order is unresolved.")
    sources = _sources(result, records, nodes, relations, expected, warnings)
    if expected - sources.keys():
        warnings.append("Missing evidence: some document or commit excerpts lack retrieved matching chunk provenance.")
    lines = [f"Knowledge Freshness for {entity.label} ({entity.id}). "
             "These bounded review recommendations do not establish that a document is wrong or that other documents are current."]
    for finding in data.review_candidates:
        finding.source_ids = [finding.document_id] if finding.document_id in sources else []
        citations = " ".join(f"[{id}]" for id in finding.source_ids)
        lines.append(f"Review recommended: {finding.document.label} ({finding.document_id}), "
                     f"updated {finding.updated_at}. {finding.reason} {citations}".strip())
        for trigger in finding.triggers:
            trigger.source_ids = [trigger.id] if trigger.type == "commit" and trigger.id in sources else []
            citations = " ".join(f"[{id}]" for id in trigger.source_ids)
            mode = "Retrieved graph and chunk evidence" if trigger.source_ids else "Graph-only change evidence; no textual citation established"
            lines.append(f"Later {trigger.type}: {trigger.id}, {trigger.timestamp}. {mode}. "
                         f"Directed proof: {trigger.id} —{trigger.path[0].type}→ {entity.id}. {citations}".strip())
        lines.append("Document association: " + "; ".join(
            f"{p.source} —{p.type}→ {p.target}" for p in finding.document_path) + ".")
    if not data.review_candidates:
        lines.append("No review candidates were established by the bounded retrieved evidence. "
                     "This does not prove the documentation is current.")
    if warnings:
        lines.append("Evidence limitations: " + " ".join(dict.fromkeys(warnings)))
    status = ("supported" if data.review_candidates and not warnings else
              "partially_supported" if data.review_candidates else "insufficient_evidence")
    return EvidenceContext(graph, list(sources.values()), status, "\n\n".join(lines),
                           list(dict.fromkeys(warnings)), False), data
