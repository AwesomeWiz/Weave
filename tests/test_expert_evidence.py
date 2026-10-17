"""
Weave — Tests for Expert Finder evidence.

Verifies:
  - Alice, Ravi, Maya, and Neeraj have distinguishable graph-grounded evidence.
  - Evidence paths are traversable through established typed relationships.
  - No manufactured expert_score or expert_rank properties exist in the dataset.
  - Ranking factors (approvals, commits, issues, discussions, team ownership)
    can be traversed directly from the graph.
"""

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


def test_no_manufactured_scores(seeded_graph):
    """Ensure dataset contains no fake expert_score or expert_rank properties."""
    for node in seeded_graph.all_nodes().values():
        if node.get("entity_type") == "Person":
            assert "expert_score" not in node, f"Person {node['id']} has manufactured expert_score"
            assert "expert_rank" not in node, f"Person {node['id']} has manufactured expert_rank"


def test_alice_evidence(seeded_graph):
    """Alice is strong: approved D-007, participated in D-007, discussed in message, payments team lead."""
    # APPROVED decision:D-007
    assert seeded_graph.get_relationship("person:alice", "APPROVED", "decision:D-007") is not None
    # PARTICIPATED_IN decision:D-007
    assert seeded_graph.get_relationship("person:alice", "PARTICIPATED_IN", "decision:D-007") is not None
    # WROTE message:payment-perf-7
    assert seeded_graph.get_relationship("person:alice", "WROTE", "message:payment-perf-7") is not None
    # MEMBER_OF team:payments
    assert seeded_graph.get_relationship("person:alice", "MEMBER_OF", "team:payments") is not None
    # team:payments OWNS service:payment-service
    assert seeded_graph.get_relationship("team:payments", "OWNS", "service:payment-service") is not None

    alice = seeded_graph.get_node("person:alice")
    assert alice["role"] == "Payments Tech Lead"


def test_ravi_evidence(seeded_graph):
    """Ravi is strong: implemented D-007 via commit, assigned PAY-42, participated in D-007, discussed in message."""
    # PARTICIPATED_IN decision:D-007
    assert seeded_graph.get_relationship("person:ravi", "PARTICIPATED_IN", "decision:D-007") is not None
    # AUTHORED commit:8fae2
    assert seeded_graph.get_relationship("person:ravi", "AUTHORED", "commit:8fae2") is not None
    # Commit implements decision D-007 and closes PAY-42
    assert seeded_graph.get_relationship("commit:8fae2", "IMPLEMENTS_DECISION", "decision:D-007") is not None
    assert seeded_graph.get_relationship("commit:8fae2", "ADDRESSES", "issue:PAY-42") is not None
    # Issue PAY-42 ASSIGNED_TO Ravi
    assert seeded_graph.get_relationship("issue:PAY-42", "ASSIGNED_TO", "person:ravi") is not None
    # WROTE message:payment-perf-7
    assert seeded_graph.get_relationship("person:ravi", "WROTE", "message:payment-perf-7") is not None
    # MEMBER_OF team:payments
    assert seeded_graph.get_relationship("person:ravi", "MEMBER_OF", "team:payments") is not None

    # Ravi did NOT approve D-007 (Alice approved it)
    assert seeded_graph.get_relationship("person:ravi", "APPROVED", "decision:D-007") is None


def test_maya_evidence(seeded_graph):
    """Maya is platform contributor: participated in D-007, discussed Redis infrastructure in message."""
    assert seeded_graph.get_relationship("person:maya", "PARTICIPATED_IN", "decision:D-007") is not None
    assert seeded_graph.get_relationship("person:maya", "WROTE", "message:payment-perf-7") is not None
    assert seeded_graph.get_relationship("person:maya", "MEMBER_OF", "team:platform") is not None

    # Maya did NOT author the implementation commit nor approve the decision
    assert seeded_graph.get_relationship("person:maya", "APPROVED", "decision:D-007") is None
    assert seeded_graph.get_relationship("person:maya", "AUTHORED", "commit:8fae2") is None


def test_weaker_candidate_neeraj(seeded_graph):
    """Neeraj has significantly less evidence for Payment Service / Redis decision than Alice, Ravi, or Maya."""
    assert seeded_graph.get_relationship("person:neeraj", "MEMBER_OF", "team:platform") is not None

    # No D-007 participation
    assert seeded_graph.get_relationship("person:neeraj", "PARTICIPATED_IN", "decision:D-007") is None
    # No D-007 approval
    assert seeded_graph.get_relationship("person:neeraj", "APPROVED", "decision:D-007") is None
    # No commit authorship on Redis implementation
    assert seeded_graph.get_relationship("person:neeraj", "AUTHORED", "commit:8fae2") is None
    # Not assigned to PAY-42
    assert seeded_graph.get_relationship("issue:PAY-42", "ASSIGNED_TO", "person:neeraj") is None
    # Not a participant in payment-perf-7 discussion
    assert seeded_graph.get_relationship("person:neeraj", "WROTE", "message:payment-perf-7") is None


def test_evidence_counts_distinguishable(seeded_graph):
    """Verify evidence degrees distinguish the candidates for Payment Service + Redis decision."""
    all_rels = seeded_graph.all_relationships().values()

    def get_evidence_count(person_id: str) -> int:
        count = 0
        for r in all_rels:
            if r["source_id"] == person_id or r["target_id"] == person_id:
                # Count connections to D-007, PAY-42, 8fae2, payment-perf-7, team:payments
                target_ids = {"decision:D-007", "issue:PAY-42", "commit:8fae2", "message:payment-perf-7", "team:payments"}
                other = r["target_id"] if r["source_id"] == person_id else r["source_id"]
                if other in target_ids:
                    count += 1
        return count

    alice_evidence = get_evidence_count("person:alice")
    ravi_evidence = get_evidence_count("person:ravi")
    maya_evidence = get_evidence_count("person:maya")
    neeraj_evidence = get_evidence_count("person:neeraj")

    assert alice_evidence >= 4, f"Alice should have rich decision/team/discussion evidence (got {alice_evidence})"
    assert ravi_evidence >= 4, f"Ravi should have rich commit/issue/decision evidence (got {ravi_evidence})"
    assert 0 < maya_evidence < ravi_evidence, f"Maya should have intermediate platform evidence (got {maya_evidence})"
    assert neeraj_evidence == 0, f"Neeraj should have no evidence for Payment/Redis decision (got {neeraj_evidence})"
