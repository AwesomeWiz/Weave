export const TRACE_STEP_MS = 2200;
export interface TraceClockState { playing: boolean; reduced: boolean; revision: number; cameraReset: number }

/** One elapsed-time authority: a deadline advances steps; RAF only samples it for SVG presentation. */
export class TraceClock {
  private elapsed = 0;
  private started = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private frame: number | undefined;
  private generation = 0;
  private complete: () => void = () => {};
  private listeners = new Set<() => void>();
  private frames = new Set<(progress: number) => void>();
  private state: TraceClockState = { playing: false, reduced: false, revision: 0, cameraReset: 0 };
  private key = '';

  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  subscribeFrame = (listener: (progress: number) => void) => {
    this.frames.add(listener); listener(this.progress()); this.scheduleFrame();
    return () => { this.frames.delete(listener); if (!this.frames.size && this.frame !== undefined) { cancelAnimationFrame(this.frame); this.frame = undefined; } };
  };
  progress = () => Math.min(1, (this.elapsed + (this.state.playing ? Math.max(0, performance.now() - this.started) : 0)) / TRACE_STEP_MS);
  private publish(patch: Partial<TraceClockState> = {}) {
    this.state = { ...this.state, ...patch, revision: this.state.revision + 1 };
    this.listeners.forEach(fn => fn());
  }
  private paint = () => { const value = this.progress(); this.frames.forEach(fn => fn(value)); };
  private scheduleFrame() {
    if (!this.state.playing || this.state.reduced || !this.frames.size || this.frame !== undefined) return;
    this.frame = requestAnimationFrame(() => { this.frame = undefined; this.paint(); this.scheduleFrame(); });
  }
  private cancel() {
    this.generation++;
    clearTimeout(this.timer); this.timer = undefined;
    if (this.frame !== undefined) cancelAnimationFrame(this.frame);
    this.frame = undefined;
  }
  private schedule() {
    const generation = this.generation;
    const complete = this.complete;
    this.timer = setTimeout(() => {
      if (generation !== this.generation || !this.state.playing) return;
      this.elapsed = TRACE_STEP_MS; this.started = performance.now();
      this.cancel(); this.paint(); complete();
    }, Math.max(0, TRACE_STEP_MS - this.elapsed));
    this.scheduleFrame();
  }
  setStep(key: string, complete: () => void) {
    this.complete = complete;
    if (this.key === key) return;
    this.key = key; this.cancel(); this.elapsed = 0; this.started = performance.now();
    this.publish(); this.paint(); if (this.state.playing) this.schedule();
  }
  play() {
    if (this.state.playing || this.progress() >= 1) return;
    this.started = performance.now(); this.publish({ playing: true }); this.paint(); this.schedule();
  }
  pause() {
    if (!this.state.playing) return;
    this.elapsed = this.progress() * TRACE_STEP_MS; this.cancel(); this.publish({ playing: false }); this.paint();
  }
  rewind() {
    this.cancel(); this.elapsed = 0; this.started = performance.now(); this.publish({ playing: false }); this.paint();
  }
  recenter() { this.publish({ cameraReset: this.state.cameraReset + 1 }); }
  setReduced(reduced: boolean) { this.pause(); this.publish({ reduced }); this.paint(); }
  dispose() { this.pause(); this.cancel(); }
}
