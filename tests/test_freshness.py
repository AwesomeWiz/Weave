"""
Weave — Tests for Knowledge Freshness dataset and heuristics.

Verifies:
  - Planned chronology matches documentation:
      Architecture Overview (May 1)
      < INC-17 (May 10)
      < PAY-42 (May 11)
      < Redis discussion (May 15-17)
      < D-007 (May 18)
      < Commit 8fae2 (May 19)
      < ADR-7 (May 20)
      < Runbook (May 22)
  - doc:architecture-overview is flagged as a review candidate / stale because
    it describes service:payment-service and was updated before D-007 and commit 8fae2.
  - doc:ADR-7 is current for D-007 based on its May 20 timestamp and DOCUMENTED_IN relationship.
  - Negative freshness case: doc:runbook-payment-latency is NOT flagged as stale because
    its timestamp (May 22) post-dates all decisions and architecture-changing commits.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture(scope="module")
def seeded_graph():
    adapter = InMemoryGraphAdapter()
    res = run_ingestion(DATA_DIR, adapter=adapter)
    assert res.status == "success", f"Ingestion failed: {res.errors}"
    return adapter


def test_chronology_order(seeded_graph):
    """Verify strict chronological ordering across the full chain."""
    arch_doc = seeded_graph.get_node("doc:architecture-overview")
    inc = seeded_graph.get_node("incident:INC-17")
    issue = seeded_graph.get_node("issue:PAY-42")
    msg = seeded_graph.get_node("message:payment-perf-7")
    decision = seeded_graph.get_node("decision:D-007")
    commit = seeded_graph.get_node("commit:8fae2")
    adr = seeded_graph.get_node("doc:ADR-7")
    runbook = seeded_graph.get_node("doc:runbook-payment-latency")

    t_arch = datetime.fromisoformat(arch_doc["updated_at"])
    t_inc = datetime.fromisoformat(inc["started_at"])
    t_issue = datetime.fromisoformat(issue["created_at"])
    t_msg = datetime.fromisoformat(msg["timestamp"])
    t_decision = datetime.fromisoformat(decision["decided_at"])
    t_commit = datetime.fromisoformat(commit["timestamp"])
    t_adr = datetime.fromisoformat(adr["updated_at"])
    t_runbook = datetime.fromisoformat(runbook["updated_at"])

    assert t_arch < t_inc, "Architecture Overview must precede INC-17"
    assert t_inc < t_issue, "INC-17 must precede PAY-42"
    assert t_issue < t_msg, "PAY-42 must precede discussion"
    assert t_msg < t_decision, "Discussion must precede Decision D-007"
    assert t_decision < t_commit, "Decision D-007 must precede Commit 8fae2"
    assert t_commit < t_adr, "Commit 8fae2 must precede ADR-7 update"
    assert t_adr < t_runbook, "ADR-7 must precede Runbook update"


def evaluate_freshness(adapter: InMemoryGraphAdapter, document_id: str) -> dict:
    """
    Standard graph-backed freshness evaluation following docs/04_KNOWLEDGE_GRAPH.md §10.
    A document is a review candidate if:
      (doc)-[:DESCRIBES]->(s:Service)
      AND (
        (d:Decision {status: 'accepted'})-[:AFFECTS]->(s) WHERE d.decided_at > doc.updated_at
        OR (c:Commit {architecture_change: true})-[:CHANGES]->(s) WHERE c.timestamp > doc.updated_at
      )
    """
    doc = adapter.get_node(document_id)
    assert doc is not None, f"Document {document_id} not found"
    doc_updated = datetime.fromisoformat(doc["updated_at"])

    all_rels = adapter.all_relationships().values()
    # Find services described by document
    described_services = [
        r["target_id"] for r in all_rels
        if r["source_id"] == document_id and r["rel_type"] == "DESCRIBES"
    ]

    reasons = []
    for service_id in described_services:
        # Check later accepted decisions affecting service
        for r in all_rels:
            if r["rel_type"] == "AFFECTS" and r["target_id"] == service_id:
                dec = adapter.get_node(r["source_id"])
                if dec and dec.get("entity_type") == "Decision" and dec.get("status") == "accepted":
                    dec_time = datetime.fromisoformat(dec["decided_at"])
                    if dec_time > doc_updated:
                        reasons.append({
                            "type": "decision",
                            "id": dec["id"],
                            "timestamp": dec["decided_at"],
                            "service": service_id,
                            "reason": f"Accepted decision {dec['id']} on {dec['decided_at']} affects {service_id}",
                        })

        # Check later architecture-changing commits affecting service
        for r in all_rels:
            if r["rel_type"] == "CHANGES" and r["target_id"] == service_id:
                commit = adapter.get_node(r["source_id"])
                if commit and commit.get("architecture_change"):
                    com_time = datetime.fromisoformat(commit["timestamp"])
                    if com_time > doc_updated:
                        reasons.append({
                            "type": "commit",
                            "id": commit["id"],
                            "timestamp": commit["timestamp"],
                            "service": service_id,
                            "reason": f"Architecture change commit {commit['id']} on {commit['timestamp']} changes {service_id}",
                        })

    return {
        "document_id": document_id,
        "updated_at": doc["updated_at"],
        "is_review_candidate": len(reasons) > 0,
        "reasons": reasons,
    }


def test_architecture_overview_is_review_candidate(seeded_graph):
    """Architecture Overview predates D-007 and 8fae2 -> flagged as review candidate."""
    result = evaluate_freshness(seeded_graph, "doc:architecture-overview")
    assert result["is_review_candidate"] is True
    reason_ids = {r["id"] for r in result["reasons"]}
    assert "decision:D-007" in reason_ids
    assert "commit:8fae2" in reason_ids


def test_adr7_is_current(seeded_graph):
    """ADR-7 was updated May 20, 2026, after D-007 (May 18) and Commit 8fae2 (May 19) -> current."""
    result = evaluate_freshness(seeded_graph, "doc:ADR-7")
    assert result["is_review_candidate"] is False
    assert result["reasons"] == []


def test_negative_freshness_case_runbook_is_current(seeded_graph):
    """Runbook was updated May 22, 2026, after all decisions and commits -> NOT flagged as stale."""
    result = evaluate_freshness(seeded_graph, "doc:runbook-payment-latency")
    assert result["is_review_candidate"] is False
    assert result["reasons"] == []
