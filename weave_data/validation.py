"""
Weave — Dataset validation.

Validates the normalized NovaPay dataset *before* any graph persistence:

  1.  Every record has a non-empty canonical ID.
  2.  IDs are globally unique across entity records.
  3.  Required fields are present (enforced by Pydantic models).
  4.  Entity types and source types are valid.
  5.  Timestamps parse correctly.
  6.  Every relationship reference resolves to an existing canonical ID.
  7.  Relationship targets have compatible entity types.
  8.  D-007 has all required references.
  9.  The core Redis decision chain is complete.
  10. Required service, repository, technology, and ownership relationships exist.
  11. No duplicate logical records or malformed aliases exist.
  12. All bundled data is synthetic (no credentials / private data check).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import (
    BaseRecord,
    DecisionRecord,
    EntityType,
)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    file: str
    record_id: str
    field_name: str
    message: str

    def __str__(self) -> str:
        return f"[{self.file}] {self.record_id}.{self.field_name}: {self.message}"


@dataclass
class ValidationResult:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add(self, file: str, record_id: str, field_name: str, message: str) -> None:
        self.errors.append(ValidationError(file, record_id, field_name, message))

    def summary(self) -> str:
        if self.ok:
            return "Validation passed — 0 errors."
        lines = [f"Validation failed — {len(self.errors)} error(s):"]
        for e in self.errors:
            lines.append(f"  • {e}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Expected ID prefixes per entity type
# ---------------------------------------------------------------------------

_ENTITY_PREFIX: dict[EntityType, str] = {
    EntityType.Person: "person:",
    EntityType.Team: "team:",
    EntityType.Service: "service:",
    EntityType.Technology: "tech:",
    EntityType.Repository: "repo:",
    EntityType.Commit: "commit:",
    EntityType.Issue: "issue:",
    EntityType.Message: "message:",
    EntityType.Document: "doc:",
    EntityType.Decision: "decision:",
    EntityType.Incident: "incident:",
}

# Invert: prefix → set of compatible entity types
_PREFIX_TO_TYPES: dict[str, set[EntityType]] = {}
for _et, _pf in _ENTITY_PREFIX.items():
    _PREFIX_TO_TYPES.setdefault(_pf, set()).add(_et)


def _entity_type_for_id(canonical_id: str) -> EntityType | None:
    """Best-effort entity type from ID prefix."""
    for pf, types in _PREFIX_TO_TYPES.items():
        if canonical_id.startswith(pf):
            # Return the single type if unique, else first (they share prefix)
            return next(iter(types))
    return None


# ---------------------------------------------------------------------------
# Credential / PII heuristic
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS = [
    re.compile(r"(?i)(password|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key pattern
]


def _looks_like_credential(text: str) -> bool:
    return any(p.search(text) for p in _CREDENTIAL_PATTERNS)


# ---------------------------------------------------------------------------
# Relationship compatibility rules
# ---------------------------------------------------------------------------

# Maps: (source_entity_type, field_name) → set of acceptable target entity types.
_REF_COMPATIBILITY: dict[tuple[EntityType, str], set[EntityType]] = {
    (EntityType.Incident, "affected_services"): {EntityType.Service},
    (EntityType.Incident, "related_issues"): {EntityType.Issue},
    (EntityType.Issue, "affected_services"): {EntityType.Service},
    (EntityType.Issue, "related_incidents"): {EntityType.Incident},
    (EntityType.Issue, "assignee"): {EntityType.Person},
    (EntityType.Decision, "affects"): {EntityType.Service},
    (EntityType.Decision, "introduces"): {EntityType.Technology},
    (EntityType.Decision, "participants"): {EntityType.Person},
    (EntityType.Decision, "approved_by"): {EntityType.Person},
    (EntityType.Decision, "supported_by"): {EntityType.Issue, EntityType.Message},
    (EntityType.Decision, "implemented_by"): {EntityType.Commit},
    (EntityType.Decision, "documented_in"): {EntityType.Document},
    (EntityType.Commit, "author"): {EntityType.Person},
    (EntityType.Commit, "repository"): {EntityType.Repository},
    (EntityType.Commit, "changes"): {EntityType.Service},
    (EntityType.Commit, "implements_decision"): {EntityType.Decision},
    (EntityType.Commit, "addresses"): {EntityType.Issue},
    (EntityType.Repository, "service"): {EntityType.Service},
    (EntityType.Service, "technologies"): {EntityType.Technology},
    (EntityType.Service, "depends_on"): {EntityType.Service},
    (EntityType.Team, "members"): {EntityType.Person},
    (EntityType.Team, "owns_services"): {EntityType.Service},
    (EntityType.Person, "team"): {EntityType.Team},
    (EntityType.Message, "participants"): {EntityType.Person},
    (EntityType.Document, "describes"): {EntityType.Service},
}


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_dataset(
    records: list[BaseRecord],
    aliases: dict[str, str] | None = None,
    source_file_map: dict[str, str] | None = None,
    chunks: list[Any] | None = None,
) -> ValidationResult:
    """
    Validate a list of parsed records.

    Parameters
    ----------
    records:
        All parsed and typed entity records.
    aliases:
        Optional alias map (alias → canonical ID).
    source_file_map:
        Optional mapping from record ID → source filename for error messages.
    chunks:
        Optional list of ChunkRecord objects to validate chunk/source provenance.

    Returns
    -------
    ValidationResult with accumulated errors.
    """
    result = ValidationResult()
    file_map = source_file_map or {}
    id_registry: dict[str, EntityType] = {}

    # ------------------------------------------------------------------
    # Pass 1: uniqueness, prefix, and type registration
    # ------------------------------------------------------------------
    for rec in records:
        fname = file_map.get(rec.id, "<unknown>")

        # 1. Non-empty ID (Pydantic enforces this, but double-check)
        if not rec.id:
            result.add(fname, "(empty)", "id", "Record has an empty canonical ID.")
            continue

        # 2. Uniqueness
        if rec.id in id_registry:
            result.add(fname, rec.id, "id", f"Duplicate ID — already seen as {id_registry[rec.id].value}.")
            continue

        # Prefix consistency
        expected_prefix = _ENTITY_PREFIX.get(rec.entity_type)
        if expected_prefix and not rec.id.startswith(expected_prefix):
            result.add(fname, rec.id, "id",
                       f"ID prefix mismatch: expected '{expected_prefix}' for {rec.entity_type.value}.")
        elif expected_prefix and rec.id.startswith(expected_prefix):
            identifier = rec.id[len(expected_prefix):]
            if not identifier or re.search(r"\s", rec.id) or not re.match(r"^[a-zA-Z0-9_\-\./]+$", identifier):
                result.add(fname, rec.id, "id", f"Malformed canonical ID format: '{rec.id}'.")

        id_registry[rec.id] = rec.entity_type

    # ------------------------------------------------------------------
    # Pass 2: reference resolution and type compatibility
    # ------------------------------------------------------------------
    for rec in records:
        fname = file_map.get(rec.id, "<unknown>")
        rec_dict = rec.model_dump()

        for field_name, value in rec_dict.items():
            if field_name in ("id", "source", "entity_type"):
                continue

            refs: list[str] = []
            if isinstance(value, str) and ":" in value and field_name not in (
                "name", "title", "summary", "description", "text", "message",
                "url", "email_alias", "sha", "key", "channel", "thread_id",
                "doc_type", "category", "criticality", "status", "priority",
                "role", "default_branch", "content",
            ):
                refs = [value]
            elif isinstance(value, list):
                refs = [v for v in value if isinstance(v, str) and ":" in v]

            if not refs:
                continue

            compat_key = (rec.entity_type, field_name)
            allowed_types = _REF_COMPATIBILITY.get(compat_key)

            for ref_id in refs:
                # 6. Reference resolves
                if ref_id not in id_registry:
                    result.add(fname, rec.id, field_name,
                               f"Unresolved reference: '{ref_id}' not in ID registry.")
                    continue

                # 7. Type compatibility
                if allowed_types is not None:
                    target_type = id_registry[ref_id]
                    if target_type not in allowed_types:
                        result.add(fname, rec.id, field_name,
                                   f"Type mismatch: '{ref_id}' is {target_type.value}, "
                                   f"expected one of {sorted(t.value for t in allowed_types)}.")

    # ------------------------------------------------------------------
    # Pass 3: D-007 completeness
    # ------------------------------------------------------------------
    _validate_d007(records, id_registry, file_map, result)

    # ------------------------------------------------------------------
    # Pass 4: Redis decision chain completeness
    # ------------------------------------------------------------------
    _validate_redis_chain(records, id_registry, result)

    # ------------------------------------------------------------------
    # Pass 5: Required structural relationships
    # ------------------------------------------------------------------
    _validate_structural_relationships(records, id_registry, result)

    # ------------------------------------------------------------------
    # Pass 6: Aliases
    # ------------------------------------------------------------------
    if aliases is not None:
        _validate_aliases(aliases, id_registry, result)

    # ------------------------------------------------------------------
    # Pass 7: Credential / private-data scan
    # ------------------------------------------------------------------
    for rec in records:
        fname = file_map.get(rec.id, "<unknown>")
        rec_dict = rec.model_dump()
        for field_name, value in rec_dict.items():
            if isinstance(value, str) and _looks_like_credential(value):
                result.add(fname, rec.id, field_name,
                           "Possible credential or private data detected.")

    # ------------------------------------------------------------------
    # Pass 8: Orphan decisions check
    # ------------------------------------------------------------------
    _validate_orphan_decisions(records, file_map, result)

    # ------------------------------------------------------------------
    # Pass 9: Service ownership check
    # ------------------------------------------------------------------
    _validate_service_ownership(records, file_map, result)

    # ------------------------------------------------------------------
    # Pass 10: Primary decision evidence check
    # ------------------------------------------------------------------
    _validate_decision_evidence(records, file_map, result)

    # ------------------------------------------------------------------
    # Pass 11: Timestamp chronology check
    # ------------------------------------------------------------------
    _validate_chronology(records, file_map, result)

    # ------------------------------------------------------------------
    # Pass 12: Text integrity check
    # ------------------------------------------------------------------
    _validate_text_integrity(records, file_map, result)

    # ------------------------------------------------------------------
    # Pass 13: Chunk/source provenance integrity check
    # ------------------------------------------------------------------
    if chunks is not None:
        _validate_chunks(chunks, id_registry, result)

    return result


# ---------------------------------------------------------------------------
# D-007 contract
# ---------------------------------------------------------------------------

def _validate_d007(
    records: list[BaseRecord],
    id_registry: dict[str, EntityType],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    d007: DecisionRecord | None = None
    for rec in records:
        if rec.id == "decision:D-007" and isinstance(rec, DecisionRecord):
            d007 = rec
            break

    if d007 is None:
        result.add("decisions.json", "decision:D-007", "id", "D-007 record is missing.")
        return

    fname = file_map.get("decision:D-007", "decisions.json")
    required = {
        "affects": ["service:payment-service"],
        "introduces": ["tech:redis"],
        "participants": ["person:alice", "person:ravi", "person:maya"],
        "approved_by": ["person:alice"],
        "supported_by": ["issue:PAY-42", "message:payment-perf-7"],
        "implemented_by": ["commit:8fae2"],
        "documented_in": ["doc:ADR-7"],
    }

    for field_name, expected_ids in required.items():
        actual: list[str] = getattr(d007, field_name, [])
        for eid in expected_ids:
            if eid not in actual:
                result.add(fname, "decision:D-007", field_name,
                           f"Missing required reference: '{eid}'.")

    if d007.status != "accepted":
        result.add(fname, "decision:D-007", "status",
                   f"Expected 'accepted', got '{d007.status}'.")

    if d007.decided_at is None:
        result.add(fname, "decision:D-007", "decided_at",
                   "Decision timestamp is missing.")


# ---------------------------------------------------------------------------
# Redis decision chain validation
# ---------------------------------------------------------------------------

def _validate_redis_chain(
    records: list[BaseRecord],
    id_registry: dict[str, EntityType],
    result: ValidationResult,
) -> None:
    """Verify the canonical evidence chain is complete."""
    required_ids = [
        "incident:INC-17",
        "issue:PAY-42",
        "message:payment-perf-7",
        "decision:D-007",
        "commit:8fae2",
        "repo:novapay/payments-api",
        "service:payment-service",
        "tech:redis",
        "doc:ADR-7",
    ]
    for rid in required_ids:
        if rid not in id_registry:
            result.add("<dataset>", rid, "id",
                       f"Core Redis chain: required record '{rid}' is missing.")


# ---------------------------------------------------------------------------
# Structural relationships
# ---------------------------------------------------------------------------

def _validate_structural_relationships(
    records: list[BaseRecord],
    id_registry: dict[str, EntityType],
    result: ValidationResult,
) -> None:
    from .models import ServiceRecord, TeamRecord, RepositoryRecord

    # Payment Service uses Redis
    for rec in records:
        if isinstance(rec, ServiceRecord) and rec.id == "service:payment-service":
            if "tech:redis" not in rec.technologies:
                result.add("<dataset>", rec.id, "technologies",
                           "Payment Service must list tech:redis.")
            break
    else:
        result.add("<dataset>", "service:payment-service", "id",
                   "Payment Service record is missing.")

    # Checkout depends on Payment
    for rec in records:
        if isinstance(rec, ServiceRecord) and rec.id == "service:checkout-service":
            if "service:payment-service" not in rec.depends_on:
                result.add("<dataset>", rec.id, "depends_on",
                           "Checkout Service must depend on Payment Service.")
            break

    # payments-api implements Payment Service
    for rec in records:
        if isinstance(rec, RepositoryRecord) and rec.id == "repo:novapay/payments-api":
            if rec.service != "service:payment-service":
                result.add("<dataset>", rec.id, "service",
                           "payments-api must implement service:payment-service.")
            break

    # Payments team owns Payment Service
    for rec in records:
        if isinstance(rec, TeamRecord) and rec.id == "team:payments":
            if "service:payment-service" not in rec.owns_services:
                result.add("<dataset>", rec.id, "owns_services",
                           "Payments team must own service:payment-service.")
            break


# ---------------------------------------------------------------------------
# Alias validation
# ---------------------------------------------------------------------------

def _validate_aliases(
    aliases: dict[str, str],
    id_registry: dict[str, EntityType],
    result: ValidationResult,
) -> None:
    seen_aliases: set[str] = set()
    for alias, target in aliases.items():
        if not alias or not alias.strip():
            result.add("aliases.json", "(empty)", "alias", "Empty alias string.")
            continue
        normalized = alias.strip().lower()
        if normalized in seen_aliases:
            result.add("aliases.json", normalized, "alias", "Duplicate alias.")
        seen_aliases.add(normalized)

        if target not in id_registry:
            result.add("aliases.json", alias, "target",
                       f"Alias target '{target}' not found in ID registry.")


# ---------------------------------------------------------------------------
# Additional data quality checks (Passes 8–13)
# ---------------------------------------------------------------------------

def _validate_orphan_decisions(
    records: list[BaseRecord],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    for rec in records:
        if isinstance(rec, DecisionRecord):
            fname = file_map.get(rec.id, "<unknown>")
            connections = (
                rec.affects + rec.introduces + rec.participants +
                rec.approved_by + rec.supported_by + rec.implemented_by +
                rec.documented_in
            )
            if not connections:
                result.add(fname, rec.id, "id", f"Orphan Decision: '{rec.id}' has no connected entities.")


def _validate_service_ownership(
    records: list[BaseRecord],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    from .models import ServiceRecord, TeamRecord
    owned_services: set[str] = set()
    for rec in records:
        if isinstance(rec, TeamRecord):
            owned_services.update(rec.owns_services)
    for rec in records:
        if isinstance(rec, ServiceRecord):
            fname = file_map.get(rec.id, "<unknown>")
            if rec.id not in owned_services:
                result.add(fname, rec.id, "owns_services", f"Service '{rec.id}' has no owner team.")


def _validate_decision_evidence(
    records: list[BaseRecord],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    for rec in records:
        if isinstance(rec, DecisionRecord):
            fname = file_map.get(rec.id, "<unknown>")
            if rec.status == "accepted" and len(rec.supported_by) < 2:
                result.add(
                    fname, rec.id, "supported_by",
                    f"Primary/accepted decision '{rec.id}' has insufficient evidence sources ({len(rec.supported_by)} < 2)."
                )


def _validate_chronology(
    records: list[BaseRecord],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    from .models import IssueRecord, MessageRecord, CommitRecord, DocumentRecord, IncidentRecord
    rec_map = {r.id: r for r in records}
    for rec in records:
        fname = file_map.get(rec.id, "<unknown>")
        if isinstance(rec, DecisionRecord) and rec.decided_at:
            for sup_id in rec.supported_by:
                sup = rec_map.get(sup_id)
                if isinstance(sup, IssueRecord) and sup.created_at and sup.created_at > rec.decided_at:
                    result.add(
                        fname, rec.id, "decided_at",
                        f"Chronology error: supporting issue '{sup_id}' created ({sup.created_at}) after decision ({rec.decided_at})."
                    )
                elif isinstance(sup, MessageRecord) and sup.timestamp and sup.timestamp > rec.decided_at:
                    result.add(
                        fname, rec.id, "decided_at",
                        f"Chronology error: supporting message '{sup_id}' timestamp ({sup.timestamp}) after decision ({rec.decided_at})."
                    )
            for imp_id in rec.implemented_by:
                imp = rec_map.get(imp_id)
                if isinstance(imp, CommitRecord) and imp.timestamp and imp.timestamp < rec.decided_at:
                    result.add(
                        fname, rec.id, "decided_at",
                        f"Chronology error: implementing commit '{imp_id}' timestamp ({imp.timestamp}) before decision ({rec.decided_at})."
                    )
        elif isinstance(rec, IncidentRecord) and rec.started_at:
            for issue_id in rec.related_issues:
                iss = rec_map.get(issue_id)
                if isinstance(iss, IssueRecord) and iss.created_at and iss.created_at < rec.started_at:
                    result.add(
                        fname, rec.id, "started_at",
                        f"Chronology error: incident '{rec.id}' started ({rec.started_at}) after related issue '{issue_id}' created ({iss.created_at})."
                    )


def _validate_text_integrity(
    records: list[BaseRecord],
    file_map: dict[str, str],
    result: ValidationResult,
) -> None:
    from .models import IssueRecord, MessageRecord, CommitRecord, DocumentRecord
    for rec in records:
        fname = file_map.get(rec.id, "<unknown>")
        if isinstance(rec, IssueRecord):
            if not rec.title or not rec.title.strip():
                result.add(fname, rec.id, "title", "Issue has empty title.")
            if rec.description is not None and not rec.description.strip():
                result.add(fname, rec.id, "description", "Issue has empty description text.")
        elif isinstance(rec, MessageRecord):
            if not rec.text or not rec.text.strip():
                result.add(fname, rec.id, "text", "Message has empty text.")
        elif isinstance(rec, CommitRecord):
            if not rec.message or not rec.message.strip():
                result.add(fname, rec.id, "message", "Commit has empty message.")
        elif isinstance(rec, DocumentRecord):
            if not rec.title or not rec.title.strip():
                result.add(fname, rec.id, "title", "Document has empty title.")
            if rec.content is not None and not rec.content.strip():
                result.add(fname, rec.id, "content", "Document has empty content text.")


def _validate_chunks(
    chunks: list[Any],
    id_registry: dict[str, EntityType],
    result: ValidationResult,
) -> None:
    for chunk in chunks:
        cid = getattr(chunk, "id", "")
        if not cid or not str(cid).strip():
            result.add("<chunks>", "(empty)", "id", "Chunk has an empty ID.")
            continue
        if not str(cid).startswith("chunk:"):
            result.add("<chunks>", cid, "id", f"Chunk ID missing 'chunk:' prefix: '{cid}'.")
        sid = getattr(chunk, "source_id", "")
        if sid not in id_registry:
            result.add(
                "<chunks>", cid, "source_id",
                f"Chunk provenance error: source '{sid}' not found in ID registry."
            )
        else:
            target_type = id_registry[sid]
            stype = getattr(chunk, "source_type", "")
            if stype != target_type.value:
                result.add(
                    "<chunks>", cid, "source_type",
                    f"Chunk source_type '{stype}' does not match target entity type '{target_type.value}'."
                )
        text = getattr(chunk, "text", "")
        if not text or not str(text).strip():
            result.add("<chunks>", cid, "text", "Chunk has empty text.")
