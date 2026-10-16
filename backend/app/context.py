import json
from dataclasses import dataclass
from urllib.parse import urlparse

from .graph import GraphContractError
from .models import EvidenceGraph, GraphNode, Source, SupportStatus, TraceInput, TraceResult


def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if (parsed.scheme in {"https", "http"} and parsed.hostname
                and not parsed.username and not parsed.password
                and not parsed.hostname.endswith(".invalid")):
            return url
    except ValueError:
        pass
    return None


@dataclass
class EvidenceContext:
    graph: EvidenceGraph
    sources: list[Source]
    status: SupportStatus
    summary: str
    warnings: list[str]
    can_explain: bool

    def prompt_json(self) -> str:
        # Preserve every path and ID, but exclude irrelevant/large node properties.
        return json.dumps({
            "entities": [{"id": n.id, "type": n.type, "label": n.label,
                          **({"status": n.properties.get("status")} if n.type == "Decision" else {})}
                         for n in self.graph.nodes],
            "paths": [{"source": e.source, "type": e.type, "target": e.target}
                      for e in self.graph.edges],
            "sources": [s.model_dump(exclude={"metadata"}) for s in self.sources],
            "support_status": self.status,
            "grounded_summary": self.summary,
        }, ensure_ascii=False)


def _retrieved_chunk_path(source: Source, parent: GraphNode, nodes: dict[str, GraphNode],
                          relations: set[tuple[str, str, str]]) -> bool:
    """Verify the cited aggregate against its returned Chunk -> Source evidence."""
    relationship = {"Issue": "FROM_ISSUE", "Message": "FROM_MESSAGE"}.get(parent.type)
    chunk_ids = source.metadata.get("chunk_ids")
    if (not relationship or source.type != parent.type
            or source.metadata.get("source_id") != parent.id
            or source.metadata.get("source_type") != parent.type
            or not isinstance(chunk_ids, list) or not chunk_ids
            or any(not isinstance(id, str) for id in chunk_ids)
            or len(set(chunk_ids)) != len(chunk_ids)):
        return False
    chunks = []
    for chunk_id in chunk_ids:
        chunk = nodes.get(chunk_id)
        if (chunk is None or chunk.type != "Chunk"
                or (chunk_id, relationship, parent.id) not in relations):
            return False
        props = chunk.properties
        if (props.get("source_id") != parent.id or props.get("source_type") != parent.type
                or type(props.get("chunk_index")) is not int or props["chunk_index"] < 0
                or not isinstance(props.get("text"), str) or not props["text"].strip()):
            return False
        chunks.append(chunk)
    chunks.sort(key=lambda chunk: (chunk.properties["chunk_index"], chunk.id))
    excerpt = "\n\n".join(chunk.properties["text"].strip() for chunk in chunks)
    return excerpt[:1600] == source.snippet


