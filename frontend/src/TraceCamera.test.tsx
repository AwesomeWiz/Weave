import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import dagre from '@dagrejs/dagre';
import EvidenceGraph from './components/EvidenceGraph';
import { changeWithPlayback } from './test/tracePlaybackFixture';
import { preferredTrace } from './tracePresentation';
import { TraceClock } from './traceClock';

const mock = vi.hoisted(() => ({ fit: vi.fn(async () => true), setViewport: vi.fn(async () => true), getViewport: () => ({ x: 100, y: 50, zoom: 1 }),
  move: null as null | ((event: unknown) => void), zoom: null as null | (() => void) }));
vi.mock('@xyflow/react', async original => ({ ...await original<typeof import('@xyflow/react')>(),
  ReactFlow: ({ children, onMoveStart }: { children: import('react').ReactNode; onMoveStart: (event: unknown) => void }) => { mock.move = onMoveStart; return <div>{children}</div>; },
  Background: () => null, Controls: ({ onZoomIn }: { onZoomIn: () => void }) => { mock.zoom = onZoomIn; return null; }, MiniMap: () => null,
  useNodesInitialized: () => true, useReactFlow: () => ({ fitView: mock.fit, getViewport: mock.getViewport, setViewport: mock.setViewport }),
  useStore: (select: (s: { width: number; height: number }) => unknown) => select({ width: 800, height: 540 }),
}));
const result = changeWithPlayback(); const sequence = preferredTrace(result.data.trace_playback!.sequences)!;
const graph = { nodes: result.graph.nodes.filter(n => sequence.steps.some(s => s.source === n.id || s.target === n.id)),
  edges: result.graph.edges.filter(e => sequence.steps.some(s => s.edge_id === e.id)) };
const props = (clock: TraceClock, index = 0) => ({ graph, onSelect: vi.fn(), clock, trace: { sequence, index }, fitNodeIds: [sequence.steps[index].source, sequence.steps[index].target] });
async function frame() { await act(async () => { await vi.advanceTimersByTimeAsync(20); }); }
beforeEach(() => { vi.useFakeTimers(); mock.fit.mockClear(); mock.setViewport.mockClear(); });
afterEach(() => { cleanup(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe('cinematic camera without repeated graph layout', () => {
  it('frames the actual endpoints smoothly and does not recalculate positions on each step', async () => {
    const layout = vi.spyOn(dagre, 'layout'); const clock = new TraceClock();
    const app = render(<EvidenceGraph {...props(clock)} />); await frame();
    expect(mock.fit).toHaveBeenLastCalledWith(expect.objectContaining({ duration: 450, nodes: props(clock).fitNodeIds.map(id => ({ id })) }));
    app.rerender(<EvidenceGraph {...props(clock, 1)} />); await frame();
    expect(mock.fit).toHaveBeenLastCalledWith(expect.objectContaining({ nodes: props(clock, 1).fitNodeIds.map(id => ({ id })) }));
    expect(layout).toHaveBeenCalledTimes(1); clock.dispose();
  });
  it('respects a deliberate pan/zoom until an explicit recenter or replay', async () => {
    const clock = new TraceClock(); const app = render(<EvidenceGraph {...props(clock)} />); await frame();
    mock.move!({ type: 'wheel' }); app.rerender(<EvidenceGraph {...props(clock, 1)} />); await frame(); expect(mock.fit).toHaveBeenCalledTimes(1);
    act(() => clock.recenter()); await frame(); expect(mock.fit).toHaveBeenCalledTimes(2); clock.dispose();
  });
  it('does not treat programmatic viewport changes as user gestures', async () => {
    const clock = new TraceClock(); const app = render(<EvidenceGraph {...props(clock)} />); await frame();
    mock.move!(null); app.rerender(<EvidenceGraph {...props(clock, 1)} />); await frame(); expect(mock.fit).toHaveBeenCalledTimes(2); clock.dispose();
  });
  it('uses an instant camera and keeps exact endpoint framing for reduced motion', async () => {
    const clock = new TraceClock(); clock.setReduced(true); render(<EvidenceGraph {...props(clock)} />); await frame();
    expect(mock.fit).toHaveBeenLastCalledWith(expect.objectContaining({ duration: 0, nodes: props(clock).fitNodeIds.map(id => ({ id })) })); clock.dispose();
  });
  it('resets user camera ownership for a new sequence clock', async () => {
    const first = new TraceClock(), second = new TraceClock(); const app = render(<EvidenceGraph {...props(first)} />); await frame();
    mock.move!({ type: 'pointerdown' }); app.rerender(<EvidenceGraph {...props(second, 1)} />); await frame(); expect(mock.fit).toHaveBeenCalledTimes(2);
    first.dispose(); second.dispose();
  });
  it('does not apply a queued automatic frame after a user gesture begins', async () => {
    const clock = new TraceClock(); render(<EvidenceGraph {...props(clock)} />);
    mock.move!({ type: 'pointerdown' }); await frame(); expect(mock.fit).not.toHaveBeenCalled(); clock.dispose();
  });
  it('also respects deliberate zoom through the existing graph controls', async () => {
    const clock = new TraceClock(); const app = render(<EvidenceGraph {...props(clock)} />); await frame();
    mock.zoom!(); app.rerender(<EvidenceGraph {...props(clock, 1)} />); await frame(); expect(mock.fit).toHaveBeenCalledTimes(1); clock.dispose();
  });
  it('freezes an automatic camera on Pause and reframes on Resume', async () => {
    const clock = new TraceClock(); clock.setStep('one', () => {}); render(<EvidenceGraph {...props(clock)} />); await frame();
    act(() => clock.play()); await frame(); act(() => clock.pause()); await frame();
    expect(mock.setViewport).toHaveBeenLastCalledWith({ x: 100, y: 50, zoom: 1 }, { duration: 0 });
    const count = mock.fit.mock.calls.length; act(() => clock.play()); await frame(); expect(mock.fit).toHaveBeenCalledTimes(count + 1); clock.dispose();
  });
});
