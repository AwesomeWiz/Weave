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
  metadata: { latency_ms: number; graph_mode: GraphMode; generation: 'deterministic' | 'ollama'; warnings: string[] };
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
