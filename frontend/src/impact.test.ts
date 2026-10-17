import { afterEach, describe, expect, it, vi } from 'vitest';
import { analyzeImpact } from './api';
import { routeImpactQuestion } from './impact';
import { impactFixture } from './test/impactFixture';

afterEach(() => vi.unstubAllGlobals());
const request = { entity_id: 'service:payment-service', max_depth: 2 };
describe('Impact Analysis API and endpoint selection', () => {
  it('posts a bounded canonical request and preserves actual paths', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(impactFixture)));
    vi.stubGlobal('fetch', fetch);
    expect((await analyzeImpact(request)).data.indirect_impact[0].path_edges).toEqual(impactFixture.data.indirect_impact[0].path_edges);
    expect(fetch.mock.calls[0][0]).toBe('/api/tools/impact-analysis');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
  });
  it.each(['direction', 'missing edge', 'self impact', 'cycle', 'unknown source', 'unlinked owner', 'depth', 'missing entity', 'missing data'])('rejects invalid %s', async damage => {
    const response = structuredClone(impactFixture);
    const finding = response.data.direct_impact[0];
    if (damage === 'direction') finding.path_edges[0].source = request.entity_id;
    if (damage === 'missing edge') response.graph.edges = [];
    if (damage === 'self impact') finding.service_id = request.entity_id;
    if (damage === 'cycle') finding.path = [request.entity_id, request.entity_id];
    if (damage === 'unknown source') finding.source_ids = ['issue:invented'];
    if (damage === 'unlinked owner') finding.owners = [{ id: request.entity_id, name: 'Invented owner' }];
    if (damage === 'depth') finding.impact_depth = 4;
    if (damage === 'missing entity') response.data.entity = null;
    if (damage === 'missing data') Reflect.deleteProperty(response, 'data');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(response))));
    await expect(analyzeImpact(request)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('surfaces unavailable graph errors without demo evidence', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'GRAPH_UNAVAILABLE', message: 'Graph unavailable.' } }), { status: 503 })));
    await expect(analyzeImpact(request)).rejects.toMatchObject({ code: 'GRAPH_UNAVAILABLE' });
  });
  it.each([
    ['What would be affected if Payment Service changed?', 'service:payment-service'],
    ['What depends on Payment Service?', 'service:payment-service'],
    ['What services would be impacted if Redis were removed?', 'tech:redis'],
    ['What depends on Checkout Service?', 'service:checkout-service'],
  ])('selects the impact endpoint for %s', (question, entity_id) => {
    expect(routeImpactQuestion(question)).toEqual({ entity_id, max_depth: 2 });
  });
  it.each(['Why does Payment Service use Redis?', 'Why does Payment Service use Redis, and what breaks if removed?', 'What depends on Payment Service and Redis?', 'What depends on Payment Service and Fraud Service?', 'What does Payment Service depend on?', 'What depends on Fraud Service?'])('leaves non-impact or ambiguous %s to backend routing', question => {
    expect(routeImpactQuestion(question)).toBeNull();
  });
  it.each([
    'What led to Redis being introduced for Payment Service, and what services might be affected if Redis were removed?',
    'What led to Redis being introduced, and what services might be affected if Redis were removed?',
    'What depends on Payment Service; who knows about it?',
    'What depends on Payment Service, and are the docs up to date?',
    'What changed in Payment Service?',
  ])('leaves compound question %s to the backend multi-tool planner', question => {
    expect(routeImpactQuestion(question)).toBeNull();
  });
});
