import type { FreshnessResponse } from '../types';

// Explicit component-test data. Never used by application retrieval.
const service = { id: 'service:payment-service', type: 'Service', label: 'Payment Service', properties: { id: 'service:payment-service', name: 'Payment Service' } };
const document = { id: 'doc:architecture-overview', type: 'Document', label: 'Architecture Overview', properties: { id: 'doc:architecture-overview', title: 'Architecture Overview', updated_at: '2026-05-01T00:00:00Z' } };
const decision = { id: 'decision:D-007', type: 'Decision', label: 'Introduce Redis caching', properties: { id: 'decision:D-007', title: 'Introduce Redis caching', status: 'accepted', decided_at: '2026-05-18T00:00:00Z' } };
const commit = { id: 'commit:8fae2', type: 'Commit', label: 'Add Redis cache', properties: { id: 'commit:8fae2', title: 'Add Redis cache', architecture_change: true, timestamp: '2026-05-19T00:00:00Z' } };
const path = (source: string, type: string, target: string) => ({ source, type, target });
const association = path(document.id, 'DESCRIBES', service.id);
const changes = [path(decision.id, 'AFFECTS', service.id), path(commit.id, 'CHANGES', service.id)];
export const freshnessFixture: FreshnessResponse = {
  answer: 'Test-only review recommendation [doc:architecture-overview] [commit:8fae2].',
  support_status: 'supported', tools_used: ['find_stale_knowledge'],
  graph: { nodes: [service, document, decision, commit], edges: [association, ...changes].map(e => ({ ...e, id: `${e.source}|${e.type}|${e.target}`, properties: {} })) },
  sources: [document, commit].map(n => ({ id: n.id, type: n.type, title: n.label, snippet: 'Test-only retrieved excerpt.',
    url: null, timestamp: null, entity_ids: [n.id], metadata: { synthetic: true } })),
  metadata: { latency_ms: 1, graph_mode: 'fixture', generation: 'deterministic', warnings: [] },
  data: { entity: service, review_candidates: [{ document, document_id: document.id,
    updated_at: document.properties.updated_at, affected_entity_id: service.id, document_path: [association],
    reason: 'Later graph-linked changes affect the same service; review may be warranted.', source_ids: [document.id],
    triggers: [{ type: 'decision', id: decision.id, timestamp: decision.properties.decided_at,
      affected_entity_id: service.id, path: [changes[0]], source_ids: [] },
    { type: 'commit', id: commit.id, timestamp: commit.properties.timestamp,
      affected_entity_id: service.id, path: [changes[1]], source_ids: [commit.id] }],
  }] },
};
