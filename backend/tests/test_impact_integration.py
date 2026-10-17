"""Actual merged impact/retrieval functions against an explicit offline database double."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.antony import AntonyGateway, normalize_impact
from app.config import Settings
from app.graph import FalkorGateway, FixtureGateway, GraphContractError
from app.impact import build_impact_context
from app.main import create_app
from app.models import ImpactInput
from app.router import route_question
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion
from weave_graph.impact import impact_analysis

PAYMENT = "service:payment-service"
CHECKOUT = "service:checkout-service"
ORDER = "service:order-service"
REDIS = "tech:redis"


@pytest.fixture
def database(monkeypatch):
    store = InMemoryGraphAdapter()
    assert run_ingestion(Path(__file__).resolve().parents[2] / "data/novapay", store).status == "success"
    calls, closed = [], []

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def execute(self, query, params):
            calls.append((query, params))
            nodes = {id: SimpleNamespace(labels=[n["entity_type"]],
                                         properties={k: v for k, v in n.items() if k != "entity_type"})
                     for id, n in store.all_nodes().items()}
            edges = list(store.all_relationships().values())
            if "RETURN n" in query:
                rows = [(nodes[params["entity_id"]],)] if params["entity_id"] in nodes else []
            elif "RETURN s\n" in query:
                rows = [(nodes[params["service_id"]],)]
            elif "RETURN c, type(r), source.id" in query:
                rows = [(nodes[e["source_id"]], e["rel_type"], e["target_id"])
                        for e in edges if e["rel_type"].startswith("FROM_")
                        and e["target_id"] in params["source_ids"]]
            else:
                if "RETURN dependent, r, dependency" in query:
                    kind, label, target = "DEPENDS_ON", "Service", params["dependency_id"]
                elif "RETURN s, r, t" in query:
                    kind, label, target = "USES", "Service", params["entity_id"]
                elif "RETURN team, r, s" in query:
                    kind, label, target = "OWNS", "Team", params["service_id"]
                elif "RETURN issue, r, s" in query:
                    kind, label, target = "AFFECTS", "Issue", params["service_id"]
                elif "RETURN incident, r, s" in query:
                    kind, label, target = "AFFECTS", "Incident", params["service_id"]
                else:
                    assert "RETURN incident, r, issue" in query
                    kind, label, target = "LED_TO", "Incident", params["issue_id"]
                rows = [(nodes[e["source_id"]], SimpleNamespace(properties=e["properties"]), nodes[target])
                        for e in edges if e["rel_type"] == kind and e["target_id"] == target
                        and nodes[e["source_id"]].labels == [label]]
                rows.sort(key=lambda row: row[0].properties["id"])
            return SimpleNamespace(result_set=rows)

        def health_check(self):
            return True

        def close(self):
            closed.append(True)

    class SourceClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def get_chunks_for_sources(self, ids):
            return store.get_chunks_for_sources(ids)

        def close(self):
            closed.append(True)

    monkeypatch.setattr("weave_graph.client.GraphClient", Client)
    monkeypatch.setattr("weave_data.graph_adapter.FalkorDBGraphAdapter", SourceClient)
    config = Settings(graph_mode="falkordb", graph_name="novapay", source_backend="weave_data",
                      graph_factory="app.antony:create_gateway", llm_provider="none")
    return store, Client, config, closed


def retrieve(database, entity=PAYMENT, depth=2):
    _, _, config, _ = database
    gateway = AntonyGateway(config)
    query = ImpactInput(entity_id=entity, max_depth=depth)
    result = asyncio.run(gateway.impact_analysis(query))
    records = asyncio.run(gateway.find_sources(list(dict.fromkeys(s.id for s in result.sources))))
    context, data = build_impact_context(result, records, query)
    return result, records, context, data


def test_actual_tool_direct_indirect_ownership_and_canonical_retrieval(database):
    result, records, context, data = retrieve(database)
    assert [f.service_id for f in data.direct_impact] == [CHECKOUT]
    assert [f.service_id for f in data.indirect_impact] == [ORDER]
    assert data.indirect_impact[0].path == [PAYMENT, CHECKOUT, ORDER]
    assert data.direct_impact[0].owners[0].id == "team:platform"
    assert {s.id for s in records} == {"issue:PAY-42"}
    assert context.sources[0].metadata["chunk_ids"] == ["chunk:issue:PAY-42:0"]
    assert context.sources[0].metadata["source_id"] == "issue:PAY-42"
    assert context.graph.edges == result.edges
    assert {item.id for item in data.related_incidents} == {"incident:INC-17"}
    assert any(e.source == "incident:INC-17" and e.type == "LED_TO" and e.target == "issue:PAY-42"
               for e in context.graph.edges)
    assert context.status == "partially_supported" and not context.can_explain
    assert "guaranteed failure" in context.summary
    assert "[issue:PAY-42]" in context.summary
    # PAY-42 affects the target, not Checkout or Order. Do not attach it to them.
    assert all(not f.source_ids for f in data.direct_impact + data.indirect_impact)
    assert PAYMENT not in {f.service_id for f in data.direct_impact + data.indirect_impact}
    assert len(database[3]) == 2


@pytest.mark.parametrize("depth,expected", [(1, [PAYMENT]), (2, [PAYMENT, CHECKOUT]), (3, [PAYMENT, CHECKOUT, ORDER])])
def test_technology_impact_depth_and_original_direction(database, depth, expected):
    _, _, context, data = retrieve(database, REDIS, depth)
    findings = data.direct_impact + data.indirect_impact
    assert [f.service_id for f in findings] == expected
    assert findings[0].path_edges[0].model_dump() == {"source": PAYMENT, "type": "USES", "target": REDIS}
    assert all(f.impact_depth <= depth for f in findings)
    assert findings[0].source_ids == ["issue:PAY-42"]
    assert context.status == "partially_supported"


def test_cycles_diamonds_duplicate_suppression_and_direction(database):
    store = database[0]
    store.upsert_relationship(PAYMENT, "DEPENDS_ON", ORDER)
    store.upsert_relationship(ORDER, "DEPENDS_ON", PAYMENT)
    result, _, _, data = retrieve(database, depth=3)
    findings = data.direct_impact + data.indirect_impact
    assert {f.service_id for f in findings} == {CHECKOUT, ORDER}
    assert all(f.impact_depth == 1 for f in findings)
    assert len(findings) == 2
    assert len({e.id for e in result.edges}) == len(result.edges)
    assert all(len(f.path) == len(set(f.path)) for f in findings)


def test_no_sources_retains_structural_graph(database):
    result, _, _, _ = retrieve(database)
    context, _ = build_impact_context(result, [], ImpactInput(entity_id=PAYMENT))
    assert context.status == "partially_supported" and context.graph.edges and not context.sources
    assert any("provenance" in w for w in context.warnings)


def test_service_depth_one_excludes_indirect(database):
    _, _, _, data = retrieve(database, depth=1)
    assert [f.service_id for f in data.direct_impact] == [CHECKOUT]
    assert data.indirect_impact == []


def test_source_association_requires_actual_affected_service_path(database):
    # Explicit test graph relationship, not a fabricated source-to-service label.
    database[0].upsert_relationship("issue:PAY-42", "AFFECTS", CHECKOUT)
    _, _, _, data = retrieve(database)
    assert data.direct_impact[0].source_ids == ["issue:PAY-42"]
    assert data.indirect_impact[0].source_ids == []


def test_duplicate_identical_findings_are_deduplicated(database):
    result, records, _, _ = retrieve(database)
    result.data.direct_impact.append(result.data.direct_impact[0].model_copy(deep=True))
    _, data = build_impact_context(result, records, ImpactInput(entity_id=PAYMENT))
    assert len(data.direct_impact) == 1


def test_focus_bounds_are_enforced_before_source_retrieval():
    with pytest.raises(GraphContractError):
        normalize_impact({"data": {}, "sources": [{"id": f"issue:{i}"} for i in range(41)]})


def test_source_outage_retains_graph_and_deterministic_limits(database, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private-database-debug")
    monkeypatch.setattr("weave_data.graph_adapter.FalkorDBGraphAdapter", unavailable)
    response = TestClient(create_app(database[2])).post("/api/tools/impact-analysis", json={"entity_id": PAYMENT})
    assert response.status_code == 200 and "private-database-debug" not in response.text
    result = response.json()
    assert result["graph"]["edges"] and not result["sources"]
    assert result["support_status"] == "partially_supported"
    assert any("Source retrieval is unavailable" in w for w in result["metadata"]["warnings"])


@pytest.mark.parametrize("damage", ["edge", "direction", "depth", "cycle", "owner", "properties", "dangling", "target"])
def test_invalid_impact_claims_are_rejected(database, damage):
    result, records, _, _ = retrieve(database)
    finding = result.data.direct_impact[0]
    if damage == "edge":
        result.edges = [e for e in result.edges if e.type != "DEPENDS_ON"]
    elif damage == "direction":
        finding.path_edges[0].source, finding.path_edges[0].target = PAYMENT, CHECKOUT
    elif damage == "depth":
        finding.impact_depth = 3
    elif damage == "cycle":
        finding.path = [PAYMENT, PAYMENT]
    elif damage == "owner":
        result.edges = [e for e in result.edges if e.type != "OWNS"]
    elif damage == "properties":
        finding.service = {"id": "service:invented"}
    elif damage == "dangling":
        result.nodes = [n for n in result.nodes if n.id != CHECKOUT]
    else:
        result.data.entity.id = REDIS
    with pytest.raises(GraphContractError):
        build_impact_context(result, records, ImpactInput(entity_id=PAYMENT))


@pytest.mark.parametrize("damage", ["chunk_edge", "text", "parent", "unrequested"])
def test_missing_or_mismatched_source_provenance_never_cited(database, damage):
    result, records, _, _ = retrieve(database)
    if damage == "chunk_edge":
        result.edges = [e for e in result.edges if not e.type.startswith("FROM_")]
    elif damage == "text":
        records[0].snippet = "Invented evidence"
    elif damage == "parent":
        records[0].metadata["source_id"] = "issue:other"
    else:
        result.sources = []
    context, _ = build_impact_context(result, records, ImpactInput(entity_id=PAYMENT))
    assert context.graph.edges and context.status == "partially_supported"
    assert not context.sources and "[issue:PAY-42]" not in context.summary


def test_missing_entity_and_no_dependents(database):
    _, _, context, data = retrieve(database, "service:missing")
    assert data.entity is None and context.status == "insufficient_evidence"
    assert not context.graph.nodes and not context.sources
    _, _, context, data = retrieve(database, ORDER)
    assert data.entity.id == ORDER and not data.direct_impact and not data.indirect_impact
    assert context.status == "insufficient_evidence"


@pytest.mark.parametrize("question,entity", [
    ("What would be affected if Payment Service changed?", PAYMENT),
    ("What depends on Payment Service?", PAYMENT),
    ("What services would be impacted if Redis were removed?", REDIS),
    ("What depends on Order Service?", ORDER),
])
def test_impact_routing(question, entity):
    assert route_question(question) == ImpactInput(entity_id=entity)


@pytest.mark.parametrize("question", ["Why does Payment Service use Redis, and what breaks if removed?",
                                     "What depends on Payment Service and Redis?",
                                     "What depends on Payment Service and Fraud Service?",
                                     "What does Payment Service depend on?",
                                     "What depends on Fraud Service?", "Who owns Payment Service?"])
def test_ambiguous_or_multi_tool_questions_do_not_route(question):
    assert route_question(question) is None


def test_http_tool_shape_query_contract_and_phase_one_regression(database):
    client = TestClient(create_app(database[2]))
    response = client.post("/api/tools/impact-analysis", json={"entity_id": PAYMENT, "max_depth": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["tools_used"] == ["impact_analysis"] and data["metadata"]["graph_mode"] == "falkordb"
    assert data["data"]["direct_impact"][0]["service_id"] == CHECKOUT
    query = client.post("/api/query", json={"question": "What depends on Payment Service?"})
    assert query.status_code == 200
    assert set(query.json()) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert query.json()["graph"] == data["graph"]
    assert query.json()["sources"] == data["sources"]


@pytest.mark.parametrize("body", [{}, {"entity_id": "Payment Service"}, {"entity_id": "service:x' MATCH (n)"},
                                  {"entity_id": PAYMENT, "max_depth": True}, {"entity_id": PAYMENT, "max_depth": "2"},
                                  {"entity_id": PAYMENT, "max_depth": 0}, {"entity_id": PAYMENT, "max_depth": 4},
                                  {"entity_id": PAYMENT, "cypher": "anything"}])
def test_impact_request_validation(body):
    response = TestClient(create_app(Settings(graph_mode="fixture"))).post("/api/tools/impact-analysis", json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_REQUEST"


def test_fixture_explicit_and_real_unavailable_never_falls_back(monkeypatch):
    client = TestClient(create_app(Settings(graph_mode="fixture")))
    response = client.post("/api/tools/impact-analysis", json={"entity_id": REDIS, "max_depth": 2})
    assert response.status_code == 200 and response.json()["metadata"]["graph_mode"] == "fixture"
    assert "Development fixture" in response.json()["metadata"]["warnings"][0]
    assert response.json()["data"]["indirect_impact"][0]["service_id"] == CHECKOUT
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("fixture fallback"))
    gateway = FalkorGateway(Settings(graph_mode="falkordb", graph_factory=""))
    client = TestClient(create_app(Settings(graph_mode="falkordb"), gateway=gateway))
    response = client.post("/api/tools/impact-analysis", json={"entity_id": PAYMENT})
    assert response.status_code == 503 and response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
    assert "sources" not in response.json()


def test_impact_runtime_failure_and_malformed_output_are_sanitized():
    class Bad:
        async def impact_analysis(self, _):
            raise RuntimeError("secret-password")
    config = Settings(graph_mode="falkordb", graph_factory="")
    gateway = FalkorGateway(config)
    gateway.delegate = Bad()
    client = TestClient(create_app(config, gateway=gateway))
    response = client.post("/api/tools/impact-analysis", json={"entity_id": PAYMENT})
    assert response.status_code == 503 and "secret-password" not in response.text
    with pytest.raises(GraphContractError):
        normalize_impact({"data": {"direct_impact": [{"private": "secret-password"}]}})


def test_actual_upstream_invalid_depth_does_not_query(database):
    class NoQuery:
        def execute(self, *_):
            pytest.fail("Invalid depth queried the database")
    for depth in (0, 4, True, "2"):
        assert impact_analysis(NoQuery(), PAYMENT, depth)["data"]["entity"] is None
