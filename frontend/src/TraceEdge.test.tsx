import { act, cleanup, render } from '@testing-library/react';
import { ReactFlowProvider, Position } from '@xyflow/react';
import type { ComponentProps } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TraceEdge, TraceDetourEdge } from './components/TraceEdge';
import { TraceClock } from './traceClock';

const originalLength = Object.getOwnPropertyDescriptor(SVGElement.prototype, 'getTotalLength');
const originalPoint = Object.getOwnPropertyDescriptor(SVGElement.prototype, 'getPointAtLength');
const originalBox = Object.getOwnPropertyDescriptor(SVGElement.prototype, 'getBBox');
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(SVGElement.prototype, 'getTotalLength', { configurable: true, value: () => 100 });
  Object.defineProperty(SVGElement.prototype, 'getPointAtLength', { configurable: true, value: (length: number) => ({ x: length, y: length / 2 }) });
  Object.defineProperty(SVGElement.prototype, 'getBBox', { configurable: true, value: () => ({ x: 0, y: 0, width: 40, height: 12 }) });
});
afterEach(() => {
  cleanup(); vi.clearAllTimers(); vi.useRealTimers();
  if (originalLength) Object.defineProperty(SVGElement.prototype, 'getTotalLength', originalLength); else Reflect.deleteProperty(SVGElement.prototype, 'getTotalLength');
  if (originalPoint) Object.defineProperty(SVGElement.prototype, 'getPointAtLength', originalPoint); else Reflect.deleteProperty(SVGElement.prototype, 'getPointAtLength');
  if (originalBox) Object.defineProperty(SVGElement.prototype, 'getBBox', originalBox); else Reflect.deleteProperty(SVGElement.prototype, 'getBBox');
});
function draw(reverse = false, detour = false, reduced = false, active = true) {
  const clock = new TraceClock(); clock.setStep('one', () => clock.pause()); clock.setReduced(reduced);
  const props: ComponentProps<typeof TraceEdge> = { id: 'actual-stored-edge', source: 'stored-source', target: 'stored-target',
    sourceX: 0, sourceY: 0, targetX: 100, targetY: 50, sourcePosition: Position.Right, targetPosition: Position.Left,
    selected: false, animated: false, selectable: false, deletable: false, label: 'uses', markerEnd: 'url(#stored-arrow)',
    data: { clock, active, reverse } };
  const Component = detour ? TraceDetourEdge : TraceEdge;
  const app = render(<ReactFlowProvider><svg><Component {...props} /></svg></ReactFlowProvider>);
  return { ...app, clock, dot: () => app.container.querySelector('circle')! };
}

describe('motion on actual React Flow edge geometry', () => {
  it.each([false, true])('uses the exact base curve for illumination and motion (detour=%s)', detour => {
    const app = draw(false, detour); const base = app.container.querySelector('.react-flow__edge-path')!;
    const overlay = app.container.querySelector('.trace-edge-light')!;
    expect(overlay.getAttribute('d')).toBe(base.getAttribute('d')); expect(base).toHaveAttribute('id', 'actual-stored-edge');
    expect(base).toHaveAttribute('marker-end', 'url(#stored-arrow)');
    act(() => { app.clock.play(); vi.advanceTimersByTime(1100); });
    expect(Number(app.dot().getAttribute('cx'))).toBeCloseTo(Number(app.dot().getAttribute('data-progress')) * 100, 2);
    expect(Number(app.dot().getAttribute('data-progress'))).toBeCloseTo(0.5, 1);
    app.clock.dispose();
  });
  it('pauses exactly at the current point, resumes from it and resets on manual navigation', () => {
    const app = draw(); act(() => { app.clock.play(); vi.advanceTimersByTime(550); app.clock.pause(); });
    const paused = app.dot().outerHTML;
    act(() => vi.advanceTimersByTime(5000)); expect(app.dot().outerHTML).toBe(paused);
    act(() => { app.clock.play(); vi.advanceTimersByTime(550); }); expect(Number(app.dot().getAttribute('cx'))).toBeCloseTo(50, 0);
    act(() => app.clock.rewind()); expect(app.dot()).toHaveAttribute('cx', '0'); app.clock.dispose();
  });
  it('reverses only the traveling marker for Impact, preserving the stored path and arrow', () => {
    const app = draw(true); expect(app.dot()).toHaveAttribute('cx', '100');
    act(() => { app.clock.play(); vi.advanceTimersByTime(550); app.clock.pause(); });
    expect(Number(app.dot().getAttribute('cx'))).toBeCloseTo(75, 0);
    expect(app.container.querySelector('.trace-edge-motion')).toHaveAttribute('data-direction', 'reverse');
    expect(app.container.querySelector('.react-flow__edge-path')).toHaveAttribute('marker-end', 'url(#stored-arrow)'); app.clock.dispose();
  });
  it.each([[true, true], [false, false]])('renders no moving overlay when reduced=%s and active=%s', (reduced, active) => {
    const app = draw(false, false, reduced, active); expect(app.container.querySelector('.trace-edge-motion')).toBeNull(); app.clock.dispose();
  });
  it('unsubscribes visual frames after unmount', () => {
    const app = draw(); act(() => app.clock.play()); app.unmount();
    expect(vi.getTimerCount()).toBe(1); // Only the authoritative step deadline remains until owner disposal.
    app.clock.dispose(); expect(vi.getTimerCount()).toBe(0);
  });
  it('removes active motion immediately when reduced motion is enabled during playback', () => {
    const app = draw(); act(() => { app.clock.play(); vi.advanceTimersByTime(550); app.clock.setReduced(true); });
    expect(app.container.querySelector('.trace-edge-motion')).toBeNull(); expect(app.clock.getSnapshot().playing).toBe(false); app.clock.dispose();
  });
});
