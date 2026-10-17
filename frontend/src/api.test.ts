import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, askQuestion, getHealth, safeSourceUrl } from './api';
import type { QueryResponse } from './types';

afterEach(() => vi.unstubAllGlobals());

describe('API failures and contracts', () => {
  it('surfaces actionable graph-unavailable errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: false,
      error: { code: 'GRAPH_UNAVAILABLE', message: 'Configure the graph adapter.' } }), { status: 503 })));
    await expect(askQuestion('Why Redis?')).rejects.toEqual(new ApiError('Configure the graph adapter.', 'GRAPH_UNAVAILABLE'));
  });
  it('handles an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
  });
  it('handles non-JSON proxy errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad gateway', { status: 502 })));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('rejects incompatible successful payloads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ answer: 'test' }))));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('reads degraded health from HTTP 503', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: 'unavailable', graph_mode: 'falkordb', backend: 'available', graph: 'novapay',
      falkordb: 'unavailable', graph_tool: 'unavailable', llm: 'disabled',
    }), { status: 503 })));
    expect((await getHealth()).status).toBe('unavailable');
  });
  it('rejects incomplete health instead of displaying a false ready status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }))));
    await expect(getHealth()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  const valid: QueryResponse = {
    answer: 'Test evidence', support_status: 'partially_supported', tools_used: ['trace_decision'],
    sources: [], graph: { nodes: [{ id: '1', type: 'Service', label: 'Test', properties: {} }],
      edges: [{ id: 'edge', source: '1', target: '1', type: 'TEST', properties: {} }] },
    metadata: { latency_ms: 1, graph_mode: 'fixture', generation: 'deterministic', warnings: [] },
  };
  it('accepts OpenRouter generation through the existing query contract', async () => {
    const response = { ...valid, metadata: { ...valid.metadata, generation: 'openrouter' } };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(response))));
    expect(await askQuestion('Why Redis?')).toEqual(response);
  });
  it('continues rejecting unrecognized generation providers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...valid, metadata: { ...valid.metadata, generation: 'invented-provider' },
    }))));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it.each([
    ['numeric endpoint', { ...valid.graph, edges: [{ ...valid.graph.edges[0], source: 1 }] }],
    ['duplicate node IDs', { ...valid.graph, nodes: [...valid.graph.nodes, ...valid.graph.nodes] }],
    ['duplicate edge IDs', { ...valid.graph, edges: [...valid.graph.edges, ...valid.graph.edges] }],
    ['array properties', { ...valid.graph, nodes: [{ ...valid.graph.nodes[0], properties: [] }] }],
    ['dangling endpoint', { ...valid.graph, edges: [{ ...valid.graph.edges[0], target: 'absent' }] }],
  ])('rejects %s before graph rendering', async (_name, graph) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...valid, graph }))));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('rejects malformed graph nodes before rendering', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      answer: 'test', support_status: 'supported', tools_used: ['trace_decision'], sources: [],
      graph: { nodes: [{ id: 'bad' }], edges: [] },
      metadata: { latency_ms: 1, graph_mode: 'fixture', generation: 'deterministic', warnings: [] },
    }))));
    await expect(askQuestion('Why Redis?')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it.each(['javascript:alert(1)', 'data:text/html,x', 'file:///test', 'https://user:pass@example.org', 'https://example.invalid/jira'])('blocks unsafe or placeholder URL %s', url => {
    expect(safeSourceUrl(url)).toBeUndefined();
  });
  it('allows a normal HTTPS source URL', () => {
    expect(safeSourceUrl('https://example.org/docs')).toBe('https://example.org/docs');
  });
});
