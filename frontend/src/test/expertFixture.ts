import type { ExpertEvidence, ExpertResponse } from '../types';

// Explicit offline component-test data; never used by application retrieval.
const node = (id: string, type: string, label: string, properties: Record<string, unknown> = {}) =>
  ({ id, type, label, properties: { id, name: label, ...properties } });
const person = node('person:alice', 'Person', 'Alice Menon', { role: 'Tech Lead' });
const service = node('service:payment-service', 'Service', 'Payment Service');
const team = node('team:payments', 'Team', 'Payments Team');
const decision = node('decision:D-007', 'Decision', 'Introduce Redis caching');
const issue = node('issue:PAY-42', 'Issue', 'Reduce payment latency');
const chunk = node('chunk:issue:PAY-42:0', 'Chunk', 'Test-only excerpt');
const path = (source: string, type: string, target: string) => ({ source, type, target });
const approval: ExpertEvidence = { category: 'decision_approval', entity_id: decision.id, entity_type: 'Decision',
  path: [path(person.id, 'APPROVED', decision.id)], source_ids: [issue.id] };
const ownership: ExpertEvidence = { category: 'team_ownership', entity_id: service.id, entity_type: 'Service',
  path: [path(person.id, 'MEMBER_OF', team.id), path(team.id, 'OWNS', service.id)], source_ids: [] };
export const expertFixture: ExpertResponse = {
  answer: 'Test-only expert ranking [issue:PAY-42].', tools_used: ['find_expert'], support_status: 'supported',
  sources: [{ id: issue.id, type: 'Issue', title: issue.label, snippet: 'Test-only retrieved rationale excerpt.',
    url: null, timestamp: '2026-05-11T10:00:00Z', entity_ids: [issue.id],
    metadata: { source_id: issue.id, source_type: 'Issue', chunk_ids: [chunk.id] } }],
  graph: { nodes: [service, person, team, decision, issue, chunk], edges: [...approval.path, ...ownership.path,
    path(decision.id, 'AFFECTS', service.id), path(decision.id, 'SUPPORTED_BY', issue.id), path(chunk.id, 'FROM_ISSUE', issue.id),
  ].map(e => ({ ...e, id: `${e.source}|${e.type}|${e.target}`, properties: {} })) },
  metadata: { latency_ms: 1, generation: 'deterministic', graph_mode: 'fixture', warnings: [] },
  data: { query: 'Who knows Payment Service?', topics: [service],
    scoring: { team_ownership: 4, decision_approval: 5, decision_participation: 3, commit_authorship: 4, issue_assignment: 3, discussion_contribution: 2 },
    experts: [{ person: { id: person.id, name: person.label, role: 'Tech Lead' }, score: 9,
      evidence: [approval, ownership], ownership: [ownership], historical_contributions: [approval],
      ranking_reasons: ['decision approval: decision:D-007', 'team ownership: service:payment-service'],
      ownership_classification: 'team_membership_with_team_owned_service' }],
  },
};
