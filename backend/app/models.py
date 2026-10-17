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


class TraceResult(BaseModel):
    """Team integration contract; source IDs are resolved independently."""
    graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    source_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Metadata(BaseModel):
    latency_ms: int
    graph_mode: Literal["fixture", "falkordb"]
    generation: Literal["deterministic", "ollama"] = "deterministic"
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
