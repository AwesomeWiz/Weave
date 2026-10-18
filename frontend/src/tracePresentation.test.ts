import { describe, expect, it } from 'vitest';
import { preferredTrace, traceEntityName, traceSentence, traceTitle } from './tracePresentation';
import { changeWithPlayback } from './test/tracePlaybackFixture';

const response = changeWithPlayback(), nodes = response.graph.nodes, sequences = response.data.trace_playback!.sequences;
const architecture = preferredTrace(sequences)!;
describe('friendly presentation of unchanged validated evidence', () => {
  it('prefers the real architecture path and falls back only to an existing sequence', () => {
    expect(architecture.path_id).toBe('decision_to_current_architecture');
    expect(preferredTrace(sequences.filter(s => s !== architecture))).toBe(sequences[0]); expect(preferredTrace([])).toBeUndefined();
  });
  it('uses actual returned names and generic entity formatting', () => {
    const payment = nodes.find(n => n.id === 'service:payment-service')!;
    expect(traceEntityName(payment, payment.id)).toBe('Payment Service');
    const renamed = { ...payment, label: 'Different', properties: { name: 'A separate example service' } };
    expect(traceEntityName(renamed, renamed.id)).toBe('A separate example service');
    expect(traceEntityName(nodes.find(n => n.id === 'decision:D-007'), 'decision:D-007')).toBe('Decision D-007');
    expect(traceEntityName(nodes.find(n => n.id === 'commit:8fae2'), 'commit:8fae2')).toBe('Commit 8fae2');
  });
  it('explains the three exact architecture edges without changing their objects', () => {
    const original = structuredClone(architecture);
    expect(architecture.steps.map(s => traceSentence(s, nodes))).toEqual([
      'Decision D-007 was implemented through Commit 8fae2.', 'Commit 8fae2 changed Payment Service.', 'Payment Service uses Redis.',
    ]);
    expect(architecture).toEqual(original);
  });
  it('uses stored direction for a reverse Impact step and labels the whole genuine dependency path', () => {
    const order = sequences.find(s => s.id === 'impact_analysis/service:order-service')!;
    expect(traceTitle(order, nodes)).toBe('How Order Service depends on Redis');
    expect(traceSentence(order.steps[1], nodes)).toBe('Checkout Service depends on Payment Service.');
    expect(order.steps[1].traversal_from).toBe('service:payment-service');
  });
  it('falls back neutrally for an unknown relationship instead of inventing its meaning', () => {
    const step = { ...architecture.steps[0], type: 'NEW_UNDOCUMENTED_LINK' };
    expect(traceSentence(step, nodes)).toBe('Decision D-007 is linked to Commit 8fae2 by “NEW_UNDOCUMENTED_LINK”.');
  });
  it('keeps separate histories separate and does not translate path IDs into invented chronology', () => {
    expect(traceTitle(sequences[0], nodes)).toBe('From Payment requests timing out during peak traffic to Reduce payment latency under burst traffic');
    expect(traceTitle(architecture, nodes)).toBe('From Decision D-007 to Redis');
    expect(sequences.filter(s => s.tool === 'decision_trace')).toHaveLength(5);
  });
});
