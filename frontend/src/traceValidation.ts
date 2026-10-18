import type { ChangeBriefData, QueryResponse, TracePlaybackData, TraceSequence } from './types';

const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const keys = (v: Record<string, unknown>, expected: string[]) => Object.keys(v).length === expected.length && expected.every(k => k in v);
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** Verify server steps against the original inventories; never author replacement steps. */
export function validTracePlayback(value: unknown, data: ChangeBriefData, response: QueryResponse): value is TracePlaybackData | null | undefined {
  if (value === undefined || value === null) return true; // Legacy responses remain readable.
  if (!record(value) || !keys(value, ['version', 'sequences']) || value.version !== 1 || !Array.isArray(value.sequences)
    || value.sequences.length > 140) return false;
  const inventory = [
    ...(data.historical_context.relationship_paths ?? []).map(p => ({ tool: 'decision_trace' as const, id: p.id,
      steps: p.steps, traversal: [p.steps[0].source, ...p.steps.map(s => s.target)], status: data.historical_context.support_status })),
    ...[...data.impact.direct_impact, ...data.impact.indirect_impact].map(f => ({ tool: 'impact_analysis' as const, id: f.service_id,
      steps: f.path_edges, traversal: f.path, status: data.impact.support_status })),
  ];
  if (value.sequences.length !== inventory.length) return false;
  const ids = new Set<string>();
  const edges = new Map(response.graph.edges.map(e => [e.id, e]));
  return value.sequences.every((sequence, index) => {
    const original = inventory[index];
    const local = data.tool_support[original.tool];
    if (!record(sequence) || !keys(sequence, ['id', 'path_id', 'tool', 'support_status', 'steps'])
      || sequence.id !== `${original.tool}/${original.id}` || sequence.path_id !== original.id || sequence.tool !== original.tool
      || typeof sequence.id !== 'string' || sequence.id.length > 160 || ids.has(sequence.id)
      || sequence.support_status !== original.status || local?.state !== 'validated' || local.support_status !== original.status
      || !Array.isArray(sequence.steps) || !sequence.steps.length || sequence.steps.length > 10
      || sequence.steps.length !== original.steps.length
      || original.tool === 'impact_analysis' && new Set(original.traversal).size !== original.traversal.length) return false;
    ids.add(sequence.id);
    const proof = local.evidence.relationship_paths.some(p => same(p, (sequence.steps as Record<string, unknown>[]).map(s => s?.edge_id)));
    if (!proof) return false;
    return sequence.steps.every((step, i) => {
      const raw = original.steps[i];
      if (!record(step) || !keys(step, ['number', 'sequence_id', 'source', 'type', 'target', 'edge_id', 'tool', 'traversal_from', 'traversal_to', 'evidence', 'explanation', 'citation_ids'])
        || step.number !== i + 1 || step.sequence_id !== sequence.id || step.tool !== original.tool
        || step.source !== raw.source || step.type !== raw.type || step.target !== raw.target
        || step.traversal_from !== original.traversal[i] || step.traversal_to !== original.traversal[i + 1]
        || typeof step.edge_id !== 'string' || !local.evidence.edge_ids.includes(step.edge_id)
        || !local.evidence.node_ids.includes(raw.source) || !local.evidence.node_ids.includes(raw.target)
        || !response.graph.nodes.some(n => n.id === raw.source) || !response.graph.nodes.some(n => n.id === raw.target)) return false;
      const edge = edges.get(step.edge_id);
      const ref = step.evidence;
      const explanation = `Stored relationship: ${raw.source} —${raw.type}→ ${raw.target}.`
        + (original.tool === 'impact_analysis' ? ' Traversal proceeds from dependency to dependent; this does not establish failure propagation.' : '');
      return edge?.source === raw.source && edge.type === raw.type && edge.target === raw.target
        && (original.tool === 'decision_trace' ? raw.source === step.traversal_from && raw.target === step.traversal_to
          : raw.source === step.traversal_to && raw.target === step.traversal_from && raw.type === (i === 0 ? 'USES' : 'DEPENDS_ON'))
        && step.explanation === explanation && explanation.length <= 2000 && same(step.citation_ids, [])
        && record(ref) && keys(ref, ['tool', 'node_ids', 'edge_ids', 'source_ids', 'relationship_paths']) && ref.tool === original.tool
        && same(ref.node_ids, [...new Set([raw.source, raw.target])]) && same(ref.edge_ids, [step.edge_id])
        && same(ref.source_ids, []) && same(ref.relationship_paths, [[step.edge_id]])
        && (original.tool !== 'decision_trace' || !!data.historical_context.evidence?.relationship_paths.some(p => same(p, (sequence.steps as Record<string, unknown>[]).map(s => s?.edge_id))));
    });
  });
}

export function traceSequences(response: QueryResponse | null): TraceSequence[] {
  if (!response || !('data' in response) || !record(response.data) || !('proposed_change' in response.data)) return [];
  const data = response.data as unknown as ChangeBriefData;
  try { return validTracePlayback(data.trace_playback, data, response) ? data.trace_playback?.sequences ?? [] : []; }
  catch { return []; } // An invalid restored inventory never triggers reconstruction.
}
