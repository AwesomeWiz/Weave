import { useEffect, useRef, useState } from 'react';
import type { GraphNode, Source, TraceSequence } from '../types';

export default function TracePlayer({ sequences, selection, onChange, onClose, nodes, sources, onNode, onSource }: {
  sequences: TraceSequence[]; selection: { sequenceId: string; step: number } | null | undefined;
  onChange: (sequence: TraceSequence, step: number) => void; onClose: () => void;
  nodes: GraphNode[]; sources: Source[]; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
}) {
  const sequence = sequences.find(s => s.id === selection?.sequenceId);
  const index = selection?.step;
  return <section className="trace-player" aria-label="Trace Mode">
    <div className="panel-heading"><h2>Trace Mode</h2><button className="button small" onClick={onClose}>Close Trace Mode</button></div>
    <p className="small muted">Stored evidence, one relationship at a time. Playback runs locally and does not upgrade evidence support.</p>
    <label className="trace-selector">Evidence sequence<select aria-label="Trace sequence" value={sequence?.id ?? ''}
      onChange={e => { const next = sequences.find(s => s.id === e.target.value); if (next) onChange(next, 0); }}>
      <option value="" disabled>Select a validated path</option>
      {sequences.map(s => <option key={s.id} value={s.id}>{s.tool === 'decision_trace' ? 'Decision' : 'Impact'} · {s.path_id}</option>)}
    </select></label>
    {sequence && Number.isInteger(index) && index! >= 0 && index! < sequence.steps.length
      ? <TraceRun key={sequence.id} sequence={sequence} index={index!} onChange={i => onChange(sequence, i)} nodes={nodes} sources={sources} onNode={onNode} onSource={onSource} />
      : <p role="status">No selected validated path is available. Select a returned sequence; no path will be inferred.</p>}
    {!sequences.length && <p>No backend-authored playback data was returned. Legacy evidence remains available in the brief.</p>}
  </section>;
}

function TraceRun({ sequence, index, onChange, nodes, sources, onNode, onSource }: {
  sequence: TraceSequence; index: number; onChange: (step: number) => void;
  nodes: GraphNode[]; sources: Source[]; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
  const change = useRef(onChange);
  useEffect(() => { change.current = onChange; }, [onChange]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const preference = () => { setReduced(media?.matches ?? false); setPlaying(false); };
    const hidden = () => { if (document.visibilityState === 'hidden') setPlaying(false); };
    media?.addEventListener('change', preference); document.addEventListener('visibilitychange', hidden);
    return () => { media?.removeEventListener('change', preference); document.removeEventListener('visibilitychange', hidden); };
  }, []);
  useEffect(() => {
    if (!playing || index >= sequence.steps.length - 1) return;
    const advance = change.current; // Bind the owner/index that scheduled this timer.
    const timer = setTimeout(() => {
      advance(index + 1);
      if (index + 1 === sequence.steps.length - 1) setPlaying(false);
    }, 2200);
    return () => clearTimeout(timer);
  }, [playing, index, sequence.steps.length]);
  const step = sequence.steps[index];
  const inspect = (id: string) => { setPlaying(false); const node = nodes.find(n => n.id === id); if (node) onNode(node); };
  const move = (i: number) => { setPlaying(false); onChange(i); };
  return <div className={reduced ? 'trace-run reduced-motion' : 'trace-run'}>
    <p className="small"><strong>{sequence.tool === 'decision_trace' ? 'Decision Trace' : 'Impact Trace'}</strong> · {sequence.support_status.replaceAll('_', ' ')}</p>
    {reduced && <p className="small muted">Reduced motion enabled. Highlights change instantly; playback starts only when requested.</p>}
    <div className="trace-controls" aria-label="Playback controls">
      <button className="button" disabled={index === 0} onClick={() => move(index - 1)}>Previous step</button>
      <button className="button primary" disabled={!playing && index === sequence.steps.length - 1}
        onClick={() => { if (playing) setPlaying(false); else { onChange(index); setPlaying(true); } }}>{playing ? 'Pause' : 'Play'}</button>
      <button className="button" disabled={index === sequence.steps.length - 1} onClick={() => move(index + 1)}>Next step</button>
      <button className="button" onClick={() => { onChange(0); setPlaying(sequence.steps.length > 1); }}>Replay</button>
    </div>
    <div className="trace-progress"><progress aria-label="Trace progress" max={sequence.steps.length} value={index + 1} />
      <span role="status">Step {index + 1} of {sequence.steps.length} · {playing ? 'Playing' : 'Paused'}</span></div>
    <div className="trace-current" aria-live="polite" aria-atomic="true"><p>{step.explanation}</p>
      {sequence.tool === 'impact_analysis' && <p className="small">Traversal: <code>{step.traversal_from}</code> → <code>{step.traversal_to}</code></p>}</div>
    <div className="trace-inspect"><button className="button small" onClick={() => inspect(step.source)}>Inspect source entity</button>
      <button className="button small" onClick={() => inspect(step.target)}>Inspect target entity</button>
      {step.citation_ids.map(id => { const source = sources.find(s => s.id === id); return source && <button className="citation" key={id} onClick={() => { setPlaying(false); onSource(source); }}>{id}</button>; })}</div>
    {!step.citation_ids.length && <p className="small muted">Graph-only step; no textual citation assigned. Inspector shows this step’s graph proof. Other sources remain in Key sources.</p>}
    <details className="trace-step-list"><summary>All {sequence.steps.length} steps</summary><ol>{sequence.steps.map((s, i) =>
      <li key={s.number}><button aria-current={i === index ? 'step' : undefined} onClick={() => move(i)}><span>{s.number}. </span><code>{s.source}</code> —{s.type}→ <code>{s.target}</code></button></li>)}</ol></details>
  </div>;
}
