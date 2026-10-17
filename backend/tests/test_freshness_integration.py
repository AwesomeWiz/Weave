"""Offline integration uses actual teammate tools and ingested demo provenance."""
import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.antony import AntonyGateway, normalize_freshness
from app.config import Settings
from app.freshness import build_freshness_context
from app.graph import FalkorGateway, FixtureGateway, GraphContractError
from app.main import create_app
from app.models import FreshnessInput
from app.orchestration import execute_plan
from app.router import plan_question
from test_expert_integration import database as database, expert_db as expert_db
from test_openrouter import TEST_KEY, http_boundary as http_boundary
from tests.test_freshness_finder import AdapterClient, CappedDocumentClient
from weave_graph.freshness import find_stale_knowledge

QUESTION = "Which documents about Payment Service need review?"
FOUR = ("Why does Payment Service use Redis?; What would be affected if Redis changed?; "
        "Who knows Payment Service?; Which documents about Payment Service need review?")


@pytest.fixture
def freshness_db(expert_db, monkeypatch):
    from weave_graph.client import GraphClient

    class Client(GraphClient):
        def execute(self, query, params):
            if any(marker in query for marker in (
                "RETURN entity", "RETURN document, relationship, service",
                "RETURN decision, documented, document, affects, service",
                "RETURN decision, relationship, service", "RETURN commit, relationship, service",
                "RETURN incident, relationship, service", "RETURN chunk, relationship, source",
            )):
                return AdapterClient(expert_db[0]).execute(query, params)
            return super().execute(query, params)

    monkeypatch.setattr("weave_graph.client.GraphClient", Client)
    return expert_db


def evidence(database, client_type=AdapterClient, entity="Payment Service"):
    result = normalize_freshness(find_stale_knowledge(client_type(database[0]), entity))
    records = asyncio.run(AntonyGateway(database[2]).find_sources([s.id for s in result.sources]))
    return result, records, FreshnessInput(entity=entity)


