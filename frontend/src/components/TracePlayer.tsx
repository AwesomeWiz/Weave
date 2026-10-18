import { Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react';
import type { GraphNode, Source, SupportStatus, TraceSequence } from '../types';
import type { TraceClock } from '../traceClock';
import { traceSentence, traceTitle } from '../tracePresentation';
import { useTracePlayback } from '../useTracePlayback';

interface Props {
  sequences: TraceSequence[]; selection: { sequenceId: string; step: number } | null | undefined;
  onChange: (sequence: TraceSequence, step: number) => void; onClose: () => void;
  nodes: GraphNode[]; sources: Source[]; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
  onMotion?: (clock: TraceClock) => (() => void); autoPlay?: boolean; onStarted?: () => void;
  overallSupport?: SupportStatus;
}
export default function TracePlayer(props: Props) {
  const { sequences, selection, onChange, onClose, nodes } = props;
  const sequence = sequences.find(s => s.id === selection?.sequenceId);
  const index = selection?.step;
  return <section className="trace-player" aria-label="Trace Mode">
    <div className="panel-heading"><p className="trace-panel-title">Now watching</p><button className="trace-close" onClick={onClose}>Close Trace Mode</button></div>
    <p className="trace-intro">Watch how your systems connect, one step at a time.</p>
    <label className="trace-selector"><span>Choose a story</span><select aria-label="Trace sequence" value={sequence?.id ?? ''}
      onChange={e => { const next = sequences.find(s => s.id === e.target.value); if (next) onChange(next, 0); }}>
      <option value="" disabled>Select an available trace</option>
      {sequences.map(s => <option key={s.id} value={s.id}>{traceTitle(s, nodes)}</option>)}
    </select></label>
    {sequence && Number.isInteger(index) && index! >= 0 && index! < sequence.steps.length
      ? <TraceRun key={sequence.id} {...props} sequence={sequence} index={index!} onStep={i => onChange(sequence, i)} />
      : <p role="status">No selected validated path is available. Choose a returned trace; no connections will be invented.</p>}
    {!sequences.length && <p>No playable trace was returned. You can still explore the original evidence in the brief.</p>}
  </section>;
}

function TraceRun({ sequence, index, onStep, nodes, sources, onNode, onSource, onMotion, autoPlay, onStarted, overallSupport }: Props & {
  sequence: TraceSequence; index: number; onStep: (step: number) => void;
}) {
  const { clock, playing, reduced, move, replay } = useTracePlayback(sequence, index, onStep, onMotion, autoPlay, onStarted);
  const step = sequence.steps[index];
  const support = sequence.support_status === 'insufficient_evidence' || overallSupport === 'insufficient_evidence' ? 'insufficient_evidence'
    : sequence.support_status === 'partially_supported' || overallSupport === 'partially_supported' ? 'partially_supported' : 'supported';
  const inspect = (id: string) => { clock.pause(); const node = nodes.find(n => n.id === id); if (node) onNode(node); };
  return <div className={reduced ? 'trace-run reduced-motion' : 'trace-run'}>
    <p className="trace-kind">{sequence.tool === 'decision_trace' ? 'Decision story' : 'Potential impact'}</p>
    <h2 className="trace-story-title">{traceTitle(sequence, nodes)}</h2>
    <div className="trace-current" aria-live="polite" aria-atomic="true"><p>{traceSentence(step, nodes)}</p></div>
    {sequence.tool === 'impact_analysis' && <p className="trace-qualification">A change may affect the connected services. This does not mean they will necessarily fail.</p>}
    {support !== 'supported' && <p className="trace-support" role="note">{support === 'partially_supported'
      ? 'Some evidence is incomplete. This trace shows only the connections that were verified.' : 'Evidence is insufficient for a complete conclusion. These connections alone do not establish one.'}</p>}
    <div className="trace-controls" aria-label="Playback controls">
      <button className="button" aria-label="Previous step" disabled={index === 0} onClick={() => move(index - 1)}><SkipBack size={17} /><span>Previous</span></button>
      <button className="button primary" disabled={!playing && clock.progress() >= 1} onClick={() => playing ? clock.pause() : clock.play()}>
        {playing ? <Pause size={17} /> : <Play size={17} />}<span>{playing ? 'Pause' : 'Play'}</span></button>
      <button className="button" aria-label="Next step" disabled={index === sequence.steps.length - 1} onClick={() => move(index + 1)}><SkipForward size={17} /><span>Next</span></button>
      <button className="button" onClick={replay}><RotateCcw size={16} /><span>Replay</span></button>
    </div>
    <div className="trace-progress"><progress aria-label="Trace progress" max={sequence.steps.length} value={index + 1} />
      <span role="status">Step {index + 1} of {sequence.steps.length} · {playing ? 'Playing' : 'Paused'}</span></div>
    {reduced && <p className="small muted">Reduced motion enabled. Highlights replace edge and camera animation.</p>}
    <details className="trace-evidence" onToggle={event => { if (event.currentTarget.open) clock.pause(); }}><summary>View evidence</summary>
      <p className="small muted">{sequence.support_status.replaceAll('_', ' ')} · {sequence.tool === 'decision_trace' ? 'Decision Trace' : 'Impact Analysis'}</p>
      {overallSupport && <p className="small muted">Overall review: {overallSupport.replaceAll('_', ' ')}</p>}
      <dl className="trace-proof"><div><dt>Path</dt><dd><code>{sequence.path_id}</code></dd></div>
        <div><dt>Stored relationship</dt><dd><code>{step.source}</code> —<code>{step.type}</code>→ <code>{step.target}</code></dd></div>
        <div><dt>Edge ID</dt><dd><code>{step.edge_id}</code></dd></div>
        <div><dt>Tool provenance</dt><dd><code>{step.tool}</code></dd></div>
        <div><dt>Playback direction</dt><dd><code>{step.traversal_from}</code> → <code>{step.traversal_to}</code></dd></div></dl>
      {step.traversal_from !== step.source && <p className="small muted">Playback follows dependencies toward the services that use them. The arrow still shows the stored relationship in its original direction.</p>}
      <p className="small muted">{step.explanation}</p>
      <div className="trace-inspect"><button className="button small" onClick={() => inspect(step.source)}>Inspect source entity</button>
        <button className="button small" onClick={() => inspect(step.target)}>Inspect target entity</button>
        {step.citation_ids.map(id => { const source = sources.find(s => s.id === id); return source && <button className="citation" key={id} onClick={() => { clock.pause(); onSource(source); }}>{id}</button>; })}</div>
      {!step.citation_ids.length && <p className="small muted">Graph-only step; no textual citation assigned. Inspector shows this step’s graph proof. Other sources remain in Key sources.</p>}
    </details>
    <details className="trace-step-list"><summary>All {sequence.steps.length} steps</summary><ol>{sequence.steps.map((s, i) =>
      <li key={s.number}><button aria-current={i === index ? 'step' : undefined} onClick={() => move(i)}><span>{s.number}. </span>{traceSentence(s, nodes)}</button></li>)}</ol></details>
  </div>;
}
