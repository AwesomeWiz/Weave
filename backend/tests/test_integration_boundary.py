"""Regressions for teammate adapter shapes that differ from development data."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.context import build_context
from app.graph import FalkorGateway, FixtureGateway, GraphContractError
from app.main import create_app
from app.models import TraceInput


TARGET = TraceInput(service="Payment Service", technology="Redis")


def test_source_ids_can_differ_from_graph_entity_ids():
    gateway = FixtureGateway()
    sources = [source.model_copy(update={"id": f"source:{source.id}"})
               for source in gateway.sources]
    gateway.trace.source_ids = [source.id for source in sources]
    context = build_context(gateway.trace, sources, TARGET)
    assert context.status == "supported"
    assert "[source:incident:INC-17]" in context.summary
    assert "[source:issue:PAY-42]" in context.summary
    assert "[source:message:payment-perf-7]" in context.summary
    assert "[source:doc:ADR-7]" in context.summary
    assert "[source:commit:8fae2]" in context.summary


def test_nonaccepted_decision_does_not_explain_current_use():
    gateway = FixtureGateway()
    decision = next(n for n in gateway.trace.graph.nodes if n.type == "Decision")
    decision.properties["status"] = "proposed"
    context = build_context(gateway.trace, gateway.sources, TARGET)
    assert context.status == "partially_supported"
    assert not context.can_explain
    assert "Redis was introduced" not in context.summary
    assert any("accepted" in warning for warning in context.warnings)


def test_llm_probe_failure_does_not_mark_working_graph_unavailable():
    class BrokenProbe:
        async def availability(self):
            raise RuntimeError("provider failure")

        async def generate(self, *_args):
            pytest.fail("Health must not generate an answer")

    client = TestClient(create_app(Settings(graph_mode="falkordb"),
                                  gateway=FixtureGateway(), provider=BrokenProbe()))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["graph_tool"] == "available"
    assert response.json()["llm"] == "unavailable"


def test_malformed_trace_is_a_contract_error():
    class InvalidAdapter:
        async def trace_decision(self, _query):
            return {"graph": {"nodes": [{"id": "no-type-or-label"}], "edges": []}}

    gateway = FalkorGateway(Settings(graph_factory=""))
    gateway.delegate = InvalidAdapter()
    with pytest.raises(GraphContractError):
        asyncio.run(gateway.trace_decision(TARGET))


def test_malformed_sources_are_a_contract_error():
    class InvalidAdapter:
        async def find_sources(self, _ids):
            return [{"id": "no-excerpt-or-type"}]

    gateway = FalkorGateway(Settings(graph_factory=""))
    gateway.delegate = InvalidAdapter()
    with pytest.raises(GraphContractError):
        asyncio.run(gateway.find_sources(["no-excerpt-or-type"]))


@pytest.mark.parametrize("stage", ["trace", "sources"])
def test_invalid_adapter_payload_returns_sanitized_502(stage):
    fixture = FixtureGateway()

    class InvalidAdapter:
        async def trace_decision(self, _query):
            if stage == "trace":
                return {"graph": {"nodes": [{"id": "private-debug-value"}]}}
            return fixture.trace

        async def find_sources(self, _ids):
            return [{"id": "private-debug-value"}]

    gateway = FalkorGateway(Settings(graph_factory=""))
    gateway.delegate = InvalidAdapter()
    client = TestClient(create_app(Settings(graph_mode="falkordb"), gateway=gateway))
    response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "GRAPH_CONTRACT_ERROR"
    assert "private-debug-value" not in response.text
