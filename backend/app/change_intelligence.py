"""Deterministic workflow over Phase 2's independently validated capabilities.

Graph discovery/retrieval stay in existing capabilities; presentation is optional.
"""
import re
import time
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from .citations import validate_citations
from .change_synthesis import prepare_change_synthesis
from .context_v2 import CombinedContext
from .context import validate_trace_paths
from .graph import GraphContractError, GraphGateway
from .models import (
    ChangeBriefData, ChangeDocumentReview, ChangeEvidenceReference, ChangeHistoricalContext,
    ChangeImpact, ChangeInput, ChangeResponse, ChangeReviewer, ChangeRisk, ChangeTarget,
    ChangeToolSupport, ChangeValidationStep, ExpertData, ExpertInput, FreshnessData,
    EvidenceGraph, FreshnessInput, ImpactData, ImpactInput, Metadata, TraceInput,
)
from .orchestration import execute_plan
from .router import IMPACT_ALIASES, RoutingPlan, ToolCall
from .synthesis import SynthesisPacket

SERVICE = "service:payment-service"
TECHNOLOGY = "tech:redis"
TOOLS = ("decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge")


def _alias(value):
    text = value.strip().casefold()
    return text if text in IMPACT_ALIASES.values() else IMPACT_ALIASES.get(text)


def _proposal(request: ChangeInput | str) -> tuple[ChangeTarget, bool]:
    change = request.change if isinstance(request, ChangeInput) else request.strip()
    target = request.target if isinstance(request, ChangeInput) else None
    result = ChangeTarget(requested_target=target, requested_change=change,
                          intent="unsupported", resolution="unsupported")
    match = re.fullmatch(
        r"(?:(?:what (?:happens|would happen) if|if) we |(?:please |can we |should we )?)"
        r"remove (.+?) from (.+?)\s*[?.!]?", change, re.I)
    if not match:
        result.limitation = "Unsupported change intent. This foundation supports explicit removal of Redis from Payment Service only."
        return result, False
    technology, service = (part.strip().rstrip("?.! ") for part in match.groups())
    result.intent = "remove_technology"
    if any(re.search(r"\b(and|or|either|both|it|this|that)\b", value, re.I)
           for value in (technology, service, target or "")):
        result.resolution, result.limitation = "ambiguous", "The proposal has an ambiguous service or technology; specify one exact target."
        return result, False
    service_id, technology_id = _alias(service), _alias(technology)
    if target is not None and _alias(target) is None:
        result.resolution, result.limitation = "unresolved", "The requested target is unknown to the bounded Change Intelligence resolver."
        return result, False
    if target is not None and _alias(target) != service_id:
        result.resolution, result.limitation = "inconsistent", "The requested target and the service in the proposed change do not agree."
        return result, False
    if service_id != SERVICE or technology_id != TECHNOLOGY:
        result.resolution, result.limitation = "unresolved", "This service/technology pair is outside the validated Redis-removal scenario; no change analysis was performed."
        return result, False
    # Alias resolution selects arguments, not evidence of entity existence or use.
    result.resolution = "unresolved"
    return result, True


def change_plan() -> RoutingPlan:
    return RoutingPlan((
        ToolCall("decision_trace", TraceInput(service="Payment Service", technology="Redis")),
        ToolCall("impact_analysis", ImpactInput(entity_id=TECHNOLOGY, max_depth=3)),
        ToolCall("find_expert", ExpertInput(query="Who knows Payment Service?", limit=5)),
        ToolCall("find_stale_knowledge", FreshnessInput(entity=SERVICE)),
    ), composite=True)


def _reference(context, tool, *, node_ids=(), edge_ids=(), source_ids=(), paths=()):
    provenance = context.per_tool[tool]
    if (provenance.state != "validated" or set(node_ids) - set(provenance.node_ids)
            or set(edge_ids) - set(provenance.edge_ids) or set(source_ids) - set(provenance.source_ids)
            or any(set(path) - set(edge_ids) for path in paths)):
        raise GraphContractError("Change claim references evidence outside its own capability")
    return ChangeEvidenceReference(tool=tool, node_ids=list(dict.fromkeys(node_ids)),
                                   edge_ids=list(dict.fromkeys(edge_ids)), source_ids=list(dict.fromkeys(source_ids)),
                                   relationship_paths=[list(path) for path in paths])


def _whole_reference(context, tool):
    p = context.per_tool[tool]
    return _reference(context, tool, node_ids=p.node_ids, edge_ids=p.edge_ids,
                      source_ids=p.source_ids, paths=p.relationship_paths)


