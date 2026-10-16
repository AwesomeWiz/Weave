import asyncio
import sys
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.context import build_context, safe_url
from app.graph import FalkorGateway, FixtureGateway, GraphContractError, GraphUnavailable
from app.llm import OllamaProvider
from app.main import create_app
from app.models import GraphEdge, QueryResponse, TraceInput, TraceResult
from app.router import route_question

QUESTION = "Why does Payment Service use Redis?"
TARGET = TraceInput(service="Payment Service", technology="Redis")


@pytest.fixture
def fixture_gateway():
    return FixtureGateway()


@pytest.fixture
def client(fixture_gateway):
    with TestClient(create_app(Settings(graph_mode="fixture", llm_provider="none"),
                              gateway=fixture_gateway)) as client:
        yield client


def test_health_fixture_honestly_reports_no_falkordb(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["falkordb"] == "not_checked"
    assert data["graph_tool"] == "fixture"
    assert data["llm"] == "disabled"


def test_fixture_query_contract_and_canonical_evidence(client):
    response = client.post("/api/query", json={"question": QUESTION, "session_id": "demo-session"})
    assert response.status_code == 200
    data = QueryResponse.model_validate(response.json())
    assert data.support_status == "supported"
    assert data.tools_used == ["trace_decision"]
    assert data.metadata.graph_mode == "fixture"
    assert "Development fixture" in data.metadata.warnings[0]
    assert data.answer and len(data.sources) == 6 and len(data.graph.edges) > 0
    ids = {node.id for node in data.graph.nodes}
    assert {"decision:D-007", "service:payment-service", "tech:redis"} <= ids
    assert all(source.metadata["synthetic"] for source in data.sources)
    assert all(edge.source in ids and edge.target in ids for edge in data.graph.edges)


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "  "},
                                 {"question": "x" * 2001}, {"question": 1},
                                 {"question": QUESTION, "session_id": "x" * 129},
                                 {"question": QUESTION, "cypher": "MATCH (n) RETURN n"}])
def test_invalid_request_is_sanitized(client, body):
    response = client.post("/api/query", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "traceback" not in response.text.lower()


def test_unsupported_question_has_no_made_up_evidence(client):
    data = client.post("/api/query", json={"question": "Why does Fraud Service use MongoDB?"}).json()
    assert data["support_status"] == "insufficient_evidence"
    assert data["sources"] == [] and data["graph"]["nodes"] == [] and data["tools_used"] == []


def test_router_word_boundaries_and_phase_two_questions():
    assert route_question("Why was Redis introduced?") == TARGET
    assert route_question("Why was Redis introduced in Payment Service?") == TARGET
    assert route_question("Why does Nonpayment Service use Redis?") is None
    assert route_question("Why does Payment Service use Redis, and what breaks if removed?") is None


def test_real_mode_without_tool_never_substitutes_fixture(monkeypatch):
    gateway = FalkorGateway(Settings(graph_mode="falkordb", graph_factory=""))

    async def db_health():
        return False

    monkeypatch.setattr(gateway, "database_health", db_health)
    with TestClient(create_app(Settings(graph_mode="falkordb"), gateway=gateway)) as client:
        health = client.get("/api/health")
        assert health.status_code == 503
        assert health.json()["status"] == "unavailable"
        assert health.json()["falkordb"] == "unavailable"
        response = client.post("/api/query", json={"question": QUESTION})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
        assert "sources" not in response.json()


def test_connected_database_without_graph_tool_is_still_unavailable(monkeypatch):
    gateway = FalkorGateway(Settings(graph_factory=""))

    async def db_health():
        return True

    monkeypatch.setattr(gateway, "database_health", db_health)
    client = TestClient(create_app(Settings(graph_mode="falkordb"), gateway=gateway))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["falkordb"] == "connected"
    assert response.json()["graph_tool"] == "unavailable"


def test_replaceable_factory_and_output_normalization(monkeypatch, fixture_gateway):
    class TeamGateway:
        async def health(self):
            return True

        async def trace_decision(self, query):
            assert query == TARGET
            return fixture_gateway.trace.model_dump()

        async def find_sources(self, ids):
            return [s.model_dump() for s in fixture_gateway.sources if s.id in ids]

    module = types.ModuleType("test_team_adapter")
    module.create = lambda settings: TeamGateway()
    monkeypatch.setitem(sys.modules, "test_team_adapter", module)
    gateway = FalkorGateway(Settings(graph_factory="test_team_adapter:create"))
    trace = asyncio.run(gateway.trace_decision(TARGET))
    assert isinstance(trace, TraceResult)
    assert trace.decision_ids == ["decision:D-007"]
    sources = asyncio.run(gateway.find_sources(trace.source_ids))
    assert len(sources) == 6 and sources[0].id in trace.source_ids


def test_bad_factory_is_unavailable_and_does_not_leak_error():
    gateway = FalkorGateway(Settings(graph_factory="missing_secret_module:create"))
    assert not asyncio.run(gateway.health())
    with pytest.raises(GraphUnavailable):
        asyncio.run(gateway.trace_decision(TARGET))


def test_context_deduplicates_and_preserves_canonical_paths(fixture_gateway):
    original = fixture_gateway.trace.model_copy(deep=True)
    original.graph.nodes.append(original.graph.nodes[0])
    original.graph.edges.append(original.graph.edges[0])
    sources = fixture_gateway.sources + [fixture_gateway.sources[0].model_copy(update={"snippet": "short"})]
    context = build_context(original, sources, TARGET)
    assert len(context.sources) == 6
    assert len(context.graph.nodes) == 12
    assert len(context.graph.edges) == 14
    assert context.sources[0].snippet != "short"
    assert "decision:D-007" in context.prompt_json()
    assert context.status == "supported"


def test_dangling_edges_rejected(fixture_gateway):
    fixture_gateway.trace.graph.edges.append(GraphEdge(
        id="bad", source="missing", target="tech:redis", type="USES",
    ))
    with pytest.raises(GraphContractError):
        build_context(fixture_gateway.trace, fixture_gateway.sources, TARGET)


def test_missing_introduces_edge_changes_answer_and_support(fixture_gateway):
    trace = fixture_gateway.trace
    trace.graph.edges = [e for e in trace.graph.edges if e.type != "INTRODUCES"]
    context = build_context(trace, fixture_gateway.sources, TARGET)
    assert context.status == "partially_supported"
    assert "couldn't find enough connected evidence" in context.summary
    assert "Redis was introduced" not in context.summary


def test_missing_sources_reduce_support(fixture_gateway):
    context = build_context(fixture_gateway.trace, fixture_gateway.sources[1:], TARGET)
    assert context.status == "partially_supported"
    assert context.warnings


def test_no_sources_is_insufficient_but_graph_retained(fixture_gateway):
    context = build_context(fixture_gateway.trace, [], TARGET)
    assert context.status == "insufficient_evidence"
    assert context.graph.nodes


def test_source_failure_preserves_graph(fixture_gateway):
    async def unavailable_sources(_ids):
        raise GraphUnavailable()

    fixture_gateway.find_sources = unavailable_sources
    client = TestClient(create_app(Settings(graph_mode="fixture"), gateway=fixture_gateway))
    data = client.post("/api/query", json={"question": QUESTION}).json()
    assert data["support_status"] == "insufficient_evidence"
    assert data["graph"]["nodes"] and data["sources"] == []


def test_llm_failure_keeps_answer_sources_and_graph(fixture_gateway):
    class BrokenProvider:
        async def availability(self):
            return "unavailable"

        async def generate(self, *_args):
            raise RuntimeError("secret-token-should-not-leak")

    client = TestClient(create_app(Settings(graph_mode="fixture", llm_provider="ollama"),
                                  gateway=fixture_gateway, provider=BrokenProvider()))
    response = client.post("/api/query", json={"question": QUESTION})
    data = response.json()
    assert data["answer"] and data["sources"] and data["graph"]["edges"]
    assert data["metadata"]["generation"] == "deterministic"
    assert "secret-token" not in response.text
    assert any("LLM generation unavailable" in w for w in data["metadata"]["warnings"])


def test_empty_graph_insufficient(fixture_gateway):
    fixture_gateway.trace = TraceResult()
    client = TestClient(create_app(Settings(graph_mode="fixture"), gateway=fixture_gateway))
    data = client.post("/api/query", json={"question": QUESTION}).json()
    assert data["support_status"] == "insufficient_evidence"
    assert data["graph"]["nodes"] == []


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,test", "file:///etc/passwd",
                                 "https://user:secret@example.org/", "https://example.invalid/doc"])
