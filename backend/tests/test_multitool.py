"""Multi-capability contracts; actual teammate functions use offline DB doubles."""
import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.context import EvidenceContext, build_context
from app.context_v2 import ToolEvidence, merge_contexts, validate_source_records
from app.graph import FalkorGateway, FixtureGateway, GraphContractError, GraphUnavailable
from app.main import create_app
from app.models import EvidenceGraph, GraphEdge, GraphNode, Source, TraceInput
from app.orchestration import ToolSpec, execute_plan
from app.router import DeferredIntent, RoutingRule, ToolCall, RoutingPlan, plan_question
from test_impact_integration import database as database

COMBINED = ("What led to Redis being introduced for Payment Service, "
            "and what services might be affected if Redis were removed?")
TRACE = "Why does Payment Service use Redis?"
IMPACT = "What services might be affected if Redis were removed?"


class CountingGateway(FalkorGateway):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    async def trace_decision(self, query):
        self.calls.append(("decision_trace", query))
        return await super().trace_decision(query)

    async def impact_analysis(self, query):
        self.calls.append(("impact_analysis", query))
        return await super().impact_analysis(query)

    async def find_sources(self, ids):
        self.calls.append(("sources", ids))
        return await super().find_sources(ids)


def test_actual_combined_context_membership_dedup_and_support(database):
    gateway = CountingGateway(database[2])
    context, tools = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert tools == ["trace_decision", "impact_analysis"]
    assert [name for name, _ in gateway.calls] == ["decision_trace", "impact_analysis", "sources"]
    assert len(gateway.calls[-1][1]) == len(set(gateway.calls[-1][1])) == 4
    assert context.per_tool["decision_trace"].status == "supported"
    assert context.per_tool["impact_analysis"].status == "partially_supported"
    assert context.status == "partially_supported"
    packet = context.packet.model_dump()
    assert set(packet) == {"entities", "paths", "snippets", "sources"}
    assert len({n.id for n in context.graph.nodes}) == len(context.graph.nodes)
    assert len({(e.source, e.type, e.target) for e in context.graph.edges}) == len(context.graph.edges)
    assert len(context.sources) == 4
    pay = next(s for s in context.packet.sources if s.id == "issue:PAY-42")
    assert pay.tools == ["decision_trace", "impact_analysis"]
    assert pay.timestamp and pay.metadata["chunk_ids"] == ["chunk:issue:PAY-42:0"]
    assert len([s for s in context.packet.snippets if "issue:PAY-42" in s.source_ids]) == 1
    assert "Historical decision evidence (supported)" in context.summary
    assert "potential downstream impact (partially supported)" in context.summary
    assert "guaranteed failure" in context.summary
    assert len(context.per_tool["impact_analysis"].relationship_paths[-1]) == 2
    uses = next(p for p in context.packet.paths if p.type == "USES")
    assert uses.source == "service:payment-service" and uses.target == "tech:redis"
    assert uses.tools == ["decision_trace", "impact_analysis"]


def test_combined_http_exact_public_contract_and_no_llm(database):
    class NoGeneration:
        async def availability(self):
            return "available"
        async def generate(self, *_):
            pytest.fail("Multi-tool answers must stay deterministic")
    config = database[2].model_copy(update={"llm_provider": "ollama"})
    gateway = CountingGateway(config)
    response = TestClient(create_app(config, gateway=gateway, provider=NoGeneration())).post(
        "/api/query", json={"question": COMBINED})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert data["metadata"]["generation"] == "deterministic"
    assert data["tools_used"] == ["trace_decision", "impact_analysis"]
    assert data["support_status"] == "partially_supported" and len(data["sources"]) == 4