def _path_reference(context, tool, steps):
    p = context.per_tool[tool]
    local = [e for e in context.graph.edges if e.id in p.edge_ids]
    ids = [next(e.id for e in local if (e.source, e.type, e.target) ==
                (step.source, step.type, step.target)) for step in steps]
    return _reference(context, tool, node_ids=[id for step in steps for id in (step.source, step.target)],
                      edge_ids=ids, paths=[ids])


def _build(context: CombinedContext, proposed: ChangeTarget) -> ChangeBriefData:
    nodes = {n.id: n for n in context.graph.nodes}
    edges = {e.id: e for e in context.graph.edges}
    data = ChangeBriefData(proposed_change=proposed, limitations=list(context.warnings))
    for tool, p in context.per_tool.items():
        reference = _whole_reference(context, tool) if p.state == "validated" else ChangeEvidenceReference(tool=tool)
        data.tool_support[tool] = ChangeToolSupport(support_status=p.status, state=p.state, evidence=reference)
    trace = context.per_tool.get("decision_trace")
    if trace and trace.state == "validated":
        ordered = validate_trace_paths(list(trace.ordered_paths), EvidenceGraph(
            nodes=[nodes[id] for id in trace.node_ids], edges=[edges[id] for id in trace.edge_ids]))
        sequences = [tuple((edges[id].source, edges[id].type, edges[id].target) for id in path)
                     for path in trace.relationship_paths]
        if any(tuple((s.source, s.type, s.target) for s in p.steps) not in sequences for p in ordered):
            raise GraphContractError("Historical path differs from its validated edge sequence")
        data.historical_context = ChangeHistoricalContext(
            support_status=trace.status, summary=trace.summary,
            decision_ids=[id for id in trace.node_ids if nodes[id].type == "Decision"],
            evidence=_whole_reference(context, "decision_trace"), relationship_paths=ordered)

    # A proposal must be anchored in an actual local Service USES Technology edge.
    anchors = [(tool, e) for tool, p in context.per_tool.items() if p.state == "validated"
               for id in p.edge_ids if (e := edges[id]).source == SERVICE and e.type == "USES"
               and e.target == TECHNOLOGY and nodes[e.source].type == "Service" and nodes[e.target].type == "Technology"]
    if not anchors:
        proposed.limitation = "The retrieved evidence does not establish Payment Service USES Redis; the proposed removal remains unresolved."
        data.limitations.append(proposed.limitation)
        context.status = "insufficient_evidence"
        return data
    proposed.resolution, proposed.service, proposed.technology = "resolved", nodes[SERVICE], nodes[TECHNOLOGY]
    anchor_tool, anchor = anchors[0]
    anchor_ref = _reference(context, anchor_tool, node_ids=[SERVICE, TECHNOLOGY], edge_ids=[anchor.id], paths=[[anchor.id]])

    impact = context.per_tool.get("impact_analysis")
    if impact and impact.state == "validated":
        if not isinstance(impact.data, ImpactData):
            raise GraphContractError("Missing validated structured Impact output")
        raw = impact.data.model_copy(deep=True)
        # Redis may have other users. Removing it from this service does not
        # establish impact along branches that do not pass through this service.
        direct = [f for f in raw.direct_impact if f.path[:2] == [TECHNOLOGY, SERVICE]]
        indirect = [f for f in raw.indirect_impact if f.path[:2] == [TECHNOLOGY, SERVICE]]
        scope = {f.service_id for f in direct + indirect}
        data.impact = ChangeImpact(entity=raw.entity, direct_impact=direct, indirect_impact=indirect,
                                   related_issues=[r for r in raw.related_issues if r.service_id in scope],
                                   related_incidents=[r for r in raw.related_incidents if r.service_id in scope],
                                   support_status=impact.status if scope else "insufficient_evidence", max_depth=3)
        if not scope:
            data.limitations.append("No independently validated impact path through Payment Service was returned; other Redis users do not establish this change's impact.")
        for finding in direct + indirect:
            ref = _path_reference(context, "impact_analysis", finding.path_edges)
            last = finding.path_edges[-1]
            relationship = "uses" if last.type == "USES" else "depends on"
            data.risks.append(ChangeRisk(classification="KNOWN_FACT",
                description=f"{nodes[last.source].label} {relationship} {nodes[last.target].label}.",
                evidence=[ref], uncertainty="Stored structural relationship; it does not establish guaranteed failure.",
                affected_entity_ids=[finding.service_id]))
            data.validation_steps.append(ChangeValidationStep(
                description=f"Test the returned dependency path to {nodes[finding.service_id].label} under the proposed cache removal; do not assume failure propagation.",
                evidence=[ref]))

    expert = context.per_tool.get("find_expert")
    if expert and expert.state == "validated":
        if not isinstance(expert.data, ExpertData):
            raise GraphContractError("Missing validated structured Expert output")
        data.reviewers = [ChangeReviewer.model_validate(r.model_dump()) for r in expert.data.experts]
        if data.reviewers:
            data.validation_steps.append(ChangeValidationStep(
                description="Request review from the evidence-ranked contributors and verify current ownership and approval responsibilities. Team membership is not personal ownership.",
                evidence=[_whole_reference(context, "find_expert")]))
    freshness = context.per_tool.get("find_stale_knowledge")
    if freshness and freshness.state == "validated":
        if not isinstance(freshness.data, FreshnessData):
            raise GraphContractError("Missing validated structured Freshness output")
        data.current_freshness_findings = [f.model_copy(deep=True) for f in freshness.data.review_candidates]

    # Conditional document review uses only returned local document associations.
    # No document is declared stale by this recommendation; no new edge is made.
    documents = {}
    for tool in ("find_stale_knowledge", "decision_trace"):
        p = context.per_tool.get(tool)
        if not p or p.state != "validated":
            continue
        local = [edges[id] for id in p.edge_ids]
        for doc in (nodes[id] for id in p.node_ids if nodes[id].type == "Document"):
            path = next(([e.id] for e in local if (e.source, e.type, e.target) == (doc.id, "DESCRIBES", SERVICE)), None)
            if path is None:
                for documented in local:
                    if documented.type != "DOCUMENTED_IN" or documented.target != doc.id or nodes[documented.source].type != "Decision":
                        continue
                    affects = next((e for e in local if (e.source, e.type, e.target) ==
                                    (documented.source, "AFFECTS", SERVICE)), None)
                    if affects:
                        path = [documented.id, affects.id]
                        break
            if path and doc.id not in documents:
                ref = _reference(context, tool, node_ids=[id for eid in path for id in (edges[eid].source, edges[eid].target)],
                                  edge_ids=path, paths=[path])
                documents[doc.id] = ChangeDocumentReview(document=doc,
                    reason="Review this service-linked document if Redis removal is approved and implemented; this recommendation does not establish current staleness.",
                    evidence=[ref])
    data.documents_to_review_if_change_proceeds = [documents[id] for id in sorted(documents)]
    if documents:
        data.validation_steps.append(ChangeValidationStep(
            description="If the change is approved and implemented, review the returned service-linked documents and record the new architecture decision.",
            evidence=[documents[id].evidence[0] for id in sorted(documents)[:4]]))

    # A source excerpt can itself contain blank paragraphs. Match the complete
    # validated Decision Trace rationale span, rather than splitting an excerpt
    # away from its closing citation or assigning a neighboring source to it.
    rationale_sources = [source for source in context.sources
        if trace and trace.state == "validated" and source.id in trace.source_ids
        and any(nodes[id].type == "Decision" and nodes[id].properties.get("status") == "accepted"
                and f"{nodes[id].label}: {source.snippet} [{source.id}]" in trace.summary for id in trace.node_ids)
        and re.search(r"\blatency\b", source.snippet, re.I)
        and re.search(r"\b(burst|traffic|peak)\b", source.snippet, re.I)]
    if trace and trace.status == "supported" and rationale_sources:
        citations = [source.id for source in rationale_sources]
        historical = _reference(context, "decision_trace", node_ids=trace.node_ids,
                                edge_ids=trace.edge_ids, paths=trace.relationship_paths, source_ids=citations)
        data.risks.append(ChangeRisk(classification="INFERRED_RISK",
            description="Removing Redis may reintroduce the latency pressure described in the historical rationale under comparable traffic conditions.",
            evidence=[historical, anchor_ref], affected_entity_ids=[SERVICE],
            uncertainty="Inference from historical evidence, not a benchmark or prediction of the proposed implementation."))
        data.validation_steps.append(ChangeValidationStep(
            description="Load-test Payment Service under comparable burst traffic and compare latency before approving cache removal.", evidence=[historical, anchor_ref]))
    data.risks.append(ChangeRisk(classification="RECOMMENDATION",
        description="Validate Payment Service's cache-removal behavior before rollout.", evidence=[anchor_ref],
        affected_entity_ids=[SERVICE], uncertainty="Suggested engineering action; no test has been performed by this analysis."))
    data.validation_steps.append(ChangeValidationStep(
        description="Verify Payment Service's behavior without Redis before rollout; this analysis does not execute the change or run tests.", evidence=[anchor_ref]))
    return data


