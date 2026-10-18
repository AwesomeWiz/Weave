import { afterEach, describe, expect, it, vi } from 'vitest';
import { analyzeChange } from './api';
import { CHANGE_QUESTION, changeGraphFocus, historicalPathReference, routeChangeQuestion } from './change';
import { changeFixture } from './test/changeFixture';
import { changeWithoutSources, unresolvedChange } from './test/changeTestCases';
import { changeWithOrderedPaths } from './test/orderedTraceFixture';
import type { ChangeResponse } from './types';

const request = { target: 'Payment Service', change: 'Remove Redis from Payment Service' };
afterEach(() => vi.unstubAllGlobals());
function respond(result: ChangeResponse) {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
  vi.stubGlobal('fetch', fetch); return fetch;
}

describe('Change endpoint and proposal routing', () => {
  it('preserves named historical path order and highlights only actual local graph edges', async () => {
    const result = changeWithOrderedPaths(); respond(result);
    const received = await analyzeChange(request);
    expect(received).toEqual(result);
    const path = received.data.historical_context.relationship_paths!.find(p => p.id === 'decision_to_current_architecture')!;
    expect(path.steps).toEqual([
      { source: 'decision:D-007', type: 'IMPLEMENTED_BY', target: 'commit:8fae2' },
      { source: 'commit:8fae2', type: 'CHANGES', target: 'service:payment-service' },
      { source: 'service:payment-service', type: 'USES', target: 'tech:redis' },
    ]);
    const reference = historicalPathReference(received, path)!;
    expect(reference.tool).toBe('decision_trace'); expect(reference.source_ids).toEqual([]);
    expect(reference.edge_ids).toEqual(path.steps.map(s => result.graph.edges.find(e => e.source === s.source && e.type === s.type && e.target === s.target)!.id));
    expect(reference.relationship_paths).toEqual([reference.edge_ids]);
    expect(reference.edge_ids.every(id => changeGraphFocus(received).graph.edges.some(e => e.id === id))).toBe(true);
    expect(historicalPathReference(changeFixture, path)).toBeNull();
  });
  it('accepts omitted or empty historical paths for backward compatibility', async () => {
    for (const result of [structuredClone(changeFixture), changeWithOrderedPaths()]) {
      if (result.data.historical_context.relationship_paths) result.data.historical_context.relationship_paths = [];
      respond(result); expect(await analyzeChange(request)).toEqual(result);
    }
  });
  it.each(['order', 'direction', 'type', 'node', 'missing edge', 'sibling edge', 'duplicate id',
    'empty steps', 'disconnected', 'too many steps', 'too many paths', 'null', 'extra field', 'extra step field', 'wrong sequence', 'no history'])('rejects invalid ordered path: %s', async damage => {
    const result = changeWithOrderedPaths();
    const history = result.data.historical_context;
    const paths = history.relationship_paths!;
    const path = paths.find(p => p.id === 'decision_to_current_architecture')!;
    if (damage === 'order') path.steps.reverse();
    if (damage === 'direction') [path.steps[0].source, path.steps[0].target] = [path.steps[0].target, path.steps[0].source];
    if (damage === 'type') path.steps[0].type = 'INVENTED';
    if (damage === 'node') path.steps[0].source = 'decision:invented';
    if (damage === 'missing edge') result.graph.edges = result.graph.edges.filter(e => e.type !== 'CHANGES');
    if (damage === 'sibling edge') {
      const id = result.graph.edges.find(e => e.type === 'CHANGES')!.id;
      history.evidence!.edge_ids = history.evidence!.edge_ids.filter(e => e !== id);
      history.evidence!.relationship_paths = history.evidence!.relationship_paths.filter(p => !p.includes(id));
      result.data.tool_support.decision_trace!.evidence = structuredClone(history.evidence!);
    }
    if (damage === 'duplicate id') paths.push(structuredClone(path));
    if (damage === 'empty steps') path.steps = [];
    if (damage === 'disconnected') path.steps[1] = paths.find(p => p.id === 'incident_to_investigation')!.steps[0];
    if (damage === 'too many steps') path.steps = Array.from({ length: 11 }, () => path.steps[0]);
    if (damage === 'too many paths') history.relationship_paths = Array.from({ length: 81 }, (_, i) => ({ ...path, id: String(i) }));
    if (damage === 'null') history.relationship_paths = null as never;
    if (damage === 'extra field') Object.assign(path, { citations: ['doc:invented'] });
    if (damage === 'extra step field') Object.assign(path.steps[0], { approved: true });
    if (damage === 'wrong sequence') history.evidence!.relationship_paths = history.evidence!.relationship_paths.map(p => [...p].reverse());
    if (damage === 'no history') history.evidence = null;
    expect(historicalPathReference(result, path)).toBeNull();
    respond(result); await expect(analyzeChange(request)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('requests structured data once and preserves the actual backend response', async () => {
    const fetch = respond(changeFixture);
    expect(await analyzeChange(request)).toEqual(changeFixture);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toContain('/api/change-intelligence');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
  });
  it.each([CHANGE_QUESTION, 'What would happen if we remove Redis from Payment Service?',
    'If we remove Redis from Payment Service', 'Remove Redis from Payment Service'])('routes an explicit removal: %s', question => {
    expect(routeChangeQuestion(question)).toEqual({ target: 'Payment Service', change: question });
  });
  it.each(['Upgrade Redis in Payment Service', 'Replace Redis with PostgreSQL in Payment Service',
    'Migrate Payment Service', 'Deprecate Redis', 'Switch from Redis', 'Move away from Redis'])('sends unsupported proposals to the backend for qualification: %s', question => {
    expect(routeChangeQuestion(question)?.change).toBe(question);
  });
  it.each(['Why does Payment Service use Redis?', 'Who knows Payment Service?', 'Which documents about Payment Service need review?',
    'What depends on Payment Service?', 'What services might be affected if Redis were removed?'])('preserves Phase 2 selection: %s', question => {
    expect(routeChangeQuestion(question)).toBeNull();
  });
  it('uses only returned graph objects and excludes chunk clutter from focus', () => {
    const original = structuredClone(changeFixture);
    const focus = changeGraphFocus(changeFixture);
    expect(focus.graph.nodes.some(n => n.type === 'Chunk')).toBe(false);
    expect(focus.graph.nodes.length).toBeLessThan(changeFixture.graph.nodes.length);
    expect(focus.graph.nodes.every(n => changeFixture.graph.nodes.includes(n))).toBe(true);
    expect(focus.graph.edges.every(e => changeFixture.graph.edges.includes(e))).toBe(true);
    expect(focus.graph.edges.some(e => e.source === 'service:checkout-service' && e.type === 'DEPENDS_ON' && e.target === 'service:payment-service')).toBe(true);
    expect(focus.primaryNodeIds).toContain('service:order-service');
    expect(changeFixture).toEqual(original);
  });
  it('surfaces network and graph-unavailable errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(analyzeChange(request)).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'GRAPH_UNAVAILABLE', message: 'Graph not ready.' } }), { status: 503 })));
    await expect(analyzeChange(request)).rejects.toMatchObject({ code: 'GRAPH_UNAVAILABLE', message: 'Graph not ready.' });
  });
  it('accepts explicit graph-only and qualified unsupported responses', async () => {
    respond(changeWithoutSources());
    expect((await analyzeChange(request)).sources).toHaveLength(0);
    const change = 'Upgrade Redis in Payment Service';
    respond(unresolvedChange(change));
    expect((await analyzeChange({ target: 'Payment Service', change })).support_status).toBe('insufficient_evidence');
  });
  it.each(['source id', 'edge id', 'node id', 'local membership', 'tool state', 'tool status', 'overall upgrade',
    'request mismatch', 'target mismatch', 'historical source', 'history status', 'impact direction', 'impact depth',
    'impact path', 'reviewer score', 'reviewer name', 'reviewer role', 'reviewer path', 'ownership',
    'risk class', 'risk entity', 'risk source', 'validation performed', 'future condition', 'future path',
    'document date', 'trigger date', 'trigger direction', 'decision citation', 'duplicate current', 'duplicate future', 'byte bound'])('rejects invalid %s', async damage => {
    const result = structuredClone(changeFixture);
    const data = result.data;
    const fact = data.risks[0];
    const fresh = data.current_freshness_findings[0];
    const future = data.documents_to_review_if_change_proceeds[0];
    const person = data.reviewers[0];
    if (damage === 'source id') fact.evidence[0].source_ids.push('doc:invented');
    if (damage === 'edge id') fact.evidence[0].edge_ids.push('invented');
    if (damage === 'node id') fact.evidence[0].node_ids.push('service:invented');
    if (damage === 'local membership') fact.evidence[0].source_ids.push('doc:ADR-7');
    if (damage === 'tool state') data.tool_support.impact_analysis!.state = 'invalid';
    if (damage === 'tool status') data.tool_support.impact_analysis!.support_status = 'invented' as never;
    if (damage === 'overall upgrade') result.support_status = 'supported';
    if (damage === 'request mismatch') data.proposed_change.requested_change = 'Upgrade Redis';
    if (damage === 'target mismatch') data.proposed_change.service = null;
    if (damage === 'historical source') data.historical_context.summary += ' [doc:invented]';
    if (damage === 'history status') data.historical_context.support_status = 'insufficient_evidence';
    if (damage === 'impact direction') {
      const p = data.impact.direct_impact[0].path_edges[0]; [p.source, p.target] = [p.target, p.source];
    }
    if (damage === 'impact depth') data.impact.direct_impact[0].impact_depth = 2;
    if (damage === 'impact path') data.impact.indirect_impact[0].path[1] = 'service:order-service';
    if (damage === 'reviewer score') person.score = 0;
    if (damage === 'reviewer name') person.person.name = 'Invented';
    if (damage === 'reviewer role') person.person.role = 'Invented';
    if (damage === 'reviewer path') person.evidence[0].path[0].type = 'INVENTED';
    if (damage === 'ownership') person.ownership_classification = 'personal_owner' as never;
    if (damage === 'risk class') fact.classification = 'PROVEN_OUTAGE' as never;
    if (damage === 'risk entity') fact.affected_entity_ids.push('service:unrelated');
    if (damage === 'risk source') fact.evidence[0].source_ids.push('doc:ADR-7');
    if (damage === 'validation performed') data.validation_steps[0].performed = true as never;
    if (damage === 'future condition') future.condition = 'currently_stale' as never;
    if (damage === 'future path') future.evidence[0].edge_ids = [];
    if (damage === 'document date') fresh.updated_at = 'not-a-date';
    if (damage === 'trigger date') fresh.triggers[0].timestamp = '2020-01-01T00:00:00Z';
    if (damage === 'trigger direction') fresh.triggers[0].path[0].type = 'INVENTED';
    if (damage === 'decision citation') fresh.triggers.find(t => t.type === 'decision')!.source_ids.push('doc:ADR-7');
    if (damage === 'duplicate current') data.current_freshness_findings.push(fresh);
    if (damage === 'duplicate future') data.documents_to_review_if_change_proceeds.push(future);
    if (damage === 'byte bound') data.limitations.push('x'.repeat(160001));
    respond(result);
    await expect(analyzeChange(request)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});
