import { useState } from 'react';
import type { GraphNode, ImpactFinding, ImpactInput, ImpactResponse, Source } from '../types';
import { IMPACT_TARGETS } from '../impact';
import EntityIcon from './EntityIcon';
import { SourceRow } from './Inspector';

export function ImpactControls({ request, disabled, onRun }: {
  request: ImpactInput; disabled: boolean; onRun: (request: ImpactInput) => void;
}) {
  const [target, setTarget] = useState(request.entity_id);
  const [depth, setDepth] = useState(request.max_depth);
  return <form className="impact-controls" aria-label="Impact Analysis controls" onSubmit={event => { event.preventDefault(); onRun({ entity_id: target, max_depth: depth }); }}>
    <label>Target entity<select value={target} disabled={disabled} onChange={event => setTarget(event.target.value)}>
      {IMPACT_TARGETS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select></label>
    <label>Traversal depth<select value={depth} disabled={disabled} onChange={event => setDepth(Number(event.target.value))}>
      {[1, 2, 3].map(n => <option key={n} value={n}>{n} {n === 1 ? 'hop' : 'hops'}</option>)}
    </select></label>
    <button className="button primary" disabled={disabled}>Analyze impact</button>
  </form>;
}

export default function ImpactResults({ result, onNode, onSource, onPath, highlightedId }: {
  result: ImpactResponse; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
  onPath: (finding: ImpactFinding) => void; highlightedId?: string;
}) {
  const nodes = new Map(result.graph.nodes.map(n => [n.id, n]));
  const sources = new Map(result.sources.map(s => [s.id, s]));
  const target = result.data.entity;
  function entity(id: string) {
    const node = nodes.get(id);
    return node ? <button className="impact-entity" onClick={() => onNode(node)}><EntityIcon type={node.type} size={17} />{node.label}</button> : id;
  }
  function section(title: string, findings: ImpactFinding[]) {
    return <section className="impact-section" aria-label={title}><h3>{title}<span className="tiny-tag">{findings.length}</span></h3>
      {findings.length ? findings.map(f => <article className="impact-finding" key={f.service_id}>
        <div className="panel-heading">{entity(f.service_id)}<span className="tiny-tag">Depth {f.impact_depth}</span></div>
        <code className="impact-id">{f.service_id}</code>
        <div className="impact-path" aria-label={`Stored path to ${nodes.get(f.service_id)?.label}`}>
          {f.path_edges.map((edge, index) => <p key={index}>{entity(edge.source)}<span> —{edge.type}→ </span>{entity(edge.target)}</p>)}
        </div>
        <button className="button small" aria-pressed={highlightedId === f.service_id} onClick={() => onPath(f)}>Highlight path to {nodes.get(f.service_id)?.label}</button>
        <p className="impact-owners">Owners / teams: {f.owners.length ? f.owners.map(owner => <span key={owner.id}>{entity(owner.id)} </span>) : 'Not returned'}</p>
        {f.source_ids.length ? <div className="impact-sources">{f.source_ids.map(id => {
          const source = sources.get(id);
          return source ? <button className="citation" key={id} onClick={() => onSource(source)}>{source.id}</button> : null;
        })}</div> : <p className="small muted">No retrieved textual evidence linked to this service.</p>}
      </article>) : <p className="muted">No services returned within this traversal.</p>}
    </section>;
  }
  return <div className="impact-results">
    <h2>What could be affected</h2>
    {target ? <div className="impact-target"><span className="small muted">Target entity</span>{entity(target.id)}<code>{target.id}</code></div> : <p>No supported impact target was found in the graph.</p>}
    <p className="impact-caution">Potential impact from stored dependencies. These relationships do not establish guaranteed failure.</p>
    {section('Direct Impact', result.data.direct_impact)}
    {section('Potential Downstream Impact', result.data.indirect_impact)}
    {result.sources.length > 0 && <section className="impact-section"><h3>Related historical sources</h3><p className="small muted">These excerpts provide context; they do not prove failure propagation.</p>
      {result.sources.map(source => <SourceRow key={source.id} source={source} onClick={() => onSource(source)} />)}
    </section>}
  </div>;
}
