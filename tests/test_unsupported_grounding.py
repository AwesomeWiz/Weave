"""
Weave — Negative test for unsupported-question grounding.

Verifies:
  - Unsupported question: "Why did NovaPay choose MongoDB for the fraud service?"
  - No MongoDB entity exists in technologies.json, graph nodes, or aliases.
  - No Fraud Service entity exists in services.json, graph nodes, or aliases.
  - No decision exists introducing MongoDB or affecting a fraud service.
  - find_sources() returns [] for MongoDB or fraud-related keys.
  - Redis evidence for Payment Service does NOT leak into or support MongoDB/fraud queries.
"""

from pathlib import Path
import pytest

from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion
from weave_data.loader import load_aliases, load_records
from weave_data.retrieval import find_sources

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture(scope="module")
def dataset_and_graph():
    adapter = InMemoryGraphAdapter()
    res = run_ingestion(DATA_DIR, adapter=adapter)
    assert res.status == "success"
    records, _ = load_records(DATA_DIR)
    aliases = load_aliases(DATA_DIR)
    return records, aliases, adapter


def test_no_mongodb_node(dataset_and_graph):
    records, _, adapter = dataset_and_graph
    # Check loaded records
    for r in records:
        assert "mongo" not in r.id.lower()
        if hasattr(r, "name"):
            assert "mongo" not in r.name.lower()

    # Check graph nodes
    for nid, node in adapter.all_nodes().items():
        assert "mongo" not in nid.lower()
        for k, v in node.items():
            if isinstance(v, str):
                assert "mongodb" not in v.lower(), f"Node {nid} mentions MongoDB in property {k}"


def test_no_fraud_service_node(dataset_and_graph):
    records, _, adapter = dataset_and_graph
    for r in records:
        assert "fraud" not in r.id.lower()
        if hasattr(r, "name"):
            assert "fraud" not in r.name.lower()

    for nid, node in adapter.all_nodes().items():
        assert "fraud" not in nid.lower()
        for k, v in node.items():
            if isinstance(v, str):
                assert "fraud service" not in v.lower(), f"Node {nid} mentions fraud service in property {k}"


def test_no_mongodb_or_fraud_decision(dataset_and_graph):
    records, _, _ = dataset_and_graph
    from weave_data.models import DecisionRecord
    for r in records:
        if isinstance(r, DecisionRecord):
            assert "mongo" not in r.title.lower()
            assert "fraud" not in r.title.lower()
            if r.summary:
                assert "mongo" not in r.summary.lower()
                assert "fraud" not in r.summary.lower()
            for tech in r.introduces:
                assert "mongo" not in tech.lower()
            for svc in r.affects:
                assert "fraud" not in svc.lower()


def test_no_mongodb_or_fraud_aliases(dataset_and_graph):
    _, aliases, _ = dataset_and_graph
    for alias, target in aliases.items():
        assert "mongo" not in alias.lower(), f"Alias '{alias}' accidentally introduces MongoDB"
        assert "fraud" not in alias.lower(), f"Alias '{alias}' accidentally introduces fraud"
        assert "mongo" not in target.lower()
        assert "fraud" not in target.lower()


def test_source_retrieval_returns_empty_for_unsupported_targets(dataset_and_graph):
    _, _, adapter = dataset_and_graph
    unsupported_ids = [
        "tech:mongodb",
        "service:fraud-service",
        "decision:D-MONGO",
        "doc:ADR-MONGO",
    ]
    # Local retrieval
    res_local = find_sources(unsupported_ids, data_dir=DATA_DIR)
    assert res_local == [], "find_sources() must return [] for unsupported question IDs in local mode"

    # Graph retrieval
    res_graph = find_sources(unsupported_ids, adapter=adapter)
    assert res_graph == [], "find_sources() must return [] for unsupported question IDs in graph mode"


def test_payment_service_redis_evidence_does_not_mention_mongodb(dataset_and_graph):
    """Payment Service / D-007 evidence chain is purely Redis-focused."""
    records, _, _ = dataset_and_graph
    for r in records:
        if r.id in ("decision:D-007", "issue:PAY-42", "commit:8fae2", "message:payment-perf-7", "doc:ADR-7"):
            text = " ".join(str(v) for v in r.model_dump().values() if v is not None)
            assert "mongo" not in text.lower()
            assert "fraud" not in text.lower()
