"""
Weave — Tests for Impact Analysis graph relationships.

Verifies:
  - Direct dependents: services that directly DEPEND_ON Payment Service (e.g. Checkout Service).
  - Indirect dependents: services downstream of direct dependents (e.g. Order Service -> Checkout -> Payment).
  - Tech usage impact: technologies USES by services.
  - Ownership: teams OWNS services.
  - Traversal paths distinguish direct (1-hop) from indirect (2-hop) dependents.
"""

from pathlib import Path
import pytest

from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion, prepare_ingestion
from weave_data.relationships import extract_relationships

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture(scope="module")
def seeded_graph():
    adapter = InMemoryGraphAdapter()
    res = run_ingestion(DATA_DIR, adapter=adapter)
    assert res.status == "success", f"Ingestion failed: {res.errors}"
    return adapter


def test_payment_service_technologies(seeded_graph):
    rel = seeded_graph.get_relationship("service:payment-service", "USES", "tech:redis")
    assert rel is not None, "Payment Service must use tech:redis"

    rel_pg = seeded_graph.get_relationship("service:payment-service", "USES", "tech:postgresql")
    assert rel_pg is not None, "Payment Service must use tech:postgresql"


def test_direct_dependent_checkout_service(seeded_graph):
    """Direct impact: Checkout Service depends directly on Payment Service (1 hop)."""
    rel = seeded_graph.get_relationship("service:checkout-service", "DEPENDS_ON", "service:payment-service")
    assert rel is not None, "Checkout Service must directly DEPEND_ON Payment Service"


def test_indirect_dependent_order_service(seeded_graph):
    """Indirect impact: Order Service depends on Checkout Service (2 hops from Payment Service)."""
    rel1 = seeded_graph.get_relationship("service:order-service", "DEPENDS_ON", "service:checkout-service")
    assert rel1 is not None, "Order Service must DEPEND_ON Checkout Service"

    # Verify traversal path from Order Service to Payment Service
    # (order:Order Service)-[:DEPENDS_ON]->(checkout:Checkout Service)-[:DEPENDS_ON]->(payment:Payment Service)
    assert rel1["target_id"] == "service:checkout-service"
    rel2 = seeded_graph.get_relationship(rel1["target_id"], "DEPENDS_ON", "service:payment-service")
    assert rel2 is not None, "Checkout Service must bridge Order Service to Payment Service"


def test_distinguish_direct_from_indirect_dependents(seeded_graph):
    """Algorithmic BFS/traversal distinguishing direct vs indirect dependents of Payment Service."""
    all_rels = seeded_graph.all_relationships().values()
    depends_on_edges = [r for r in all_rels if r["rel_type"] == "DEPENDS_ON"]

    # 1-hop (direct)
    direct_dependents = {r["source_id"] for r in depends_on_edges if r["target_id"] == "service:payment-service"}
    assert direct_dependents == {"service:checkout-service"}

    # 2-hop (indirect)
    indirect_dependents = set()
    for dep in direct_dependents:
        for r in depends_on_edges:
            if r["target_id"] == dep:
                indirect_dependents.add(r["source_id"])

    assert indirect_dependents == {"service:order-service"}
    assert direct_dependents.isdisjoint(indirect_dependents), "Direct and indirect sets must be disjoint"


def test_service_ownership_relationships(seeded_graph):
    """Teams OWNS services."""
    rel_pay = seeded_graph.get_relationship("team:payments", "OWNS", "service:payment-service")
    assert rel_pay is not None, "team:payments must own service:payment-service"

    rel_chk = seeded_graph.get_relationship("team:platform", "OWNS", "service:checkout-service")
    assert rel_chk is not None, "team:platform must own service:checkout-service"

    rel_ord = seeded_graph.get_relationship("team:platform", "OWNS", "service:order-service")
    assert rel_ord is not None, "team:platform must own service:order-service"
