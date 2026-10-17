"""Actual teammate graph/retrieval functions against an explicit offline DB double."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.antony import AntonyGateway
from app.config import Settings
from app.experts import build_expert_context
from app.graph import FalkorGateway, FixtureGateway, GraphContractError, GraphUnavailable
from app.main import create_app
from app.models import ExpertInput
from app.orchestration import execute_plan
from app.router import plan_question
from test_impact_integration import database as database
from test_openrouter import TEST_KEY, http_boundary as http_boundary
from tests.test_expert_finder import (
    AdapterClient,
    AmbiguousTopicAdapterClient,
    CappedTraversalAdapterClient,
    NoChunkAdapterClient,
)

QUESTION = "Who knows Payment Service?"
SHOWCASE = "Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?"


@pytest.fixture
def expert_db(database, monkeypatch):
    original = database[1]

    class Client(original):
        def execute(self, query, params):
            if any(
                marker in query
                for marker in (
                    "RETURN topic",
                    "RETURN source, relationship, target",
                    "RETURN person, relationship, entity",
                    "RETURN issue, relationship, person",
                    "RETURN person, membership, team, owns, service",
                    "RETURN chunk, relationship, source",
                )
            ):
                return AdapterClient(database[0]).execute(query, params)
            return super().execute(query, params)

    monkeypatch.setattr("weave_graph.client.GraphClient", Client)
    return database


def evidence(database, query=QUESTION, client_type=AdapterClient, limit=5):
    from weave_graph.experts import find_expert
    from app.antony import normalize_experts

    arguments = ExpertInput(query=query, limit=limit)
    result = normalize_experts(find_expert(client_type(database[0]), query, limit))
    records = asyncio.run(AntonyGateway(database[2]).find_sources([s.id for s in result.sources]))
    return result, records, arguments


def test_actual_gateway_and_dedicated_endpoint_preserve_ranking_and_sources(expert_db):
    result = asyncio.run(FalkorGateway(expert_db[2]).find_expert(ExpertInput(query=QUESTION)))
    raw = result.model_dump()
    response = TestClient(create_app(expert_db[2])).post(
        "/api/tools/expert-finder", json={"query": QUESTION}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "answer",
        "support_status",
        "tools_used",
        "sources",
        "graph",
        "metadata",
        "data",
    }
    assert body["support_status"] == "supported"
    assert [e["person"]["id"] for e in body["data"]["experts"]] == [
        "person:ravi",
        "person:alice",
        "person:maya",
    ]
    assert body["graph"] == {"nodes": raw["nodes"], "edges": raw["edges"]}
    assert {s["id"] for s in body["sources"]} == {
        "issue:PAY-42",
        "message:payment-perf-7",
        "commit:8fae2",
    }
    for first, validated in zip(raw["data"]["experts"], body["data"]["experts"], strict=True):
        for field in ("person", "score", "ranking_reasons", "ownership_classification"):
            assert first[field] == validated[field]
    assert "personal ownership is not established" in body["answer"]
    assert expert_db[3]  # worker-owned clients are closed
    assert result.model_dump() == raw


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "a" * 2001},
        {"query": 42},
        {"query": QUESTION, "entity_id": "service:payment-service"},
    ]
    + [{"query": QUESTION, "limit": value} for value in (0, 11, True, 2.5, "5", None)],
)
def test_query_and_limit_validation_uses_sanitized_error_envelope(body):
    config = Settings(_env_file=None, graph_factory="", llm_provider="none")
    response = TestClient(create_app(config)).post("/api/tools/expert-finder", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "input" not in response.text and "Traceback" not in response.text


@pytest.mark.parametrize(
    "question",
    [
        QUESTION,
        "Who can explain the Redis decision?",
        "Who worked on Payment Service?",
        "Who approved D-007?",
        "Who knows why Payment Service uses Redis?",
    ],
)
def test_expert_routing_and_query_exact_contract(expert_db, question):
    plan = plan_question(question)
    assert [c.name for c in plan.calls] == ["find_expert"] and not plan.limitations
    assert plan.calls[0].arguments.query == question.strip("?")
    body = (
        TestClient(create_app(expert_db[2])).post("/api/query", json={"question": question}).json()
    )
    assert set(body) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    assert body["tools_used"] == ["find_expert"] and body["graph"]["nodes"]


def test_three_tools_run_independently_and_merge_genuine_evidence(expert_db):
    plan = plan_question(SHOWCASE)
    assert [c.name for c in plan.calls] == ["decision_trace", "impact_analysis", "find_expert"]
    context, tools = asyncio.run(execute_plan(plan, FalkorGateway(expert_db[2])))
    assert tools == ["trace_decision", "impact_analysis", "find_expert"]
    assert context.per_tool["find_expert"].status == "supported"
    assert context.status == "partially_supported"
    assert "Expert Finder" in context.summary and "person:alice" in context.summary
    assert len({n.id for n in context.graph.nodes}) == len(context.graph.nodes)


@pytest.mark.parametrize(
    "client,query",
    [(AmbiguousTopicAdapterClient, QUESTION), (AdapterClient, "Who is the best service expert?")],
)
def test_ambiguous_and_low_confidence_topics_do_not_rank(database, client, query):
    result, records, arguments = evidence(database, query, client)
    context, data = build_expert_context(result, records, arguments)
    assert context.status == "insufficient_evidence" and not data.experts
    assert not context.sources and "No experts were ranked" in context.summary


@pytest.mark.parametrize("client", [NoChunkAdapterClient, CappedTraversalAdapterClient])
def test_missing_chunks_and_caps_keep_ranking_incomplete(database, client):
    result, records, arguments = evidence(database, client_type=client)
    context, data = build_expert_context(result, records, arguments)
    assert context.status == "partially_supported" and data.experts
    assert context.warnings and "not an exhaustive" in context.summary
    if client is NoChunkAdapterClient:
        assert not context.sources and all(
            not e.source_ids for p in data.experts for e in p.evidence
        )


@pytest.mark.parametrize(
    "damage",
    [
        "score",
        "order",
        "reasons",
        "person",
        "role",
        "topic",
        "direction",
        "path",
        "evidence type",
        "personal owner",
        "ownership",
        "history",
        "duplicate evidence",
        "duplicate person",
        "node conflict",
        "edge conflict",
        "source conflict",
        "source ref",
        "policy",
        "wrong query",
    ],
)
def test_unverifiable_rankings_fail_closed(database, damage):
    result, records, arguments = evidence(database)
    expert = result.data.experts[0]
    if damage == "score":
        expert.score += 1
    elif damage == "order":
        result.data.experts.reverse()
    elif damage == "reasons":
        expert.ranking_reasons.append("Unsupported personal owner")
    elif damage == "person":
        expert.person.id = "person:invented"
    elif damage == "role":
        expert.person.role = "Invented title"
    elif damage == "topic":
        result.data.topics[0].label = "Unrelated topic"
    elif damage == "direction":
        proof = expert.evidence[0].path[0]
        proof.source, proof.target = proof.target, proof.source
    elif damage == "path":
        result.edges = [e for e in result.edges if e.type != "AUTHORED"]
    elif damage == "evidence type":
        expert.evidence[0].entity_type = "Person"
    elif damage == "personal owner":
        expert.ownership_classification = "current_owner"
    elif damage == "ownership":
        expert.ownership.clear()
    elif damage == "history":
        expert.historical_contributions.clear()
    elif damage == "duplicate evidence":
        expert.evidence.append(expert.evidence[0].model_copy(deep=True))
    elif damage == "duplicate person":
        result.data.experts.append(expert.model_copy(deep=True))
    elif damage == "node conflict":
        result.nodes.append(result.nodes[0].model_copy(update={"label": "Conflict"}))
    elif damage == "edge conflict":
        result.edges.append(result.edges[0].model_copy(update={"type": "Conflict"}))
    elif damage == "source conflict":
        records.append(records[0].model_copy(update={"snippet": "Conflicting text"}))
    elif damage == "source ref":
        result.sources[0].text = "Unsupported excerpt"
    elif damage == "policy":
        result.data.scoring["team_ownership"] = 100
    elif damage == "wrong query":
        result.data.query = "A different question"
    with pytest.raises(GraphContractError):
        build_expert_context(result, records, arguments)


@pytest.mark.parametrize("damage", ["chunk ids", "snippet", "source type", "source parent", "title", "url", "timestamp", "person association", "chunk metadata"])
def test_missing_record_provenance_cannot_supply_citations(database, damage):
    result, records, arguments = evidence(database)
    if damage == "chunk ids":
        for r in records:
            r.metadata["chunk_ids"] = ["chunk:invented"]
    elif damage == "snippet":
        for r in records:
            r.snippet = "Unsupported excerpt"
    elif damage == "source type":
        for r in records:
            r.type = "Decision"
    elif damage == "source parent":
        for r in records:
            r.metadata["source_id"] = "issue:unrelated"
    elif damage == "person association":
        for r in records:
            r.entity_ids.append("person:unrelated")
    elif damage == "chunk metadata":
        for r in records:
            r.metadata["chunks"][0]["source_id"] = "issue:unrelated"
    else:
        for r in records:
            setattr(r, damage, {"title": "Unsupported title", "url": "https://unrelated.example/source",
                               "timestamp": "2020-01-01T00:00:00Z"}[damage])
    context, data = build_expert_context(result, records, arguments)
    assert context.status == "partially_supported" and not context.sources
    assert all(not e.source_ids for p in data.experts for e in p.evidence)


def test_hosted_expert_and_three_tool_answers_preserve_ranking(expert_db, http_boundary):
    enabled = expert_db[2].model_copy(
        update={"llm_provider": "openrouter", "openrouter_api_key": SecretStr(TEST_KEY)}
    )
    for path, body in [
        ("/api/tools/expert-finder", {"query": QUESTION}),
        ("/api/query", {"question": SHOWCASE}),
    ]:
        baseline = TestClient(create_app(expert_db[2])).post(path, json=body).json()
        response = TestClient(create_app(enabled)).post(path, json=body)
        assert response.status_code == 200, response.text
        actual = response.json()
        assert actual["metadata"]["generation"] == "openrouter", actual["metadata"]
        for field in ("graph", "sources", "support_status", "tools_used"):
            assert actual[field] == baseline[field]
        if "data" in actual:
            assert actual["data"] == baseline["data"]
        assert "personal ownership" in actual["answer"] and "not an exhaustive" in actual["answer"]


def test_hosted_unsupported_expert_claim_falls_back_exactly(expert_db, http_boundary):
    http_boundary[1]["mode"] = "injected_claim"
    body = {"query": QUESTION}
    baseline = (
        TestClient(create_app(expert_db[2])).post("/api/tools/expert-finder", json=body).json()
    )
    enabled = expert_db[2].model_copy(
        update={"llm_provider": "openrouter", "openrouter_api_key": SecretStr(TEST_KEY)}
    )
    actual = TestClient(create_app(enabled)).post("/api/tools/expert-finder", json=body).json()
    for field in ("answer", "graph", "sources", "support_status", "data"):
        assert actual[field] == baseline[field]
    assert actual["metadata"]["generation"] == "deterministic"


def test_expert_failure_cannot_borrow_trace_approval_or_sources(expert_db, monkeypatch):
    gateway = FalkorGateway(expert_db[2])
    original = gateway.find_expert
    async def broken(query):
        result = await original(query)
        result.edges = [e for e in result.edges if e.type != "APPROVED"]
        return result
    monkeypatch.setattr(gateway, "find_expert", broken)
    context, tools = asyncio.run(execute_plan(plan_question(SHOWCASE), gateway))
    assert tools == ["trace_decision", "impact_analysis"]
    assert context.per_tool["find_expert"].state == "invalid"
    assert context.status == "partially_supported" and "Expert Finder returned invalid evidence" in context.summary


def test_source_outage_retains_ranked_graph_without_fabricated_citations(expert_db, monkeypatch):
    gateway = FalkorGateway(expert_db[2])
    async def unavailable(_):
        raise GraphUnavailable("private-debug-source-details")
    monkeypatch.setattr(gateway, "find_sources", unavailable)
    response = TestClient(create_app(expert_db[2], gateway=gateway)).post(
        "/api/tools/expert-finder", json={"query": QUESTION})
    assert response.status_code == 200
    body = response.json()
    assert body["support_status"] == "partially_supported" and body["data"]["experts"]
    assert body["graph"]["edges"] and not body["sources"]
    assert all(not e["source_ids"] for p in body["data"]["experts"] for e in p["evidence"])
    assert "private-debug" not in response.text


def test_generic_pronouns_remain_qualified():
    plan = plan_question("Who made the decision, and what would be affected if we removed it?")
    assert plan.limitations and not any(c.name == "impact_analysis" for c in plan.calls)


def test_unrelated_person_contributions_cannot_be_ranked(database):
    result, records, arguments = evidence(database)
    # Keep a person's actual contribution edge but disconnect its entity from
    # the topic. Another person's unrelated record cannot justify this ranking.
    result.edges = [e for e in result.edges if e.type not in {"IMPLEMENTED_BY", "IMPLEMENTS_DECISION", "ADDRESSES", "CHANGES", "IN_REPOSITORY"}]
    with pytest.raises(GraphContractError):
        build_expert_context(result, records, arguments)


def test_real_outage_does_not_create_fixtures(monkeypatch):
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Fixture fallback"))
    config = Settings(_env_file=None, graph_mode="falkordb", graph_factory="", llm_provider="none")
    response = TestClient(create_app(config)).post(
        "/api/tools/expert-finder", json={"query": QUESTION}
    )
    assert response.status_code == 503 and response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"


def test_development_mode_has_no_invented_experts():
    response = TestClient(create_app(Settings(_env_file=None, graph_mode="fixture"))).post(
        "/api/tools/expert-finder", json={"query": QUESTION}
    )
    assert response.status_code == 200
    assert response.json()["support_status"] == "insufficient_evidence"
    assert not response.json()["data"]["experts"]
    assert response.json()["metadata"]["warnings"][0].startswith("Development fixture")
