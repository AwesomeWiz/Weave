"""Opt-in, read-only acceptance against an actually seeded FalkorDB; never hosted."""
import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FixtureGateway
from app.main import create_app


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_FRESHNESS_INTEGRATION") != "1",
                    reason="Requires actual seeded NovaPay FalkorDB and real teammate adapters")
def test_real_freshness_and_four_tool_application(monkeypatch):
    monkeypatch.setattr(FixtureGateway, "__init__", lambda *_: pytest.fail("Real-mode fixture fallback"))
    config = Settings(graph_mode="falkordb", source_backend="weave_data", llm_provider="none")
    assert config.graph_factory == "app.antony:create_gateway"
    with TestClient(create_app(config)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["falkordb"] == "connected"
        response = client.post("/api/tools/freshness", json={"entity": "Payment Service"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["metadata"]["graph_mode"] == "falkordb"
        assert body["metadata"]["generation"] == "deterministic"
        assert body["support_status"] == "supported"
        assert body["data"]["entity"]["id"] == "service:payment-service"
        findings = {f["document_id"]: f for f in body["data"]["review_candidates"]}
        finding = findings["doc:architecture-overview"]
        assert "doc:ADR-7" not in findings and "doc:runbook-payment-latency" not in findings
        assert {t["id"] for t in finding["triggers"]} == {"decision:D-007", "commit:8fae2", "incident:INC-17"}
        edges = {(e["source"], e["type"], e["target"]) for e in body["graph"]["edges"]}
        assert ("doc:architecture-overview", "DESCRIBES", "service:payment-service") in edges
        for trigger in finding["triggers"]:
            assert all((p["source"], p["type"], p["target"]) in edges for p in trigger["path"])
            assert trigger["source_ids"] == ([trigger["id"]] if trigger["type"] == "commit" else [])
        assert {s["id"] for s in body["sources"]} == {"doc:architecture-overview", "commit:8fae2"}
        assert all(s["metadata"]["chunk_ids"] and s["metadata"]["chunks"] for s in body["sources"])
        response = client.post("/api/query", json={"question":
            "Why does Payment Service use Redis?; What would be affected if Redis changed?; "
            "Who knows Payment Service?; Which documents about Payment Service need review?"})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
        assert body["tools_used"] == ["trace_decision", "impact_analysis", "find_expert", "find_stale_knowledge"]
        assert body["support_status"] == "partially_supported"
