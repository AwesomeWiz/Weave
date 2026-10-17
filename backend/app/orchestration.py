"""Bounded deterministic execution of trusted, registered graph capabilities."""
import asyncio
import inspect
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, TypeAdapter, ValidationError

from .context import build_context
from .context_v2 import CombinedContext, ToolEvidence, ToolProvenance, merge_contexts, validate_source_records
from .graph import GraphContractError, GraphGateway, GraphUnavailable
from .impact import build_impact_context
from .experts import build_expert_context
from .models import ExpertInput, ExpertResult, ImpactInput, ImpactResult, Source, TraceInput, TraceResult
from .router import RoutingPlan


@dataclass(frozen=True)
class ToolSpec:
    title: str
    public_name: str
    method: str
    input_type: type[BaseModel]
    result_type: type[BaseModel]
    source_ids: Callable[[BaseModel], list[str]]
    build: Callable[[BaseModel, list[Source], BaseModel], ToolEvidence]


def _trace(result, records, arguments):
    context = build_context(result, records, arguments)
    return ToolEvidence("decision_trace", "Decision Trace", "trace_decision", context,
                        tuple((e.id,) for e in context.graph.edges))


def _impact(result, records, arguments):
    context, data = build_impact_context(result, records, arguments)
    paths = tuple(tuple(next(e.id for e in context.graph.edges
                             if (e.source, e.type, e.target) == (step.source, step.type, step.target))
                        for step in finding.path_edges)
                  for finding in data.direct_impact + data.indirect_impact)
    return ToolEvidence("impact_analysis", "Current graph relationships and potential downstream impact",
                        "impact_analysis", context, paths)


def _expert(result, records, arguments):
    context, data = build_expert_context(result, records, arguments)
    paths = tuple(tuple(next(e.id for e in context.graph.edges
                             if (e.source, e.type, e.target) == (step.source, step.type, step.target))
                        for step in proof.path)
                  for person in data.experts for proof in person.evidence)
    return ToolEvidence("find_expert", "Expert Finder", "find_expert", context, paths)


TOOL_REGISTRY = {
    "decision_trace": ToolSpec("Decision Trace", "trace_decision", "trace_decision", TraceInput, TraceResult,
                               lambda result: result.source_ids, _trace),
    "impact_analysis": ToolSpec("Impact Analysis", "impact_analysis", "impact_analysis", ImpactInput, ImpactResult,
                                lambda result: [s.id for s in result.sources], _impact),
    "find_expert": ToolSpec("Expert Finder", "find_expert", "find_expert", ExpertInput, ExpertResult,
                            lambda result: [s.id for s in result.sources], _expert),
}
FUTURE_TITLES = {"find_stale_knowledge": "Knowledge Freshness"}


async def execute_plan(plan: RoutingPlan, gateway: GraphGateway,
                       registry: dict[str, ToolSpec] | None = None) -> tuple[CombinedContext, list[str]]:
    registry = TOOL_REGISTRY if registry is None else registry
    if len(plan.calls) > 4:
        raise GraphContractError("Too many selected capabilities")
    pending, failures, limitations, seen, incomplete = [], [], list(plan.limitations), set(), {}
    for call in plan.calls:
        if call.key in seen:
            continue
        seen.add(call.key)
        spec = registry.get(call.name)
        if spec is None:
            title = FUTURE_TITLES.get(call.name, "Requested capability")
            limitations.append(f"{title} is not implemented or registered; no results were retrieved for that part.")
            incomplete[call.name] = ToolProvenance("insufficient_evidence", (), (), (), (), "unregistered")
            continue
        method = getattr(gateway, spec.method, None)
        try:
            if not inspect.iscoroutinefunction(method):
                raise GraphUnavailable()
            arguments = spec.input_type.model_validate(call.arguments.model_dump())
            raw = await asyncio.wait_for(method(arguments), timeout=15)
            result = spec.result_type.model_validate(raw)
            ids = list(dict.fromkeys(spec.source_ids(result)))
            if len(ids) > 40 or any(not id.strip() for id in ids):
                raise GraphContractError("Invalid bounded source lookup")
            pending.append((call.name, spec, result, arguments, ids))
        except ValidationError:
            failures.append(GraphContractError())
            limitations.append(f"{spec.title} returned invalid evidence; its result was excluded.")
            incomplete[call.name] = ToolProvenance("insufficient_evidence", (), (), (), (), "invalid")
        except GraphContractError:
            failures.append(GraphContractError())
            limitations.append(f"{spec.title} returned invalid evidence; its result was excluded.")
            incomplete[call.name] = ToolProvenance("insufficient_evidence", (), (), (), (), "invalid")
        except (GraphUnavailable, TimeoutError):
            failures.append(GraphUnavailable())
            limitations.append(f"{spec.title} is unavailable; no results were retrieved for that part.")
            incomplete[call.name] = ToolProvenance("insufficient_evidence", (), (), (), (), "unavailable")
    ids = list(dict.fromkeys(id for *_, source_ids in pending for id in source_ids))
    if len(ids) > 60:
        raise GraphContractError("Combined source lookup exceeds its bound")
    retrieval_warning = False
    try:
        records = TypeAdapter(list[Source]).validate_python(
            await asyncio.wait_for(gateway.find_sources(ids), timeout=10)) if ids else []
    except (GraphUnavailable, TimeoutError):
        records, retrieval_warning = [], True
    except ValidationError as exc:
        raise GraphContractError("Invalid combined source payload") from exc
    records = [r for r in records if r.id in ids]
    validate_source_records(records)
    results = []
    for name, spec, result, arguments, source_ids in pending:
        try:
            evidence = spec.build(result, [r.model_copy(deep=True) for r in records if r.id in source_ids], arguments)
            if evidence.tool != name or evidence.public_name != spec.public_name:
                raise GraphContractError("Capability context identity mismatch")
            if retrieval_warning:
                evidence.context.warnings.append("Source retrieval is unavailable; graph evidence was retained.")
            results.append(evidence)
        except GraphContractError:
            failures.append(GraphContractError())
            limitations.append(f"{spec.title} returned invalid evidence; its result was excluded.")
            incomplete[name] = ToolProvenance("insufficient_evidence", (), (), (), (), "invalid")
    if not results and failures:
        if any(isinstance(f, GraphContractError) for f in failures):
            raise GraphContractError("No valid capability evidence")
        raise GraphUnavailable()
    context = merge_contexts(results, limitations)
    context.per_tool.update(incomplete)
    return context, [r.public_name for r in results]
