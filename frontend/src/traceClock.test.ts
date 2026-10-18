import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TraceClock, TRACE_STEP_MS } from './traceClock';

beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });
describe('single authoritative trace clock', () => {
  it('samples elapsed progress, freezes pause, and resumes for exactly the remaining duration', () => {
    const clock = new TraceClock(), finish = vi.fn(); clock.setStep('one', finish); clock.play();
    vi.advanceTimersByTime(550); expect(clock.progress()).toBeCloseTo(0.25);
    clock.pause(); vi.advanceTimersByTime(5000); expect(clock.progress()).toBeCloseTo(0.25); expect(finish).not.toHaveBeenCalled();
    clock.play(); vi.advanceTimersByTime(1649); expect(finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1); expect(finish).toHaveBeenCalledTimes(1); expect(clock.progress()).toBe(1); clock.dispose();
  });
  it('uses sampled RAF for presentation without advancing steps early', () => {
    const clock = new TraceClock(), finish = vi.fn(), paint = vi.fn(); clock.setStep('one', finish);
    const off = clock.subscribeFrame(paint); clock.play(); vi.advanceTimersByTime(1100);
    expect(paint.mock.calls.length).toBeGreaterThan(20); expect(paint.mock.lastCall![0]).toBeCloseTo(0.5, 1);
    expect(finish).not.toHaveBeenCalled(); clock.pause(); const samples = paint.mock.calls.length;
    vi.advanceTimersByTime(3000); expect(paint).toHaveBeenCalledTimes(samples); off(); clock.dispose();
  });
  it.each(['pause', 'rewind', 'dispose', 'new step'])('invalidates a previously queued deadline on %s', action => {
    const clock = new TraceClock(), finish = vi.fn(); clock.setStep('one', finish);
    const scheduled = vi.spyOn(globalThis, 'setTimeout'); clock.play();
    const queued = scheduled.mock.calls.find(([, delay]) => delay === TRACE_STEP_MS)![0] as () => void;
    if (action === 'new step') clock.setStep('two', vi.fn()); else clock[action as 'pause' | 'rewind' | 'dispose']();
    queued(); expect(finish).not.toHaveBeenCalled(); clock.dispose();
  });
  it('resets progress on a new step and replay while preserving continuous playback across steps', () => {
    const clock = new TraceClock();
    clock.setStep('one', () => clock.setStep('two', () => clock.pause())); clock.play(); vi.advanceTimersByTime(2200);
    expect(clock.progress()).toBe(0); expect(clock.getSnapshot().playing).toBe(true);
    vi.advanceTimersByTime(1100); expect(clock.progress()).toBeCloseTo(0.5);
    clock.rewind(); expect(clock.progress()).toBe(0); expect(clock.getSnapshot().playing).toBe(false);
    const reset = clock.getSnapshot().cameraReset; clock.recenter(); expect(clock.getSnapshot().cameraReset).toBe(reset + 1); clock.dispose();
  });
  it('disables motion frame loops for reduced motion while retaining explicit step playback', () => {
    const clock = new TraceClock(), finish = vi.fn(), paint = vi.fn(); clock.setStep('one', finish);
    clock.setReduced(true); clock.subscribeFrame(paint); clock.play(); const count = paint.mock.calls.length;
    vi.advanceTimersByTime(1100); expect(paint).toHaveBeenCalledTimes(count); expect(finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1100); expect(finish).toHaveBeenCalledTimes(1); clock.dispose();
  });
  it('does not trigger React-style state subscribers on each animation frame', () => {
    const clock = new TraceClock(), state = vi.fn(); clock.setStep('one', () => {});
    clock.subscribe(state); clock.subscribeFrame(() => {}); clock.play(); const count = state.mock.calls.length;
    vi.advanceTimersByTime(1800); expect(state).toHaveBeenCalledTimes(count); clock.dispose();
  });
});
