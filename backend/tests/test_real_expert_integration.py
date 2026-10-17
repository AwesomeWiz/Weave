"""Opt-in, read-only application smoke against an actually seeded FalkorDB."""
import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FixtureGateway
from app.main import create_app


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_EXPERT_INTEGRATION") != "1",
                    reason="Requires actual seeded NovaPay FalkorDB and the real teammate adapters")
def test_real_expert_and_three_tool_application(monkeypatch):
    def forbidden_fixture(*_args, **_kwargs):
        pytest.fail("Real Expert Finder must never instantiate a development fixture")
    monkeypatch.setattr(FixtureGateway, "__init__", forbidden_fixture)
    config = Settings(graph_mode="falkordb", source_backend="weave_data", llm_provider="none")
    assert config.graph_factory == "app.antony:create_gateway"
    with TestClient(create_app(config)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200 and health.json()["falkordb"] == "connected"
        response = client.post("/api/tools/expert-finder", json={"query": "Who knows Payment Service?"})
        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["graph_mode"] == "falkordb"
        assert body["support_status"] == "supported"
        assert [t["id"] for t in body["data"]["topics"]] == ["service:payment-service"]
        people = {e["person"]["id"]: e for e in body["data"]["experts"]}
        assert {"person:alice", "person:ravi", "person:maya"} <= people.keys()
        assert people["person:alice"]["ownership_classification"] == "team_membership_with_team_owned_service"
        assert {"issue:PAY-42", "message:payment-perf-7", "commit:8fae2"} <= {s["id"] for s in body["sources"]}
        assert all(s["metadata"]["chunk_ids"] and s["metadata"]["chunks"] for s in body["sources"])
        for query in ("Who approved D-007?", "Who can explain the Redis decision?"):
            decision = client.post("/api/tools/expert-finder", json={"query": query})
            assert decision.status_code == 200
            data = decision.json()["data"]
            assert [t["id"] for t in data["topics"]] == ["decision:D-007"]
            assert any(e["category"] == "decision_approval" and e["entity_id"] == "decision:D-007"
                       for p in data["experts"] if p["person"]["id"] == "person:alice" for e in p["evidence"])
        response = client.post("/api/query", json={"question":
            "Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?"})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"answer", "support_status", "tools_used", "sources", "graph", "metadata"}
        assert body["tools_used"] == ["trace_decision", "impact_analysis", "find_expert"]
        assert body["support_status"] == "partially_supported"
        assert any(n["id"] == "decision:D-007" and n["properties"]["status"] == "accepted" for n in body["graph"]["nodes"])
