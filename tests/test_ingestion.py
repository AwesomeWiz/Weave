"""
Weave — Automated tests for Data & Ingestion.

Covers:
  - Valid dataset loads successfully
  - All canonical IDs are unique
  - All required references resolve
  - D-007 contains its complete relationship contract
  - Timestamps are valid and chronological
  - Alias resolution returns the correct canonical IDs
  - Expected relationship mappings are generated
  - Source chunks retain provenance
  - Malformed IDs and unresolved references fail validation
  - Repeated normalization produces identical output
  - Repeated ingestion does not duplicate logical records (in-memory)
  - Idempotent ingestion counts are stable

No external LLM or paid API required.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Adjust path so we can import weave_data when running from repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from weave_data.loader import load_records, load_aliases, load_adr_content
from weave_data.models import (
    BaseRecord,
    ChunkRecord,
    CommitRecord,
    DecisionRecord,
    DocumentRecord,
    EntityType,
    IncidentRecord,
    IssueRecord,
    MessageRecord,
    PersonRecord,
    RepositoryRecord,
    ServiceRecord,
    TeamRecord,
    TechnologyRecord,
)
from weave_data.validation import validate_dataset, ValidationResult
from weave_data.relationships import extract_relationships, RelationshipOp
from weave_data.chunks import generate_chunks
from weave_data.graph_adapter import InMemoryGraphAdapter
from weave_data.ingest import run_ingestion, prepare_ingestion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "novapay"


@pytest.fixture(scope="module")
def loaded_data():
    """Load once for the module."""
    records, source_file_map = load_records(DATA_DIR)
    aliases = load_aliases(DATA_DIR)
    adr_content = load_adr_content(DATA_DIR)
    return records, source_file_map, aliases, adr_content


@pytest.fixture(scope="module")
def validation_result(loaded_data):
    records, source_file_map, aliases, _ = loaded_data
    return validate_dataset(records, aliases, source_file_map)


@pytest.fixture(scope="module")
def relationships(loaded_data):
    records, _, _, _ = loaded_data
    return extract_relationships(records)


@pytest.fixture(scope="module")
def chunks(loaded_data):
    records, _, _, adr_content = loaded_data
    return generate_chunks(records, adr_content)


# ===========================================================================
# 1. Loading
# ===========================================================================

class TestLoading:
    def test_loads_records(self, loaded_data):
        records, _, _, _ = loaded_data
        assert len(records) > 0, "Should load at least one record."

    def test_has_all_core_ids(self, loaded_data):
        records, _, _, _ = loaded_data
        ids = {r.id for r in records}
        required = {
            "person:alice", "person:ravi", "person:maya",
            "team:payments",
            "service:payment-service", "service:checkout-service",
            "tech:redis",
            "repo:novapay/payments-api",
            "incident:INC-17",
            "issue:PAY-42",
            "message:payment-perf-7",
            "decision:D-007",
            "commit:8fae2",
            "doc:ADR-7",
        }
        missing = required - ids
        assert not missing, f"Missing canonical IDs: {missing}"

    def test_loads_aliases(self, loaded_data):
        _, _, aliases, _ = loaded_data
        assert "payment service" in aliases
        assert aliases["payment service"] == "service:payment-service"
        assert aliases["redis"] == "tech:redis"

    def test_loads_adr_content(self, loaded_data):
        _, _, _, adr_content = loaded_data
        assert adr_content is not None
        assert "Redis" in adr_content


# ===========================================================================
# 2. Validation
# ===========================================================================

class TestValidation:
    def test_dataset_passes_validation(self, validation_result):
        assert validation_result.ok, validation_result.summary()

    def test_all_ids_unique(self, loaded_data):
        records, _, _, _ = loaded_data
        ids = [r.id for r in records]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_entity_types_valid(self, loaded_data):
        records, _, _, _ = loaded_data
        for rec in records:
            assert isinstance(rec.entity_type, EntityType)


# ===========================================================================
# 3. D-007 contract
# ===========================================================================

class TestD007:
    def test_d007_exists(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = [r for r in records if r.id == "decision:D-007"]
        assert len(d007) == 1

    def test_d007_status(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert isinstance(d007, DecisionRecord)
        assert d007.status == "accepted"

    def test_d007_affects(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "service:payment-service" in d007.affects

    def test_d007_introduces(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "tech:redis" in d007.introduces

    def test_d007_participants(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        expected = {"person:alice", "person:ravi", "person:maya"}
        assert expected.issubset(set(d007.participants))

    def test_d007_approved_by(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "person:alice" in d007.approved_by

    def test_d007_supported_by(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "issue:PAY-42" in d007.supported_by
        assert "message:payment-perf-7" in d007.supported_by

    def test_d007_implemented_by(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "commit:8fae2" in d007.implemented_by

    def test_d007_documented_in(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert "doc:ADR-7" in d007.documented_in

    def test_d007_decided_at(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert d007.decided_at is not None


# ===========================================================================
# 4. Timestamps and chronology
# ===========================================================================

class TestTimestamps:
    def test_inc17_before_pay42(self, loaded_data):
        records, _, _, _ = loaded_data
        inc = next(r for r in records if r.id == "incident:INC-17")
        pay = next(r for r in records if r.id == "issue:PAY-42")
        assert inc.started_at < pay.created_at

    def test_pay42_before_discussion(self, loaded_data):
        records, _, _, _ = loaded_data
        pay = next(r for r in records if r.id == "issue:PAY-42")
        msg = next(r for r in records if r.id == "message:payment-perf-7")
        assert pay.created_at < msg.timestamp

    def test_discussion_before_decision(self, loaded_data):
        records, _, _, _ = loaded_data
        msg = next(r for r in records if r.id == "message:payment-perf-7")
        d007 = next(r for r in records if r.id == "decision:D-007")
        assert msg.timestamp < d007.decided_at

    def test_decision_before_commit(self, loaded_data):
        records, _, _, _ = loaded_data
        d007 = next(r for r in records if r.id == "decision:D-007")
        commit = next(r for r in records if r.id == "commit:8fae2")
        assert d007.decided_at < commit.timestamp

    def test_all_timestamps_parse(self, loaded_data):
        records, _, _, _ = loaded_data
        for rec in records:
            rec_dict = rec.model_dump()
            for key, val in rec_dict.items():
                if isinstance(val, datetime):
                    assert val.tzinfo is not None or val.year > 0, \
                        f"{rec.id}.{key}: timestamp did not parse correctly"


# ===========================================================================
# 5. Alias resolution
# ===========================================================================

class TestAliases:
    def test_payment_service_aliases(self, loaded_data):
        _, _, aliases, _ = loaded_data
        for alias in ["payment service", "payments api", "payments service", "payment-service"]:
            assert aliases.get(alias) == "service:payment-service", f"Alias '{alias}' not resolved"

    def test_redis_aliases(self, loaded_data):
        _, _, aliases, _ = loaded_data
        for alias in ["redis", "redis cache"]:
            assert aliases.get(alias) == "tech:redis", f"Alias '{alias}' not resolved"

    def test_people_aliases(self, loaded_data):
        _, _, aliases, _ = loaded_data
        assert aliases.get("alice menon") == "person:alice"
        assert aliases.get("ravi nair") == "person:ravi"
        assert aliases.get("maya joseph") == "person:maya"


# ===========================================================================
# 6. Relationship mappings
# ===========================================================================

class TestRelationships:
    def test_has_relationships(self, relationships):
        assert len(relationships) > 0

    def test_inc17_led_to_pay42(self, relationships):
        assert _has_rel(relationships, "incident:INC-17", "LED_TO", "issue:PAY-42")

    def test_inc17_affects_payment_service(self, relationships):
        assert _has_rel(relationships, "incident:INC-17", "AFFECTS", "service:payment-service")

    def test_pay42_affects_payment_service(self, relationships):
        assert _has_rel(relationships, "issue:PAY-42", "AFFECTS", "service:payment-service")

    def test_d007_affects_payment_service(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "AFFECTS", "service:payment-service")

    def test_d007_introduces_redis(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "INTRODUCES", "tech:redis")

    def test_alice_participated_in_d007(self, relationships):
        assert _has_rel(relationships, "person:alice", "PARTICIPATED_IN", "decision:D-007")

    def test_alice_approved_d007(self, relationships):
        assert _has_rel(relationships, "person:alice", "APPROVED", "decision:D-007")

    def test_d007_supported_by_pay42(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "SUPPORTED_BY", "issue:PAY-42")

    def test_d007_supported_by_message(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "SUPPORTED_BY", "message:payment-perf-7")

    def test_d007_implemented_by_commit(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "IMPLEMENTED_BY", "commit:8fae2")

    def test_d007_documented_in_adr7(self, relationships):
        assert _has_rel(relationships, "decision:D-007", "DOCUMENTED_IN", "doc:ADR-7")

    def test_commit_belongs_to_repo(self, relationships):
        assert _has_rel(relationships, "commit:8fae2", "BELONGS_TO", "repo:novapay/payments-api")

    def test_commit_changes_payment_service(self, relationships):
        assert _has_rel(relationships, "commit:8fae2", "CHANGES", "service:payment-service")

    def test_repo_implements_payment_service(self, relationships):
        assert _has_rel(relationships, "repo:novapay/payments-api", "IMPLEMENTS", "service:payment-service")

    def test_payment_service_uses_redis(self, relationships):
        assert _has_rel(relationships, "service:payment-service", "USES", "tech:redis")

    def test_checkout_depends_on_payment(self, relationships):
        assert _has_rel(relationships, "service:checkout-service", "DEPENDS_ON", "service:payment-service")

    def test_team_owns_payment_service(self, relationships):
        assert _has_rel(relationships, "team:payments", "OWNS", "service:payment-service")

    def test_no_duplicates(self, relationships):
        keys = [r.stable_key for r in relationships]
        assert len(keys) == len(set(keys))


# ===========================================================================
# 7. Chunks
# ===========================================================================

class TestChunks:
    def test_has_chunks(self, chunks):
        assert len(chunks) >= 4, f"Expected at least 4 chunks, got {len(chunks)}"

    def test_pay42_chunk(self, chunks):
        c = _find_chunk(chunks, "issue:PAY-42")
        assert c is not None
        assert "latency" in c.text.lower()
        assert c.source_type == "Issue"

    def test_message_chunk(self, chunks):
        c = _find_chunk(chunks, "message:payment-perf-7")
        assert c is not None
        assert "redis" in c.text.lower()
        assert c.source_type == "Message"

    def test_commit_chunk(self, chunks):
        c = _find_chunk(chunks, "commit:8fae2")
        assert c is not None
        assert "redis" in c.text.lower()
        assert c.source_type == "Commit"

    def test_adr7_chunk(self, chunks):
        c = _find_chunk(chunks, "doc:ADR-7")
        assert c is not None
        assert "Redis" in c.text
        assert c.source_type == "Document"

    def test_chunk_provenance(self, chunks):
        for c in chunks:
            assert c.source_id, f"Chunk {c.id} missing source_id"
            assert c.source_type, f"Chunk {c.id} missing source_type"
            assert c.chunk_index >= 0
            assert c.text


# ===========================================================================
# 8. Malformed data
# ===========================================================================

class TestMalformedData:
    def test_empty_id_fails(self):
        with pytest.raises(Exception):
            PersonRecord(id="", source="hr", entity_type=EntityType.Person, name="X")

    def test_missing_prefix_detected(self):
        with pytest.raises(Exception):
            PersonRecord(id="alice", source="hr", entity_type=EntityType.Person, name="X")

    def test_unresolved_reference_fails(self):
        records = [
            PersonRecord(id="person:test", source="hr", entity_type=EntityType.Person, name="Test"),
            ServiceRecord(
                id="service:test", source="service-catalog",
                entity_type=EntityType.Service, name="Test Service",
                technologies=["tech:nonexistent"],
            ),
        ]
        result = validate_dataset(records)
        assert not result.ok, "Should fail on unresolved reference tech:nonexistent"

    def test_duplicate_id_fails(self):
        records = [
            PersonRecord(id="person:dup", source="hr", entity_type=EntityType.Person, name="A"),
            PersonRecord(id="person:dup", source="hr", entity_type=EntityType.Person, name="B"),
        ]
        result = validate_dataset(records)
        assert not result.ok, "Should fail on duplicate ID"


# ===========================================================================
# 9. Deterministic normalization
# ===========================================================================

class TestDeterminism:
    def test_repeated_load_identical(self):
        r1, _ = load_records(DATA_DIR)
        r2, _ = load_records(DATA_DIR)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a.model_dump() == b.model_dump()

    def test_repeated_relationships_identical(self):
        r1, _ = load_records(DATA_DIR)
        r2, _ = load_records(DATA_DIR)
        ops1 = extract_relationships(r1)
        ops2 = extract_relationships(r2)
        assert len(ops1) == len(ops2)
        for a, b in zip(ops1, ops2):
            assert a.stable_key == b.stable_key

    def test_repeated_chunks_identical(self):
        r1, _ = load_records(DATA_DIR)
        r2, _ = load_records(DATA_DIR)
        adr = load_adr_content(DATA_DIR)
        c1 = generate_chunks(r1, adr)
        c2 = generate_chunks(r2, adr)
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a.model_dump() == b.model_dump()


# ===========================================================================
# 10. Idempotent ingestion (in-memory)
# ===========================================================================

class TestIdempotency:
    def test_double_ingestion_same_counts(self):
        adapter = InMemoryGraphAdapter()
        r1 = run_ingestion(DATA_DIR, adapter)
        assert r1.status == "success", f"First ingestion failed: {r1.errors}"
        n1 = adapter.node_count()
        rel1 = adapter.relationship_count()
        ch1 = adapter.chunk_count()

        r2 = run_ingestion(DATA_DIR, adapter)
        assert r2.status == "success", f"Second ingestion failed: {r2.errors}"
        n2 = adapter.node_count()
        rel2 = adapter.relationship_count()
        ch2 = adapter.chunk_count()

        assert n1 == n2, f"Nodes changed: {n1} → {n2}"
        assert rel1 == rel2, f"Relationships changed: {rel1} → {rel2}"
        assert ch1 == ch2, f"Chunks changed: {ch1} → {ch2}"

    def test_ingestion_counts_accurate(self):
        adapter = InMemoryGraphAdapter()
        result = run_ingestion(DATA_DIR, adapter)
        assert result.status == "success"
        assert result.nodes_created_or_updated > 0
        assert result.relationships_processed > 0
        assert result.chunks_created_or_updated > 0
        # Counts match adapter
        assert result.nodes_created_or_updated == adapter.node_count()
        assert result.chunks_created_or_updated == adapter.chunk_count()


# ===========================================================================
# 11. Prepare-only mode
# ===========================================================================

class TestPrepareOnly:
    def test_prepare_returns_all_components(self):
        records, rel_ops, chunks, aliases, validation = prepare_ingestion(DATA_DIR)
        assert validation.ok, validation.summary()
        assert len(records) > 0
        assert len(rel_ops) > 0
        assert len(chunks) > 0
        assert len(aliases) > 0


# ===========================================================================
# 12. Integration Audit: Adapter Hardening & Error Propagation
# ===========================================================================

class TestAdapterHardening:
    def test_relationship_without_endpoints_raises(self):
        adapter = InMemoryGraphAdapter()
        with pytest.raises(ValueError, match="missing endpoint node"):
            adapter.upsert_relationship("service:nonexistent", "USES", "tech:nonexistent")

    def test_empty_canonical_id_node_raises(self):
        adapter = InMemoryGraphAdapter()
        with pytest.raises(ValueError, match="canonical_id"):
            adapter.upsert_node("Person", "", {"name": "Anonymous"})

    def test_empty_canonical_id_chunk_raises(self):
        adapter = InMemoryGraphAdapter()
        with pytest.raises(ValueError, match="chunk_id"):
            adapter.upsert_chunk("", {"text": "Some text"})

    def test_adapter_persistence_failure_surfaced(self):
        class FailingAdapter(InMemoryGraphAdapter):
            def upsert_node(self, entity_type: str, canonical_id: str, properties: dict) -> None:
                raise RuntimeError("Disk quota exceeded / connection reset")

        result = run_ingestion(DATA_DIR, adapter=FailingAdapter())
        assert result.status == "failed"
        assert len(result.errors) > 0
        assert any("Disk quota exceeded" in e for e in result.errors)


# ===========================================================================
# 13. Integration Audit: Pre-Persistence Guard
# ===========================================================================

class TestPrePersistenceGuard:
    def test_invalid_dataset_blocks_mutation(self, tmp_path):
        # Create a malformed dataset directory where a record has an unresolved reference
        bad_dir = tmp_path / "bad_data"
        bad_dir.mkdir()
        # Copy people.json but with broken reference
        bad_people = [
            {
                "id": "person:test-user",
                "name": "Test User",
                "team": "team:nonexistent-team",
                "email_alias": "testuser",
                "role": "Engineer",
                "active": True
            }
        ]
        (bad_dir / "people.json").write_text(json.dumps(bad_people), encoding="utf-8")
        (bad_dir / "teams.json").write_text("[]", encoding="utf-8")
        (bad_dir / "services.json").write_text("[]", encoding="utf-8")
        (bad_dir / "technologies.json").write_text("[]", encoding="utf-8")
        (bad_dir / "incidents.json").write_text("[]", encoding="utf-8")
        (bad_dir / "decisions.json").write_text("[]", encoding="utf-8")
        (bad_dir / "aliases.json").write_text("{}", encoding="utf-8")

        adapter = InMemoryGraphAdapter()
        result = run_ingestion(data_dir=bad_dir, adapter=adapter)

        # Ingestion must fail before writing any nodes or edges
        assert result.status == "failed"
        assert len(result.errors) > 0
        assert adapter.node_count() == 0, "No nodes should be written when validation fails"
        assert adapter.relationship_count() == 0, "No edges should be written when validation fails"


# ===========================================================================
# 14. Integration Audit: Canonical Evidence Chain Completeness
# ===========================================================================

class TestCanonicalDecisionEvidenceChain:
    def test_full_linear_evidence_chain(self, relationships):
        """
        Verify the exact decision-intelligence path:
        INC-17 -> PAY-42 -> D-007 -> 8fae2 -> payments-api -> Payment Service -> Redis.
        """
        # 1. INC-17 LED_TO PAY-42
        assert _has_rel(relationships, "incident:INC-17", "LED_TO", "issue:PAY-42")
        # 2. D-007 SUPPORTED_BY PAY-42
        assert _has_rel(relationships, "decision:D-007", "SUPPORTED_BY", "issue:PAY-42")
        # 3. D-007 SUPPORTED_BY payment-perf-7 (discussion)
        assert _has_rel(relationships, "decision:D-007", "SUPPORTED_BY", "message:payment-perf-7")
        # 4. D-007 IMPLEMENTED_BY commit 8fae2
        assert _has_rel(relationships, "decision:D-007", "IMPLEMENTED_BY", "commit:8fae2")
        # 5. commit 8fae2 BELONGS_TO repo payments-api
        assert _has_rel(relationships, "commit:8fae2", "BELONGS_TO", "repo:novapay/payments-api")
        # 6. repo payments-api IMPLEMENTS payment-service
        assert _has_rel(relationships, "repo:novapay/payments-api", "IMPLEMENTS", "service:payment-service")
        # 7. payment-service USES redis
        assert _has_rel(relationships, "service:payment-service", "USES", "tech:redis")

    def test_all_canonical_governance_and_topology_edges(self, relationships):
        """Verify approvals, participants, documentation, and dependencies."""
        # Alice approved D-007
        assert _has_rel(relationships, "person:alice", "APPROVED", "decision:D-007")
        # Participants in D-007
        assert _has_rel(relationships, "person:alice", "PARTICIPATED_IN", "decision:D-007")
        assert _has_rel(relationships, "person:ravi", "PARTICIPATED_IN", "decision:D-007")
        assert _has_rel(relationships, "person:maya", "PARTICIPATED_IN", "decision:D-007")
        # D-007 documented in ADR-7
        assert _has_rel(relationships, "decision:D-007", "DOCUMENTED_IN", "doc:ADR-7")
        # Checkout service depends on payment-service
        assert _has_rel(relationships, "service:checkout-service", "DEPENDS_ON", "service:payment-service")
        # Payments team owns payment-service
        assert _has_rel(relationships, "team:payments", "OWNS", "service:payment-service")


# ===========================================================================
# 15. Integration Audit: Reporting Structure
# ===========================================================================

class TestReportingStructure:
    def test_success_result_to_dict(self):
        adapter = InMemoryGraphAdapter()
        res = run_ingestion(DATA_DIR, adapter=adapter)
        d = res.to_dict()
        assert d["status"] == "success"
        assert d["records_processed"] == 15
        assert d["nodes_created_or_updated"] == 15
        assert d["relationships_processed"] == 33
        assert d["chunks_created_or_updated"] == 4
        assert d["errors"] == []

    def test_failure_result_to_dict(self):
        class ExplodingAdapter(InMemoryGraphAdapter):
            def upsert_node(self, *args, **kwargs):
                raise IOError("Network timeout")

        res = run_ingestion(DATA_DIR, adapter=ExplodingAdapter())
        d = res.to_dict()
        assert d["status"] == "failed"
        assert len(d["errors"]) > 0


# ===========================================================================
# 16. Integration Contract: Chunk Relationships & Persistence
# ===========================================================================

class TestChunkRelationships:
    def test_chunk_to_source_relationships_generated(self):
        records, rel_ops, chunks, _, _ = prepare_ingestion(DATA_DIR)
        # Verify (Chunk)-[:FROM_*]->(Source)
        assert _has_rel(rel_ops, "chunk:issue:PAY-42:0", "FROM_ISSUE", "issue:PAY-42")
        assert _has_rel(rel_ops, "chunk:message:payment-perf-7:0", "FROM_MESSAGE", "message:payment-perf-7")
        assert _has_rel(rel_ops, "chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2")
        assert _has_rel(rel_ops, "chunk:doc:ADR-7:0", "FROM_DOCUMENT", "doc:ADR-7")

    def test_chunk_relationships_persisted_in_graph(self):
        adapter = InMemoryGraphAdapter()
        res = run_ingestion(DATA_DIR, adapter=adapter)
        assert res.status == "success"
        # Total relationships = 29 entity-entity + 4 chunk-source = 33
        assert adapter.relationship_count() == 33
        assert adapter.get_relationship("chunk:issue:PAY-42:0", "FROM_ISSUE", "issue:PAY-42") is not None
        assert adapter.get_relationship("chunk:doc:ADR-7:0", "FROM_DOCUMENT", "doc:ADR-7") is not None
        assert adapter.get_relationship("chunk:commit:8fae2:0", "FROM_COMMIT", "commit:8fae2") is not None
        assert adapter.get_relationship("chunk:message:payment-perf-7:0", "FROM_MESSAGE", "message:payment-perf-7") is not None

    def test_chunk_relationship_missing_source_fails(self):
        adapter = InMemoryGraphAdapter()
        # Seed only chunk node; source node is missing
        adapter.upsert_chunk("chunk:issue:PAY-42:0", {"text": "hello"})
        with pytest.raises(ValueError, match="missing endpoint node"):
            adapter.upsert_relationship("chunk:issue:PAY-42:0", "FROM_ISSUE", "issue:MISSING")



# ===========================================================================
# 17. Integration Contract: Chunk Metadata & Schema
# ===========================================================================

class TestChunkMetadata:
    def test_all_chunks_have_valid_metadata_and_urls(self, chunks):
        for c in chunks:
            assert c.id.startswith("chunk:")
            assert c.source_id
            assert c.source_type in ("Issue", "Message", "Commit", "Document")
            assert c.chunk_index == 0
            assert c.text and len(c.text.strip()) > 0
            assert c.title and len(c.title.strip()) > 0
            assert c.url and c.url.startswith("https://")
            assert c.timestamp is not None

    def test_exact_chunk_source_ids(self, chunks):
        chunk_map = {c.id: c for c in chunks}
        assert "chunk:issue:PAY-42:0" in chunk_map
        assert chunk_map["chunk:issue:PAY-42:0"].source_id == "issue:PAY-42"
        assert chunk_map["chunk:issue:PAY-42:0"].url == "https://jira.novapay.example/browse/PAY-42"

        assert "chunk:message:payment-perf-7:0" in chunk_map
        assert chunk_map["chunk:message:payment-perf-7:0"].source_id == "message:payment-perf-7"

        assert "chunk:commit:8fae2:0" in chunk_map
        assert chunk_map["chunk:commit:8fae2:0"].source_id == "commit:8fae2"

        assert "chunk:doc:ADR-7:0" in chunk_map
        assert chunk_map["chunk:doc:ADR-7:0"].source_id == "doc:ADR-7"
        assert chunk_map["chunk:doc:ADR-7:0"].url == "https://docs.novapay.example/adrs/ADR-7"


# ===========================================================================
# 18. Integration Contract: Exact Source Retrieval (find_sources)
# ===========================================================================

class TestExactSourceRetrieval:
    def test_find_sources_single(self):
        from weave_data.retrieval import find_sources
        results = find_sources(["issue:PAY-42"], data_dir=DATA_DIR)
        assert len(results) == 1
        src = results[0]
        assert src.id == "issue:PAY-42"
        assert src.type == "Issue"
        assert src.title == "Reduce payment latency under burst traffic"
        assert "INC-17 incident" in src.snippet
        assert src.url == "https://jira.novapay.example/browse/PAY-42"
        assert src.chunk_ids == ["chunk:issue:PAY-42:0"]

    def test_find_sources_multiple(self):
        from weave_data.retrieval import find_sources
        results = find_sources(["doc:ADR-7", "commit:8fae2"], data_dir=DATA_DIR)
        assert len(results) == 2
        ids = [r.id for r in results]
        assert ids == ["doc:ADR-7", "commit:8fae2"]

    def test_find_sources_deduplication(self):
        from weave_data.retrieval import find_sources
        results = find_sources(["issue:PAY-42", "issue:PAY-42", "doc:ADR-7"], data_dir=DATA_DIR)
        assert len(results) == 2
        assert [r.id for r in results] == ["issue:PAY-42", "doc:ADR-7"]

    def test_find_sources_unknown_id(self):
        from weave_data.retrieval import find_sources
        results = find_sources(["issue:UNKNOWN-999"], data_dir=DATA_DIR)
        assert results == []

    def test_find_sources_empty_input(self):
        from weave_data.retrieval import find_sources
        assert find_sources([], data_dir=DATA_DIR) == []
        assert find_sources(None, data_dir=DATA_DIR) == []
        assert find_sources([""], data_dir=DATA_DIR) == []

    def test_find_sources_multiple_chunks_same_source(self):
        from weave_data.retrieval import find_sources
        # Create mock chunks where two chunks belong to the same source
        c1 = ChunkRecord(
            id="chunk:doc:ADR-7:0",
            source_id="doc:ADR-7",
            source_type="Document",
            chunk_index=0,
            title="ADR Part 1",
            text="Context and problem statement.",
            url="https://docs.novapay.example/adrs/ADR-7"
        )
        c2 = ChunkRecord(
            id="chunk:doc:ADR-7:1",
            source_id="doc:ADR-7",
            source_type="Document",
            chunk_index=1,
            title="ADR Part 2",
            text="Decision and consequences.",
            url="https://docs.novapay.example/adrs/ADR-7"
        )
        results = find_sources(["doc:ADR-7"], chunks=[c2, c1], records=[])
        assert len(results) == 1
        src = results[0]
        assert src.id == "doc:ADR-7"
        assert src.chunk_ids == ["chunk:doc:ADR-7:0", "chunk:doc:ADR-7:1"]
        # Snippet combines both in chunk_index order
        assert "Context and problem statement.\n\nDecision and consequences." == src.snippet

    def test_find_sources_never_fabricates_text(self):
        from weave_data.retrieval import find_sources
        results = find_sources(["message:payment-perf-7"], data_dir=DATA_DIR)
        assert len(results) == 1
        src = results[0]
        # Text must match exact source content
        assert "Thread: Payment Service latency improvements" in src.snippet
        assert "Ravi Nair: Agreed. I ran a local benchmark" in src.snippet


# ===========================================================================
# 19. Integration Contract: Graph-Backed Source Retrieval
# ===========================================================================

class TestGraphBackedRetrieval:
    @pytest.fixture
    def ingested_adapter(self):
        adapter = InMemoryGraphAdapter()
        res = run_ingestion(DATA_DIR, adapter=adapter)
        assert res.status == "success"
        return adapter

    def test_graph_backed_retrieval_all_evidence_types(self, ingested_adapter):
        from weave_data.retrieval import find_sources
        source_ids = ["issue:PAY-42", "message:payment-perf-7", "commit:8fae2", "doc:ADR-7"]
        results = find_sources(source_ids, adapter=ingested_adapter)
        assert len(results) == 4

        res_by_id = {r.id: r for r in results}
        # Issue
        issue_src = res_by_id["issue:PAY-42"]
        assert issue_src.type == "Issue"
        assert issue_src.title == "Reduce payment latency under burst traffic"
        assert "INC-17 incident" in issue_src.snippet
        assert issue_src.url == "https://jira.novapay.example/browse/PAY-42"
        assert issue_src.chunk_ids == ["chunk:issue:PAY-42:0"]

        # Message
        msg_src = res_by_id["message:payment-perf-7"]
        assert msg_src.type == "Message"
        assert "payment-perf" in msg_src.title
        assert "Ravi Nair: Agreed" in msg_src.snippet
        assert msg_src.url == "https://slack.novapay.example/archives/payments-engineering/payment-perf-2026-05"
        assert msg_src.chunk_ids == ["chunk:message:payment-perf-7:0"]

        # Commit
        commit_src = res_by_id["commit:8fae2"]
        assert commit_src.type == "Commit"
        assert "introduce Redis-backed caching" in commit_src.title
        assert "Add RedisCache adapter" in commit_src.snippet
        assert commit_src.url == "https://github.novapay.example/novapay/payments-api/commit/8fae2d4"
        assert commit_src.chunk_ids == ["chunk:commit:8fae2:0"]

        # Document
        doc_src = res_by_id["doc:ADR-7"]
        assert doc_src.type == "Document"
        assert "Redis Caching for Payment Service" in doc_src.title
        assert "# ADR-7: Redis Caching for Payment Service" in doc_src.snippet
        assert doc_src.url == "https://docs.novapay.example/adrs/ADR-7"
        assert doc_src.chunk_ids == ["chunk:doc:ADR-7:0"]

    def test_graph_backed_retrieval_works_without_local_files(self, ingested_adapter, tmp_path):
        from weave_data.retrieval import find_sources
        # Pass a nonexistent directory as data_dir: retrieval must succeed from graph adapter alone
        nonexistent_dir = tmp_path / "empty_dir"
        nonexistent_dir.mkdir()
        results = find_sources(["issue:PAY-42", "doc:ADR-7"], data_dir=nonexistent_dir, adapter=ingested_adapter)
        assert len(results) == 2
        assert [r.id for r in results] == ["issue:PAY-42", "doc:ADR-7"]
        assert "INC-17 incident" in results[0].snippet
        assert "# ADR-7:" in results[1].snippet

    def test_graph_backed_retrieval_does_not_fallback_when_adapter_fails(self, tmp_path):
        from weave_data.retrieval import find_sources

        class FailingAdapter(InMemoryGraphAdapter):
            def get_chunks_for_sources(self, source_ids):
                raise RuntimeError("graph is unavailable")

        with pytest.raises(RuntimeError, match="graph is unavailable"):
            find_sources(
                ["issue:PAY-42"],
                data_dir=tmp_path / "no-local-data",
                adapter=FailingAdapter(),
            )

    def test_graph_backed_retrieval_unknown_and_empty_ids(self, ingested_adapter):
        from weave_data.retrieval import find_sources
        assert find_sources([], adapter=ingested_adapter) == []
        assert find_sources(None, adapter=ingested_adapter) == []
        assert find_sources(["issue:UNKNOWN-999"], adapter=ingested_adapter) == []

    def test_graph_backed_retrieval_deduplication(self, ingested_adapter):
        from weave_data.retrieval import find_sources
        results = find_sources(["issue:PAY-42", "issue:PAY-42", "doc:ADR-7"], adapter=ingested_adapter)
        assert len(results) == 2
        assert [r.id for r in results] == ["issue:PAY-42", "doc:ADR-7"]

    def test_graph_backed_retrieval_multiple_chunks_aggregation_order(self):
        from weave_data.retrieval import find_sources
        adapter = InMemoryGraphAdapter()
        # Seed source node
        adapter.upsert_node("Document", "doc:ADR-99", {"title": "ADR 99 Title", "url": "https://example.com/adr99"})
        # Seed two chunks in reverse order
        adapter.upsert_chunk("chunk:doc:ADR-99:1", {
            "source_id": "doc:ADR-99",
            "source_type": "Document",
            "chunk_index": 1,
            "title": "ADR 99 Part 2",
            "text": "Consequences section.",
            "url": "https://example.com/adr99",
        })
        adapter.upsert_chunk("chunk:doc:ADR-99:0", {
            "source_id": "doc:ADR-99",
            "source_type": "Document",
            "chunk_index": 0,
            "title": "ADR 99 Part 1",
            "text": "Context section.",
            "url": "https://example.com/adr99",
        })
        # Connect with FROM_DOCUMENT relationships
        adapter.upsert_relationship("chunk:doc:ADR-99:1", "FROM_DOCUMENT", "doc:ADR-99")
        adapter.upsert_relationship("chunk:doc:ADR-99:0", "FROM_DOCUMENT", "doc:ADR-99")

        results = find_sources(["doc:ADR-99"], adapter=adapter)
        assert len(results) == 1
        src = results[0]
        assert src.id == "doc:ADR-99"
        assert src.chunk_ids == ["chunk:doc:ADR-99:0", "chunk:doc:ADR-99:1"]
        assert src.snippet == "Context section.\n\nConsequences section."

    def test_graph_backed_retrieval_missing_provenance_relationship(self):
        from weave_data.retrieval import find_sources
        adapter = InMemoryGraphAdapter()
        # Chunk exists but without any FROM_* relationship connecting it to source
        adapter.upsert_chunk("chunk:issue:PAY-99:0", {
            "source_id": "issue:PAY-99",
            "text": "Orphaned chunk",
        })
        # Querying issue:PAY-99 returns nothing because graph relationship is missing
        results = find_sources(["issue:PAY-99"], adapter=adapter)
        assert results == []



# ===========================================================================
# Helpers
# ===========================================================================

def _has_rel(rels: list[RelationshipOp], src: str, rel: str, tgt: str) -> bool:
    key = f"{src}|{rel}|{tgt}"
    return any(r.stable_key == key for r in rels)


def _find_chunk(chunks: list[ChunkRecord], source_id: str) -> ChunkRecord | None:
    for c in chunks:
        if c.source_id == source_id:
            return c
    return None

