"""Actual merged trace and source functions, with explicit offline database doubles."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.antony import AntonyGateway, normalize_trace
from app.config import Settings
from app.context import build_context
from app.graph import FalkorGateway, FixtureGateway, GraphContractError
from app.main import create_app
from app.models import TraceInput
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import prepare_ingestion, run_ingestion
from weave_graph.trace import trace_decision

DATA = Path(__file__).resolve().parents[2] / "data" / "novapay"
IDS = {"issue:PAY-42", "message:payment-perf-7", "commit:8fae2", "doc:ADR-7"}
TARGET = TraceInput(service="Payment Service", technology="Redis")


@pytest.fixture
def merged_database(monkeypatch):
    records, edges, chunks, _, validation = prepare_ingestion(DATA)
    assert validation.ok
    nodes = {r.id: SimpleNamespace(properties=r.model_dump(mode="json"), labels=[r.entity_type.value])
             for r in records}
    calls, closed = [], []
    store = InMemoryGraphAdapter()
    assert run_ingestion(DATA, store).status == "success"

    class ClientDouble:
        def __init__(self, **kwargs):
            assert kwargs["graph_name"] == "novapay"
            calls.append(kwargs)

        def execute(self, query, params):
            if "RETURN d, s, t" in query:
                assert params == {"service_id": "service:payment-service", "technology_id": "tech:redis"}
                rows = [(nodes["decision:D-007"], nodes[params["service_id"]], nodes[params["technology_id"]])]
            elif "RETURN type(r), e" in query:
                rows = [(e.rel_type, nodes[e.target_id]) for e in edges
                        if e.source_id == params["decision_id"] and e.rel_type in {
                            "SUPPORTED_BY", "IMPLEMENTED_BY", "DOCUMENTED_IN"}]
            elif "RETURN s, r, t" in query:
                rows = [(nodes[e.source_id], SimpleNamespace(properties=e.properties or {}), nodes[e.target_id])
                        for e in edges if e.rel_type == "USES" and e.source_id == params["service_id"]
                        and e.target_id == params["technology_id"]]
            elif "RETURN i, r, issue" in query:
                rows = [(nodes[e.source_id], SimpleNamespace(properties=e.properties or {}), nodes[e.target_id])
                        for e in edges if e.rel_type == "LED_TO" and e.source_id == params["incident_id"]
                        and e.target_id == params["issue_id"]]
            else:
                assert "RETURN c, type(r), source.id" in query
                rows = [(SimpleNamespace(properties=c.model_dump(mode="json")),
                         f"FROM_{c.source_type.upper()}", c.source_id)
                        for c in chunks if c.source_id in params["source_ids"]]
            return SimpleNamespace(result_set=rows)

        def health_check(self):
            return True

        def close(self):
            closed.append(True)

    class SourceDouble:
        def __init__(self, **kwargs):
            assert kwargs["graph_name"] == "novapay"
        def get_chunks_for_sources(self, ids):
            return store.get_chunks_for_sources(ids)
        def close(self):
            pass

    monkeypatch.setattr("weave_graph.client.GraphClient", ClientDouble)
    monkeypatch.setattr("weave_data.graph_adapter.FalkorDBGraphAdapter", SourceDouble)
    def no_fixture(*_args, **_kwargs):
        pytest.fail("Real integration used development fixtures")
    monkeypatch.setattr(FixtureGateway, "__init__", no_fixture)
    return ClientDouble, calls, closed


@pytest.mark.parametrize("query", [TARGET, TraceInput(service="service:payment-service", technology="tech:redis")])
def test_actual_trace_normalization_and_canonical_inputs(merged_database, query):
    _, calls, closed = merged_database
    trace = asyncio.run(AntonyGateway(Settings(graph_mode="falkordb")).trace_decision(query))
    assert set(trace.source_ids) == IDS
    assert trace.decision_ids == ["decision:D-007"]
    decision = next(n for n in trace.graph.nodes if n.id == "decision:D-007")
    assert decision.properties["status"] == "accepted"
    assert any(e.type == "SUPPORTED_BY" and e.target == "message:payment-perf-7" for e in trace.graph.edges)
    assert len([n for n in trace.graph.nodes if n.type == "Chunk"]) == 4
    signatures = {(e.source, e.type, e.target) for e in trace.graph.edges}
    assert ("service:payment-service", "USES", "tech:redis") in signatures
    assert ("incident:INC-17", "LED_TO", "issue:PAY-42") in signatures
    assert trace.warnings == []
    assert len(calls) == len(closed) == 1


def test_complete_merged_offline_api_path_recognizes_supported_provenance(merged_database):
    config = Settings(graph_mode="falkordb", graph_factory="app.antony:create_gateway",
                      source_backend="weave_data", llm_provider="none")
    with TestClient(create_app(config)) as client:
        response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert data["tools_used"] == ["trace_decision"]
    assert data["support_status"] == "supported"
    assert {s["id"] for s in data["sources"]} == IDS
    assert all(s["metadata"]["chunk_ids"] and s["timestamp"] for s in data["sources"])
    assert any("latency" in s["snippet"].lower() for s in data["sources"])
    assert "[issue:PAY-42]" in data["answer"]
    assert "[decision:D-007]" not in data["answer"]


def test_do_not_turn_decision_summary_into_a_fabricated_source(merged_database):
    gateway = AntonyGateway(Settings(graph_mode="falkordb"))
    trace = asyncio.run(gateway.trace_decision(TARGET))
    sources = asyncio.run(gateway.find_sources(trace.source_ids))
    before = trace.model_dump()
    # The retrieved multi-hop path supplies provenance without a synthetic Decision source.
    assert any(e.type == "USES" for e in trace.graph.edges)
    context = build_context(trace, sources, TARGET)
    assert context.status == "supported" and context.can_explain
    assert all(s.id != "decision:D-007" for s in sources)
    assert context.graph.model_dump() == trace.graph.model_dump() == before["graph"]
    assert "[decision:D-007]" not in context.summary


def test_retrieved_message_path_can_ground_rationale_without_issue_path(merged_database):
    gateway = AntonyGateway(Settings(graph_mode="falkordb"))
    trace = asyncio.run(gateway.trace_decision(TARGET))
    sources = asyncio.run(gateway.find_sources(trace.source_ids))
    trace.graph.edges = [e for e in trace.graph.edges
                         if not (e.type == "SUPPORTED_BY" and e.target == "issue:PAY-42")]
    context = build_context(trace, sources, TARGET)
    assert context.status == "supported" and context.can_explain
    assert "[message:payment-perf-7]" in context.summary


@pytest.mark.parametrize("missing", ["decision_support", "chunk_provenance"])
def test_actual_pipeline_cannot_ground_rationale_without_retrieved_path(merged_database, missing):
    gateway = AntonyGateway(Settings(graph_mode="falkordb"))
    trace = asyncio.run(gateway.trace_decision(TARGET))
    sources = asyncio.run(gateway.find_sources(trace.source_ids))
    kinds = {"SUPPORTED_BY"} if missing == "decision_support" else {"FROM_ISSUE", "FROM_MESSAGE"}
    trace.graph.edges = [e for e in trace.graph.edges if e.type not in kinds]
    context = build_context(trace, sources, TARGET)
    assert context.status == "partially_supported" and not context.can_explain


def test_missing_decision_is_insufficient_without_sources():
    payload = {"data": {"decision": None}, "sources": [], "nodes": [], "edges": [], "error": "not found"}
    trace = normalize_trace(payload)
    assert trace.graph.nodes == [] and trace.source_ids == []
    assert build_context(trace, [], TARGET).status == "insufficient_evidence"


def test_proposed_actual_decision_remains_proposed(merged_database):
    client_class, _, _ = merged_database
    payload = trace_decision(client_class(graph_name="novapay"))
    payload["data"]["decision"]["status"] = "proposed"
    payload["data"]["decision_status"] = "proposed"
    trace = normalize_trace(payload)
    assert next(n for n in trace.graph.nodes if n.type == "Decision").properties["status"] == "proposed"
    context = build_context(trace, [], TARGET)
    assert context.status == "insufficient_evidence" and not context.can_explain


def test_client_uses_configured_graph_credentials_timeouts_and_existing_graph_health(monkeypatch):
    from weave_graph.client import GraphClient
    captured = {}
    class GraphDouble:
        def query(self, query, params=None, timeout=None):
            captured.update(query=query, params=params, timeout=timeout)
            return SimpleNamespace(result_set=[[1]])
    class DatabaseDouble:
        def __init__(self, **kwargs):
            captured["options"] = kwargs
            self.connection = self
        def select_graph(self, name):
            captured["graph"] = name
            return GraphDouble()
        def list_graphs(self):
            return ["novapay"]
        def close(self):
            captured["closed"] = True
    monkeypatch.setattr("weave_graph.client.FalkorDB", DatabaseDouble)
    client = GraphClient(host="graph.test", port=6380, graph_name="novapay",
                         username="test-user", password="test-only-password", ssl=True)
    assert client.health_check()
    assert captured["graph"] == "novapay"
    assert captured["options"]["ssl"] is True
    assert captured["options"]["password"] == "test-only-password"
    assert captured["timeout"] == 5000
    monkeypatch.setattr(client.db, "list_graphs", lambda: [])
    assert client.health_check() is False
    client.close()
    assert captured["closed"]


@pytest.mark.parametrize("damage", ["status", "decision", "source", "envelope"])
def test_invalid_actual_tool_payload_is_a_contract_error(merged_database, damage):
    client_class, _, _ = merged_database
    payload = trace_decision(client_class(graph_name="novapay"))
    if damage == "status":
        payload["data"]["decision_status"] = "accepted-but-not-real"
    elif damage == "decision":
        payload["nodes"][0]["properties"] = {"status": "proposed"}
    elif damage == "source":
        payload["sources"][0]["id"] = None
    else:
        payload = {"nodes": []}
    with pytest.raises(GraphContractError):
        normalize_trace(payload)


def test_unavailable_actual_client_returns_sanitized_graph_error(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("private-database-password")
    monkeypatch.setattr("weave_graph.client.GraphClient", fail)
    config = Settings(graph_mode="falkordb", graph_factory="app.antony:create_gateway",
                      source_backend="weave_data")
    with TestClient(create_app(config)) as client:
        response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
    assert "private-database-password" not in response.text


def test_factory_reuses_actual_client_health_and_closes_it(merged_database):
    _, calls, closed = merged_database
    gateway = FalkorGateway(Settings(graph_mode="falkordb", graph_factory="app.antony:create_gateway",
                                    source_backend="weave_data"))
    assert asyncio.run(gateway.health()) is True
    assert len(calls) == len(closed) == 1


@pytest.mark.parametrize("relationship, query_marker", [("USES", "RETURN s, r, t"), ("LED_TO", "RETURN i, r, issue")])
def test_latest_missing_path_warnings_survive_normalization(merged_database, monkeypatch, relationship, query_marker):
    client_class, _, _ = merged_database
    original = client_class.execute
    def missing_path(self, query, params):
        if query_marker in query:
            return SimpleNamespace(result_set=[])
        return original(self, query, params)
    monkeypatch.setattr(client_class, "execute", missing_path)
    trace = asyncio.run(AntonyGateway(Settings(graph_mode="falkordb")).trace_decision(TARGET))
    assert not any(e.type == relationship for e in trace.graph.edges)
    assert len([w for w in trace.warnings if f"Missing {relationship} relationship" in w]) == 1


def test_latest_missing_provenance_warning_is_not_discarded(merged_database, monkeypatch):
    client_class, _, _ = merged_database
    original = client_class.execute
    def missing_chunks(self, query, params):
        if "RETURN c, type(r), source.id" in query:
            return SimpleNamespace(result_set=[])
        return original(self, query, params)
    monkeypatch.setattr(client_class, "execute", missing_chunks)
    trace = asyncio.run(AntonyGateway(Settings(graph_mode="falkordb")).trace_decision(TARGET))
    assert any(w.startswith("Missing linked evidence chunks for:") for w in trace.warnings)
    assert not trace.source_ids
    assert not any(n.type == "Chunk" for n in trace.graph.nodes)


def test_latest_teammate_smoke_assertions_pass_with_offline_database(merged_database, monkeypatch, capsys):
    from weave_graph import test_trace
    monkeypatch.setattr(test_trace, "GraphClient", merged_database[0])
    test_trace.main()
    assert "Decision trace regression test: PASS" in capsys.readouterr().out