def test_actual_gateway_api_paths_timestamps_and_genuine_sources(freshness_db):
    result = asyncio.run(FalkorGateway(freshness_db[2]).find_stale_knowledge(FreshnessInput(entity="Payment Service")))
    raw = result.model_dump()
    response = TestClient(create_app(freshness_db[2])).post("/api/tools/freshness", json={"entity": "Payment Service"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"answer", "support_status", "sources", "graph", "tools_used", "metadata", "data"}
    assert body["support_status"] == "supported"
    assert body["graph"] == {"nodes": raw["nodes"], "edges": raw["edges"]}
    finding, = body["data"]["review_candidates"]
    assert finding["document_id"] == "doc:architecture-overview"
    assert {t["id"] for t in finding["triggers"]} == {"decision:D-007", "incident:INC-17", "commit:8fae2"}
    assert {s["id"] for s in body["sources"]} == {"doc:architecture-overview", "commit:8fae2"}
    assert finding["source_ids"] == [finding["document_id"]]
    for trigger in finding["triggers"]:
        assert trigger["source_ids"] == ([trigger["id"]] if trigger["type"] == "commit" else [])
        assert trigger["timestamp"] in body["answer"]
    assert "Graph-only change evidence" in body["answer"] and "does not" not in finding["reason"]
    assert "not establish that a document is wrong" in body["answer"]
    assert freshness_db[3] and result.model_dump() == raw


@pytest.mark.parametrize("body", [{"entity": v} for v in ("", "  ", 3, None, "a" * 257)] +
                         [{}, {"entity": "Payment Service", "max_depth": 2}])
def test_validation(body):
    response = TestClient(create_app(Settings(_env_file=None, llm_provider="none"))).post("/api/tools/freshness", json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "input" not in response.text


@pytest.mark.parametrize("question", [QUESTION, "Is the Payment Service documentation outdated?",
                                      "Are Payment Service docs up to date?", "Check freshness for service:payment-service",
                                      "is the payment service documentation outdated?"])
def test_single_routing_public_contract(freshness_db, question):
    plan = plan_question(question)
    assert [c.name for c in plan.calls] == ["find_stale_knowledge"] and not plan.limitations
    response = TestClient(create_app(freshness_db[2])).post("/api/query", json={"question": question})
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"answer", "support_status", "sources", "graph", "tools_used", "metadata"}
    assert response.json()["tools_used"] == ["find_stale_knowledge"]


@pytest.mark.parametrize("question", ["Is our architecture documentation still current?", "Are the docs up to date?",
                                      "Is the Payment Service and Checkout Service documentation outdated?"])
def test_ambiguous_targets_are_never_inferred(question):
    plan = plan_question(question)
    assert not plan.calls and plan.limitations


def test_four_actual_tools_keep_local_proofs_and_conservative_status(freshness_db):
    plan = plan_question(FOUR)
    assert len(plan.calls) == 4 and not plan.limitations
    context, tools = asyncio.run(execute_plan(plan, FalkorGateway(freshness_db[2])))
    assert tools == ["trace_decision", "impact_analysis", "find_expert", "find_stale_knowledge"]
    assert context.per_tool["find_stale_knowledge"].status == "supported"
    assert context.per_tool["find_stale_knowledge"].relationship_paths
    assert context.status == "partially_supported"
    assert "updated" in context.per_tool["find_stale_knowledge"].summary
    assert len({n.id for n in context.graph.nodes}) == len(context.graph.nodes)


@pytest.mark.parametrize("damage", ["reverse", "missing", "association", "document date", "event date",
                                     "earlier", "naive", "rejected", "nonarchitecture", "reason",
                                     "duplicate", "node conflict", "edge conflict", "ref", "source conflict"])
def test_invalid_proofs_fail_closed(database, damage):
    result, records, query = evidence(database)
    finding = result.data.review_candidates[0]
    trigger = next(t for t in finding.triggers if t.type == "decision")
    if damage == "reverse":
        trigger.path[0].source, trigger.path[0].target = trigger.path[0].target, trigger.path[0].source
    elif damage == "missing":
        result.edges = [e for e in result.edges if e.source != trigger.id]
    elif damage == "association":
        finding.document_path[0].target = "service:checkout-service"
    elif damage == "document date":
        finding.updated_at = "2020-01-01T00:00:00Z"
    elif damage == "event date":
        trigger.timestamp = "2030-01-01T00:00:00Z"
    elif damage in {"earlier", "naive"}:
        trigger.timestamp = "2020-01-01T00:00:00Z" if damage == "earlier" else "2030-01-01T00:00:00"
        next(n for n in result.nodes if n.id == trigger.id).properties["decided_at"] = trigger.timestamp
    elif damage == "rejected":
        next(n for n in result.nodes if n.id == trigger.id).properties["status"] = "proposed"
    elif damage == "nonarchitecture":
        next(n for n in result.nodes if n.type == "Commit").properties["architecture_change"] = False
    elif damage == "reason":
        finding.reason = "This document is definitely wrong."
    elif damage == "duplicate":
        finding.triggers.append(trigger.model_copy(deep=True))
    elif damage == "node conflict":
        result.nodes.append(result.nodes[0].model_copy(update={"label": "conflict"}))
    elif damage == "edge conflict":
        result.edges.append(result.edges[0].model_copy(update={"properties": {"conflict": True}}))
    elif damage == "ref":
        result.sources[0].text = "unsupported"
    elif damage == "source conflict":
        records.append(records[0].model_copy(update={"snippet": "conflict"}))
    with pytest.raises(GraphContractError):
        build_freshness_context(result, records, query)


@pytest.mark.parametrize("damage", ["record", "chunk", "from", "metadata", "snippet", "timestamp", "url", "title", "parent timestamp"])
def test_missing_provenance_never_creates_citations(database, damage):
    result, records, query = evidence(database)
    if damage == "record":
        records = []
    elif damage in {"chunk", "from"}:
        # Graph tool legitimately found the changes, but returned no chunk proofs.
        result.sources.clear()
        result.edges = [e for e in result.edges if not e.type.startswith("FROM_")]
        if damage == "chunk":
            result.nodes = [n for n in result.nodes if n.type != "Chunk"]
    else:
        for record in records:
            if damage == "parent timestamp":
                record.timestamp = "2020-01-01T00:00:00Z"
                for row in record.metadata["chunks"]:
                    row["timestamp"] = record.timestamp
                for node in result.nodes:
                    if node.type == "Chunk" and node.properties["source_id"] == record.id:
                        node.properties["timestamp"] = record.timestamp
            elif damage == "metadata":
                record.metadata["chunks"][0]["source_id"] = "doc:unrelated"
            else:
                setattr(record, damage, "unsupported")
    context, data = build_freshness_context(result, records, query)
    assert context.status == "partially_supported" and not context.sources
    assert data.review_candidates and context.graph.edges
    assert all(not t.source_ids for f in data.review_candidates for t in f.triggers)


def test_caps_and_no_findings_do_not_prove_currentness(database):
    result, records, query = evidence(database, CappedDocumentClient)
    context, _ = build_freshness_context(result, records, query)
    assert context.status == "partially_supported" and any("cap" in w for w in context.warnings)
    result, records, query = evidence(database, entity="Checkout Service")
    context, data = build_freshness_context(result, records, query)
    assert not data.review_candidates and context.status == "insufficient_evidence"
    assert "does not prove" in context.summary


def test_excerpt_truncation_is_visible_and_incomplete(database):
    result, records, query = evidence(database)
    ref = result.sources[0]
    ref.text += "x" * 1700
    next(n for n in result.nodes if n.id == ref.chunk_id).properties["text"] = ref.text
    next(r for r in records if r.id == ref.id).snippet = ref.text.strip()
    context, _ = build_freshness_context(result, records, query)
    assert context.status == "partially_supported" and any("truncated" in w for w in context.warnings)
    assert len(next(s for s in context.sources if s.id == ref.id).snippet) == 1600


def test_provenance_cap_is_not_hidden_by_duplicate_chunk_dedup(database):
    class CappedProvenanceClient(AdapterClient):
        def execute(self, query, params=None):
            result = super().execute(query, params)
            if "RETURN chunk, relationship, source" in query and result.result_set:
                result.result_set = (result.result_set * 100)[:100]
            return result
    result, records, query = evidence(database, CappedProvenanceClient)
    context, _ = build_freshness_context(result, records, query)
    assert context.status == "partially_supported"
    assert any("cap of 100" in w for w in context.warnings)


def test_decision_documentation_association_is_valid_only_with_both_actual_edges(database):
    client = AdapterClient(database[0])
    # Use actual ingested D-007 DOCUMENTED_IN ADR-7 and AFFECTS Payment Service.
    client.nodes["doc:ADR-7"]["updated_at"] = "2026-01-01T00:00:00Z"
    client.relationships = [r for r in client.relationships if not (
        r["source_id"] == "doc:ADR-7" and r["rel_type"] == "DESCRIBES")]
    for node in client.nodes.values():
        if node.get("source_id") == "doc:ADR-7":
            node["timestamp"] = "2026-01-01T00:00:00Z"
    result = normalize_freshness(find_stale_knowledge(client, "Payment Service"))
    records = asyncio.run(AntonyGateway(database[2]).find_sources([s.id for s in result.sources]))
    for record in records:
        if record.id == "doc:ADR-7":
            record.timestamp = "2026-01-01T00:00:00Z"
            for row in record.metadata["chunks"]:
                row["timestamp"] = record.timestamp
    context, data = build_freshness_context(result, records, FreshnessInput(entity="Payment Service"))
    finding = next(f for f in data.review_candidates if f.document_id == "doc:ADR-7")
    assert [p.type for p in finding.document_path] == ["DOCUMENTED_IN", "AFFECTS"]
    assert context.status == "partially_supported"  # ADR excerpt exceeds the explicit 1600-character bound.
    assert finding.source_ids == ["doc:ADR-7"]
    result.edges = [e for e in result.edges if not (e.type == "DOCUMENTED_IN" and e.target == "doc:ADR-7")]
    with pytest.raises(GraphContractError):
        build_freshness_context(result, records, FreshnessInput(entity="Payment Service"))


def test_graph_only_decision_and_incident_do_not_require_fabricated_chunks(database):
    result, records, query = evidence(database)
    result.data.review_candidates[0].triggers = [t for t in result.data.review_candidates[0].triggers if t.type != "commit"]
    result.sources = [r for r in result.sources if r.id != "commit:8fae2"]
    context, data = build_freshness_context(result, records, query)
    assert context.status == "supported"
    assert {s.id for s in context.sources} == {"doc:architecture-overview"}
    assert all(not t.source_ids for f in data.review_candidates for t in f.triggers)
    assert "Graph-only change evidence" in context.summary


def test_ambiguous_resolution_and_nonservice_targets_are_qualified(database):
    result, records, query = evidence(database)
    first = result.data.entity
    second = first.model_copy(deep=True)
    second.id = second.properties["id"] = "service:duplicate"
    result.nodes = [first, second]
    result.edges = []
    result.sources = []
    result.data.entity = None
    result.data.review_candidates = []
    context, _ = build_freshness_context(result, records, query)
    assert context.status == "insufficient_evidence" and not context.sources
    for entity in ("Redis", "not-a-record"):
        result, records, query = evidence(database, entity=entity)
        context, _ = build_freshness_context(result, records, query)
        assert context.status == "insufficient_evidence" and not context.sources


def test_temporal_order_uses_instants_and_rejects_equal_offset_dates(database):
    result, records, query = evidence(database)
    finding = result.data.review_candidates[0]
    event = next(t for t in finding.triggers if t.type == "decision")
    # Same document instant with a different UTC offset is not a later event.
    from datetime import datetime, timedelta, timezone
    event.timestamp = datetime.fromisoformat(finding.updated_at).astimezone(timezone(timedelta(hours=5))).isoformat()
    next(n for n in result.nodes if n.id == event.id).properties["decided_at"] = event.timestamp
    with pytest.raises(GraphContractError):
        build_freshness_context(result, records, query)


def test_missing_from_edge_cannot_be_borrowed_from_source_records(database):
    result, records, query = evidence(database)
    result.edges = [e for e in result.edges if e.type != "FROM_DOCUMENT"]
    with pytest.raises(GraphContractError):
        build_freshness_context(result, records, query)


def test_mocked_four_tool_synthesis_preserves_every_local_fact_or_falls_back(freshness_db, http_boundary):
    from app.synthesis import prepare_synthesis
    context, _ = asyncio.run(execute_plan(plan_question(FOUR), FalkorGateway(freshness_db[2])))
    packet = prepare_synthesis(context)
    assert len(packet.blocks) == 4
    assert "updated" in packet.blocks[-1].variants["recorded"]
    config = freshness_db[2].model_copy(update={"llm_provider": "openrouter", "openrouter_api_key": SecretStr(TEST_KEY)})
    baseline = TestClient(create_app(freshness_db[2])).post("/api/query", json={"question": FOUR}).json()
    actual = TestClient(create_app(config)).post("/api/query", json={"question": FOUR}).json()
    for field in ("graph", "sources", "support_status", "tools_used"):
        assert actual[field] == baseline[field]
    assert len(http_boundary[0]) == 1
    assert actual["metadata"]["generation"] in {"openrouter", "deterministic"}
    assert "review may be warranted" in actual["answer"]
    if actual["metadata"]["generation"] == "deterministic":
        assert actual["answer"] == baseline["answer"]


def test_bound_overflow_is_rejected_and_errors_are_sanitized(freshness_db, monkeypatch):
    gateway = FalkorGateway(freshness_db[2])
    async def malformed(_):
        return {"private-debug": "secret"}
    monkeypatch.setattr(gateway.delegate, "find_stale_knowledge", malformed)
    response = TestClient(create_app(freshness_db[2], gateway=gateway)).post("/api/tools/freshness", json={"entity": "Payment Service"})
    assert response.status_code == 502 and "private-debug" not in response.text
    result, _, _ = evidence(freshness_db)
    raw = result.model_dump()
    raw["nodes"] *= 81
    with pytest.raises(GraphContractError):
        normalize_freshness(raw)


@pytest.mark.parametrize("field,entity", [("updated_at", "doc:architecture-overview"), ("timestamp", "commit:8fae2")])
def test_naive_timestamp_graph_bug_is_qualified_not_a_crash(database, field, entity):
    client = AdapterClient(database[0])
    client.nodes[entity][field] = "2020-01-01T00:00:00"
    result = find_stale_knowledge(client, "Payment Service")
    assert any(f"{entity}" in w and "no comparable" in w for w in result["warnings"])
    assert all(t["id"] != entity for f in result["data"]["review_candidates"] for t in f["triggers"])


@pytest.mark.parametrize("mode", ["valid", "injected_claim", "unknown_citation", "status_upgrade", "network"])
def test_mocked_openrouter_preserves_freshness_evidence(freshness_db, http_boundary, mode):
    http_boundary[1]["mode"] = mode
    body = {"entity": "Payment Service"}
    baseline = TestClient(create_app(freshness_db[2])).post("/api/tools/freshness", json=body).json()
    config = freshness_db[2].model_copy(update={"llm_provider": "openrouter", "openrouter_api_key": SecretStr(TEST_KEY)})
    actual = TestClient(create_app(config)).post("/api/tools/freshness", json=body).json()
    for field in ("graph", "sources", "support_status", "data"):
        assert actual[field] == baseline[field]
    assert actual["metadata"]["generation"] == ("openrouter" if mode == "valid" else "deterministic")
    assert "not establish that a document is wrong" in actual["answer"]
    if mode != "valid":
        assert actual["answer"] == baseline["answer"]


def test_fixture_is_explicit_and_real_outage_has_no_fallback(monkeypatch):
    config = Settings(_env_file=None, graph_mode="fixture", llm_provider="none")
    body = TestClient(create_app(config)).post("/api/tools/freshness", json={"entity": "Payment Service"}).json()
    assert not body["data"]["review_candidates"] and body["support_status"] == "insufficient_evidence"
    assert body["metadata"]["warnings"][0].startswith("Development fixture")
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Fixture fallback"))
    config = Settings(_env_file=None, graph_mode="falkordb", graph_factory="", llm_provider="none")
    response = TestClient(create_app(config)).post("/api/tools/freshness", json={"entity": "Payment Service"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
