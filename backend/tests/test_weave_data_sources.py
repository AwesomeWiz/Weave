"""Actual ingestion/retrieval package with an explicit offline graph test double."""
import asyncio
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FalkorGateway, FixtureGateway, GraphUnavailable
from app.main import create_app
from app.models import GraphEdge, GraphNode, TraceResult, EvidenceGraph
from app.sources import WeaveDataSourceRetriever
from weave_data import ingest, retrieval
from weave_data.graph_adapter import InMemoryGraphAdapter

DATA = Path(__file__).resolve().parents[2] / "data" / "novapay"
IDS = ["issue:PAY-42", "message:payment-perf-7", "commit:8fae2", "doc:ADR-7"]


@pytest.fixture
def source_store(monkeypatch):
    store = InMemoryGraphAdapter()
    assert ingest.run_ingestion(DATA, store).status == "success"
    closed = []

    class DatabaseDouble:
        def __init__(self, **kwargs):
            assert kwargs["host"] == "localhost"
            assert kwargs["graph_name"] == "novapay"

        def get_chunks_for_sources(self, ids):
            return store.get_chunks_for_sources(ids)

        def close(self):
            closed.append(True)

    monkeypatch.setattr("weave_data.graph_adapter.FalkorDBGraphAdapter", DatabaseDouble)

    def no_files(*_args, **_kwargs):
        pytest.fail("Source retrieval must not load local data or application fixtures")

    monkeypatch.setattr(retrieval, "load_records", no_files)
    monkeypatch.setattr(retrieval, "load_adr_content", no_files)
    monkeypatch.setattr(FixtureGateway, "__init__", no_files)
    return store, closed


def test_actual_sources_preserve_canonical_ids_chunk_provenance_and_timestamps(source_store):
    store, closed = source_store
    gateway = FalkorGateway(Settings(graph_mode="falkordb", source_backend="weave_data", graph_factory=""))
    sources = asyncio.run(gateway.find_sources(IDS + [IDS[0], "issue:unknown"]))
    assert [s.id for s in sources] == IDS
    for source in sources:
        chunks = store.get_chunks_for_sources([source.id])
        assert source.snippet == "\n\n".join(c["text"].strip() for c in chunks)
        assert source.metadata["chunk_ids"] == [c["id"] for c in chunks]
        assert source.entity_ids == [source.id]
        assert source.timestamp and source.metadata["chunks"][0]["timestamp"] == source.timestamp
        assert source.metadata["chunks"][0]["source_id"] == source.id
        assert source.metadata["chunks"][0]["chunk_index"] == 0
    assert closed == [True]
    # Source readiness does not pretend Antony's missing graph tool is working.
    assert asyncio.run(gateway.health()) is False


def test_multiple_chunks_keep_parent_citation_id_and_order(source_store):
    store, _ = source_store
    store.upsert_chunk("chunk:doc:ADR-7:1", {"source_id": "doc:ADR-7", "source_type": "Document",
                        "chunk_index": 1, "title": "Consequences", "text": "Additional stored text."})
    store.upsert_relationship("chunk:doc:ADR-7:1", "FROM_DOCUMENT", "doc:ADR-7")
    source = asyncio.run(WeaveDataSourceRetriever(Settings(graph_mode="falkordb")).find_sources(["doc:ADR-7"]))[0]
    assert source.id == "doc:ADR-7"
    assert source.metadata["chunk_ids"] == ["chunk:doc:ADR-7:0", "chunk:doc:ADR-7:1"]
    assert source.snippet.endswith("\n\nAdditional stored text.")


