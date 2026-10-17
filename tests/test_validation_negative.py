"""
Weave — Negative tests for dataset validation.

Verifies that the validator correctly rejects:
  1. Duplicate canonical IDs
  2. Unresolved references
  3. Broken or inconsistent canonical ID formats (whitespace, missing prefix, etc.)
  4. Orphan Decisions (no connections to any entity)
  5. Services with no owner/team
  6. Primary decisions with insufficient evidence (< 2 evidence sources)
  7. Timestamp chronology violations (issue after decision, commit before decision, etc.)
  8. Chunk/source provenance integrity errors (chunk source_id not in registry, source_type mismatch)
  9. Missing or empty text in evidence-bearing records
  10. Incompatible relationship endpoint types
"""

import copy
from datetime import datetime, timezone
from pathlib import Path
import pytest

from weave_data.loader import load_records, load_aliases
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
from weave_data.validation import validate_dataset

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "novapay"


@pytest.fixture
def base_records():
    records, _ = load_records(DATA_DIR)
    return records


@pytest.fixture
def aliases():
    return load_aliases(DATA_DIR)


def test_baseline_dataset_passes(base_records, aliases):
    res = validate_dataset(base_records, aliases=aliases)
    assert res.ok, f"Baseline dataset should pass validation, got: {res.summary()}"


def test_duplicate_canonical_id_fails(base_records):
    records = list(base_records)
    records.append(PersonRecord(id="person:alice", source="hr", name="Alice Duplicate"))
    res = validate_dataset(records)
    assert not res.ok
    assert any("Duplicate ID" in str(e) for e in res.errors)


def test_unresolved_reference_fails(base_records):
    records = list(base_records)
    records.append(ServiceRecord(
        id="service:s2", source="service-catalog", name="S2",
        technologies=["tech:nonexistent"]
    ))
    res = validate_dataset(records)
    assert not res.ok
    assert any("Unresolved reference: 'tech:nonexistent'" in str(e) for e in res.errors)


def test_malformed_canonical_id_format_fails():
    # Canonical ID with space (fails Pydantic model validation)
    with pytest.raises(Exception):
        PersonRecord(id="person: alice", source="hr", name="Invalid Space")

    # Canonical ID missing prefix (fails Pydantic model validation)
    with pytest.raises(Exception):
        PersonRecord(id="alice_no_prefix", source="hr", name="Invalid Prefix")


def test_orphan_decision_fails(base_records):
    records = list(base_records)
    orphan = DecisionRecord(
        id="decision:D-ORPHAN", source="decision-log", title="Disconnected",
        status="proposed"
    )
    records.append(orphan)
    res = validate_dataset(records)
    assert not res.ok
    assert any("Orphan Decision" in str(e) for e in res.errors)


def test_service_with_no_owner_team_fails(base_records):
    records = list(base_records)
    unowned = ServiceRecord(id="service:s-unowned", source="service-catalog", name="Unowned")
    records.append(unowned)
    res = validate_dataset(records)
    assert not res.ok
    assert any("has no owner team" in str(e) for e in res.errors)


def test_primary_decision_insufficient_evidence_fails(base_records):
    records = list(base_records)
    weak_dec = DecisionRecord(
        id="decision:D-WEAK", source="decision-log", title="Weak evidence",
        status="accepted", decided_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        affects=["service:payment-service"], supported_by=["issue:PAY-42"]  # Only 1 supporting item
    )
    records.append(weak_dec)
    res = validate_dataset(records)
    assert not res.ok
    assert any("insufficient evidence sources" in str(e) for e in res.errors)


def test_chronology_issue_after_decision_fails(base_records):
    records = copy.deepcopy(base_records)
    # Mutate issue:PAY-42 to be created AFTER decision:D-007
    for r in records:
        if r.id == "issue:PAY-42":
            r.created_at = datetime(2026, 5, 25, tzinfo=timezone.utc)
    res = validate_dataset(records)
    assert not res.ok
    assert any("Chronology error: supporting issue" in str(e) for e in res.errors)


def test_chronology_commit_before_decision_fails(base_records):
    records = copy.deepcopy(base_records)
    # Mutate commit:8fae2 to be timestamped BEFORE decision:D-007
    for r in records:
        if r.id == "commit:8fae2":
            r.timestamp = datetime(2026, 5, 1, tzinfo=timezone.utc)
    res = validate_dataset(records)
    assert not res.ok
    assert any("Chronology error: implementing commit" in str(e) for e in res.errors)


def test_chronology_incident_after_issue_fails(base_records):
    records = copy.deepcopy(base_records)
    # Mutate incident:INC-17 to start AFTER issue:PAY-42 was created
    for r in records:
        if r.id == "incident:INC-17":
            r.started_at = datetime(2026, 5, 25, tzinfo=timezone.utc)
    res = validate_dataset(records)
    assert not res.ok
    assert any("started" in str(e) and "after related issue" in str(e) for e in res.errors)


def test_empty_text_in_evidence_records_fails(base_records):
    records = copy.deepcopy(base_records)
    for r in records:
        if r.id == "issue:PAY-42":
            r.description = "   "  # whitespace only
    res = validate_dataset(records)
    assert not res.ok
    assert any("empty description text" in str(e) for e in res.errors)


def test_chunk_provenance_missing_source_fails(base_records):
    orphan_chunk = ChunkRecord(
        id="chunk:issue:GHOST:0", source_id="issue:GHOST", source_type="Issue",
        chunk_index=0, text="Some text", title="Title"
    )
    res = validate_dataset(base_records, chunks=[orphan_chunk])
    assert not res.ok
    assert any("Chunk provenance error: source 'issue:GHOST' not found" in str(e) for e in res.errors)


def test_chunk_provenance_source_type_mismatch_fails(base_records):
    mismatched_chunk = ChunkRecord(
        id="chunk:issue:PAY-42:0", source_id="issue:PAY-42", source_type="Commit",  # Target is Issue!
        chunk_index=0, text="Some text", title="Title"
    )
    res = validate_dataset(base_records, chunks=[mismatched_chunk])
    assert not res.ok
    assert any("does not match target entity type" in str(e) for e in res.errors)


def test_relationship_type_mismatch_fails(base_records):
    records = list(base_records)
    records.append(IssueRecord(
        id="issue:I-BAD", source="jira", title="Bad Ref",
        assignee="team:payments"  # team:payments is a Team, but assignee expects Person!
    ))
    res = validate_dataset(records)
    assert not res.ok
    assert any("Type mismatch" in str(e) and "expected one of ['Person']" in str(e) for e in res.errors)
