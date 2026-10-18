"""Merge independently grounded contexts without borrowing support between tools."""
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from .context import EvidenceContext, validate_trace_paths
from .graph import GraphContractError
from .models import EvidenceGraph, GraphEdge, GraphNode, Source, SupportStatus, TraceRelationshipPath


class ContextEntity(GraphNode):
    tools: list[str] = Field(default_factory=list)


class ContextPath(GraphEdge):
    tools: list[str] = Field(default_factory=list)
    retrieved_ids: dict[str, list[str]] = Field(default_factory=dict)


class ContextSnippet(BaseModel):
    text: str
    source_ids: list[str]
    tools: list[str]


class ContextSource(Source):
    tools: list[str] = Field(default_factory=list)


class ContextPacket(BaseModel):
    entities: list[ContextEntity] = Field(default_factory=list)
    paths: list[ContextPath] = Field(default_factory=list)
    snippets: list[ContextSnippet] = Field(default_factory=list)
    sources: list[ContextSource] = Field(default_factory=list)


@dataclass
class ToolEvidence:
    tool: str
    title: str
    public_name: str
    context: EvidenceContext
    # Actual validated impact traversal sequences; never inferred at merge time.
    relationship_paths: tuple[tuple[str, ...], ...] = ()
    # Optional structured output, populated only by the capability's validator.
    data: BaseModel | None = None
    ordered_paths: tuple[TraceRelationshipPath, ...] = ()


@dataclass
class ToolProvenance:
    status: SupportStatus
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    relationship_paths: tuple[tuple[str, ...], ...]
    state: Literal["validated", "unavailable", "invalid", "unregistered"] = "validated"
    summary: str = ""
    data: BaseModel | None = None
    ordered_paths: tuple[TraceRelationshipPath, ...] = ()


@dataclass
class CombinedContext:
    packet: ContextPacket
    graph: EvidenceGraph
    sources: list[Source]
    status: SupportStatus
    summary: str
    warnings: list[str]
    per_tool: dict[str, ToolProvenance] = field(default_factory=dict)


def _source_identity(source: Source) -> dict:
    identity = source.model_dump(mode="json")
    identity["entity_ids"] = sorted(set(source.entity_ids))
    return identity


def validate_source_records(records: list[Source]) -> None:
    """Check before legacy builders can merge duplicate records by richest text."""
    seen = {}
    for source in records:
        identity = _source_identity(source)
        if source.id in seen and seen[source.id] != identity:
            raise GraphContractError("Conflicting source content or provenance")
        seen[source.id] = identity