def _render(data: ChangeBriefData, status: str) -> str:
    proposed = data.proposed_change
    if proposed.resolution != "resolved":
        return proposed.limitation or "The proposed change could not be resolved with sufficient evidence."
    lines = ["Change Brief: proposed removal of Redis from Payment Service. This analysis does not execute the change."]
    history = data.historical_context
    lines.append(f"Historical context ({history.support_status}): " + (
        history.summary if len(history.summary) <= 2000 else "See the complete validated historical_context in the structured brief."))
    for finding in data.impact.direct_impact + data.impact.indirect_impact:
        path = "; ".join(f"{e.source} —{e.type}→ {e.target}" for e in finding.path_edges)
        lines.append(f"Potential {finding.impact_type} impact, depth {finding.impact_depth}: {path}. Not guaranteed failure.")
    if not data.impact.direct_impact and not data.impact.indirect_impact:
        lines.append("No validated impact paths through Payment Service were available; this does not establish no impact.")
    for person in data.reviewers:
        lines.append(f"Reviewer: {person.person.name} ({person.person.id}), evidence score {person.score}. "
                     "Historical expertise and team membership do not establish current personal ownership.")
    if not data.reviewers:
        lines.append("No independently validated reviewer rankings were available.")
    for finding in data.current_freshness_findings:
        lines.append(f"Current freshness: review recommended for {finding.document_id}, updated {finding.updated_at}; "
                     "later graph-linked changes warrant review, not a conclusion that the document is wrong.")
    if not data.current_freshness_findings:
        lines.append("No current freshness findings established; documentation is not thereby proven current.")
    if data.documents_to_review_if_change_proceeds:
        lines.append("If approved and implemented, review: " + ", ".join(
            d.document.id for d in data.documents_to_review_if_change_proceeds) + ". This is separate from current freshness.")
    for risk in data.risks:
        citations = sorted({id for ref in risk.evidence for id in ref.source_ids})
        lines.append(f"{risk.classification}: {risk.description} {risk.uncertainty} " + " ".join(f"[{id}]" for id in citations))
    lines.append("Recommended validation (not performed): " + " ".join(step.description for step in data.validation_steps))
    lines.append("Per-tool support: " + "; ".join(f"{tool}: {p.support_status} ({p.state})" for tool, p in data.tool_support.items()))
    lines.append(f"Overall evidence status: {status}. Potential downstream impact is not guaranteed failure.")
    if data.limitations:
        lines.append("Limitations: " + " ".join(data.limitations))
    return "\n\n".join(line.strip() for line in lines)