def test_unsafe_source_urls(url):
    assert safe_url(url) is None


def test_safe_source_url():
    assert safe_url("https://example.org/adr/7") == "https://example.org/adr/7"


def test_cors(client):
    response = client.options("/api/query", headers={"Origin": "http://localhost:5173",
                                                    "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_ollama_response_validation(monkeypatch, fixture_gateway):
    context = build_context(fixture_gateway.trace, fixture_gateway.sources, TARGET)

    async def post(_self, _url, **kwargs):
        assert kwargs["json"]["stream"] is False
        return httpx.Response(200, request=httpx.Request("POST", "http://localhost/api/chat"),
                              json={"message": {"content": '{"answer":"Invented", "source_ids":["unknown"]}'}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = OllamaProvider(Settings(llm_provider="ollama"))
    with pytest.raises(ValueError):
        asyncio.run(provider.generate(QUESTION, context))


def test_ollama_success_and_model_availability(monkeypatch, fixture_gateway):
    context = build_context(fixture_gateway.trace, fixture_gateway.sources, TARGET)

    async def get(_self, _url):
        return httpx.Response(200, request=httpx.Request("GET", "http://localhost/api/tags"),
                              json={"models": [{"name": "qwen2.5:7b"}]})

    async def post(_self, _url, **kwargs):
        assert "decision:D-007" in kwargs["json"]["messages"][1]["content"]
        return httpx.Response(200, request=httpx.Request("POST", "http://localhost/api/chat"),
                              json={"message": {"content": '{"answer":"Redis caches selected '
                                    'payment reads [decision:D-007].", '
                                    '"source_ids":["decision:D-007"]}'}})

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = OllamaProvider(Settings(llm_provider="ollama"))
    assert asyncio.run(provider.availability()) == "available"
    assert "[decision:D-007]" in asyncio.run(provider.generate(QUESTION, context))


def test_missing_core_relationship_never_calls_llm(fixture_gateway):
    fixture_gateway.trace.graph.edges = [e for e in fixture_gateway.trace.graph.edges
                                         if e.type != "INTRODUCES"]

    class MustNotGenerate:
        async def availability(self):
            return "available"

        async def generate(self, *_args):
            pytest.fail("Incomplete rationale must not be explained by an LLM")

    client = TestClient(create_app(Settings(graph_mode="fixture", llm_provider="ollama"),
                                  gateway=fixture_gateway, provider=MustNotGenerate()))
    response = client.post("/api/query", json={"question": QUESTION})
    assert response.json()["support_status"] == "partially_supported"
    assert response.json()["metadata"]["generation"] == "deterministic"

