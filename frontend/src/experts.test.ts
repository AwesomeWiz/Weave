import { afterEach, describe, expect, it, vi } from 'vitest';
import { findExperts } from './api';
import { routeExpertQuestion } from './experts';
import { expertFixture } from './test/expertFixture';

afterEach(() => vi.unstubAllGlobals());
describe('Expert Finder contracts', () => {
  it('uses the query-based endpoint with canonical rankings and citations', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(expertFixture)));
    vi.stubGlobal('fetch', fetch);
    expect(await findExperts({ query: expertFixture.data.query, limit: 5 })).toEqual(expertFixture);
    expect(fetch.mock.calls[0][0]).toBe('/api/tools/expert-finder');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ query: expertFixture.data.query, limit: 5 });
  });
  it.each(['person', 'duplicate', 'direction', 'citation', 'owner', 'topic', 'score', 'query'])('rejects invalid %s before rendering', async damage => {
    const body = structuredClone(expertFixture);
    const expert = body.data.experts[0];
    if (damage === 'person') expert.person.id = 'person:invented';
    if (damage === 'duplicate') body.data.experts.push(expert);
    if (damage === 'direction') expert.evidence[0].path[0].source = 'service:payment-service';
    if (damage === 'citation') expert.evidence[0].source_ids = ['doc:invented'];
    if (damage === 'owner') Object.assign(expert, { ownership_classification: 'current_owner' });
    if (damage === 'topic') body.data.topics.push(body.graph.nodes[3]);
    if (damage === 'score') expert.score = -1;
    if (damage === 'query') body.data.query = 'Different topic';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(findExperts({ query: expertFixture.data.query, limit: 5 })).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it.each(['Who knows Payment Service?', 'Who approved D-007?', 'Who can explain the Redis decision?', 'Who worked on Payment Service?'])('routes a single expert question: %s', query => {
    expect(routeExpertQuestion(query)).toEqual({ query, limit: 5 });
  });
  it('keeps three-tool and other combined questions on the backend planner', () => {
    expect(routeExpertQuestion('Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?')).toBeNull();
    expect(routeExpertQuestion('Who knows Redis? What depends on Redis?')).toBeNull();
  });
});