def merge_contexts(results: list[ToolEvidence], limitations: list[str] | None = None) -> CombinedContext:
    """Fail closed on conflicts/size, preserving membership and directed paths.

    Inputs must already have passed their capability's Context Builder. No tool
    gains citations, relationships, or a stronger support status from a sibling.
    """
    limitations = list(limitations or [])
    if len(results) > 4 or len({r.tool for r in results}) != len(results):
        raise GraphContractError("Invalid tool context set")
    packet = ContextPacket()
    nodes, edge_ids, relations, sources, snippets, per_tool = {}, {}, {}, {}, {}, {}
    graph_nodes, graph_edges = {}, {}
    warnings, paragraphs, already_cited = [], [], set()
    for result in results:
        context, tool = result.context, result.tool
        if context.status not in {"supported", "partially_supported", "insufficient_evidence"}:
            raise GraphContractError("Invalid capability support status")
        local_nodes = {n.id for n in context.graph.nodes}
        local_sources = {s.id for s in context.sources}
        cited = set(re.findall(r"\[([A-Za-z][A-Za-z0-9_-]*:[^\]\s]+)\]", context.summary))
        if cited - local_sources:
            raise GraphContractError("Tool summary cites evidence outside its own context")
        for node in context.graph.nodes:
            if node.id in graph_nodes and graph_nodes[node.id] != node:
                raise GraphContractError("Conflicting canonical node across tools")
            if node.id not in nodes:
                graph_nodes[node.id] = node.model_copy(deep=True)
                nodes[node.id] = ContextEntity(**node.model_dump(), tools=[])
            if tool not in nodes[node.id].tools:
                nodes[node.id].tools.append(tool)
        local_edges = {}
        for edge in context.graph.edges:
            if edge.source not in local_nodes or edge.target not in local_nodes:
                raise GraphContractError("Tool relationship depends on another tool's graph")
            if edge.id in edge_ids and edge_ids[edge.id] != edge:
                raise GraphContractError("Conflicting edge identity across tools")
            edge_ids[edge.id] = edge
            signature = (edge.source, edge.type, edge.target,
                         json.dumps(edge.model_dump(mode="json")["properties"], sort_keys=True))
            if signature not in relations:
                relations[signature] = ContextPath(**edge.model_dump(), tools=[], retrieved_ids={})
                graph_edges[edge.id] = edge.model_copy(deep=True)
            path = relations[signature]
            if tool not in path.tools:
                path.tools.append(tool)
            if edge.id not in path.retrieved_ids.setdefault(tool, []):
                path.retrieved_ids[tool].append(edge.id)
            local_edges[edge.id] = path.id
        for path in result.relationship_paths:
            if not path or any(id not in local_edges for id in path):
                raise GraphContractError("Tool traversal contains an unreturned edge")
        if result.ordered_paths and tool != "decision_trace":
            raise GraphContractError("Ordered historical paths belong to Decision Trace only")
        ordered = validate_trace_paths(list(result.ordered_paths), context.graph)
        original_edges = {e.id: e for e in context.graph.edges}
        sequences = [tuple((original_edges[id].source, original_edges[id].type, original_edges[id].target)
                           for id in path) for path in result.relationship_paths]
        if any(tuple((s.source, s.type, s.target) for s in p.steps) not in sequences for p in ordered):
            raise GraphContractError("Ordered path differs from its tool-local edge sequence")
        validate_source_records(context.sources)
        for source in context.sources:
            if (not source.id.strip() or not source.snippet.strip()
                    or not ({source.id, *source.entity_ids} & local_nodes)):
                raise GraphContractError("Source is not linked within its own tool context")
            if source.id in sources and _source_identity(sources[source.id]) != _source_identity(source):
                raise GraphContractError("Conflicting source provenance across tools")
            if source.id not in sources:
                sources[source.id] = source.model_copy(deep=True)
                packet.sources.append(ContextSource(**source.model_dump(), tools=[]))
            entry = next(s for s in packet.sources if s.id == source.id)
            if tool not in entry.tools:
                entry.tools.append(tool)
            if source.snippet not in snippets:
                snippets[source.snippet] = ContextSnippet(text=source.snippet, source_ids=[], tools=[])
            snippet = snippets[source.snippet]
            if source.id not in snippet.source_ids:
                snippet.source_ids.append(source.id)
            if tool not in snippet.tools:
                snippet.tools.append(tool)
        per_tool[tool] = ToolProvenance(
            context.status, tuple(dict.fromkeys(n.id for n in context.graph.nodes)),
            tuple(dict.fromkeys(local_edges.values())), tuple(dict.fromkeys(s.id for s in context.sources)),
            tuple(tuple(local_edges[id] for id in path) for path in result.relationship_paths),
            summary=context.summary,
            data=result.data.model_copy(deep=True) if result.data is not None else None,
            ordered_paths=tuple(ordered),
        )
        # Keep narratives distinct. Already-cited historical sources remain in
        # the packet/inspector; avoid repeating their excerpts in a sibling summary.
        narrative = []
        for paragraph in context.summary.split("\n\n"):
            references = set(re.findall(r"\[([^\]]+)\]", paragraph)) & local_sources
            if paragraph.startswith("Related source — ") and references and references <= already_cited:
                continue
            narrative.append(paragraph)
            already_cited.update(references)
        label = "Historical decision evidence" if tool == "decision_trace" else result.title
        paragraphs.append(f"{label} ({context.status.replace('_', ' ')}):\n" + "\n\n".join(narrative))
        warnings.extend(f"{result.title}: {warning}" for warning in context.warnings)
    packet.entities, packet.paths, packet.snippets = list(nodes.values()), list(relations.values()), list(snippets.values())
    if (len(packet.entities) > 80 or len(packet.paths) > 200 or len(packet.sources) > 30
            or sum(len(s.text) for s in packet.snippets) > 24000
            or len(packet.model_dump_json().encode("utf-8")) > 160000):
        raise GraphContractError("Combined evidence exceeds the bounded context contract")
    statuses = [r.context.status for r in results]
    if statuses and all(s == "supported" for s in statuses) and not limitations:
        status: SupportStatus = "supported"
    elif any(s in {"supported", "partially_supported"} for s in statuses):
        status = "partially_supported"
    else:
        status = "insufficient_evidence"
    if limitations:
        paragraphs.append("Missing evidence: " + " ".join(limitations))
        warnings.extend(limitations)
    if not paragraphs:
        paragraphs.append("No registered capability could resolve this question with supported evidence.")
    return CombinedContext(packet, EvidenceGraph(nodes=list(graph_nodes.values()), edges=list(graph_edges.values())),
                           list(sources.values()), status, "\n\n".join(paragraphs),
                           list(dict.fromkeys(warnings)), per_tool)
