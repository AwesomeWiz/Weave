import type { ChangeEvidenceReference, ChangeInput, ChangeResponse, EvidenceGraph, QueryResponse } from './types';

export const CHANGE_QUESTION = 'What happens if we remove Redis from Payment Service?';
export const CHANGE_TOOL_LABELS = {
  decision_trace: 'Historical rationale', impact_analysis: 'Potential impact',
  find_expert: 'Reviewer evidence', find_stale_knowledge: 'Current freshness',
} as const;

/** Endpoint selection mirrors the backend's explicit proposal prefixes. */
export function routeChangeQuestion(question: string): ChangeInput | null {
  if (!/^\s*(?:what (?:happens|would happen) if\b|if we (?:remove|replace)\b|(?:please |can we |should we )?(?:remove|replace|migrate|deprecate|switch from|move away from|upgrade)\b)/i.test(question)) return null;
  const removal = question.trim().match(/^(?:(?:what (?:happens|would happen) if|if) we |(?:please |can we |should we )?)remove (.+?) from (.+?)\s*[?.!]?$/i);
  // This is an explicit missing-target label, never a guessed canonical entity.
  const target = removal?.[2]?.replace(/[?.!\s]+$/, '')
    ?? question.match(/\b(?:in|for|from)\s+(.+?Service)\s*[?.!]?$/i)?.[1] ?? 'Unspecified service';
  return { target, change: question.trim() };
}

export function isChangeResponse(result: QueryResponse): result is ChangeResponse {
  return 'data' in result && typeof result.data === 'object' && result.data !== null && 'proposed_change' in result.data;
}

/** A subset of returned evidence, not a reconstructed historical path. */
export function changeGraphFocus(result: ChangeResponse): { graph: EvidenceGraph; primaryNodeIds: string[]; primaryEdgeIds: string[] } {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();
  const primaryNodeIds = new Set<string>();
  const primaryEdgeIds = new Set<string>();
  const add = (ref: ChangeEvidenceReference) => { ref.node_ids.forEach(id => nodeIds.add(id)); ref.edge_ids.forEach(id => edgeIds.add(id)); };
  const data = result.data;
  if (data.historical_context.evidence) add(data.historical_context.evidence);
  for (const finding of [...data.impact.direct_impact, ...data.impact.indirect_impact]) {
    finding.path.forEach(id => { nodeIds.add(id); primaryNodeIds.add(id); });
    for (const step of finding.path_edges) {
      result.graph.edges.filter(e => e.source === step.source && e.type === step.type && e.target === step.target)
        .forEach(e => { edgeIds.add(e.id); primaryEdgeIds.add(e.id); });
    }
  }
  for (const node of [data.proposed_change.service, data.proposed_change.technology]) {
    if (node) { nodeIds.add(node.id); primaryNodeIds.add(node.id); }
  }
  data.reviewers.forEach(person => { nodeIds.add(person.person.id); person.evidence.forEach(proof => {
    nodeIds.add(proof.entity_id);
    proof.path.forEach(step => {
      nodeIds.add(step.source); nodeIds.add(step.target);
      result.graph.edges.filter(e => e.source === step.source && e.type === step.type && e.target === step.target).forEach(e => edgeIds.add(e.id));
    });
  }); });
  data.documents_to_review_if_change_proceeds.forEach(doc => { nodeIds.add(doc.document.id); doc.evidence.forEach(add); });
  data.current_freshness_findings.forEach(f => {
    nodeIds.add(f.document_id);
    [...f.document_path, ...f.triggers.flatMap(t => t.path)].forEach(step => {
      nodeIds.add(step.source); nodeIds.add(step.target);
      result.graph.edges.filter(e => e.source === step.source && e.type === step.type && e.target === step.target).forEach(e => edgeIds.add(e.id));
    });
  });
  const nodes = result.graph.nodes.filter(n => nodeIds.has(n.id) && n.type !== 'Chunk');
  const visible = new Set(nodes.map(n => n.id));
  return { graph: { nodes, edges: result.graph.edges.filter(e => edgeIds.has(e.id) && visible.has(e.source) && visible.has(e.target)) },
    primaryNodeIds: [...primaryNodeIds], primaryEdgeIds: [...primaryEdgeIds] };
}