def build_context(trace: TraceResult, records: list[Source], query: TraceInput) -> EvidenceContext:
    # Bounded contract prevents accidental delivery of a whole-company graph.
    if len(trace.graph.nodes) > 30 or len(trace.graph.edges) > 80:
        raise GraphContractError("Trace exceeds the focused subgraph contract")
    nodes = {}
    for node in trace.graph.nodes:
        if node.id in nodes and nodes[node.id] != node:
            raise GraphContractError("Conflicting canonical node ID")
        nodes[node.id] = node
    edges = {}
    for edge in trace.graph.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise GraphContractError("Dangling relationship endpoint")
        if edge.id in edges and edges[edge.id] != edge:
            raise GraphContractError("Conflicting relationship ID")
        edges[edge.id] = edge
    graph = EvidenceGraph(nodes=list(nodes.values()), edges=list(edges.values()))
    sources: dict[str, Source] = {}
    for source in records:
        linked = source.id in nodes or any(i in nodes for i in source.entity_ids)
        if source.id not in trace.source_ids or not linked or not source.snippet.strip():
            continue
        clean = source.model_copy(update={
            "snippet": source.snippet.strip()[:1600], "url": safe_url(source.url),
            "entity_ids": sorted(set(source.entity_ids)),
        })
        if clean.id in sources:
            previous = sources[clean.id]
            # Deterministic merge; retain metadata and the richest available excerpt.
            clean = previous.model_copy(update={
                "snippet": max((previous.snippet, clean.snippet), key=len),
                "entity_ids": sorted(set(previous.entity_ids + clean.entity_ids)),
                "metadata": {**clean.metadata, **previous.metadata},
                "url": previous.url or clean.url,
                "timestamp": previous.timestamp or clean.timestamp,
            })
        sources[clean.id] = clean
    if len(sources) > 20:
        raise GraphContractError("Too many source records for a focused trace")

    # Source-native IDs need not equal canonical entity IDs. Resolve explicit links
    # once and retain original citation IDs throughout the generated explanation.
    by_entity: dict[str, list[Source]] = {}
    for source in sources.values():
        for entity_id in {source.id, *source.entity_ids} & nodes.keys():
            by_entity.setdefault(entity_id, []).append(source)
    source_for = {
        entity_id: min(candidates, key=lambda source: (
            source.id != entity_id, source.type != nodes[entity_id].type, source.id,
        ))
        for entity_id, candidates in by_entity.items()
    }

    relations = {(e.source, e.type, e.target) for e in graph.edges}
    services = [n.id for n in nodes.values()
                if n.type == "Service" and n.label.casefold() == query.service.casefold()]
    technologies = [n.id for n in nodes.values()
                    if n.type == "Technology" and n.label.casefold() == query.technology.casefold()]
    decisions = [n for n in nodes.values() if n.type == "Decision" and n.id in trace.decision_ids]
    direct = [d for d in decisions if any(
        (s, "USES", t) in relations and (d.id, "AFFECTS", s) in relations
        and (d.id, "INTRODUCES", t) in relations for s in services for t in technologies
    )]
    # A Decision need not be a text source itself. Recognize only the retrieved
    # Decision -SUPPORTED_BY-> Issue/Message <-FROM_*- Chunk path, with matching
    # source/chunk IDs and text. Keep the real parent-source citation unchanged.
    for decision in direct:
        if decision.id in source_for or decision.properties.get("status") != "accepted":
            continue
        candidates = [source for edge in graph.edges
                      if edge.source == decision.id and edge.type == "SUPPORTED_BY"
                      for source in by_entity.get(edge.target, [])
                      if _retrieved_chunk_path(source, nodes[edge.target], nodes, relations)]
        if candidates:
            source_for[decision.id] = min(candidates, key=lambda source: source.id)
    source_entities = {i for s in sources.values() for i in [s.id, *s.entity_ids]}
    rationale = [d for d in direct if d.id in source_for
                 and d.properties.get("status") == "accepted"]
    supported = any(
        any(e.source == d.id and e.type in {"SUPPORTED_BY", "DOCUMENTED_IN", "DISCUSSED_IN"}
            and e.target in source_entities for e in graph.edges)
        and d.properties.get("status") == "accepted" for d in rationale
    )
    warnings = list(trace.warnings)
    if any(d.properties.get("status") != "accepted" for d in direct):
        warnings.append("Decisions not marked accepted cannot establish the current-use rationale.")
    missing = set(trace.source_ids) - set(sources)
    if missing:
        warnings.append("Some graph-linked source records are unavailable.")
    status: SupportStatus = "supported" if supported else (
        "partially_supported" if graph.edges and sources else "insufficient_evidence"
    )
    if missing and status == "supported":
        status = "partially_supported"

    if not rationale:
        summary = ("I couldn't find enough connected evidence to explain why "
                   f"{query.service} uses {query.technology}.")
        if graph.nodes:
            summary += " The available records are shown below; the decision rationale is incomplete."
    else:
        sentences = []
        for decision in rationale:
            source = source_for[decision.id]
            sentences.append(f"{decision.label}: {source.snippet} [{source.id}]")
            approved = [nodes[e.source].label for e in graph.edges
                        if e.type == "APPROVED" and e.target == decision.id]
            if approved:
                sentences.append(f"The graph records approval by {', '.join(approved)}.")
        evidence = []
        for edge in graph.edges:
            source_record = source_for.get(edge.source)
            target_record = source_for.get(edge.target)
            if edge.type == "LED_TO" and source_record and target_record:
                evidence.append(f"{source_record.title} [{source_record.id}] led to "
                                f"{target_record.title} [{target_record.id}].")
            if edge.source in {d.id for d in rationale} and target_record:
                if edge.type == "DISCUSSED_IN":
                    evidence.append(f"The decision was discussed in {target_record.title} "
                                    f"[{target_record.id}].")
                elif edge.type == "IMPLEMENTED_BY":
                    evidence.append(f"Implemented in {nodes[edge.target].label} "
                                    f"[{target_record.id}].")
                elif edge.type == "DOCUMENTED_IN":
                    evidence.append(f"Documented in {nodes[edge.target].label} "
                                    f"[{target_record.id}].")
        if evidence:
            sentences.append(" ".join(evidence))
        if status != "supported":
            sentences.append("The evidence chain is incomplete; this is a partial account.")
        summary = "\n\n".join(sentences)
    return EvidenceContext(graph, list(sources.values()), status, summary, warnings, bool(rationale))
