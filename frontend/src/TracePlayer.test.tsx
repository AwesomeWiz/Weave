import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TracePlayer from './components/TracePlayer';
import { changeWithPlayback } from './test/tracePlaybackFixture';

const result = changeWithPlayback();
const sequences = result.data.trace_playback!.sequences;
const architecture = sequences.find(s => s.path_id === 'decision_to_current_architecture')!;
const onChange = vi.fn(), onNode = vi.fn(), onSource = vi.fn();
function Harness({ initial = architecture.id }: { initial?: string }) {
  const [selection, setSelection] = useState({ sequenceId: initial, step: 0 });
  return <TracePlayer sequences={sequences} selection={selection} onChange={(s, step) => { onChange(s.id, step); setSelection({ sequenceId: s.id, step }); }}
    onClose={() => {}} nodes={result.graph.nodes} sources={result.sources} onNode={onNode} onSource={onSource} />;
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const advance = (ms = 2200) => act(() => { vi.advanceTimersByTime(ms); });
beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('local deterministic Trace Mode controls', () => {
  it('starts paused, plays one step at a time, pauses and resumes through completion', () => {
    render(<Harness />); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    click('Play'); advance(); expect(screen.getByText('Step 2 of 3 · Playing')).toBeInTheDocument();
    expect(screen.getByText(architecture.steps[1].explanation)).toBeInTheDocument();
    click('Pause'); advance(9000); expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
    click('Play'); advance(); expect(screen.getByText('Step 3 of 3 · Paused')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled();
    expect(screen.getByRole('progressbar', { name: 'Trace progress' })).toHaveAttribute('value', '3');
  });
  it('supports next, previous and replay, with manual actions pausing the timer', () => {
    render(<Harness />); expect(screen.getByRole('button', { name: 'Previous step' })).toBeDisabled();
    click('Next step'); expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
    click('Play'); click('Previous step'); advance(7000); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    click('Next step'); click('Next step'); click('Replay');
    expect(screen.getByText('Step 1 of 3 · Playing')).toBeInTheDocument(); advance(); expect(screen.getByText('Step 2 of 3 · Playing')).toBeInTheDocument();
  });
  it('switches to an Impact sequence, cancels the old timer and retains stored direction', () => {
    render(<Harness />); click('Play');
    fireEvent.change(screen.getByLabelText('Trace sequence'), { target: { value: 'impact_analysis/service:order-service' } });
    advance(9000); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    expect(screen.getByText(/Traversal proceeds from dependency to dependent/)).toBeInTheDocument();
    click('Next step'); expect(onChange).toHaveBeenLastCalledWith('impact_analysis/service:order-service', 1);
  });
  it('syncs the existing entity Inspector and labels steps without textual citations', () => {
    render(<Harness />); click('Play'); click('Inspect target entity');
    expect(onNode).toHaveBeenLastCalledWith(result.graph.nodes.find(n => n.id === 'commit:8fae2'));
    expect(screen.getByText(/Graph-only step; no textual citation assigned/)).toBeInTheDocument();
    advance(9000); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument(); expect(onSource).not.toHaveBeenCalled();
  });
  it('cleans up timers on unmount and starts paused on remount', () => {
    const app = render(<Harness />); click('Play'); const before = onChange.mock.calls.length;
    app.unmount(); advance(9000); expect(onChange).toHaveBeenCalledTimes(before);
    render(<Harness />); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
  });
  it('pauses when the document is hidden', () => {
    render(<Harness />); click('Play');
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden'); fireEvent(document, new Event('visibilitychange'));
    advance(9000); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
  });
  it('honors reduced motion without autoplay and keeps keyboard controls functional', async () => {
    vi.useRealTimers();
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    const user = userEvent.setup(); render(<Harness />);
    expect(screen.getByText(/Reduced motion enabled/)).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Next step' }).focus(); await user.keyboard('{Enter}');
    expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Play' }).focus(); await user.keyboard(' ');
    expect(screen.getByText('Step 2 of 3 · Playing')).toBeInTheDocument();
    await user.keyboard(' '); expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
  });
  it('supports single-step paths without scheduling an advance', () => {
    render(<Harness initial={sequences[0].id} />); expect(screen.getByText('Step 1 of 1 · Paused')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled(); click('Replay'); advance(9000);
    expect(screen.getByText('Step 1 of 1 · Paused')).toBeInTheDocument();
  });
  it('does not play missing selections or construct paths for legacy responses', () => {
    render(<TracePlayer sequences={[]} selection={{ sequenceId: 'missing', step: 8 }} onChange={onChange} onClose={() => {}}
      nodes={[]} sources={[]} onNode={onNode} onSource={onSource} />);
    expect(screen.getByText(/No selected validated path/)).toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Play' })).not.toBeInTheDocument();
  });
});
