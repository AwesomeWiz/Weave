"""Change workflow over actual Phase 2 tools and explicit offline graph doubles."""
import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from app.change_intelligence import analyze_change, change_plan
from app.config import Settings
from app.graph import FalkorGateway, FixtureGateway, GraphUnavailable
from app.main import create_app
from app.models import ChangeInput, GraphEdge, GraphNode
from app.router import is_change_question, plan_question, route_question
from test_freshness_integration import database as database, expert_db as expert_db, freshness_db as freshness_db

QUESTION = "What happens if we remove Redis from Payment Service?"
REQUEST = {"target": "Payment Service", "change": "Remove Redis from Payment Service"}


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

    async def find_expert(self, query):
        self.calls.append(("find_expert", query))
        return await super().find_expert(query)

    async def find_stale_knowledge(self, query):
        self.calls.append(("find_stale_knowledge", query))
        return await super().find_stale_knowledge(query)

    async def find_sources(self, ids):
        self.calls.append(("sources", ids))
        return await super().find_sources(ids)


def post(database, gateway=None, path="/api/change-intelligence", body=None, provider=None):
    return TestClient(create_app(database[2], gateway=gateway, provider=provider)).post(path, json=body or REQUEST)


def test_complete_structured_brief_and_single_deduplicated_retrieval(freshness_db):
    gateway = CountingGateway(freshness_db[2])
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"answer", "support_status", "tools_used", "sources", "graph", "data", "metadata"}
    assert body["support_status"] == "partially_supported"
    assert [name for name, _ in gateway.calls] == ["decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge", "sources"]
    assert len(gateway.calls[-1][1]) == len(set(gateway.calls[-1][1]))
    assert gateway.calls[1][1].max_depth == 3
    assert gateway.calls[3][1].entity == "service:payment-service"
    assert body["data"]["proposed_change"]["resolution"] == "resolved"
    assert body["data"]["proposed_change"]["technology"]["id"] == "tech:redis"
    assert body["data"]["historical_context"]["decision_ids"] == ["decision:D-007"]
    assert body["data"]["historical_context"]["support_status"] == "supported"
    assert body["data"]["impact"]["support_status"] == "partially_supported"
    assert len({n["id"] for n in body["graph"]["nodes"]}) == len(body["graph"]["nodes"])
    assert all(s["metadata"]["chunk_ids"] for s in body["sources"])
    assert set(body["tools_used"]) == {"trace_decision", "impact_analysis", "find_expert", "find_stale_knowledge"}
    for risk in body["data"]["risks"]:
        for ref in risk["evidence"]:
            local = body["data"]["tool_support"][ref["tool"]]["evidence"]
            for key in ("node_ids", "edge_ids", "source_ids"):
                assert set(ref[key]) <= set(local[key])


def test_canonical_query_routes_change_but_public_response_is_exact(freshness_db):
    assert is_change_question(QUESTION)
    response = post(freshness_db, path="/api/query", body={"question": QUESTION})
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert "Change Brief" in response.json()["answer"]


@pytest.mark.parametrize("question", [QUESTION, "What would happen if we remove Redis from Payment Service?",
    "If we remove Redis from Payment Service", "Replace Redis with PostgreSQL in Payment Service",
    "Migrate Payment Service", "Deprecate Redis", "Switch from Redis", "Move away from Redis", "Upgrade Redis"])
def test_explicit_proposals_select_workflow(question):
    assert is_change_question(question)


@pytest.mark.parametrize("question,tool", [
    ("Why does Payment Service use Redis?", "decision_trace"),
    ("What depends on Payment Service?", "impact_analysis"),
    ("Who knows Payment Service?", "find_expert"),
    ("Which Payment Service documents need review?", "find_stale_knowledge"),
    ("What services might be affected if Redis were removed?", "impact_analysis"),
])
def test_phase2_selection_is_preserved(question, tool):
    assert not is_change_question(question)
    assert [c.name for c in plan_question(question).calls] == [tool]
    if tool in {"decision_trace", "impact_analysis"}:
        assert route_question(question) is not None


