import { shortId } from './format';
import type { GraphNode, TraceSequence, TraceStep } from './types';

/** Display text only. The server steps and evidence objects are never rewritten. */
export function traceEntityName(node: GraphNode | undefined, id: string): string {
  if (!node) return shortId(id);
  if (['Decision', 'Commit'].includes(node.type)) return `${node.type} ${shortId(node.id)}`;
  let label = typeof node.properties.name === 'string' && node.properties.name.trim() ? node.properties.name : node.label;
  if (!label || label === node.id) label = shortId(node.id);
  return label;
}

const verbs: Record<string, string> = {
  USES: 'uses', DEPENDS_ON: 'depends on', IMPLEMENTED_BY: 'was implemented through', CHANGES: 'changed',
  SUPPORTED_BY: 'is supported by', DOCUMENTED_IN: 'is documented in', INTRODUCES: 'introduced',
  LED_TO: 'led to', AFFECTS: 'affects', APPROVED: 'approved', DECIDED_BY: 'was decided by',
};
export const traceRelationshipLabel = (type: string) => type.replaceAll('_', ' ').toLowerCase();

export function traceSentence(step: TraceStep, nodes: GraphNode[]): string {
  const source = traceEntityName(nodes.find(n => n.id === step.source), step.source);
  const target = traceEntityName(nodes.find(n => n.id === step.target), step.target);
  return verbs[step.type] ? `${source} ${verbs[step.type]} ${target}.` : `${source} is linked to ${target} by “${step.type}”.`;
}

export function traceTitle(sequence: TraceSequence, nodes: GraphNode[]): string {
  const first = sequence.steps[0], last = sequence.steps.at(-1)!;
  const name = (id: string) => traceEntityName(nodes.find(n => n.id === id), id);
  if (sequence.tool === 'impact_analysis') return `How ${name(last.traversal_to)} ${sequence.steps.length === 1 && first.type === 'USES' ? 'uses' : 'depends on'} ${name(first.traversal_from)}`;
  return `From ${name(first.traversal_from)} to ${name(last.traversal_to)}`;
}

export function preferredTrace(sequences: TraceSequence[]): TraceSequence | undefined {
  return sequences.find(s => s.tool === 'decision_trace' && s.path_id === 'decision_to_current_architecture') ?? sequences[0];
}
