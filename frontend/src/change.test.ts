import { afterEach, describe, expect, it, vi } from 'vitest';
import { analyzeChange } from './api';
import { CHANGE_QUESTION, changeGraphFocus, routeChangeQuestion } from './change';
import { changeFixture } from './test/changeFixture';
import { changeWithoutSources, unresolvedChange } from './test/changeTestCases';
import type { ChangeResponse } from './types';

const request = { target: 'Payment Service', change: 'Remove Redis from Payment Service' };
afterEach(() => vi.unstubAllGlobals());
function respond(result: ChangeResponse) {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
  vi.stubGlobal('fetch', fetch); return fetch;
}

describe('Change endpoint and proposal routing', () => {
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