@pytest.mark.parametrize("question,names", [
    (TRACE, ["decision_trace"]), (IMPACT, ["impact_analysis"]),
    (COMBINED, ["decision_trace", "impact_analysis"]),
    (IMPACT + ", and " + TRACE, ["decision_trace", "impact_analysis"]),
    (TRACE + "; " + TRACE, ["decision_trace"]),
    ("What led to Redis being introduced for Payment Service?", ["decision_trace"]),
    (TRACE + ", and who knows about Redis?", ["decision_trace", "find_expert"]),
    ("Are the docs up to date?", ["find_stale_knowledge"]),
])
def test_routing_plan_order_and_rules(question, names):
    assert [call.name for call in plan_question(question).calls] == names


@pytest.mark.parametrize("question", [
    "Why does Fraud Service use MongoDB?",
    "What depends on Payment Service and Redis?",
    "Why does Payment Service use Redis and PostgreSQL?",
    "Who knows why Payment Service uses Redis?",  # ambiguous expert/rationale clause
    "What changed in Payment Service?",
    "What has changed in Redis?",
    "; ".join([TRACE] * 5),
])
def test_ambiguous_or_out_of_bounds_plans_do_not_select_graph_calls(question):
    plan = plan_question(question)
    assert not plan.calls and plan.limitations


def test_two_different_targets_for_same_tool_are_not_guessed():
    plan = plan_question("What depends on Payment Service? What depends on Checkout Service?")
    assert not plan.calls and any("Multiple targets" in w for w in plan.limitations)


def test_repeated_intents_traverse_once_and_fetch_sources_once(database):
    gateway = CountingGateway(database[2])
    plan = plan_question(TRACE + "; " + TRACE + "; " + IMPACT + "; " + IMPACT)
    context, _ = asyncio.run(execute_plan(plan, gateway))
    assert [name for name, _ in gateway.calls] == ["decision_trace", "impact_analysis", "sources"]
    assert context.status == "partially_supported"


@pytest.mark.parametrize("failed", ["trace_decision", "impact_analysis"])
def test_partial_tool_outage_isolated_and_sanitized(database, monkeypatch, failed):
    gateway = CountingGateway(database[2])
    async def unavailable(_):
        raise GraphUnavailable("private-debug-secret")
    monkeypatch.setattr(gateway, failed, unavailable)
    response = TestClient(create_app(database[2], gateway=gateway)).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 200 and "private-debug-secret" not in response.text
    data = response.json()
    assert data["support_status"] == "partially_supported"
    assert data["tools_used"] == (["impact_analysis"] if failed == "trace_decision" else ["trace_decision"])
    assert "Missing evidence" in data["answer"] and any("unavailable" in w for w in data["metadata"]["warnings"])


