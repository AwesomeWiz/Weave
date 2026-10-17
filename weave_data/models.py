"""
Weave — Canonical record schemas (Pydantic models).

These models define the validated structure of every entity in the NovaPay
dataset.  They enforce:
  - non-empty canonical IDs
  - required fields per entity type
  - ISO-8601 timestamp parsing
  - explicit relationship references using canonical IDs

The models are intentionally decoupled from FalkorDB so that validation
and normalization can run independently of the graph layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    Person = "Person"
    Team = "Team"
    Service = "Service"
    Technology = "Technology"
    Repository = "Repository"
    Commit = "Commit"
    Issue = "Issue"
    Message = "Message"
    Document = "Document"
    Decision = "Decision"
    Incident = "Incident"
    Chunk = "Chunk"


class SourceType(str, Enum):
    hr = "hr"
    github = "github"
    jira = "jira"
    slack = "slack"
    pagerduty = "pagerduty"
    decision_log = "decision-log"
    service_catalog = "service-catalog"
    docs = "docs"


class DecisionStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    superseded = "superseded"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseRecord(BaseModel):
    """Every source record must carry a canonical ID, source, and entity_type."""
    id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    entity_type: EntityType

    @field_validator("id")
    @classmethod
    def id_must_be_prefixed(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(f"Canonical ID must contain a colon prefix, got: {v!r}")
        if re.search(r"\s", v):
            raise ValueError(f"Canonical ID must not contain whitespace, got: {v!r}")
        return v


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------

class PersonRecord(BaseRecord):
    entity_type: EntityType = EntityType.Person
    name: str = Field(..., min_length=1)
    email_alias: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None
    active: bool = True


class TeamRecord(BaseRecord):
    entity_type: EntityType = EntityType.Team
    name: str = Field(..., min_length=1)
    members: list[str] = Field(default_factory=list)
    owns_services: list[str] = Field(default_factory=list)


class ServiceRecord(BaseRecord):
    entity_type: EntityType = EntityType.Service
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    criticality: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class TechnologyRecord(BaseRecord):
    entity_type: EntityType = EntityType.Technology
    name: str = Field(..., min_length=1)
    category: Optional[str] = None


class RepositoryRecord(BaseRecord):
    entity_type: EntityType = EntityType.Repository
    name: str = Field(..., min_length=1)
    url: Optional[str] = None
    default_branch: Optional[str] = None
    service: Optional[str] = None


class CommitRecord(BaseRecord):
    entity_type: EntityType = EntityType.Commit
    sha: Optional[str] = None
    message: str = Field(..., min_length=1)
    timestamp: datetime
    author: Optional[str] = None
    repository: Optional[str] = None
    changes: list[str] = Field(default_factory=list)
    implements_decision: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    architecture_change: bool = False
    url: Optional[str] = None


class IssueRecord(BaseRecord):
    entity_type: EntityType = EntityType.Issue
    key: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    assignee: Optional[str] = None
    affected_services: list[str] = Field(default_factory=list)
    related_incidents: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class MessageRecord(BaseRecord):
    entity_type: EntityType = EntityType.Message
    channel: Optional[str] = None
    thread_id: Optional[str] = None
    text: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = None
    participants: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class DocumentRecord(BaseRecord):
    entity_type: EntityType = EntityType.Document
    title: str = Field(..., min_length=1)
    doc_type: Optional[str] = None
    content: Optional[str] = None
    updated_at: Optional[datetime] = None
    url: Optional[str] = None
    describes: list[str] = Field(default_factory=list)


class DecisionRecord(BaseRecord):
    entity_type: EntityType = EntityType.Decision
    title: str = Field(..., min_length=1)
    summary: Optional[str] = None
    status: DecisionStatus = DecisionStatus.proposed
    decided_at: Optional[datetime] = None
    category: Optional[str] = None
    affects: list[str] = Field(default_factory=list)
    introduces: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    approved_by: list[str] = Field(default_factory=list)
    supported_by: list[str] = Field(default_factory=list)
    implemented_by: list[str] = Field(default_factory=list)
    documented_in: list[str] = Field(default_factory=list)


class IncidentRecord(BaseRecord):
    entity_type: EntityType = EntityType.Incident
    title: str = Field(..., min_length=1)
    severity: Optional[str] = None
    summary: Optional[str] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    affected_services: list[str] = Field(default_factory=list)
    related_issues: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class ChunkRecord(BaseModel):
    """Retrieval chunk — not a source record, so no source/entity_type."""
    id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    chunk_index: int = Field(default=0, ge=0)
    title: Optional[str] = None
    text: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = None
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# Model registry: entity_type → model class
# ---------------------------------------------------------------------------

ENTITY_MODEL_MAP: dict[EntityType, type[BaseRecord]] = {
    EntityType.Person: PersonRecord,
    EntityType.Team: TeamRecord,
    EntityType.Service: ServiceRecord,
    EntityType.Technology: TechnologyRecord,
    EntityType.Repository: RepositoryRecord,
    EntityType.Commit: CommitRecord,
    EntityType.Issue: IssueRecord,
    EntityType.Message: MessageRecord,
    EntityType.Document: DocumentRecord,
    EntityType.Decision: DecisionRecord,
    EntityType.Incident: IncidentRecord,
}
