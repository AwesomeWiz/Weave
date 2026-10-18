import { changeFixture } from './changeFixture';
import type { ChangeResponse } from '../types';

export function changeWithoutSources(): ChangeResponse {
  const result = structuredClone(changeFixture);
  result.sources = [];
  const clear = (v: unknown) => {
    if (!v || typeof v !== 'object') return;
    if (Array.isArray(v)) { v.forEach(clear); return; }
    for (const [key, value] of Object.entries(v)) {
      if (key === 'source_ids') (v as Record<string, unknown>)[key] = [];
      else clear(value);
    }
  };
  clear(result.data);
  result.data.historical_context.summary = 'The retrieved rationale is incomplete because matching source provenance is missing.';
  result.data.historical_context.support_status = 'insufficient_evidence';
  result.data.tool_support.decision_trace!.support_status = 'insufficient_evidence';
  result.data.tool_support.find_expert!.support_status = 'partially_supported';
  result.data.tool_support.find_stale_knowledge!.support_status = 'partially_supported';
  result.data.risks = result.data.risks.filter(r => r.classification !== 'INFERRED_RISK');
  result.data.limitations.push('Matching textual provenance was not retrieved; graph-only findings remain qualified.');
  result.answer = 'Graph-only findings remain qualified; matching textual provenance is missing.';
  return result;
}

export function unresolvedChange(change: string, resolution: 'unsupported' | 'unresolved' | 'ambiguous' = 'unsupported'): ChangeResponse {
  const result = structuredClone(changeFixture);
  const message = resolution === 'ambiguous' ? 'Specify one unambiguous service and technology.' : 'This proposed change is outside the validated Redis-removal scenario.';
  result.support_status = 'insufficient_evidence'; result.sources = []; result.graph = { nodes: [], edges: [] }; result.tools_used = [];
  result.answer = message;
  result.data = { proposed_change: { requested_target: 'Payment Service', requested_change: change, intent: 'unsupported', resolution,
    service: null, technology: null, limitation: message }, historical_context: { support_status: 'insufficient_evidence', summary: 'No validated historical rationale was retrieved.', decision_ids: [], evidence: null },
  impact: { entity: null, direct_impact: [], indirect_impact: [], related_issues: [], related_incidents: [], support_status: 'insufficient_evidence', max_depth: 3 },
  reviewers: [], risks: [], validation_steps: [], current_freshness_findings: [], documents_to_review_if_change_proceeds: [], tool_support: {}, limitations: [message] };
  result.metadata.warnings = [message];
  return result;
}
