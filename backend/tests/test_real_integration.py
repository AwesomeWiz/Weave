"""Opt-in acceptance check. Never seeds or substitutes a fixture into real mode."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.config import Settings
from app.graph import FixtureGateway
from app.main import create_app
from app.models import Source
from real_acceptance import assert_primary_evidence


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_INTEGRATION") != "1",
                    reason="Requires teammate graph adapter, seeded FalkorDB and evidence export")
def test_seeded_falkordb_primary_question(monkeypatch):
    def forbidden_fixture(*_args, **_kwargs):
        pytest.fail("Real integration must never instantiate the development fixture")

    monkeypatch.setattr(FixtureGateway, "__init__", forbidden_fixture)
    settings = Settings(graph_mode="falkordb", llm_provider="none")
    assert settings.graph_factory, "Configure the teammate graph adapter factory"
    manifest_path = os.getenv("WEAVE_REAL_EVIDENCE_MANIFEST")
    assert manifest_path, "Provide an independently reviewed export of Alen's seeded source corpus"
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    assert manifest["graph_name"] == settings.graph_name
    assert isinstance(manifest["dataset_revision"], str) and manifest["dataset_revision"].strip()
    authoritative = TypeAdapter(list[Source]).validate_python(manifest["sources"])
    assert authoritative
    assert all(s.metadata.get("dataset") != "development_fixture" for s in authoritative)
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, "Actual seeded FalkorDB and graph tool must be available"
        assert health.json()["falkordb"] == "connected"
        assert health.json()["graph_tool"] == "available"
        assert health.json()["graph_mode"] == "falkordb"
        assert health.json()["graph"] == manifest["graph_name"]
        response = client.post("/api/query", json={"question": "Why does Payment Service use Redis?"})
        assert response.status_code == 200
        assert_primary_evidence(response.json(), authoritative)
