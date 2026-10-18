"""Actual merged trace paths through the four-tool Change pipeline, offline only."""
import asyncio
import copy

import pytest
from pydantic import ValidationError

from app.change_intelligence import _build, change_plan
from app.change_synthesis import prepare_change_synthesis
from app.context import build_context
from app.context_v2 import merge_contexts
from app.graph import GraphContractError
from app.models import ChangeTarget, TraceRelationshipPath
from app.orchestration import _trace, execute_plan
from test_change_intelligence import CountingGateway, QUESTION, post
from test_freshness_integration import database as database, expert_db as expert_db, freshness_db as freshness_db


ARCHITECTURE = {
    "id": "decision_to_current_architecture",
    "steps": [
        {"source": "decision:D-007", "type": "IMPLEMENTED_BY", "target": "commit:8fae2"},
        {"source": "commit:8fae2", "type": "CHANGES", "target": "service:payment-service"},
        {"source": "service:payment-service", "type": "USES", "target": "tech:redis"},
    ],
}


def trace_and_sources(db):
    gateway = CountingGateway(db[2])
    trace = asyncio.run(gateway.trace_decision(change_plan().calls[0].arguments))
    sources = asyncio.run(gateway.find_sources(trace.source_ids))
    return trace, sources


def proposed():
    return ChangeTarget(requested_target="Payment Service", requested_change=QUESTION,
                        intent="remove_technology", resolution="unresolved")


def test_actual_named_ordered_paths_reach_dedicated_response_without_extra_traversals(freshness_db):
    trace, _ = trace_and_sources(freshness_db)
    expected = [p.model_dump() for p in trace.relationship_paths]
    gateway = CountingGateway(freshness_db[2])
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["data"]["historical_context"]["relationship_paths"] == expected
    assert ARCHITECTURE in expected
    assert [name for name, _ in gateway.calls] == ["decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge", "sources"]
    assert result["support_status"] == "partially_supported"
    assert result["data"]["historical_context"]["support_status"] == "supported"
    graph = {(e["source"], e["type"], e["target"]) for e in result["graph"]["edges"]}
    local = {(e.source, e.type, e.target) for e in trace.graph.edges}
    assert all((s["source"], s["type"], s["target"]) in local & graph for p in expected for s in p["steps"])
    assert not any(s["source"] == "issue:PAY-42" and s["target"] == "message:payment-perf-7"
                   for p in expected for s in p["steps"])
    query = post(freshness_db, path="/api/query", body={"question": QUESTION}).json()
    assert set(query) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}


@pytest.mark.parametrize("damage", ["missing_edge", "reverse_direction", "reverse_order", "disconnected",
                                    "unknown_node", "duplicate_id", "empty_steps", "extra_step", "too_many_paths"])
def test_stale_or_mutated_typed_paths_fail_before_context_merge(freshness_db, damage):
    trace, sources = trace_and_sources(freshness_db)
    path = next(p for p in trace.relationship_paths if p.id == ARCHITECTURE["id"])
    if damage == "missing_edge":
        trace.graph.edges = [e for e in trace.graph.edges if e.type != "CHANGES"]
    elif damage == "reverse_direction":
        step = path.steps[0]
        step.source, step.target = step.target, step.source
    elif damage == "reverse_order":
        path.steps.reverse()
    elif damage == "disconnected":
        path.steps[1] = next(p.steps[0] for p in trace.relationship_paths if p.id == "incident_to_investigation")
    elif damage == "unknown_node":
        path.steps[0].source = "decision:invented"
    elif damage == "duplicate_id":
        trace.relationship_paths.append(path.model_copy(deep=True))
    elif damage == "empty_steps":
        path.steps = []
    elif damage == "extra_step":
        path.steps *= 4
    else:
        trace.relationship_paths *= 81
    with pytest.raises(GraphContractError):
        build_context(trace, sources, change_plan().calls[0].arguments)
    with pytest.raises(GraphContractError):
        _trace(trace, sources, change_plan().calls[0].arguments)


