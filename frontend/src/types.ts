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
