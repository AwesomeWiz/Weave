import { describe, expect, it } from 'vitest';
import { validChangeData } from './changeValidation';
import { traceSequences, validTracePlayback } from './traceValidation';
import { changeWithPlayback } from './test/tracePlaybackFixture';
import { emptyWorkspace, restoreArchive } from './workspace';

const request = { target: 'Payment Service', change: 'Remove Redis from Payment Service' };
describe('backend-authored playback display boundary', () => {
  it('accepts the frozen actual-tool artifact and preserves all thirteen steps and edge identities', () => {
    const result = changeWithPlayback();
    expect(validChangeData(result.data, result, request)).toBe(true);
    expect(traceSequences(result)).toEqual(result.data.trace_playback!.sequences);
    expect(traceSequences(result).flatMap(s => s.steps)).toHaveLength(13);
    const impact = traceSequences(result).find(s => s.id === 'impact_analysis/service:order-service')!;
    expect(impact.steps.map(s => s.type)).toEqual(['USES', 'DEPENDS_ON', 'DEPENDS_ON']);
    expect(impact.steps[0].traversal_from).toBe('tech:redis');
    expect(impact.steps[0].source).toBe('service:payment-service');
  });
  it.each(['version', 'extra', 'order', 'unknown edge', 'unknown node', 'reversed', 'disconnected', 'traversal', 'number', 'tool', 'sibling',
    'proof order', 'citation', 'source reference', 'explanation', 'identity', 'duplicate', 'missing', 'empty', 'status', 'sequence id', 'excessive'])('rejects %s without repairing playback', damage => {
    const result = changeWithPlayback(); const playback = result.data.trace_playback!;
    const sequence = playback.sequences.find(s => s.path_id === 'decision_to_current_architecture')!;
    const step = sequence.steps[0];
    if (damage === 'version') playback.version = 2 as never;
    if (damage === 'extra') Object.assign(step, { approved: true });
    if (damage === 'order') sequence.steps.reverse();
    if (damage === 'unknown edge') step.edge_id = 'missing';
    if (damage === 'unknown node') step.source = 'decision:invented';
    if (damage === 'reversed') [step.source, step.target] = [step.target, step.source];
    if (damage === 'disconnected') sequence.steps[1].source = step.source;
    if (damage === 'traversal') step.traversal_from = step.target;
    if (damage === 'number') step.number = 2;
    if (damage === 'tool') step.tool = 'impact_analysis';
    if (damage === 'sibling') result.data.tool_support.decision_trace!.evidence.edge_ids = result.data.tool_support.decision_trace!.evidence.edge_ids.filter(id => id !== step.edge_id);
    if (damage === 'proof order') result.data.tool_support.decision_trace!.evidence.relationship_paths = result.data.tool_support.decision_trace!.evidence.relationship_paths.map(p => [...p].reverse());
    if (damage === 'citation') step.citation_ids = ['doc:ADR-7'];
    if (damage === 'source reference') step.evidence.source_ids = ['issue:PAY-42'];
    if (damage === 'explanation') step.explanation = 'This proves removing Redis is safe.';
    if (damage === 'identity') sequence.path_id = 'invented';
    if (damage === 'duplicate') playback.sequences.push(sequence);
    if (damage === 'missing') playback.sequences.pop();
    if (damage === 'empty') sequence.steps = [];
    if (damage === 'status') sequence.support_status = 'insufficient_evidence';
    if (damage === 'sequence id') step.sequence_id = 'other';
    if (damage === 'excessive') sequence.steps = Array(11).fill(step);
    expect(validTracePlayback(playback, result.data, result)).toBe(false);
    expect(validChangeData(result.data, result, request)).toBe(false);
    expect(traceSequences(result)).toEqual([]);
  });
  it('accepts absent or null playback on legacy responses without inferring sequences', () => {
    const result = changeWithPlayback(); delete result.data.trace_playback;
    expect(validChangeData(result.data, result, request)).toBe(true); expect(traceSequences(result)).toEqual([]);
    result.data.trace_playback = null;
    expect(validChangeData(result.data, result, request)).toBe(true);
    expect(traceSequences(null)).toEqual([]);
  });
});

function saved() {
  const archive = emptyWorkspace(); const chat = archive.conversations[0];
  chat.turns = [{ id: 'turn-1', question: request.change, createdAt: chat.createdAt, request: { change: request, impact: null, expert: null, freshness: null },
    result: changeWithPlayback(), status: 'complete', error: null }];
  chat.ui.selectedTurnId = 'turn-1'; chat.ui.trace = { sequenceId: 'decision_trace/decision_to_current_architecture', step: 1 };
  return archive;
}
describe('minimal trace persistence', () => {
  it('restores only a validated sequence and index, never a running flag or timer', () => {
    const archive = saved(); const restored = restoreArchive(JSON.parse(JSON.stringify(archive)));
    expect(restored).toEqual(archive);
    expect(Object.keys(restored.conversations[0].ui.trace!)).toEqual(['sequenceId', 'step']);
  });
  it.each(['missing', 'index', 'negative', 'fraction', 'corrupt', 'removed path', 'legacy'])('safely clears %s UI selection without altering saved evidence', damage => {
    const archive = saved(); const chat = archive.conversations[0];
    if (damage === 'missing') chat.ui.trace!.sequenceId = 'missing';
    if (damage === 'index') chat.ui.trace!.step = 100;
    if (damage === 'negative') chat.ui.trace!.step = -1;
    if (damage === 'fraction') chat.ui.trace!.step = 0.5;
    if (damage === 'corrupt') chat.ui.trace = 'broken' as never;
    if (damage === 'removed path') delete (chat.turns[0].result as ReturnType<typeof changeWithPlayback>).data.trace_playback;
    if (damage === 'legacy') delete chat.ui.trace;
    const evidence = structuredClone(chat.turns[0].result);
    const restored = restoreArchive(archive);
    expect(restored.conversations[0].ui.trace).toBeNull();
    expect(restored.conversations[0].turns[0].result).toEqual(evidence);
  });
  it('still rejects mutated saved path evidence rather than rewriting it', () => {
    const archive = saved(); (archive.conversations[0].turns[0].result as ReturnType<typeof changeWithPlayback>).data.trace_playback!.sequences[0].steps[0].edge_id = 'missing';
    expect(() => restoreArchive(archive)).toThrow(/incompatible/);
  });
  it('discards an injected running flag while retaining only validated UI selection', () => {
    const archive = saved(); Object.assign(archive.conversations[0].ui.trace!, { playing: true, timer: 42 });
    expect(restoreArchive(archive).conversations[0].ui.trace).toEqual({ sequenceId: 'decision_trace/decision_to_current_architecture', step: 1 });
  });
});
