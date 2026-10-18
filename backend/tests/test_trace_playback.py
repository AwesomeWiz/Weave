"""Playback from actual merged tools over explicitly offline, ingested demo data."""
import asyncio
import copy

import pytest
from pydantic import ValidationError

from app.change_intelligence import _build, change_plan
from app.graph import GraphContractError
from app.models import TracePlaybackData
from app.orchestration import execute_plan
from app.trace_playback import build_trace_playback
from test_change_intelligence import CountingGateway, post
from test_freshness_integration import database as database, expert_db as expert_db, freshness_db as freshness_db
from test_ordered_change_paths import ARCHITECTURE, proposed


def built(db):
    context, _ = asyncio.run(execute_plan(change_plan(), CountingGateway(db[2])))
    return context, _build(context, proposed())


def test_actual_paths_serialize_deterministically_without_new_retrieval(freshness_db):
    gateway = CountingGateway(freshness_db[2])
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    playback = body["data"]["trace_playback"]
    assert TracePlaybackData.model_validate(playback).model_dump() == playback
    assert [name for name, _ in gateway.calls] == ["decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge", "sources"]
    assert playback == post(freshness_db).json()["data"]["trace_playback"]
    decision = [s for s in playback["sequences"] if s["tool"] == "decision_trace"]
    assert [s["path_id"] for s in decision] == [p["id"] for p in body["data"]["historical_context"]["relationship_paths"]]
    architecture = next(s for s in decision if s["path_id"] == ARCHITECTURE["id"])
    assert [{k: step[k] for k in ("source", "type", "target")} for step in architecture["steps"]] == ARCHITECTURE["steps"]
    assert [s["number"] for s in architecture["steps"]] == [1, 2, 3]
    assert architecture["support_status"] == "supported"
    assert body["support_status"] == "partially_supported"
    for sequence in playback["sequences"]:
        local = body["data"]["tool_support"][sequence["tool"]]["evidence"]
        assert [s["edge_id"] for s in sequence["steps"]] in local["relationship_paths"]
        for step in sequence["steps"]:
            edge = next(e for e in body["graph"]["edges"] if e["id"] == step["edge_id"])
            assert all(step[k] == edge[k] for k in ("source", "type", "target"))
            assert step["edge_id"] in local["edge_ids"]
            assert set(step["evidence"]["node_ids"]) <= set(local["node_ids"])
            assert step["evidence"]["source_ids"] == step["citation_ids"] == []
            assert step["evidence"]["relationship_paths"] == [[step["edge_id"]]]
    query = post(freshness_db, path="/api/query", body={"question": "What happens if we remove Redis from Payment Service?"}).json()
    assert set(query) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}


def test_impact_traversal_preserves_returned_order_and_opposite_stored_direction(freshness_db):
    body = post(freshness_db).json()
    impact = [s for s in body["data"]["trace_playback"]["sequences"] if s["tool"] == "impact_analysis"]
    findings = body["data"]["impact"]["direct_impact"] + body["data"]["impact"]["indirect_impact"]
    assert len(impact) == len(findings) == 3
    for sequence, finding in zip(impact, findings):
        assert sequence["path_id"] == finding["service_id"]
        for i, step in enumerate(sequence["steps"]):
            assert [step["traversal_from"], step["traversal_to"]] == finding["path"][i:i + 2]
            assert (step["source"], step["target"]) == (step["traversal_to"], step["traversal_from"])
            assert step["type"] == ("USES" if i == 0 else "DEPENDS_ON")
            assert "does not establish failure propagation" in step["explanation"]


@pytest.mark.parametrize("damage", ["reversed", "disconnected", "unknown_node", "unknown_edge", "sibling_only",
                                    "proof_order", "historical_inventory", "impact_order", "impact_direction", "impact_unknown",
                                    "status", "duplicate", "too_many", "unavailable"])
def test_reject_stale_or_tool_foreign_provenance(freshness_db, damage):
    context, data = built(freshness_db)
    trace = context.per_tool["decision_trace"]
    path = next(p for p in data.historical_context.relationship_paths if p.id == ARCHITECTURE["id"])
    if damage == "reversed":
        path.steps.reverse()
    elif damage == "disconnected":
        path.steps[1].source = "decision:D-007"
    elif damage == "unknown_node":
        path.steps[0].source = "decision:missing"
    elif damage == "unknown_edge":
        context.graph.edges = [e for e in context.graph.edges if e.type != "CHANGES"]
    elif damage == "sibling_only":
        trace.edge_ids = tuple(id for id in trace.edge_ids if "|CHANGES|" not in id)
    elif damage == "proof_order":
        trace.relationship_paths = tuple(tuple(reversed(p)) for p in trace.relationship_paths)
    elif damage == "historical_inventory":
        path.id = "mutated"
    elif damage == "impact_order":
        data.impact.indirect_impact[-1].path_edges.reverse()
    elif damage == "impact_direction":
        step = data.impact.direct_impact[0].path_edges[0]
        step.source, step.target = step.target, step.source
    elif damage == "impact_unknown":
        data.impact.direct_impact[0].path[0] = "tech:unknown"
    elif damage == "status":
        data.impact.support_status = "supported"
    elif damage == "duplicate":
        data.impact.direct_impact *= 2
    elif damage == "too_many":
        data.historical_context.relationship_paths *= 81
    else:
        trace.state = "unavailable"
    with pytest.raises(GraphContractError):
        build_trace_playback(data, context)


def test_legacy_history_and_missing_capability_do_not_borrow_sequences(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    original = gateway.trace_decision
    async def legacy(query):
        result = await original(query)
        result.relationship_paths = []
        return result
    monkeypatch.setattr(gateway, "trace_decision", legacy)
    body = post(freshness_db, gateway).json()
    assert body["data"]["historical_context"]["relationship_paths"] == []
    assert all(s["tool"] == "impact_analysis" for s in body["data"]["trace_playback"]["sequences"])
    assert body["support_status"] == "partially_supported"
    context, data = built(freshness_db)
    context.per_tool["impact_analysis"].state = "invalid"
    data.impact.direct_impact = data.impact.indirect_impact = []
    assert all(s.tool == "decision_trace" for s in build_trace_playback(data, context).sequences)


def test_unsupported_proposal_and_legacy_models_remain_readable(freshness_db):
    body = post(freshness_db, body={"target": "Payment Service", "change": "Replace the database"}).json()
    assert body["data"]["trace_playback"] is None
    assert body["support_status"] == "insufficient_evidence" and body["tools_used"] == []


@pytest.mark.parametrize("damage", ["citation", "extra", "version", "empty", "number"])
def test_playback_schema_cannot_accept_citations_free_fields_or_unbounded_steps(freshness_db, damage):
    context, data = built(freshness_db)
    payload = copy.deepcopy(build_trace_playback(data, context).model_dump())
    step = payload["sequences"][0]["steps"][0]
    if damage == "citation":
        step["citation_ids"] = ["doc:ADR-7"]
    elif damage == "extra":
        step["approved"] = True
    elif damage == "version":
        payload["version"] = 2
    elif damage == "empty":
        payload["sequences"][0]["steps"] = []
    else:
        step["number"] = 11
    with pytest.raises(ValidationError):
        TracePlaybackData.model_validate(payload)
