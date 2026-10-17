"""Read-only, opt-in acceptance against the actual expanded seeded graph."""
import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FalkorGateway, FixtureGateway
from app.main import create_app
from weave_data.ingest import prepare_ingestion


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_IMPACT") != "1",
                    reason="Requires actual FalkorDB seeded with the expanded Phase 2 corpus")
def test_real_impact_http_paths_provenance_and_depth(monkeypatch):
    config = Settings(graph_mode="falkordb", graph_factory="app.antony:create_gateway",
                      source_backend="weave_data", llm_provider="none")
    _, _, expected, _, validation = prepare_ingestion(Path(__file__).resolve().parents[2] / "data/novapay")
    assert validation.ok

    def forbidden(*_args, **_kwargs):
        pytest.fail("Real impact attempted fixture, local-file, or memory fallback")
    monkeypatch.setattr(FixtureGateway, "__init__", forbidden)
    monkeypatch.setattr("weave_data.retrieval.load_records", forbidden)
    monkeypatch.setattr("weave_data.retrieval.load_adr_content", forbidden)
    monkeypatch.setattr("weave_data.graph_adapter.InMemoryGraphAdapter", forbidden)
    gateway = FalkorGateway(config)
    assert asyncio.run(gateway.database_health()), "Configured seeded FalkorDB unavailable"
    assert asyncio.run(gateway.health()), "Actual graph tool unavailable"
    client = TestClient(create_app(config, gateway=gateway))
    response = client.post("/api/tools/impact-analysis", json={"entity_id": "service:payment-service", "max_depth": 2})
    assert response.status_code == 200
    result = response.json()
    assert result["metadata"]["graph_mode"] == "falkordb"
    assert [f["service_id"] for f in result["data"]["direct_impact"]] == ["service:checkout-service"]
    assert [f["service_id"] for f in result["data"]["indirect_impact"]] == ["service:order-service"]
    assert result["data"]["indirect_impact"][0]["path"] == [
        "service:payment-service", "service:checkout-service", "service:order-service"]
    edge_set = {(e["source"], e["type"], e["target"]) for e in result["graph"]["edges"]}
    assert ("service:order-service", "DEPENDS_ON", "service:checkout-service") in edge_set
    assert ("service:checkout-service", "DEPENDS_ON", "service:payment-service") in edge_set
    source = next(s for s in result["sources"] if s["id"] == "issue:PAY-42")
    chunks = sorted((c for c in expected if c.source_id == source["id"]), key=lambda c: (c.chunk_index, c.id))
    assert source["snippet"] == "\n\n".join(c.text.strip() for c in chunks)[:1600]
    assert source["metadata"]["chunk_ids"] == [c.id for c in chunks]
    assert source["metadata"]["source_id"] == "issue:PAY-42"
    assert all((c.id, "FROM_ISSUE", c.source_id) in edge_set for c in chunks)
    assert result["support_status"] == "partially_supported"
    shallow = client.post("/api/tools/impact-analysis", json={"entity_id": "service:payment-service", "max_depth": 1}).json()
    assert not shallow["data"]["indirect_impact"]
    technology = client.post("/api/tools/impact-analysis", json={"entity_id": "tech:redis", "max_depth": 3}).json()
    assert technology["data"]["direct_impact"][0]["service_id"] == "service:payment-service"
    assert [f["impact_depth"] for f in technology["data"]["indirect_impact"]] == [2, 3]
