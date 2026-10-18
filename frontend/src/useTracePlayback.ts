import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { TraceSequence } from './types';
import { TraceClock } from './traceClock';

const idle = { playing: false, reduced: false, revision: 0, cameraReset: 0 };
const noSubscription = () => () => {};
const idleSnapshot = () => idle;
export function useTraceClockState(clock?: TraceClock | null) {
  return useSyncExternalStore(clock?.subscribe ?? noSubscription, clock?.getSnapshot ?? idleSnapshot, idleSnapshot);
}

export function useTracePlayback(sequence: TraceSequence, index: number, onChange: (index: number) => void,
  onMotion?: (clock: TraceClock) => (() => void), autoPlay = false, onStarted?: () => void) {
  const [clock] = useState(() => new TraceClock());
  const state = useSyncExternalStore(clock.subscribe, clock.getSnapshot, clock.getSnapshot);
  const change = useRef(onChange);
  useEffect(() => { change.current = onChange; }, [onChange]);
  useEffect(() => {
    const advance = change.current;
    clock.setStep(`${sequence.id}/${index}`, () => {
      if (index < sequence.steps.length - 1) advance(index + 1);
      else clock.pause();
    });
  }, [clock, index, sequence.id, sequence.steps.length]);
  useEffect(() => onMotion?.(clock), [clock, onMotion]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    clock.setReduced(media?.matches ?? false);
    const preference = () => clock.setReduced(media?.matches ?? false);
    const hidden = () => { if (document.visibilityState === 'hidden') clock.pause(); };
    media?.addEventListener('change', preference); document.addEventListener('visibilitychange', hidden);
    return () => { media?.removeEventListener('change', preference); document.removeEventListener('visibilitychange', hidden); clock.dispose(); };
  }, [clock]);
  useEffect(() => { if (autoPlay) { clock.play(); onStarted?.(); } }, [autoPlay, clock, onStarted]);
  const move = (next: number) => { clock.rewind(); onChange(next); };
  const replay = () => { clock.rewind(); clock.recenter(); onChange(0); clock.play(); };
  return { clock, ...state, move, replay };
}
