import type { Health, ImpactInput, ImpactResponse, QueryResponse } from './types';

export class ApiError extends Error {
  constructor(message: string, public code = 'REQUEST_FAILED') { super(message); }
}

const base = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nonempty(value: unknown): value is string { return typeof value === 'string' && value.trim().length > 0; }

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string');
}

function validEvidence(data: Record<string, unknown>): boolean {
  if (!record(data.graph) || !Array.isArray(data.graph.nodes) || !Array.isArray(data.graph.edges)
    || !Array.isArray(data.sources) || !record(data.metadata)) return false;
  const nodes = data.graph.nodes;
  if (!nodes.every(n => record(n) && nonempty(n.id) && nonempty(n.type)
    && nonempty(n.label) && record(n.properties))) return false;
  const ids = new Set(nodes.map((n: { id: string }) => n.id));
  if (ids.size !== nodes.length) return false;
  const edgeIds = new Set<string>();
  const sourceIds = new Set<string>();
  return data.graph.edges.every(e => {
    if (!record(e) || !nonempty(e.id) || !nonempty(e.type) || !nonempty(e.source)
      || !nonempty(e.target) || !ids.has(e.source) || !ids.has(e.target)
      || !record(e.properties) || edgeIds.has(e.id)) return false;
    edgeIds.add(e.id);
    return true;
  })
    && data.sources.every(s => {
      if (!record(s) || !nonempty(s.id) || sourceIds.has(s.id)) return false;
      sourceIds.add(s.id);
      return typeof s.type === 'string'
      && typeof s.title === 'string' && typeof s.snippet === 'string' && strings(s.entity_ids)
      && (s.url === null || typeof s.url === 'string') && (s.timestamp === null || typeof s.timestamp === 'string') && record(s.metadata);
    })
    && strings(data.tools_used) && typeof data.metadata.latency_ms === 'number'
    && Number.isFinite(data.metadata.latency_ms) && data.metadata.latency_ms >= 0
    && strings(data.metadata.warnings) && ['deterministic', 'ollama'].includes(String(data.metadata.generation));
}

async function postEvidence(path: string, body: unknown): Promise<QueryResponse> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120_000),
    });
  } catch (error) {
    throw new ApiError(error instanceof Error && error.name === 'TimeoutError'
      ? 'The request took too long. Please try again.'
      : 'Cannot reach Weave. Start the FastAPI server on port 8000 and try again.', 'NETWORK_ERROR');
  }
  let data: unknown;
  try { data = await response.json(); } catch {
    throw new ApiError('Weave returned an unreadable response. Check the backend and retry.', 'INVALID_RESPONSE');
  }
  if (!response.ok) {
    const error = record(data) && record(data.error) ? data.error : null;
    throw new ApiError(error && typeof error.message === 'string' ? error.message : 'Weave could not complete the request.',
      error && typeof error.code === 'string' ? error.code : 'REQUEST_FAILED');
  }
  if (!record(data) || typeof data.answer !== 'string'
    || !['supported', 'partially_supported', 'insufficient_evidence'].includes(String(data.support_status))
    || !Array.isArray(data.sources) || !record(data.graph)
    || !Array.isArray(data.graph.nodes) || !Array.isArray(data.graph.edges)
    || !record(data.metadata) || !['fixture', 'falkordb'].includes(String(data.metadata.graph_mode)) || !validEvidence(data)) {
    throw new ApiError('The API returned an incompatible evidence format.', 'INVALID_RESPONSE');
  }
  return data as unknown as QueryResponse;
}

export function askQuestion(question: string): Promise<QueryResponse> {
  return postEvidence('/api/query', { question, session_id: 'weave-browser' });
}

export async function analyzeImpact(request: ImpactInput): Promise<ImpactResponse> {
  const response = await postEvidence('/api/tools/impact-analysis', request);
  const data: unknown = (response as ImpactResponse).data;
  const ids = new Map(response.graph.nodes.map(n => [n.id, n]));
  const citations = new Set(response.sources.map(s => s.id));
  const seen = new Set<string>();
  function related(value: unknown): boolean {
    return Array.isArray(value) && value.every(item => record(item) && nonempty(item.id)
      && ids.has(item.id) && typeof item.title === 'string' && nonempty(item.service_id) && record(item.properties));
  }
  function findings(value: unknown, type: 'direct' | 'indirect'): boolean {
    return Array.isArray(value) && value.every(f => {
      if (!record(f) || !nonempty(f.service_id) || seen.has(f.service_id) || f.service_id === request.entity_id
        || ids.get(f.service_id)?.type !== 'Service' || !record(f.service)
        || f.impact_type !== type || !Number.isInteger(f.impact_depth) || Number(f.impact_depth) < 1
        || Number(f.impact_depth) > request.max_depth || (Number(f.impact_depth) === 1) !== (type === 'direct')
        || !strings(f.path) || f.path.length !== Number(f.impact_depth) + 1
        || new Set(f.path).size !== f.path.length || f.path.some(id => !ids.has(id))
        || f.path[0] !== request.entity_id || f.path.at(-1) !== f.service_id
        || !Array.isArray(f.path_edges) || f.path_edges.length !== f.impact_depth
        || !f.path_edges.every((edge, index) => record(edge)
          && edge.source === (f.path as string[])[index + 1] && edge.target === (f.path as string[])[index]
          && edge.type === (index === 0 && ids.get(request.entity_id)?.type === 'Technology' ? 'USES' : 'DEPENDS_ON')
          && response.graph.edges.some(e => e.source === edge.source && e.type === edge.type && e.target === edge.target))
        || !Array.isArray(f.owners) || !f.owners.every(owner => record(owner) && nonempty(owner.id)
          && ids.has(owner.id) && typeof owner.name === 'string'
          && response.graph.edges.some(e => e.source === owner.id && e.type === 'OWNS' && e.target === f.service_id))
        || !strings(f.source_ids) || !f.source_ids.every(id => citations.has(id))
        || !related(f.related_issues) || !related(f.related_incidents)) return false;
      seen.add(f.service_id);
      return true;
    });
  }
  if (!record(data) || !response.tools_used.includes('impact_analysis')
    || (data.entity !== null && (!record(data.entity) || data.entity.id !== request.entity_id || !ids.has(request.entity_id)))
    || !findings(data.direct_impact, 'direct') || !findings(data.indirect_impact, 'indirect')
    || !related(data.related_issues) || !related(data.related_incidents)
    || (data.entity === null && response.graph.nodes.length > 0)) {
    throw new ApiError('The API returned an incompatible impact format.', 'INVALID_RESPONSE');
  }
  return response as ImpactResponse;
}

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(10_000) });
  // A critical dependency outage deliberately returns HTTP 503 with a valid health body.
  const health: unknown = await response.json();
  if (![200, 503].includes(response.status) || !record(health)
    || !['ok', 'degraded', 'unavailable'].includes(String(health.status))
    || health.backend !== 'available' || !nonempty(health.graph)
    || !['fixture', 'falkordb'].includes(String(health.graph_mode))
    || !['connected', 'unavailable', 'not_checked'].includes(String(health.falkordb))
    || !['available', 'unavailable', 'fixture'].includes(String(health.graph_tool))
    || !['available', 'unavailable', 'disabled'].includes(String(health.llm))) {
    throw new ApiError('The API returned an incompatible health format.', 'INVALID_RESPONSE');
  }
  return health as unknown as Health;
}

export function safeSourceUrl(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password
      && !url.hostname.endsWith('.invalid') ? url.href : undefined;
  } catch { return undefined; }
}
