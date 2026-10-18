from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportStatus = Literal["supported", "partially_supported", "insufficient_evidence"]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=128)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value.strip()


class GraphNode(BaseModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(min_length=1)
    source: str
    target: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EvidenceGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    type: str
    title: str
    snippet: str
    url: str | None = None
    timestamp: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceInput(BaseModel):
    service: str
    technology: str


class TracePathStep(BaseModel):
    """One stored directed relationship in an ordered Decision Trace path."""
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str = Field(min_length=1)
    type: str = Field(min_length=1)
    target: str = Field(min_length=1)


class TraceRelationshipPath(BaseModel):
    """A named, ordered path returned by the graph trace tool."""
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=128)
    steps: list[TracePathStep] = Field(min_length=1, max_length=10)


class TraceResult(BaseModel):
    """Team integration contract; source IDs are resolved independently."""
    graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    source_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    relationship_paths: list[TraceRelationshipPath] = Field(default_factory=list, max_length=80)
    warnings: list[str] = Field(default_factory=list)


class Metadata(BaseModel):
    latency_ms: int
    graph_mode: Literal["fixture", "falkordb"]
    generation: Literal["deterministic", "ollama", "openrouter"] = "deterministic"
    warnings: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    support_status: SupportStatus
    tools_used: list[str]
    sources: list[Source] = Field(default_factory=list)
    graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    metadata: Metadata


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    backend: Literal["available"] = "available"
    falkordb: Literal["connected", "unavailable", "not_checked"]
    graph_tool: Literal["available", "unavailable", "fixture"]
    llm: Literal["available", "unavailable", "disabled"]
    graph: str
    graph_mode: Literal["fixture", "falkordb"]


class ImpactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str = Field(pattern=r"^(service|tech):[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=128)
    max_depth: int = Field(default=2, ge=1, le=3, strict=True)


class ImpactPathEdge(BaseModel):
    source: str
    type: Literal["DEPENDS_ON", "USES"]
    target: str


class ImpactOwner(BaseModel):
    id: str
    name: str


class ImpactRelated(BaseModel):
    id: str
    title: str
    properties: dict[str, Any]
    service_id: str


class ImpactFinding(BaseModel):
    service_id: str
    service: dict[str, Any]
    impact_depth: int = Field(ge=1, le=3, strict=True)
    impact_type: Literal["direct", "indirect"]
    path: list[str]
    path_edges: list[ImpactPathEdge]
    owners: list[ImpactOwner] = Field(default_factory=list)
    related_issues: list[ImpactRelated] = Field(default_factory=list)
    related_incidents: list[ImpactRelated] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class ImpactData(BaseModel):
    entity: GraphNode | None = None
    direct_impact: list[ImpactFinding] = Field(default_factory=list)
    indirect_impact: list[ImpactFinding] = Field(default_factory=list)
    related_issues: list[ImpactRelated] = Field(default_factory=list)
    related_incidents: list[ImpactRelated] = Field(default_factory=list)


class GraphSourceReference(BaseModel):
    id: str = Field(min_length=1)
    chunk_id: str | None = None


class ImpactResult(BaseModel):
    """Common teammate graph-tool envelope, with typed Impact Analysis data."""
    data: ImpactData
    sources: list[GraphSourceReference] = Field(default_factory=list, max_length=40)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=60)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=160)
    warnings: list[str] = Field(default_factory=list)


class ImpactResponse(QueryResponse):
    data: ImpactData


class ExpertInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10, strict=True)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank")
        return value.strip()


class ExpertPathEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str
    type: str
    target: str


class ExpertEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    category: Literal["team_ownership", "decision_approval", "decision_participation",
                      "commit_authorship", "issue_assignment", "discussion_contribution"]
    entity_id: str
    entity_type: str
    path: list[ExpertPathEdge] = Field(min_length=1, max_length=2)
    # Derived only after independent graph and source provenance validation.
    source_ids: list[str] = Field(default_factory=list)


class ExpertPerson(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    role: str | None


class ExpertRanking(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    person: ExpertPerson
    evidence: list[ExpertEvidence] = Field(min_length=1, max_length=100)
    ownership: list[ExpertEvidence] = Field(max_length=100)
    historical_contributions: list[ExpertEvidence] = Field(max_length=100)
    score: int = Field(ge=1)
    ranking_reasons: list[str] = Field(max_length=100)
    ownership_classification: Literal["team_membership_with_team_owned_service", "no_current_ownership_evidence"]


class ExpertData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str
    topics: list[GraphNode] = Field(max_length=20)
    experts: list[ExpertRanking] = Field(max_length=10)
    scoring: dict[str, int]


class ExpertSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    chunk_id: str
    title: str | None = None
    text: str | None = None
    url: str | None = None


class ExpertResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ExpertData
    sources: list[ExpertSourceReference] = Field(default_factory=list, max_length=100)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=80)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=30)