def test_source_adapter_failure_never_reads_files_or_substitutes_memory(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("private-connection-details")

    monkeypatch.setattr("weave_data.graph_adapter.FalkorDBGraphAdapter", fail)
    with pytest.raises(GraphUnavailable):
        asyncio.run(WeaveDataSourceRetriever(Settings(graph_mode="falkordb")).find_sources(IDS))


@pytest.mark.parametrize("source_failure", [False, True])
def test_existing_query_contract_uses_actual_source_package(source_store, monkeypatch, source_failure):
    records, paths, _, _, validation = ingest.prepare_ingestion(DATA)
    assert validation.ok
    selected = {*IDS, "decision:D-007", "incident:INC-17", "service:payment-service", "tech:redis"}
    trace = TraceResult(
        graph=EvidenceGraph(nodes=[GraphNode(id=r.id, type=r.entity_type.value,
              label=getattr(r, "name", None) or getattr(r, "title", None) or r.id,
              properties=r.model_dump(mode="json")) for r in records if r.id in selected],
            edges=[GraphEdge(id=p.stable_key, source=p.source_id, type=p.rel_type, target=p.target_id)
                   for p in paths if p.source_id in selected and p.target_id in selected]),
        source_ids=IDS, decision_ids=["decision:D-007"],
    )

    class TraceDouble:
        async def health(self):
            return True

        async def trace_decision(self, _query):
            return trace.model_copy(deep=True)

    module = ModuleType("trace_source_integration_test")
    module.create_gateway = lambda _settings: TraceDouble()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    settings = Settings(graph_mode="falkordb", source_backend="weave_data", llm_provider="none",
                        graph_factory=f"{module.__name__}:create_gateway")
    if source_failure:
        def fail(_ids):
            raise RuntimeError("private-connection-token")
        monkeypatch.setattr(source_store[0], "get_chunks_for_sources", fail)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
    if source_failure:
        assert data["sources"] == []
        assert data["graph"]["edges"]
        assert data["support_status"] == "insufficient_evidence"
        assert "private-connection-token" not in response.text
        assert any("Source retrieval is unavailable" in w for w in data["metadata"]["warnings"])
        return
    assert [s["id"] for s in data["sources"]] == IDS
    assert data["support_status"] == "partially_supported"
    # The package has four supporting chunks, not a retrieved decision rationale.
    assert "rationale is incomplete" in data["answer"]
    assert data["metadata"]["graph_mode"] == "falkordb"


def test_ingestion_default_does_not_fallback_when_falkordb_creation_fails(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(ingest, "FalkorDBGraphAdapter", fail)
    def no_memory():
        pytest.fail("Implicit memory fallback")
    monkeypatch.setattr(ingest, "InMemoryGraphAdapter", no_memory)
    assert ingest.run_ingestion(DATA).status == "failed"


def test_ingestion_cli_reports_failure_without_fallback(monkeypatch, capsys):
    def fail(**_kwargs):
        raise RuntimeError("private-password")

    monkeypatch.setattr(ingest, "FalkorDBGraphAdapter", fail)
    monkeypatch.setattr(sys, "argv", ["weave_data.ingest", "--json"])
    assert ingest.main() == 1
    output = capsys.readouterr().out
    assert '"status": "failed"' in output
    assert "private-password" not in output
    assert '"persistence": "unavailable"' in output


def test_offline_cli_requires_explicit_memory_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["weave_data.ingest", "--in-memory", "--json"])
    assert ingest.main() == 0
    assert '"persistence": "InMemoryGraphAdapter"' in capsys.readouterr().out


def test_fixture_mode_never_constructs_real_source_backend(monkeypatch):
    def forbidden(*_args):
        pytest.fail("Fixture mode must not construct real source retrieval")
    monkeypatch.setattr(WeaveDataSourceRetriever, "__init__", forbidden)
    with TestClient(create_app(Settings(graph_mode="fixture", source_backend="weave_data"))) as client:
        data = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"}).json()
    assert data["metadata"]["graph_mode"] == "fixture"


def test_real_client_adapter_configuration_and_read_only_query(monkeypatch):
    captured = {}
    class GraphDouble:
        def ro_query(self, query, params, timeout):
            captured.update(query=query, params=params, timeout=timeout)
            return type("Result", (), {"result_set": [[
                "issue:PAY-42", "FROM_ISSUE", "chunk:issue:PAY-42:0", "Issue", 0,
                "Stored issue", "Stored text", "2026-05-11T09:00:00Z", None,
            ]]})()

    class ClientDouble:
        def __init__(self, **kwargs):
            captured["options"] = kwargs
            self.connection = self
        def select_graph(self, name):
            captured["graph"] = name
            return GraphDouble()
        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("falkordb.FalkorDB", ClientDouble)
    config = Settings(graph_mode="falkordb", falkordb_host="graph.test", falkordb_port=6380,
                      graph_name="actual-seed", falkordb_username="test-user",
                      falkordb_password="test-only-password", falkordb_ssl=True)
    records = asyncio.run(WeaveDataSourceRetriever(config).find_sources([IDS[0]]))
    assert records[0].id == IDS[0]
    assert captured["graph"] == "actual-seed"
    assert captured["options"]["host"] == "graph.test"
    assert captured["options"]["ssl"] is True
    assert captured["options"]["password"] == "test-only-password"
    assert captured["params"] == {"source_ids": [IDS[0]]}
    assert "$source_ids" in captured["query"]
    assert captured["timeout"] == 5000 and captured["closed"]
