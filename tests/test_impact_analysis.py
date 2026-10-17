"""
Weave — Tests for Impact Analysis.

Tests:
  - Payment Service technology relationships.
  - Direct and indirect service dependencies.
  - Separation of direct and indirect dependents.
  - Service ownership relationships.
  - Live impact_analysis() results from FalkorDB.
  - Impact depths and traversal paths.
  - Ownership information in impact results.
  - Invalid depth and missing entity handling.
"""

from pathlib import Path

import pytest

from app.graph.client import GraphClient
from app.graph.impact import impact_analysis
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture(scope="module")
def seeded_graph():
    adapter = InMemoryGraphAdapter()
    result = run_ingestion(DATA_DIR, adapter=adapter)

    assert result.status == "success", (
        f"Ingestion failed: {result.errors}"
    )

    return adapter


@pytest.fixture
def live_client():
    client = GraphClient(graph_name="novapay")

    try:
        assert client.health_check(), "FalkorDB health check failed"
        yield client
    finally:
        client.close()


def test_payment_service_technologies(seeded_graph):
    redis = seeded_graph.get_relationship(
        "service:payment-service",
        "USES",
        "tech:redis",
    )
    postgresql = seeded_graph.get_relationship(
        "service:payment-service",
        "USES",
        "tech:postgresql",
    )

    assert redis is not None
    assert postgresql is not None


def test_direct_dependent_checkout_service(seeded_graph):
    relationship = seeded_graph.get_relationship(
        "service:checkout-service",
        "DEPENDS_ON",
        "service:payment-service",
    )

    assert relationship is not None


def test_indirect_dependent_order_service(seeded_graph):
    order_to_checkout = seeded_graph.get_relationship(
        "service:order-service",
        "DEPENDS_ON",
        "service:checkout-service",
    )

    assert order_to_checkout is not None
    assert order_to_checkout["target_id"] == "service:checkout-service"

    checkout_to_payment = seeded_graph.get_relationship(
        order_to_checkout["target_id"],
        "DEPENDS_ON",
        "service:payment-service",
    )

    assert checkout_to_payment is not None


def test_direct_and_indirect_dependents_are_distinct(seeded_graph):
    relationships = seeded_graph.all_relationships().values()
    dependencies = [
        relationship
        for relationship in relationships
        if relationship["rel_type"] == "DEPENDS_ON"
    ]

    direct = {
        relationship["source_id"]
        for relationship in dependencies
        if relationship["target_id"] == "service:payment-service"
    }

    indirect = {
        relationship["source_id"]
        for relationship in dependencies
        if relationship["target_id"] in direct
    }

    assert direct == {"service:checkout-service"}
    assert indirect == {"service:order-service"}
    assert direct.isdisjoint(indirect)


def test_service_ownership_relationships(seeded_graph):
    expected_relationships = [
        ("team:payments", "service:payment-service"),
        ("team:platform", "service:checkout-service"),
        ("team:platform", "service:order-service"),
    ]

    for team_id, service_id in expected_relationships:
        relationship = seeded_graph.get_relationship(
            team_id,
            "OWNS",
            service_id,
        )
        assert relationship is not None


def test_live_impact_analysis_direct_and_indirect(live_client):
    result = impact_analysis(
        live_client,
        "service:payment-service",
        max_depth=2,
    )

    direct_ids = {
        item["service_id"]
        for item in result["data"]["direct_impact"]
    }
    indirect_ids = {
        item["service_id"]
        for item in result["data"]["indirect_impact"]
    }

    assert direct_ids == {"service:checkout-service"}
    assert indirect_ids == {"service:order-service"}
    assert result["warnings"] == []


def test_live_impact_analysis_depths_and_paths(live_client):
    result = impact_analysis(
        live_client,
        "service:payment-service",
        max_depth=2,
    )

    direct = result["data"]["direct_impact"][0]
    indirect = result["data"]["indirect_impact"][0]

    assert direct["impact_depth"] == 1
    assert indirect["impact_depth"] == 2

    assert direct["path"] == [
        "service:payment-service",
        "service:checkout-service",
    ]

    assert indirect["path"] == [
        "service:payment-service",
        "service:checkout-service",
        "service:order-service",
    ]


def test_live_impact_analysis_includes_owners(live_client):
    result = impact_analysis(
        live_client,
        "service:payment-service",
        max_depth=2,
    )

    direct = next(
        item
        for item in result["data"]["direct_impact"]
        if item["service_id"] == "service:checkout-service"
    )

    owner_ids = {
        owner["id"]
        for owner in direct["owners"]
    }

    assert "team:platform" in owner_ids


def test_live_impact_analysis_rejects_invalid_depth(live_client):
    result = impact_analysis(
        live_client,
        "service:payment-service",
        max_depth=4,
    )

    assert result["data"]["direct_impact"] == []
    assert result["data"]["indirect_impact"] == []
    assert any(
        "max_depth" in warning
        for warning in result["warnings"]
    )


def test_live_impact_analysis_handles_missing_entity(live_client):
    result = impact_analysis(
        live_client,
        "service:does-not-exist",
    )

    assert result["data"]["entity"] is None
    assert result["data"]["direct_impact"] == []
    assert result["data"]["indirect_impact"] == []
    assert result["warnings"]