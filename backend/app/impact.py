"""Validate returned impact paths and prepare a bounded, deterministic context.

No dependency discovery or Cypher lives here. All findings come from Antony's tool.
Related issue excerpts are historical evidence, not proof of a future outage.
"""
from .context import EvidenceContext, _retrieved_chunk_path, safe_url
from .graph import GraphContractError
from .models import EvidenceGraph, ImpactData, ImpactInput, ImpactResult, Source


def build_impact_context(result: ImpactResult, records: list[Source], query: ImpactInput
                         ) -> tuple[EvidenceContext, ImpactData]:
    if len(result.nodes) > 60 or len(result.edges) > 160 or len(result.sources) > 40:
        raise GraphContractError("Impact exceeds the focused graph contract")
    nodes, edges = {}, {}
    for node in result.nodes:
        if node.id in nodes and nodes[node.id] != node:
            raise GraphContractError("Conflicting impact node")
        nodes[node.id] = node
    for edge in result.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise GraphContractError("Dangling impact edge")
        if edge.id in edges and edges[edge.id] != edge:
            raise GraphContractError("Conflicting impact edge")
        edges[edge.id] = edge
    graph = EvidenceGraph(nodes=list(nodes.values()), edges=list(edges.values()))
    relations = {(e.source, e.type, e.target) for e in graph.edges}
    data = result.data.model_copy(deep=True)
    warnings = list(result.warnings)
    target = data.entity
    if target is None:
        if (nodes or edges or result.sources or data.direct_impact or data.indirect_impact
                or data.related_issues or data.related_incidents):
            raise GraphContractError("Impact evidence without a target")
        return EvidenceContext(graph, [], "insufficient_evidence",
                               "No supported impact target was found in the graph.", warnings, False), data
    if (target.id != query.entity_id or nodes.get(target.id) != target
            or target.type not in {"Service", "Technology"}):
        raise GraphContractError("Impact target conflicts with graph")

    scoped_services = {f.service_id for f in data.direct_impact + data.indirect_impact}
    if target.type == "Service":
        scoped_services.add(target.id)

    def related(item, kind):
        node = nodes.get(item.id)
        if (node is None or node.type != kind or node.properties != item.properties
                or item.service_id not in scoped_services or item.service_id not in nodes
                or nodes[item.service_id].type != "Service"):
            raise GraphContractError("Invalid related impact record")
        connected = (item.id, "AFFECTS", item.service_id) in relations
        if kind == "Incident":
            connected |= any(s == item.id and r == "LED_TO"
                             and nodes[t].type == "Issue"
                             and (t, "AFFECTS", item.service_id) in relations for s, r, t in relations)
        if not connected:
            raise GraphContractError("Related impact record has no returned path")

    seen = {}
    for bucket, expected in ((data.direct_impact, "direct"), (data.indirect_impact, "indirect")):
        unique = []
        for finding in bucket:
            service = nodes.get(finding.service_id)
            depth = finding.impact_depth
            if (service is None or service.type != "Service" or service.properties != finding.service
                    or finding.service_id == target.id or finding.impact_type != expected
                    or (depth == 1) != (expected == "direct") or depth > query.max_depth
                    or len(finding.path) != depth + 1 or len(finding.path_edges) != depth
                    or len(set(finding.path)) != len(finding.path)
                    or any(id not in nodes for id in finding.path)
                    or finding.path[0] != target.id or finding.path[-1] != service.id):
                raise GraphContractError("Invalid impact depth or path")
            for index, edge in enumerate(finding.path_edges):
                previous, current = finding.path[index:index + 2]
                relation = "USES" if index == 0 and target.type == "Technology" else "DEPENDS_ON"
                if (edge.source, edge.type, edge.target) != (current, relation, previous):
                    raise GraphContractError("Impact path reverses dependency direction")
                if ((current, relation, previous) not in relations or nodes[current].type != "Service"
                        or (relation == "DEPENDS_ON" and nodes[previous].type != "Service")):
                    raise GraphContractError("Impact path is absent from graph")
            for owner in finding.owners:
                node = nodes.get(owner.id)
                if (node is None or node.type not in {"Team", "Person"}
                        or owner.name != node.properties.get("name", node.label)
                        or (owner.id, "OWNS", service.id) not in relations):
                    raise GraphContractError("Unlinked impact owner")
            for item in finding.related_issues:
                if item.service_id != service.id:
                    raise GraphContractError("Issue belongs to a different service")
                related(item, "Issue")
            for item in finding.related_incidents:
                if item.service_id != service.id:
                    raise GraphContractError("Incident belongs to a different service")
                related(item, "Incident")
            # Upstream cannot supply arbitrary citation associations.
            finding.source_ids = []
            if service.id in seen:
                if seen[service.id] != finding:
                    raise GraphContractError("Conflicting impact finding")
                continue
            seen[service.id] = finding
            unique.append(finding)
        bucket[:] = unique
    for item in data.related_issues:
        related(item, "Issue")
    for item in data.related_incidents:
        related(item, "Incident")

    requested = {ref.id for ref in result.sources}
    related_ids = {item.id for item in data.related_issues + data.related_incidents}
    sources = {}
    for source in records:
        parent = nodes.get(source.id)
        if (source.id not in requested or source.id not in related_ids
                or not source.snippet.strip() or parent is None):
            continue
        clean = source.model_copy(update={"snippet": source.snippet.strip()[:1600],
                                          "url": safe_url(source.url)})
        # Impact currently returns Issue/Incident source IDs. Only real FROM_ISSUE
        # chunks can substantiate an excerpt; an Incident node alone is not text.
        if not _retrieved_chunk_path(clean, parent, nodes, relations):
            continue
        refs = [ref for ref in result.sources if ref.id == source.id]
        if any(ref.chunk_id not in clean.metadata["chunk_ids"] for ref in refs):
            continue
        if clean.id in sources and sources[clean.id] != clean:
            raise GraphContractError("Conflicting impact source")
        sources[clean.id] = clean
    if len(sources) > 20:
        raise GraphContractError("Too many impact sources")
    for finding in seen.values():
        finding.source_ids = sorted({item.id for item in finding.related_issues + finding.related_incidents
                                     if item.id in sources})
    if requested - sources.keys():
        warnings.append("Some impact source records lack retrieved matching chunk provenance.")

    findings = data.direct_impact + data.indirect_impact
    sentences = [f"Potential impact of changes to {target.label} ({target.id}), within {query.max_depth} hops."]
    for title, bucket in (("Direct impact", data.direct_impact),
                          ("Potential downstream impact", data.indirect_impact)):
        if not bucket:
            sentences.append(f"{title}: no services returned within this traversal.")
        for finding in bucket:
            path = "; ".join(f"{e.source} -[{e.type}]-> {e.target}" for e in finding.path_edges)
            sentences.append(f"{title}: {nodes[finding.service_id].label} "
                             f"(depth {finding.impact_depth}). Stored path: {path}.")
    sentences.append("These are structural graph findings, not a prediction of guaranteed failure. "
                     "Related historical sources do not by themselves establish failure propagation.")
    for source in sources.values():
        sentences.append(f"Related source — {source.title}: {source.snippet} [{source.id}]")
    warnings.append("Impact is based on bounded graph structure; textual evidence of propagation is not established.")
    # No accepted-decision rationale is inferred, and no related issue is promoted
    # into a citation for an unsupported dependency/failure claim. Keep Phase 1 intact.
    context = EvidenceContext(graph, list(sources.values()),
                              "partially_supported" if findings else "insufficient_evidence",
                              "\n\n".join(sentences), list(dict.fromkeys(warnings)), False)
    return context, data
