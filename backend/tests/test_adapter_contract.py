"""Offline contract doubles, built independently of novapay.development.json.

These are NOT a teammate implementation or proof of real database retrieval.
"""
import sys
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FixtureGateway
from app.main import create_app
from app.models import Source
from real_acceptance import assert_primary_evidence


def independent_contract(chunks):
    specs = [
        ("service:payment-service", "Service", "Payment Service"),
        ("tech:redis", "Technology", "Redis"),
        ("decision:D-007", "Decision", "Cache selected reads"),
        ("incident:INC-17", "Incident", "Payment timeouts"),
        ("issue:PAY-42", "Issue", "Reduce latency"),
        ("message:payment-perf-7", "Message", "Payment performance discussion"),
        ("doc:ADR-7", "Document", "Cache decision record"),
        ("commit:8fae2abcd1234", "Commit", "Cache implementation"),
    ]
    nodes = [{"id": i, "type": kind, "label": label,
              "properties": {"status": "accepted"} if kind == "Decision" else {}}
             for i, kind, label in specs]
    paths = [
        ("service:payment-service", "USES", "tech:redis"),
        ("decision:D-007", "AFFECTS", "service:payment-service"),
        ("decision:D-007", "INTRODUCES", "tech:redis"),
        ("incident:INC-17", "LED_TO", "issue:PAY-42"),
        ("issue:PAY-42", "LED_TO", "decision:D-007"),
        ("decision:D-007", "DISCUSSED_IN", "message:payment-perf-7"),
        ("decision:D-007", "DOCUMENTED_IN", "doc:ADR-7"),
        ("decision:D-007", "IMPLEMENTED_BY", "commit:8fae2abcd1234"),
    ]
    records = []
    for entity, kind, title in specs[2:]:
        for index in range(2 if chunks and kind == "Document" else 1):
            source_id = f"chunk:{entity}:{index}" if chunks else entity
            native_type = {"Issue": "jira", "Message": "slack", "Commit": "github"}.get(kind, kind)
            metadata = {"source_id": entity, "source_type": native_type,
                        "dataset": "offline_contract_double", "revision": "test-only"}
            if chunks:
                metadata.update(chunk_id=source_id, chunk_index=index)
                nodes.append({"id": source_id, "type": "Chunk", "label": title,
                              "properties": {"source_id": entity, "chunk_index": index}})
                paths.append((source_id, "MENTIONS" if kind == "Decision"
                              else f"FROM_{kind.upper()}", entity))
            records.append(Source(
                id=source_id, type=kind, title=title,
                snippet=f"Offline contract excerpt for {entity}, segment {index}.",
                entity_ids=[entity], timestamp="2026-05-20T10:00:00Z",
                metadata=metadata,
            ))
    trace = {"graph": {"nodes": nodes, "edges": [
        {"id": f"{s}|{kind}|{t}", "source": s, "type": kind, "target": t, "properties": {}}
        for s, kind, t in paths]}, "decision_ids": ["decision:D-007"],
        "source_ids": [s.id for s in records], "warnings": []}
    return trace, records


def query_adapter(monkeypatch, chunks=True, missing_source=False):
    trace, records = independent_contract(chunks)

    class TraceTool:
        async def trace_decision(self, query):
            assert (query.service, query.technology) == ("Payment Service", "Redis")
            return trace

    class SourceStore:
        async def find_sources(self, source_ids):
            assert source_ids == [s.id for s in records]
            return [s.model_dump() for s in (records[:-1] if missing_source else records)]

    class TeamAdapter:
        async def health(self):
            return True

        async def trace_decision(self, query):
            return await TraceTool().trace_decision(query)

        async def find_sources(self, source_ids):
            return await SourceStore().find_sources(source_ids)

    def forbid_fixture(*_args, **_kwargs):
        pytest.fail("Real-mode adapter path tried to open development fixtures")

    monkeypatch.setattr(FixtureGateway, "__init__", forbid_fixture)
    module = ModuleType("offline_contract_adapter")
    module.create_gateway = lambda _settings: TeamAdapter()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with TestClient(create_app(Settings(graph_mode="falkordb", llm_provider="none",
                                       graph_factory=f"{module.__name__}:create_gateway"))) as client:
        response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
    assert response.status_code == 200
    return response.json(), records


@pytest.mark.parametrize("chunks", [False, True])
def test_independent_graph_and_source_contract(monkeypatch, chunks):
    data, originals = query_adapter(monkeypatch, chunks)
    assert_primary_evidence(data, originals)
    assert set(data) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    if chunks:
        assert "[chunk:decision:D-007:0]" in data["answer"]
        assert len([s for s in data["sources"] if s["metadata"]["source_id"] == "doc:ADR-7"]) == 2


def test_missing_requested_chunk_downgrades_support(monkeypatch):
    data, _ = query_adapter(monkeypatch, missing_source=True)
    assert data["support_status"] == "partially_supported"
    assert data["graph"]["edges"]


@pytest.mark.parametrize("damage", ["proposed", "path", "source", "text", "provenance", "fixture"])
def test_real_acceptance_rejects_incomplete_or_altered_evidence(monkeypatch, damage):
    data, originals = query_adapter(monkeypatch)
    if damage == "proposed":
        next(n for n in data["graph"]["nodes"] if n["id"] == "decision:D-007")["properties"]["status"] = "proposed"
    elif damage == "path":
        data["graph"]["edges"] = [e for e in data["graph"]["edges"] if e["type"] != "INTRODUCES"]
    elif damage == "source":
        data["sources"] = [s for s in data["sources"] if s["metadata"]["source_id"] != "issue:PAY-42"]
    elif damage == "text":
        data["sources"][0]["snippet"] = "Invented replacement"
    elif damage == "provenance":
        data["sources"][0]["metadata"]["source_id"] = "doc:unrelated"
    else:
        data["sources"][0]["metadata"]["dataset"] = "development_fixture"
    with pytest.raises(AssertionError):
        assert_primary_evidence(data, originals)
