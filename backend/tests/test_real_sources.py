"""Opt-in real ingestion/retrieval smoke, independent of Antony's trace tool."""
import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import Settings
from app.sources import WeaveDataSourceRetriever
from weave_data.graph_adapter import FalkorDBGraphAdapter
from weave_data.ingest import prepare_ingestion, run_ingestion


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("WEAVE_RUN_REAL_SOURCES") != "1",
                    reason="Requires an available real FalkorDB; creates a dedicated test graph")
def test_real_ingestion_and_source_retrieval(monkeypatch):
    # A unique, owned graph avoids changing a developer's seeded novapay graph.
    config = Settings(graph_mode="falkordb", source_backend="weave_data",
                      graph_name=f"weave_source_smoke_{uuid4().hex}")
    adapter = FalkorDBGraphAdapter(
        host=config.falkordb_host, port=config.falkordb_port, graph_name=config.graph_name,
        username=config.falkordb_username or None,
        password=config.falkordb_password.get_secret_value() if config.falkordb_password else None,
        ssl=config.falkordb_ssl,
    )
    data_dir = Path(__file__).resolve().parents[2] / "data" / "novapay"
    _, _, expected, _, validation = prepare_ingestion(data_dir)
    assert validation.ok
    try:
        first = run_ingestion(data_dir, adapter)
        assert first.status == "success", first.errors
        counts = (adapter.node_count(), adapter.relationship_count(), adapter.chunk_count())
        assert run_ingestion(data_dir, adapter).status == "success"
        assert counts == (adapter.node_count(), adapter.relationship_count(), adapter.chunk_count())
        # Subsequent retrieval opens a different client, using only persisted graph data.
        def forbidden(*_args, **_kwargs):
            pytest.fail("Real source retrieval attempted local-file or memory fallback")
        monkeypatch.setattr("weave_data.retrieval.load_records", forbidden)
        monkeypatch.setattr("weave_data.retrieval.load_adr_content", forbidden)
        monkeypatch.setattr("weave_data.graph_adapter.InMemoryGraphAdapter", forbidden)
        ids = ["issue:PAY-42", "message:payment-perf-7", "commit:8fae2", "doc:ADR-7"]
        sources = asyncio.run(WeaveDataSourceRetriever(config).find_sources(ids))
        assert [s.id for s in sources] == ids
        for source in sources:
            chunks = sorted((c for c in expected if c.source_id == source.id),
                            key=lambda c: (c.chunk_index, c.id))
            assert source.snippet == "\n\n".join(c.text.strip() for c in chunks)
            assert source.metadata["chunk_ids"] == [c.id for c in chunks]
            assert source.metadata["chunks"] == [c.model_dump(mode="json", exclude={"text"}) for c in chunks]
            assert source.timestamp == chunks[0].model_dump(mode="json")["timestamp"]
    finally:
        # Only the unique graph created by this test is deleted.
        try:
            adapter._graph.delete()
        finally:
            adapter.close()
