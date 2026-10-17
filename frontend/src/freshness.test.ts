import { afterEach, describe, expect, it, vi } from 'vitest';
import { checkFreshness } from './api';
import { FRESHNESS_QUESTION, routeFreshnessQuestion } from './freshness';
import { freshnessFixture } from './test/freshnessFixture';

afterEach(() => vi.unstubAllGlobals());

describe('Freshness routing and API contract', () => {
  it('preserves a lowercase explicit name for graph resolution', () => {
    expect(routeFreshnessQuestion('is the payment service documentation outdated?')).toEqual({ entity: 'payment service' });
  });
  it.each([FRESHNESS_QUESTION, 'Is the Payment Service documentation outdated?', 'Are Payment Service docs up to date?'])('resolves the explicit target: %s', question => {
    expect(routeFreshnessQuestion(question)).toEqual({ entity: 'Payment Service' });
  });
  it.each(['Is our architecture documentation still current?', 'Are the docs up to date?',
    `${FRESHNESS_QUESTION}; Who knows Payment Service?`,
    'Is the Payment Service and Checkout Service documentation outdated?'])('keeps ambiguous and combined questions with the backend: %s', question => {
    expect(routeFreshnessQuestion(question)).toBeNull();
  });
  it('calls the dedicated endpoint and preserves the structured findings', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(freshnessFixture)));
    vi.stubGlobal('fetch', fetch);
    expect(await checkFreshness({ entity: 'Payment Service' })).toEqual(freshnessFixture);
    expect(fetch.mock.calls[0][0]).toContain('/api/tools/freshness');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ entity: 'Payment Service' });
  });
  it.each(['path', 'direction', 'document time', 'change time', 'earlier', 'naive', 'decision citation', 'unknown citation', 'duplicate', 'reason'])('rejects invalid %s', async damage => {
    const result = structuredClone(freshnessFixture);
    const f = result.data.review_candidates[0];
    if (damage === 'path') result.graph.edges = [];
    if (damage === 'direction') [f.document_path[0].source, f.document_path[0].target] = [f.document_path[0].target, f.document_path[0].source];
    if (damage === 'document time') f.updated_at = 'invalid';
    if (damage === 'change time') f.triggers[0].timestamp = '2030-01-01T00:00:00Z';
    if (damage === 'earlier' || damage === 'naive') {
      f.triggers[0].timestamp = damage === 'earlier' ? '2020-01-01T00:00:00Z' : '2030-01-01T00:00:00';
      result.graph.nodes.find(n => n.type === 'Decision')!.properties.decided_at = f.triggers[0].timestamp;
    }
    if (damage === 'decision citation') f.triggers[0].source_ids = ['doc:architecture-overview'];
    if (damage === 'unknown citation') f.source_ids = ['doc:invented'];
    if (damage === 'duplicate') f.triggers.push(f.triggers[0]);
    if (damage === 'reason') f.reason = 'Definitely wrong';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(result))));
    await expect(checkFreshness({ entity: 'Payment Service' })).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
});
