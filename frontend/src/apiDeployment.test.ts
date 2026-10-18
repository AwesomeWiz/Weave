import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

it('uses the configured HTTPS backend for query, change and detailed health without a dev proxy', async () => {
  vi.stubEnv('VITE_API_URL', 'https://weave-api.example.org/');
  vi.resetModules();
  const { askQuestion, analyzeChange, getHealth } = await import('./api');
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({
    ok: false, error: { code: 'GRAPH_UNAVAILABLE', message: 'Graph unavailable' },
  }), { status: 503 })));
  vi.stubGlobal('fetch', fetch);
  await expect(askQuestion('Why does Payment Service use Redis?')).rejects.toMatchObject({ code: 'GRAPH_UNAVAILABLE' });
  const proposal = { target: 'Payment Service', change: 'Remove Redis from Payment Service' };
  await expect(analyzeChange(proposal)).rejects.toMatchObject({ code: 'GRAPH_UNAVAILABLE' });
  fetch.mockResolvedValueOnce(new Response(JSON.stringify({
    status: 'unavailable', backend: 'available', graph_mode: 'falkordb', graph: 'novapay',
    falkordb: 'unavailable', graph_tool: 'unavailable', llm: 'disabled',
  }), { status: 503 }));
  expect((await getHealth()).falkordb).toBe('unavailable');
  expect(fetch.mock.calls.map(call => call[0])).toEqual([
    'https://weave-api.example.org/api/query',
    'https://weave-api.example.org/api/change-intelligence',
    'https://weave-api.example.org/api/health',
  ]);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual(proposal);
});