@pytest.mark.parametrize("body", [{}, {"target": "Payment Service"},
    {"target": " ", "change": REQUEST["change"]}, {"target": "Payment Service", "change": " "},
    {"target": 1, "change": REQUEST["change"]}, {"target": "x" * 257, "change": "remove"},
    {"target": "Payment Service", "change": "x" * 2001}, {**REQUEST, "depth": 3}])
def test_request_validation_is_sanitized(body):
    client = TestClient(create_app(Settings(_env_file=None, llm_provider="none")))
    response = client.post("/api/change-intelligence", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "input" not in response.text and "Traceback" not in response.text


@pytest.mark.parametrize("body,resolution", [
    ({"target": "Fraud Service", "change": "Remove Redis from Fraud Service"}, "unresolved"),
    ({"target": "Payment Service", "change": "Remove MongoDB from Payment Service"}, "unresolved"),
    ({"target": "Checkout Service", "change": REQUEST["change"]}, "inconsistent"),
    ({"target": "Payment Service and Checkout Service", "change": REQUEST["change"]}, "ambiguous"),
    ({"target": "Payment Service", "change": "Remove Redis and PostgreSQL from Payment Service"}, "ambiguous"),
    ({"target": "Payment Service", "change": "Upgrade Redis in Payment Service"}, "unsupported"),
    ({"target": "Payment Service", "change": "Replace Redis with PostgreSQL in Payment Service"}, "unsupported"),
    ({"target": "Payment Service", "change": "Remove Redis"}, "unsupported"),
])
def test_unknown_ambiguous_and_unsupported_proposals_never_run_unrelated_tools(body, resolution):
    class NoCalls:
        def __getattr__(self, _):
            pytest.fail("Unsupported proposal attempted a graph call")
    response = TestClient(create_app(Settings(_env_file=None), gateway=NoCalls())).post("/api/change-intelligence", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["support_status"] == "insufficient_evidence" and not data["tools_used"]
    assert data["data"]["proposed_change"]["resolution"] == resolution
    assert not data["sources"] and not data["graph"]["nodes"]
    assert data["data"]["proposed_change"]["service"] is None


def test_structured_aliases_are_only_resolved_after_actual_graph_evidence(freshness_db):
    response = post(freshness_db, body={"target": "service:payment-service", "change": "Remove tech:redis from service:payment-service"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["proposed_change"]["resolution"] == "resolved"


def test_impact_depth_paths_ownership_and_reviewer_rankings_are_preserved(freshness_db):
    body = post(freshness_db).json()
    impact = body["data"]["impact"]
    assert [f["service_id"] for f in impact["direct_impact"]] == ["service:payment-service"]
    assert [(f["service_id"], f["impact_depth"]) for f in impact["indirect_impact"]] == [("service:checkout-service", 2), ("service:order-service", 3)]
    assert impact["indirect_impact"][-1]["path"] == ["tech:redis", "service:payment-service", "service:checkout-service", "service:order-service"]
    edges = {(e["source"], e["type"], e["target"]) for e in body["graph"]["edges"]}
    assert ("service:checkout-service", "DEPENDS_ON", "service:payment-service") in edges
    assert ("service:order-service", "DEPENDS_ON", "service:checkout-service") in edges
    assert ("tech:redis", "USES", "service:payment-service") not in edges
    people = post(freshness_db, path="/api/tools/expert-finder", body={"query": "Who knows Payment Service?"}).json()["data"]["experts"]
    assert body["data"]["reviewers"] == people
    assert all(r["ownership_classification"] != "personal_owner" for r in body["data"]["reviewers"])


def test_current_freshness_and_conditional_future_review_are_distinct(freshness_db):
    body = post(freshness_db).json()["data"]
    assert {f["document_id"] for f in body["current_freshness_findings"]} == {"doc:architecture-overview"}
    future = {f["document"]["id"]: f for f in body["documents_to_review_if_change_proceeds"]}
    assert "doc:ADR-7" in future
    assert future["doc:ADR-7"]["condition"] == "if_change_approved_and_implemented"
    assert "does not establish current staleness" in future["doc:ADR-7"]["reason"]
    assert all(not t["source_ids"] for f in body["current_freshness_findings"] for t in f["triggers"] if t["type"] != "commit")


def test_facts_risk_inference_and_unperformed_recommendations_are_explicit(freshness_db):
    body = post(freshness_db).json()["data"]
    assert {r["classification"] for r in body["risks"]} == {"KNOWN_FACT", "INFERRED_RISK", "RECOMMENDATION"}
    assert all(r["evidence"] and r["uncertainty"] for r in body["risks"])
    assert all(s["performed"] is False and s["classification"] == "RECOMMENDATION" for s in body["validation_steps"])
    assert not any(r["evidence"][0]["source_ids"] for r in body["risks"] if r["classification"] == "KNOWN_FACT")


@pytest.mark.parametrize("failed,removed", [("impact_analysis", "USES"), ("find_expert", "APPROVED"), ("find_stale_knowledge", "DESCRIBES")])
def test_sibling_graphs_cannot_repair_invalid_tool_proofs(freshness_db, monkeypatch, failed, removed):
    gateway = CountingGateway(freshness_db[2])
    original = getattr(gateway, failed)
    async def broken(query):
        result = await original(query)
        result.edges = [e for e in result.edges if e.type != removed]
        return result
    monkeypatch.setattr(gateway, failed, broken)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["support_status"] == "partially_supported"
    assert body["data"]["tool_support"][failed]["state"] == "invalid"
    assert failed not in body["tools_used"]
    if failed == "impact_analysis":
        assert not body["data"]["impact"]["direct_impact"]
    if failed == "find_expert":
        assert not body["data"]["reviewers"]
    if failed == "find_stale_knowledge":
        assert not body["data"]["current_freshness_findings"]


def test_missing_provenance_cannot_supply_rationale_or_inferred_latency_risk(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    async def no_sources(_):
        return []
    monkeypatch.setattr(gateway, "find_sources", no_sources)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["support_status"] == "partially_supported" and not body["sources"]
    assert body["data"]["historical_context"]["support_status"] == "insufficient_evidence"
    assert not any(r["classification"] == "INFERRED_RISK" for r in body["data"]["risks"])
    assert all(not ref["source_ids"] for r in body["data"]["risks"] for ref in r["evidence"])


@pytest.mark.parametrize("damage", ["identity", "source conflict", "size"])
def test_conflicts_and_context_size_fail_closed(freshness_db, monkeypatch, damage):
    gateway = CountingGateway(freshness_db[2])
    if damage == "identity":
        original = gateway.impact_analysis
        async def corrupt(query):
            result = await original(query)
            result.data.entity.label = "private-conflict"
            next(n for n in result.nodes if n.id == "tech:redis").label = "private-conflict"
            return result
        monkeypatch.setattr(gateway, "impact_analysis", corrupt)
    else:
        original = gateway.find_sources
        async def corrupt(ids):
            records = await original(ids)
            if damage == "source conflict":
                records.append(records[0].model_copy(update={"snippet": "private-conflict"}))
            else:
                records[0].metadata["oversized"] = "x" * 160001
            return records
        monkeypatch.setattr(gateway, "find_sources", corrupt)
    response = post(freshness_db, gateway)
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "GRAPH_CONTRACT_ERROR"
    assert "private-conflict" not in response.text


@pytest.mark.parametrize("provider_name", ["none", "openrouter", "ollama"])
def test_change_without_finite_provider_protocol_remains_deterministic(freshness_db, provider_name):
    class NoProviderCalls:
        async def generate(self, *_):
            pytest.fail("Change Intelligence attempted hosted synthesis")
        async def availability(self):
            pytest.fail("Change Intelligence attempted a provider health probe")
    config = freshness_db[2].model_copy(update={"llm_provider": provider_name})
    client = TestClient(create_app(config, provider=NoProviderCalls()))
    first = client.post("/api/change-intelligence", json=REQUEST).json()
    second = client.post("/api/change-intelligence", json=REQUEST).json()
    assert first["metadata"]["generation"] == "deterministic"
    if provider_name == "openrouter":
        assert "OpenRouter synthesis unavailable or rejected" in first["metadata"]["warnings"][-1]
    for field in ("answer", "data", "graph", "sources", "support_status"):
        assert first[field] == second[field]


def test_real_mode_outage_does_not_fall_back_to_fixtures(monkeypatch):
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Fixture fallback"))
    config = Settings(_env_file=None, graph_mode="falkordb", graph_factory="", llm_provider="none")
    response = TestClient(create_app(config)).post("/api/change-intelligence", json=REQUEST)
    assert response.status_code == 503 and response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"


def test_partial_tool_outage_is_preserved_and_sanitized(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    async def unavailable(_):
        raise GraphUnavailable("private-debug")
    monkeypatch.setattr(gateway, "find_expert", unavailable)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["support_status"] == "partially_supported" and not body["data"]["reviewers"]
    assert body["data"]["tool_support"]["find_expert"]["state"] == "unavailable"
    assert "private-debug" not in response.text


def test_explicit_fixture_mode_stays_labeled_and_incomplete():
    config = Settings(_env_file=None, graph_mode="fixture", llm_provider="none")
    response = TestClient(create_app(config)).post("/api/change-intelligence", json=REQUEST)
    assert response.status_code == 200, response.text
    assert response.json()["support_status"] == "partially_supported"
    assert response.json()["metadata"]["warnings"][0].startswith("Development fixture")
    assert not response.json()["data"]["reviewers"]


def test_existing_plan_bound_and_typed_data_are_preserved(freshness_db):
    assert len(change_plan().calls) == 4
    response = asyncio.run(analyze_change(ChangeInput(**REQUEST), CountingGateway(freshness_db[2]), "falkordb"))
    assert len(response.graph.nodes) <= 80 and len(response.graph.edges) <= 200
    assert len(response.answer) <= 6000 and len(response.data.model_dump_json().encode()) <= 160000


def test_unrelated_redis_users_are_not_predicted_to_be_affected_by_this_change(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    original = gateway.impact_analysis
    async def other_user(query):
        result = await original(query)
        node = GraphNode(id="service:unrelated", type="Service", label="Unrelated Service",
                         properties={"id": "service:unrelated", "name": "Unrelated Service"})
        result.nodes.append(node)
        result.edges.append(GraphEdge(id="unrelated-use", source=node.id, type="USES", target="tech:redis"))
        first = result.data.direct_impact[0].model_copy(deep=True)
        first.service_id, first.service = node.id, node.properties
        first.path = ["tech:redis", node.id]
        first.path_edges[0].source = node.id
        first.owners, first.related_issues, first.related_incidents = [], [], []
        result.data.direct_impact.append(first)
        return result
    monkeypatch.setattr(gateway, "impact_analysis", other_user)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "service:unrelated" in {n["id"] for n in body["graph"]["nodes"]}  # full bounded evidence remains inspectable
    assert all(f["service_id"] != "service:unrelated" for f in body["data"]["impact"]["direct_impact"])
    assert all("service:unrelated" not in r["affected_entity_ids"] for r in body["data"]["risks"])


def test_missing_uses_edges_cannot_be_inferred_from_properties_or_sibling_nodes(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    for name in ("trace_decision", "impact_analysis", "find_expert"):
        original = getattr(gateway, name)
        async def missing(query, original=original):
            result = await original(query)
            graph = result.graph if hasattr(result, "graph") else result
            graph.edges = [e for e in graph.edges if e.type != "USES"]
            return result
        monkeypatch.setattr(gateway, name, missing)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["support_status"] == "insufficient_evidence"
    assert body["data"]["proposed_change"]["resolution"] == "unresolved"
    assert not body["data"]["risks"] and not body["data"]["documents_to_review_if_change_proceeds"]


def test_trace_cannot_borrow_rationale_chunks_from_other_capabilities(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    original = gateway.trace_decision
    async def no_provenance(query):
        result = await original(query)
        result.graph.edges = [e for e in result.graph.edges if not e.type.startswith("FROM_")]
        return result
    monkeypatch.setattr(gateway, "trace_decision", no_provenance)
    body = post(freshness_db, gateway).json()
    assert any(e["type"] == "FROM_ISSUE" for e in body["graph"]["edges"])
    assert body["data"]["historical_context"]["support_status"] != "supported"
    assert not any(r["classification"] == "INFERRED_RISK" for r in body["data"]["risks"])


def test_latency_inference_uses_only_the_existing_rationale_citation(freshness_db):
    response = post(freshness_db).json()
    body = response["data"]
    history = body["historical_context"]["summary"]
    inference = next(r for r in body["risks"] if r["classification"] == "INFERRED_RISK")
    ids = inference["evidence"][0]["source_ids"]
    assert ids and all(f"[{id}]" in history for id in ids)
    assert all(f"{s['snippet']} [{s['id']}]" in history for s in response["sources"] if s["id"] in ids)
    assert "doc:ADR-7" not in ids and "commit:8fae2" not in ids


def test_future_document_review_requires_a_genuine_local_association(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    for name in ("trace_decision", "find_stale_knowledge"):
        original = getattr(gateway, name)
        async def disconnect(query, original=original):
            result = await original(query)
            graph = result.graph if hasattr(result, "graph") else result
            graph.edges = [e for e in graph.edges if not (e.target == "doc:ADR-7" and e.type == "DOCUMENTED_IN")
                           and not (e.source == "doc:ADR-7" and e.type == "DESCRIBES")]
            return result
        monkeypatch.setattr(gateway, name, disconnect)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "doc:ADR-7" in {n["id"] for n in body["graph"]["nodes"]}
    assert "doc:ADR-7" not in {d["document"]["id"] for d in body["data"]["documents_to_review_if_change_proceeds"]}


def test_source_outage_retains_only_qualified_structural_evidence(freshness_db, monkeypatch):
    gateway = CountingGateway(freshness_db[2])
    async def unavailable(_):
        raise GraphUnavailable("private-source-debug")
    monkeypatch.setattr(gateway, "find_sources", unavailable)
    response = post(freshness_db, gateway)
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body["sources"] and body["support_status"] == "partially_supported"
    assert any("Source retrieval is unavailable" in w for w in body["metadata"]["warnings"])
    assert "private-source-debug" not in response.text


@pytest.mark.parametrize("path,body,tool", [
    ("/api/query", {"question": "Why does Payment Service use Redis?"}, "trace_decision"),
    ("/api/tools/impact-analysis", {"entity_id": "service:payment-service"}, "impact_analysis"),
    ("/api/tools/expert-finder", {"query": "Who knows Payment Service?"}, "find_expert"),
    ("/api/tools/freshness", {"entity": "Payment Service"}, "find_stale_knowledge"),
])
def test_existing_endpoints_keep_their_grounded_contracts(freshness_db, path, body, tool):
    response = post(freshness_db, path=path, body=body)
    assert response.status_code == 200, response.text
    result = response.json()
    expected = {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert set(result) == (expected if path == "/api/query" else expected | {"data"})
    assert result["tools_used"] == [tool]


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_CHANGE_INTEGRATION") != "1",
                    reason="Requires actual seeded NovaPay FalkorDB and real Phase 2 adapters")
def test_real_seeded_change_brief_without_fixtures_or_hosted_generation(monkeypatch):
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Real Change workflow used fixture"))
    config = Settings(graph_mode="falkordb", source_backend="weave_data", llm_provider="none")
    assert config.graph_factory == "app.antony:create_gateway"
    with TestClient(create_app(config)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["falkordb"] == "connected"
        response = client.post("/api/change-intelligence", json=REQUEST)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["support_status"] == "partially_supported" and body["metadata"]["generation"] == "deterministic"
        assert body["data"]["proposed_change"]["resolution"] == "resolved"
        assert body["data"]["historical_context"]["support_status"] == "supported"
        assert any(n["id"] == "decision:D-007" and n["properties"]["status"] == "accepted" for n in body["graph"]["nodes"])
        assert {s["id"] for s in body["sources"]} >= {"issue:PAY-42", "message:payment-perf-7", "doc:ADR-7", "commit:8fae2", "doc:architecture-overview"}
        assert all(s["metadata"]["chunk_ids"] and s["metadata"]["chunks"] for s in body["sources"])
        assert {f["service_id"] for f in body["data"]["impact"]["indirect_impact"]} == {"service:checkout-service", "service:order-service"}
        assert {d["document"]["id"] for d in body["data"]["documents_to_review_if_change_proceeds"]} >= {"doc:ADR-7"}
