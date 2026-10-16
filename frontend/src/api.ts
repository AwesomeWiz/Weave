import type { Health, QueryResponse } from './types';

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

export async function askQuestion(question: string): Promise<QueryResponse> {
  let response: Response;
  try {
    response = await fetch(`${base}/api/query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: 'weave-browser' }),
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
