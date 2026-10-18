"""Offline hosting checks; no database or external provider calls."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph import FalkorGateway, FixtureGateway, GraphUnavailable
from app.main import create_app


def test_process_health_does_not_probe_dependencies_or_mask_real_mode_outage():
    probes = []

    class UnavailableGraph:
        async def health(self):
            probes.append("graph")
            return False

        async def trace_decision(self, _request):
            raise GraphUnavailable()

    class DisabledProvider:
        async def availability(self):
            probes.append("llm")
            raise AssertionError("Process health must not probe the LLM")

    with TestClient(create_app(
        Settings(_env_file=None, graph_mode="falkordb", llm_provider="none"),
        gateway=UnavailableGraph(), provider=DisabledProvider(),
    )) as client:
        live = client.get("/healthz")
        assert live.status_code == 200 and live.json() == {"status": "ok"}
        assert probes == []
        dependency = client.get("/api/health")
        assert dependency.status_code == 503
        assert dependency.json()["graph_mode"] == "falkordb"
        assert dependency.json()["falkordb"] == "unavailable"
        query = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
        assert query.status_code == 503
        assert query.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
        assert "sources" not in query.json()


@pytest.mark.parametrize("path,body", [
    ("/api/query", {"question": "Why does Payment Service use Redis?"}),
    ("/api/change-intelligence", {"target": "Payment Service", "change": "Remove Redis from Payment Service"}),
    ("/api/health", None),
])
def test_exact_https_origin_preflight_and_responses(path, body):
    origin = "https://weave-demo.vercel.app"
    with TestClient(create_app(
        Settings(_env_file=None, graph_mode="fixture", llm_provider="none", cors_origins=[origin]),
        gateway=FixtureGateway(),
    )) as client:
        method = "GET" if body is None else "POST"
        preflight = client.options(path, headers={
            "Origin": origin, "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        })
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        response = client.request(method, path, json=body, headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in response.headers
        if path == "/api/query":
            assert set(response.json()) == {
                "answer", "support_status", "tools_used", "sources", "graph", "metadata",
            }
        rejected = client.options(path, headers={
            "Origin": "https://unapproved.vercel.app", "Access-Control-Request-Method": method,
        })
        assert rejected.status_code == 400
        assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.parametrize("connector", ["trace", "sources", "health"])
def test_all_remote_connectors_require_certificates_and_hostname_verification(monkeypatch, connector):
    captured = {}

    class DatabaseDouble:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.connection = self

        def select_graph(self, name):
            assert name == "novapay"
            return SimpleNamespace(ro_query=lambda *_a, **_k: SimpleNamespace(result_set=[[1]]))

        def list_graphs(self):
            return ["novapay"]

        def close(self):
            pass

    if connector == "trace":
        from weave_graph.client import GraphClient
        monkeypatch.setattr("weave_graph.client.FalkorDB", DatabaseDouble)
        client = GraphClient(host="graph.example.org", port=6380, graph_name="novapay",
                             username="demo-user", password="test-password", ssl=True)
        client.close()
    else:
        monkeypatch.setattr("falkordb.FalkorDB", DatabaseDouble)
        if connector == "sources":
            from weave_data.graph_adapter import FalkorDBGraphAdapter
            adapter = FalkorDBGraphAdapter(host="graph.example.org", port=6380, graph_name="novapay",
                                           username="demo-user", password="test-password", ssl=True)
            adapter.close()
        else:
            settings = Settings(_env_file=None, graph_factory="", falkordb_host="graph.example.org",
                                falkordb_port=6380, falkordb_username="demo-user",
                                falkordb_password="test-password", falkordb_ssl=True)
            assert asyncio.run(FalkorGateway(settings).database_health()) is True
    assert captured["host"] == "graph.example.org" and captured["port"] == 6380
    assert captured["username"] == "demo-user" and captured["password"] == "test-password"
    assert captured["ssl"] is True
    assert captured["ssl_cert_reqs"] == "required"
    assert captured["ssl_check_hostname"] is True
    assert captured["socket_connect_timeout"] == 2
    assert 0 < captured["socket_timeout"] <= 5