async def analyze_change(request: ChangeInput | str, gateway: GraphGateway, graph_mode: str, *,
                         select_presentation: Callable[[SynthesisPacket], Awaitable[dict]] | None = None) -> ChangeResponse:
    started = time.perf_counter()
    proposed, supported = _proposal(request)
    if not supported:
        return ChangeResponse(answer=proposed.limitation, support_status="insufficient_evidence", tools_used=[],
                              data=ChangeBriefData(proposed_change=proposed, limitations=[proposed.limitation]),
                              metadata=Metadata(latency_ms=0, graph_mode=graph_mode, warnings=[proposed.limitation]))
    context, tools = await execute_plan(change_plan(), gateway)
    try:
        data = _build(context, proposed)
        # Enforce list limits after deterministic construction, as well as byte bounds.
        data = ChangeBriefData.model_validate(data.model_dump())
        if len(data.model_dump_json().encode("utf-8")) > 160000:
            raise GraphContractError("Change Brief exceeds its structured evidence bound")
        answer = _render(data, context.status)
        cited = list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", answer)))
        answer = validate_citations(answer, cited, {s.id for s in context.sources},
                                    require_every_paragraph=False, allow_empty=True)
    except (ValidationError, ValueError, StopIteration) as exc:
        raise GraphContractError("Invalid bounded Change Brief evidence") from exc
    warnings = list(data.limitations)
    if graph_mode == "fixture":
        warnings.insert(0, "Development fixture — synthetic evidence, not live FalkorDB data.")
    response = ChangeResponse(answer=answer, support_status=context.status, tools_used=tools,
                          sources=context.sources, graph=context.graph, data=data,
                          metadata=Metadata(latency_ms=round((time.perf_counter() - started) * 1000),
                                            graph_mode=graph_mode, generation="deterministic", warnings=warnings))
    if select_presentation is not None and context.status != "insufficient_evidence" and proposed.resolution == "resolved":
        try:
            packet = prepare_change_synthesis(data, context)
            # Only a finite selection plan can cross back from the provider.
            # It never receives mutable response/data/context objects.
            response.answer = packet.render(await select_presentation(packet))
            response.metadata.generation = "openrouter"
        except Exception:
            response.metadata.warnings.append("OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.")
    response.metadata.latency_ms = round((time.perf_counter() - started) * 1000)
    return response