def test_invalid_tool_evidence_is_excluded_without_borrowing_connectivity(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.trace_decision
    async def broken(query):
        result = await original(query)
        # Trace lacks USES, but Impact still has it. The merge must not repair
        # Trace's independent support status from the sibling graph.
        result.graph.edges = [e for e in result.graph.edges if e.type != "USES"]
        return result
    monkeypatch.setattr(gateway, "trace_decision", broken)
    context, _ = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert context.per_tool["decision_trace"].status == "partially_supported"
    assert context.per_tool["impact_analysis"].status == "partially_supported"
    assert any(e.type == "USES" for e in context.graph.edges)
    assert context.status == "partially_supported"
    assert "couldn't find enough connected evidence" in context.summary


def test_impact_contract_failure_excludes_entire_impact_result(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.impact_analysis
    async def broken(query):
        result = await original(query)
        result.edges = [e for e in result.edges if e.type != "DEPENDS_ON"]
        return result
    monkeypatch.setattr(gateway, "impact_analysis", broken)
    context, tools = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert tools == ["trace_decision"] and context.status == "partially_supported"
    assert "returned invalid evidence" in context.summary
    assert "service:checkout-service" not in {n.id for n in context.graph.nodes}


def test_missing_sources_and_source_outage_preserve_structural_findings(database, monkeypatch):
    gateway = CountingGateway(database[2])
    async def missing(_):
        raise GraphUnavailable()
    monkeypatch.setattr(gateway, "find_sources", missing)
    context, _ = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert not context.sources and context.graph.edges
    assert context.per_tool["decision_trace"].status == "insufficient_evidence"
    assert context.per_tool["impact_analysis"].status == "partially_supported"
    assert context.status == "partially_supported"
    assert any("Source retrieval is unavailable" in w for w in context.warnings)


def test_missing_requested_source_never_becomes_complete(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.find_sources
    async def missing(ids):
        return [r for r in await original(ids) if r.id != "doc:ADR-7"]
    monkeypatch.setattr(gateway, "find_sources", missing)
    context, _ = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert context.per_tool["decision_trace"].status == "partially_supported"
    assert "doc:ADR-7" not in {s.id for s in context.sources}
    assert context.status == "partially_supported"


def test_future_and_unknown_clauses_do_not_claim_complete_answer(database):
    gateway = CountingGateway(database[2])
    plan = plan_question(TRACE + ", and who knows about Redis?; Show our revenue forecast")
    context, tools = asyncio.run(execute_plan(plan, gateway))
    assert tools == ["trace_decision"] and context.status == "partially_supported"
    assert [name for name, _ in gateway.calls] == ["decision_trace", "sources"]
    assert "Expert Finder is not implemented" in context.summary
    assert "unknown or ambiguous" in context.summary


def test_future_only_intent_executes_nothing():
    class NoCalls:
        def __getattr__(self, _):
            pytest.fail("An unregistered future tool attempted to use a gateway")
    context, tools = asyncio.run(execute_plan(plan_question("Who knows about Redis?"), NoCalls()))
    assert context.status == "insufficient_evidence" and not tools and not context.graph.nodes
    assert "not implemented or registered" in context.summary
    assert context.per_tool["find_expert"].state == "unregistered"
    assert context.per_tool["find_expert"].status == "insufficient_evidence"


def test_missing_gateway_method_is_isolated_and_tracked(database):
    gateway = CountingGateway(database[2])
    gateway.impact_analysis = None
    context, tools = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert tools == ["trace_decision"] and context.status == "partially_supported"
    assert context.per_tool["impact_analysis"].state == "unavailable"
    assert not context.per_tool["impact_analysis"].source_ids


def test_tool_timeout_is_isolated(database, monkeypatch):
    gateway = CountingGateway(database[2])
    async def timeout(_):
        raise TimeoutError("private-debug")
    monkeypatch.setattr(gateway, "impact_analysis", timeout)
    context, tools = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert tools == ["trace_decision"] and context.status == "partially_supported"
    assert "private-debug" not in context.summary


def test_missing_chunk_path_cannot_be_repaired_by_sibling_provenance(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.trace_decision
    async def missing(query):
        trace = await original(query)
        trace.graph.edges = [e for e in trace.graph.edges if not e.type.startswith("FROM_")]
        return trace
    monkeypatch.setattr(gateway, "trace_decision", missing)
    context, _ = asyncio.run(execute_plan(plan_question(COMBINED), gateway))
    assert context.per_tool["decision_trace"].status == "partially_supported"
    assert any(e.type == "FROM_ISSUE" for e in context.graph.edges)  # from Impact only
    assert "couldn't find enough connected evidence" in context.summary


def test_conflicting_raw_source_payload_returns_sanitized_502(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.find_sources
    async def inconsistent(ids):
        sources = await original(ids)
        return sources + [sources[0].model_copy(update={"snippet": "private-debug-conflict"})]
    monkeypatch.setattr(gateway, "find_sources", inconsistent)
    response = TestClient(create_app(database[2], gateway=gateway)).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 502 and response.json()["error"]["code"] == "GRAPH_CONTRACT_ERROR"
    assert "private-debug" not in response.text and "sources" not in response.json()


def test_independently_valid_node_conflict_rejects_whole_combined_response(database, monkeypatch):
    gateway = CountingGateway(database[2])
    original = gateway.impact_analysis
    async def inconsistent(query):
        result = await original(query)
        result.data.entity.label = "Changed Redis label"
        next(n for n in result.nodes if n.id == result.data.entity.id).label = result.data.entity.label
        return result
    monkeypatch.setattr(gateway, "impact_analysis", inconsistent)
    response = TestClient(create_app(database[2], gateway=gateway)).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 502 and "sources" not in response.json()


def test_all_invalid_tools_return_contract_error(database, monkeypatch):
    gateway = CountingGateway(database[2])
    async def invalid(_):
        raise GraphContractError("private-debug")
    monkeypatch.setattr(gateway, "trace_decision", invalid)
    monkeypatch.setattr(gateway, "impact_analysis", invalid)
    response = TestClient(create_app(database[2], gateway=gateway)).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 502 and "private-debug" not in response.text


def test_executor_also_deduplicates_repeated_planned_calls(database):
    call = plan_question(TRACE).calls[0]
    gateway = CountingGateway(database[2])
    context, tools = asyncio.run(execute_plan(RoutingPlan((call, call), composite=True), gateway))
    assert tools == ["trace_decision"] and context.status == "supported"
    assert [name for name, _ in gateway.calls] == ["decision_trace", "sources"]


def test_executor_rejects_excessive_internal_plan_before_using_gateway():
    class NoCalls:
        def __getattr__(self, _):
            pytest.fail("Unbounded plan attempted a gateway call")
    call = ToolCall("decision_trace", TraceInput(service="Payment Service", technology="Redis"))
    with pytest.raises(GraphContractError):
        asyncio.run(execute_plan(RoutingPlan((call,) * 5), NoCalls()))


def test_real_mode_never_substitutes_fixtures_for_total_outage(monkeypatch):
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Fixture fallback"))
    config = Settings(graph_mode="falkordb", graph_factory="")
    response = TestClient(create_app(config)).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 503 and response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
    assert "sources" not in response.json()


def test_fixture_combined_is_explicit_and_conservative():
    response = TestClient(create_app(Settings(graph_mode="fixture"))).post("/api/query", json={"question": COMBINED})
    assert response.status_code == 200
    assert response.json()["support_status"] == "partially_supported"
    assert response.json()["metadata"]["warnings"][0].startswith("Development fixture")


def test_registration_seam_can_add_future_tool_without_rewriting_planner():
    # Explicit test-only capability; no substitute Expert Finder graph algorithm.
    rule = RoutingRule("test_capability", lambda text: DeferredIntent(question=text))
    plan = plan_question("A test-only capability", rules=(rule,))
    class TestGateway:
        async def test_tool(self, arguments):
            return arguments
    def build(result, records, arguments):
        return ToolEvidence("test_capability", "Test capability", "test_capability",
                            EvidenceContext(graph=EvidenceGraph(),
                                            sources=[], status="insufficient_evidence", summary="No graph evidence.",
                                            warnings=[], can_explain=False))
    registry = {"test_capability": ToolSpec("Test capability", "test_capability", "test_tool",
                                           DeferredIntent, DeferredIntent, lambda _: [], build)}
    context, tools = asyncio.run(execute_plan(plan, TestGateway(), registry))
    assert tools == ["test_capability"] and context.status == "insufficient_evidence"


def unit_context():
    gateway = FixtureGateway()
    context = build_context(gateway.trace, gateway.sources, TraceInput(service="Payment Service", technology="Redis"))
    return ToolEvidence("decision_trace", "Decision Trace", "trace_decision", context)


@pytest.mark.parametrize("damage", ["node type", "node properties", "edge endpoints", "source text", "source provenance", "timestamp"])
def test_cross_tool_conflicts_fail_closed(damage):
    first = unit_context()
    second = replace(first, tool="other", public_name="other", context=deepcopy(first.context))
    if damage == "node type":
        second.context.graph.nodes[0].type = "Different"
    elif damage == "node properties":
        second.context.graph.nodes[0].properties["changed"] = True
    elif damage == "edge endpoints":
        edge = second.context.graph.edges[0]
        edge.source, edge.target = edge.target, edge.source
    elif damage == "source text":
        second.context.sources[0].snippet = "Changed text"
    elif damage == "source provenance":
        second.context.sources[0].metadata["source_id"] = "doc:unrelated"
    else:
        second.context.sources[0].timestamp = "2020-01-01T00:00:00Z"
    with pytest.raises(GraphContractError):
        merge_contexts([first, second])


def test_raw_duplicate_source_conflict_is_not_hidden_by_richest_excerpt_merge():
    record = Source(id="issue:x", type="Issue", title="test", snippet="Original", metadata={"chunk_ids": ["chunk:x:0"]})
    validate_source_records([record, record.model_copy(deep=True)])
    with pytest.raises(GraphContractError):
        validate_source_records([record, record.model_copy(update={"snippet": "Different, longer excerpt"})])


def test_duplicate_edge_signatures_keep_actual_id_aliases_and_directed_inverse():
    first = unit_context()
    second = replace(first, tool="other", public_name="other", context=deepcopy(first.context))
    original = second.context.graph.edges[0]
    second.context.graph.edges[0] = original.model_copy(update={"id": "other-actual-id"})
    inverse = GraphEdge(id="inverse", source=original.target, target=original.source, type=original.type)
    second.context.graph.edges.append(inverse)
    context = merge_contexts([first, second])
    assert len(context.graph.edges) == len(first.context.graph.edges) + 1
    path = next(p for p in context.packet.paths if p.id == original.id)
    assert path.retrieved_ids["other"] == ["other-actual-id"]
    assert "inverse" in {e.id for e in context.graph.edges}


@pytest.mark.parametrize("both_supported,gap,expected", [(True, False, "supported"), (True, True, "partially_supported"),
                                                       (False, False, "partially_supported")])
def test_overall_support_is_conservative(both_supported, gap, expected):
    first = unit_context()
    second = replace(first, tool="other", public_name="other", context=deepcopy(first.context))
    if not both_supported:
        second.context.status = "insufficient_evidence"
    context = merge_contexts([first, second], ["Missing capability."] if gap else [])
    assert context.status == expected


def test_bound_excess_is_rejected_without_silent_truncation_or_supported_result():
    evidence = unit_context()
    evidence.context.graph.nodes.extend(GraphNode(id=f"node:{i}", type="Service", label=str(i)) for i in range(81))
    with pytest.raises(GraphContractError):
        merge_contexts([evidence])


@pytest.mark.parametrize("damage", ["snippet size", "metadata size"])
def test_textual_context_bounds_do_not_silently_claim_complete_evidence(damage):
    evidence = unit_context()
    if damage == "snippet size":
        evidence.context.sources[0].snippet = "x" * 24001
    else:
        evidence.context.sources[0].metadata["oversized"] = "x" * 160001
    with pytest.raises(GraphContractError):
        merge_contexts([evidence])


def test_same_snippet_from_distinct_source_ids_retains_both_associations():
    evidence = unit_context()
    source = evidence.context.sources[0]
    alternate = source.model_copy(update={"id": "source:alternate-actual-id"}, deep=True)
    evidence.context.sources.append(alternate)
    context = merge_contexts([evidence])
    snippet = next(s for s in context.packet.snippets if s.text == source.snippet)
    assert snippet.source_ids == [source.id, alternate.id]
    assert snippet.tools == ["decision_trace"]
    assert len(context.sources) == len(evidence.context.sources)


def test_tool_local_citation_cannot_borrow_source_from_another_tool():
    first = unit_context()
    first.context.summary = "Invented citation [issue:not-returned]."
    with pytest.raises(GraphContractError):
        merge_contexts([first])
