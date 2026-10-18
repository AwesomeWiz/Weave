export type SupportStatus = 'supported' | 'partially_supported' | 'insufficient_evidence';
export type GraphMode = 'fixture' | 'falkordb';
export interface GraphNode { id: string; type: string; label: string; properties: Record<string, unknown> }
export interface GraphEdge { id: string; source: string; target: string; type: string; properties: Record<string, unknown> }
export interface EvidenceGraph { nodes: GraphNode[]; edges: GraphEdge[] }
export interface Source {
  id: string; type: string; title: string; snippet: string;
  url: string | null; timestamp: string | null; entity_ids: string[]; metadata: Record<string, unknown>;
}
export interface QueryResponse {
  answer: string; support_status: SupportStatus; tools_used: string[];
  sources: Source[]; graph: EvidenceGraph;
  metadata: { latency_ms: number; graph_mode: GraphMode; generation: 'deterministic' | 'ollama' | 'openrouter'; warnings: string[] };
}
export interface Health {
  status: 'ok' | 'degraded' | 'unavailable'; backend: 'available';
  falkordb: 'connected' | 'unavailable' | 'not_checked'; graph_tool: 'available' | 'unavailable' | 'fixture';
  llm: 'available' | 'unavailable' | 'disabled'; graph: string; graph_mode: GraphMode;
}

export interface ImpactInput { entity_id: string; max_depth: number }
export interface ImpactFinding {
  service_id: string; service: Record<string, unknown>; impact_depth: number; impact_type: 'direct' | 'indirect';
  path: string[]; path_edges: { source: string; type: 'DEPENDS_ON' | 'USES'; target: string }[];
  owners: { id: string; name: string }[];
  related_issues: { id: string; title: string; service_id: string; properties: Record<string, unknown> }[];
  related_incidents: { id: string; title: string; service_id: string; properties: Record<string, unknown> }[];
  source_ids: string[];
}
export interface ImpactResponse extends QueryResponse {
  data: { entity: GraphNode | null; direct_impact: ImpactFinding[]; indirect_impact: ImpactFinding[];
    related_issues: ImpactFinding['related_issues']; related_incidents: ImpactFinding['related_incidents'] };
}

export interface ExpertInput { query: string; limit: number }
export interface ExpertEvidence {
  category: 'team_ownership' | 'decision_approval' | 'decision_participation' | 'commit_authorship' | 'issue_assignment' | 'discussion_contribution';
  entity_id: string; entity_type: string;
  path: { source: string; type: string; target: string }[];
  source_ids: string[];
}
export interface ExpertRanking {
  person: { id: string; name: string; role: string | null };
  score: number; ranking_reasons: string[]; evidence: ExpertEvidence[];
  ownership: ExpertEvidence[]; historical_contributions: ExpertEvidence[];
  ownership_classification: 'team_membership_with_team_owned_service' | 'no_current_ownership_evidence';
}
export interface ExpertResponse extends QueryResponse {
  data: { query: string; topics: GraphNode[]; experts: ExpertRanking[]; scoring: Record<string, number> };
}

export interface FreshnessInput { entity: string }
export interface FreshnessPath { source: string; type: string; target: string }
export interface FreshnessTrigger {
  type: 'decision' | 'commit' | 'incident'; id: string; timestamp: string;
  affected_entity_id: string; path: FreshnessPath[]; source_ids: string[];
}
export interface FreshnessFinding {
  document: GraphNode; document_id: string; updated_at: string; affected_entity_id: string;
  document_path: FreshnessPath[]; triggers: FreshnessTrigger[]; reason: string; source_ids: string[];
}
export interface FreshnessResponse extends QueryResponse {
  data: { entity: GraphNode | null; review_candidates: FreshnessFinding[] };
}

export interface ChangeInput { target: string; change: string }
export type ChangeTool = 'decision_trace' | 'impact_analysis' | 'find_expert' | 'find_stale_knowledge';
export interface ChangeEvidenceReference {
  tool: ChangeTool; node_ids: string[]; edge_ids: string[]; source_ids: string[]; relationship_paths: string[][];
}
export interface ChangeTarget {
  requested_target: string | null; requested_change: string; intent: 'remove_technology' | 'unsupported';
  resolution: 'resolved' | 'unsupported' | 'unresolved' | 'ambiguous' | 'inconsistent';
  service: GraphNode | null; technology: GraphNode | null; limitation: string | null;
}
export interface ChangeHistoricalContext {
  support_status: SupportStatus; summary: string; decision_ids: string[]; evidence: ChangeEvidenceReference | null;
}
export type ChangeImpact = ImpactResponse['data'] & {
  support_status: SupportStatus; max_depth: number;
}
export interface ChangeRisk {
  classification: 'KNOWN_FACT' | 'INFERRED_RISK' | 'RECOMMENDATION'; description: string;
  evidence: ChangeEvidenceReference[]; uncertainty: string; affected_entity_ids: string[];
}
export interface ChangeValidationStep {
  classification: 'RECOMMENDATION'; description: string; evidence: ChangeEvidenceReference[]; performed: false;
}
export interface ChangeDocumentReview {
  document: GraphNode; condition: 'if_change_approved_and_implemented'; reason: string; evidence: ChangeEvidenceReference[];
}
export interface ChangeToolSupport {
  support_status: SupportStatus; state: 'validated' | 'unavailable' | 'invalid' | 'unregistered'; evidence: ChangeEvidenceReference;
}
export interface ChangeBriefData {
  proposed_change: ChangeTarget; historical_context: ChangeHistoricalContext; impact: ChangeImpact;
  reviewers: ExpertRanking[]; risks: ChangeRisk[]; validation_steps: ChangeValidationStep[];
  current_freshness_findings: FreshnessFinding[]; documents_to_review_if_change_proceeds: ChangeDocumentReview[];
  tool_support: Partial<Record<ChangeTool, ChangeToolSupport>>; limitations: string[];
}
export interface ChangeResponse extends QueryResponse { data: ChangeBriefData }