def test_a_sibling_graph_cannot_repair_an_invalid_historical_path(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    original = gateway.trace_decision
    async def stale(query):
        result = await original(query)
        result.graph.edges = [e for e in result.graph.edges if e.type != "CHANGES"]
        return result  # Deliberately retain the stale ordered path.
    monkeypatch.setattr(gateway, "trace_decision", stale)
    result = post(freshness_db, gateway).json()
    assert result["data"]["tool_support"]["decision_trace"]["state"] == "invalid"
    assert result["data"]["historical_context"]["relationship_paths"] == []
    assert any(e["type"] == "CHANGES" for e in result["graph"]["edges"])  # Actual freshness evidence.
    assert result["support_status"] == "partially_supported"
    assert "trace_decision" not in result["tools_used"]


def test_context_preserves_names_order_and_immutable_copies(freshness_db):
    trace, sources = trace_and_sources(freshness_db)
    evidence = _trace(trace, sources, change_plan().calls[0].arguments)
    combined = merge_contexts([evidence])
    before = [p.model_dump() for p in trace.relationship_paths]
    assert [p.model_dump() for p in combined.per_tool["decision_trace"].ordered_paths] == before
    trace.relationship_paths[0].steps[0].type = "INVENTED"
    assert [p.model_dump() for p in combined.per_tool["decision_trace"].ordered_paths] == before
    data = _build(combined, proposed())
    assert [p.model_dump() for p in data.historical_context.relationship_paths] == before
    combined.per_tool["decision_trace"].ordered_paths[0].steps[0].type = "INVENTED"
    assert [p.model_dump() for p in data.historical_context.relationship_paths] == before
    with pytest.raises(GraphContractError):
        _build(combined, proposed())


def test_change_builder_rejects_a_replaced_local_edge_sequence(freshness_db):
    combined, _ = asyncio.run(execute_plan(change_plan(), CountingGateway(freshness_db[2])))
    # This edge is real and tool-local, but was not returned as this ordered path.
    replacement = TraceRelationshipPath(id="mutated", steps=[{
        "source": "decision:D-007", "type": "INTRODUCES", "target": "tech:redis"}])
    combined.per_tool["decision_trace"].ordered_paths = (replacement,)
    with pytest.raises(GraphContractError):
        _build(combined, proposed())


@pytest.mark.parametrize("damage", ["wrong_tool", "wrong_sequence"])
def test_merge_rejects_wrong_tool_or_mapped_sequence(freshness_db, damage):
    trace, sources = trace_and_sources(freshness_db)
    evidence = _trace(trace, sources, change_plan().calls[0].arguments)
    if damage == "wrong_tool":
        evidence.tool = "impact_analysis"
    else:
        evidence.relationship_paths = tuple(tuple(reversed(p)) for p in evidence.relationship_paths)
    with pytest.raises(GraphContractError):
        merge_contexts([evidence])


def test_legacy_trace_without_ordered_paths_keeps_existing_brief(freshness_db, monkeypatch):
    baseline = post(freshness_db).json()
    gateway = CountingGateway(freshness_db[2])
    original = gateway.trace_decision
    async def legacy(query):
        result = await original(query)
        result.relationship_paths = []
        return result
    monkeypatch.setattr(gateway, "trace_decision", legacy)
    result = post(freshness_db, gateway).json()
    assert result["data"]["historical_context"]["relationship_paths"] == []
    assert result["support_status"] == baseline["support_status"]
    assert result["answer"] == baseline["answer"]
    for key in ("impact", "reviewers", "current_freshness_findings", "documents_to_review_if_change_proceeds"):
        assert result["data"][key] == baseline["data"][key]
    assert result["sources"] == baseline["sources"] and result["graph"] == baseline["graph"]


def test_hosted_packet_cannot_accept_mutated_ordered_history(freshness_db):
    combined, _ = asyncio.run(execute_plan(change_plan(), CountingGateway(freshness_db[2])))
    data = _build(combined, proposed())
    packet = prepare_change_synthesis(data, combined)
    assert "decision_to_current_architecture" not in packet.prompt("Review")  # No expanded external payload.
    original = copy.deepcopy(data)
    data.historical_context.relationship_paths[0].steps[0].type = "INVENTED"
    with pytest.raises(ValueError):
        prepare_change_synthesis(data, combined)
    assert original.historical_context.relationship_paths == list(combined.per_tool["decision_trace"].ordered_paths)


@pytest.mark.parametrize("damage", ["extra", "extra_step_field", "wrong_id_type", "overlong_id"])
def test_ordered_path_schema_is_bounded_and_strict(damage):
    payload = copy.deepcopy(ARCHITECTURE)
    if damage == "extra":
        payload["citations"] = ["doc:invented"]
    elif damage == "extra_step_field":
        payload["steps"][0]["approved"] = True
    elif damage == "wrong_id_type":
        payload["id"] = 7
    else:
        payload["id"] = "x" * 129
    with pytest.raises(ValidationError):
        TraceRelationshipPath.model_validate(payload)
