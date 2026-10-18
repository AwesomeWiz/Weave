"""Deterministic playback of existing tool-local paths; no retrieval or inference."""
from .context import validate_trace_paths
from .context_v2 import CombinedContext
from .graph import GraphContractError
from .models import (
    ChangeBriefData, ChangeEvidenceReference, EvidenceGraph, ImpactData,
    TracePlaybackData, TraceSequence, TraceStep,
)


def build_trace_playback(data: ChangeBriefData, context: CombinedContext) -> TracePlaybackData:
    nodes = {n.id: n for n in context.graph.nodes}
    edges = {e.id: e for e in context.graph.edges}
    sequences = []

    def sequence(tool, path_id, steps, traversal, support_status):
        provenance = context.per_tool.get(tool)
        if not provenance or provenance.state != "validated" or support_status != provenance.status:
            raise GraphContractError("Playback requires validated tool-local provenance")
        triples = [(s.source, s.type, s.target) for s in steps]
        # Choose an actual returned proof sequence, never a sibling edge or a
        # display-label match. Preserve its canonical merged edge identities.
        proof = next((p for p in provenance.relationship_paths if len(p) == len(triples)
                      and all(id in provenance.edge_ids and id in edges
                              and (edges[id].source, edges[id].type, edges[id].target) == triple
                              for id, triple in zip(p, triples))), None)
        if (proof is None or len(traversal) != len(steps) + 1
                or tool == "impact_analysis" and len(set(traversal)) != len(traversal)):
            raise GraphContractError("Playback path differs from its original tool-local proof")
        if any(id not in provenance.node_ids or id not in nodes for id in traversal):
            raise GraphContractError("Playback contains an unknown local entity")
        sequence_id = f"{tool}/{path_id}"
        playback_steps = []
        for i, (step, edge_id) in enumerate(zip(steps, proof)):
            expected = (traversal[i], traversal[i + 1]) if tool == "decision_trace" else (traversal[i + 1], traversal[i])
            if (step.source, step.target) != expected:
                raise GraphContractError("Playback direction or connectivity differs from stored evidence")
            if tool == "impact_analysis" and step.type != ("USES" if i == 0 else "DEPENDS_ON"):
                raise GraphContractError("Playback has an invalid impact relationship")
            # Canonical IDs are unambiguous and do not inject source prose into
            # explanations. No adjacent source is promoted to a rationale cite.
            explanation = f"Stored relationship: {step.source} —{step.type}→ {step.target}."
            if tool == "impact_analysis":
                explanation += " Traversal proceeds from dependency to dependent; this does not establish failure propagation."
            playback_steps.append(TraceStep(
                number=i + 1, sequence_id=sequence_id, source=step.source, type=step.type,
                target=step.target, edge_id=edge_id, tool=tool,
                traversal_from=traversal[i], traversal_to=traversal[i + 1], explanation=explanation,
                evidence=ChangeEvidenceReference(tool=tool, node_ids=list(dict.fromkeys([step.source, step.target])),
                                                 edge_ids=[edge_id], relationship_paths=[[edge_id]])))
        return TraceSequence(id=sequence_id, path_id=path_id, tool=tool,
                             support_status=support_status, steps=playback_steps)

    trace = context.per_tool.get("decision_trace")
    history = data.historical_context
    if history.relationship_paths:
        if not trace or trace.state != "validated" or history.relationship_paths != list(trace.ordered_paths):
            raise GraphContractError("Playback historical inventory differs from validated Decision Trace")
        local_graph = EvidenceGraph(nodes=[nodes[id] for id in trace.node_ids if id in nodes],
                                    edges=[edges[id] for id in trace.edge_ids if id in edges])
        for path in validate_trace_paths(history.relationship_paths, local_graph):
            traversal = [path.steps[0].source, *(s.target for s in path.steps)]
            sequences.append(sequence("decision_trace", path.id, path.steps, traversal, history.support_status))
    impact = context.per_tool.get("impact_analysis")
    findings = data.impact.direct_impact + data.impact.indirect_impact
    if findings:
        if not impact or impact.state != "validated" or not isinstance(impact.data, ImpactData):
            raise GraphContractError("Playback requires validated structured Impact evidence")
        original = impact.data.direct_impact + impact.data.indirect_impact
        for finding in findings:
            if (finding not in original or len(finding.path_edges) != finding.impact_depth
                    or finding.path[0] != impact.data.entity.id or finding.path[-1] != finding.service_id):
                raise GraphContractError("Playback impact inventory differs from validated traversal")
            sequences.append(sequence("impact_analysis", finding.service_id, finding.path_edges,
                                      finding.path, data.impact.support_status))
    if len({s.id for s in sequences}) != len(sequences):
        raise GraphContractError("Duplicate playback sequence identity")
    return TracePlaybackData(sequences=sequences)