class ExpertResponse(QueryResponse):
    data: ExpertData


class FreshnessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    entity: str = Field(min_length=1, max_length=256)

    @field_validator("entity")
    @classmethod
    def strip_entity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Entity must not be blank")
        return value.strip()


class FreshnessTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["decision", "commit", "incident"]
    id: str
    timestamp: str
    affected_entity_id: str
    path: list[ExpertPathEdge] = Field(min_length=1, max_length=1)
    # Derived from validated FROM_COMMIT provenance; graph-only events stay empty.
    source_ids: list[str] = Field(default_factory=list)


class FreshnessFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document: GraphNode
    document_id: str
    updated_at: str
    affected_entity_id: str
    document_path: list[ExpertPathEdge] = Field(min_length=1, max_length=2)
    triggers: list[FreshnessTrigger] = Field(min_length=1, max_length=150)
    reason: str
    source_ids: list[str] = Field(default_factory=list)


class FreshnessData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    entity: GraphNode | None
    review_candidates: list[FreshnessFinding] = Field(max_length=50)


class FreshnessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: FreshnessData
    sources: list[ExpertSourceReference] = Field(default_factory=list, max_length=100)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=80)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=200)


class FreshnessResponse(QueryResponse):
    data: FreshnessData


class ChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target: str = Field(min_length=1, max_length=256)
    change: str = Field(min_length=1, max_length=2000)

    @field_validator("target", "change")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Target and change must not be blank")
        return value.strip()


class ChangeTarget(BaseModel):
    requested_target: str | None
    requested_change: str
    intent: Literal["remove_technology", "unsupported"]
    resolution: Literal["resolved", "unsupported", "unresolved", "ambiguous", "inconsistent"]
    service: GraphNode | None = None
    technology: GraphNode | None = None
    limitation: str | None = None


class ChangeEvidenceReference(BaseModel):
    tool: Literal["decision_trace", "impact_analysis", "find_expert", "find_stale_knowledge"]
    node_ids: list[str] = Field(default_factory=list, max_length=80)
    edge_ids: list[str] = Field(default_factory=list, max_length=200)
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    relationship_paths: list[list[str]] = Field(default_factory=list, max_length=200)


class ChangeHistoricalContext(BaseModel):
    support_status: SupportStatus = "insufficient_evidence"
    summary: str = "No validated historical rationale was retrieved."
    decision_ids: list[str] = Field(default_factory=list, max_length=30)
    evidence: ChangeEvidenceReference | None = None
    relationship_paths: list[TraceRelationshipPath] = Field(default_factory=list, max_length=80)


class ChangeImpact(ImpactData):
    support_status: SupportStatus = "insufficient_evidence"
    max_depth: int = Field(default=3, ge=1, le=3)


class ChangeReviewer(ExpertRanking):
    """Unchanged validated ranking, never an inferred individual owner."""


class ChangeRisk(BaseModel):
    classification: Literal["KNOWN_FACT", "INFERRED_RISK", "RECOMMENDATION"]
    description: str
    evidence: list[ChangeEvidenceReference] = Field(min_length=1, max_length=4)
    uncertainty: str
    affected_entity_ids: list[str] = Field(default_factory=list, max_length=80)


class ChangeValidationStep(BaseModel):
    classification: Literal["RECOMMENDATION"] = "RECOMMENDATION"
    description: str
    evidence: list[ChangeEvidenceReference] = Field(min_length=1, max_length=4)
    performed: Literal[False] = False


class ChangeDocumentReview(BaseModel):
    document: GraphNode
    condition: Literal["if_change_approved_and_implemented"] = "if_change_approved_and_implemented"
    reason: str
    evidence: list[ChangeEvidenceReference] = Field(min_length=1, max_length=4)


class ChangeToolSupport(BaseModel):
    support_status: SupportStatus
    state: Literal["validated", "unavailable", "invalid", "unregistered"]
    evidence: ChangeEvidenceReference


class ChangeBriefData(BaseModel):
    proposed_change: ChangeTarget
    historical_context: ChangeHistoricalContext = Field(default_factory=ChangeHistoricalContext)
    impact: ChangeImpact = Field(default_factory=ChangeImpact)
    reviewers: list[ChangeReviewer] = Field(default_factory=list, max_length=10)
    risks: list[ChangeRisk] = Field(default_factory=list, max_length=30)
    validation_steps: list[ChangeValidationStep] = Field(default_factory=list, max_length=30)
    current_freshness_findings: list[FreshnessFinding] = Field(default_factory=list, max_length=50)
    documents_to_review_if_change_proceeds: list[ChangeDocumentReview] = Field(default_factory=list, max_length=50)
    tool_support: dict[str, ChangeToolSupport] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class ChangeResponse(QueryResponse):
    data: ChangeBriefData
