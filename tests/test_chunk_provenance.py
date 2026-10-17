"""
Weave — Tests for Chunk and Source Provenance.

Verifies:
  - The four original chunk IDs are strictly preserved:
      chunk:issue:PAY-42:0
      chunk:message:payment-perf-7:0
      chunk:commit:8fae2:0
      chunk:doc:ADR-7:0
  - Added document chunks:
      chunk:doc:architecture-overview:0
      chunk:doc:runbook-payment-latency:0
  - Directional FROM_* provenance edges link Chunk -> Source entity.
  - Chunk metadata: source_id, source_type, title, text, chunk_index, timestamp, url.
  - Exact deterministic source retrieval via find_sources() in both local and graph-backed mode.
"""

from pathlib import Path
import pytest

from weave_data.chunks import generate_chunks
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion
from weave_data.loader import load_records, load_adr_content
from weave_data.retrieval import find_sources

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture(scope="module")
def prepared_chunks():
    records, _ = load_records(DATA_DIR)
    adr_content = load_adr_content(DATA_DIR)
    return generate_chunks(records, adr_content)


@pytest.fixture(scope="module")
def seeded_graph():
    adapter = InMemoryGraphAdapter()
    res = run_ingestion(DATA_DIR, adapter=adapter)
    assert res.status == "success"
    return adapter


def test_preserved_and_added_chunk_ids(prepared_chunks):
    chunk_ids = {c.id for c in prepared_chunks}
    expected_original = {
        "chunk:issue:PAY-42:0",
        "chunk:message:payment-perf-7:0",
        "chunk:commit:8fae2:0",
        "chunk:doc:ADR-7:0",
    }
    assert expected_original.issubset(chunk_ids), f"Missing original chunk IDs: {expected_original - chunk_ids}"

    expected_added = {
        "chunk:doc:architecture-overview:0",
        "chunk:doc:runbook-payment-latency:0",
    }
    assert expected_added.issubset(chunk_ids), f"Missing added chunk IDs: {expected_added - chunk_ids}"


def test_chunk_provenance_mapping(prepared_chunks):
    chunk_map = {c.id: c for c in prepared_chunks}

    # PAY-42
    c_pay = chunk_map["chunk:issue:PAY-42:0"]
    assert c_pay.source_id == "issue:PAY-42"
    assert c_pay.source_type == "Issue"
    assert "latency" in c_pay.text.lower()
    assert c_pay.url == "https://jira.novapay.example/browse/PAY-42"

    # message
    c_msg = chunk_map["chunk:message:payment-perf-7:0"]
    assert c_msg.source_id == "message:payment-perf-7"
    assert c_msg.source_type == "Message"
    assert "redis" in c_msg.text.lower()

    # commit
    c_commit = chunk_map["chunk:commit:8fae2:0"]
    assert c_commit.source_id == "commit:8fae2"
    assert c_commit.source_type == "Commit"
    assert "redis" in c_commit.text.lower()

    # ADR-7
    c_adr = chunk_map["chunk:doc:ADR-7:0"]
    assert c_adr.source_id == "doc:ADR-7"
    assert c_adr.source_type == "Document"
    assert "Redis" in c_adr.text

    # architecture overview
    c_arch = chunk_map["chunk:doc:architecture-overview:0"]
    assert c_arch.source_id == "doc:architecture-overview"
    assert c_arch.source_type == "Document"
    assert "PostgreSQL" in c_arch.text

    # runbook
    c_rb = chunk_map["chunk:doc:runbook-payment-latency:0"]
    assert c_rb.source_id == "doc:runbook-payment-latency"
    assert c_rb.source_type == "Document"
    assert "PaymentServiceP99LatencyHigh" in c_rb.text


def test_graph_provenance_relationships(seeded_graph):
    """Chunk -> Source relationship direction and labels."""
    expected_edges = [
        ("chunk:issue:PAY-42:0", "FROM_ISSUE", "issue:PAY-42"),
        ("chunk:message:payment-perf-7:0", "FROM_MESSAGE", "message:payment-perf-7"),
        ("chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2"),
        ("chunk:doc:ADR-7:0", "FROM_DOCUMENT", "doc:ADR-7"),
        ("chunk:doc:architecture-overview:0", "FROM_DOCUMENT", "doc:architecture-overview"),
        ("chunk:doc:runbook-payment-latency:0", "FROM_DOCUMENT", "doc:runbook-payment-latency"),
    ]

    for src_chunk, rel_type, tgt_source in expected_edges:
        rel = seeded_graph.get_relationship(src_chunk, rel_type, tgt_source)
        assert rel is not None, f"Missing provenance edge: ({src_chunk})-[:{rel_type}]->({tgt_source})"


def test_deterministic_retrieval_all_sources(seeded_graph):
    """find_sources() retrieves exact structured evidence for all text-bearing sources."""
    sources = [
        "issue:PAY-42",
        "message:payment-perf-7",
        "commit:8fae2",
        "doc:ADR-7",
        "doc:architecture-overview",
        "doc:runbook-payment-latency",
    ]

    results_graph = find_sources(sources, adapter=seeded_graph)
    assert len(results_graph) == 6
    assert [r.id for r in results_graph] == sources

    results_local = find_sources(sources, data_dir=DATA_DIR)
    assert len(results_local) == 6
    assert [r.id for r in results_local] == sources

    # Snippets from graph and local must match verbatim
    for rg, rl in zip(results_graph, results_local):
        assert rg.id == rl.id
        assert rg.snippet == rl.snippet
        assert rg.chunk_ids == rl.chunk_ids
        assert rg.title == rl.title
