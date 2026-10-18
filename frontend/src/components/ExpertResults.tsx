import { useState } from 'react';
import type { ExpertEvidence, ExpertInput, ExpertResponse, GraphNode, Source } from '../types';
import EntityIcon from './EntityIcon';

export function ExpertControls({ request, disabled, onRun }: {
  request: ExpertInput; disabled: boolean; onRun: (request: ExpertInput) => void;
}) {
  const [query, setQuery] = useState(request.query);
  const [limit, setLimit] = useState(request.limit);
  return <form className="impact-controls" aria-label="Expert Finder controls" onSubmit={event => {
    event.preventDefault(); if (query.trim()) onRun({ query: query.trim(), limit });
  }}>
    <label>Expertise query<input value={query} maxLength={2000} disabled={disabled} required onChange={e => setQuery(e.target.value)} /></label>
    <label>Maximum people<select value={limit} disabled={disabled} onChange={e => setLimit(Number(e.target.value))}>
      {[1, 2, 3, 5, 10].map(n => <option key={n} value={n}>{n}</option>)}
    </select></label>
    <button className="button primary" disabled={disabled || !query.trim()}>Find experts</button>
  </form>;
}

export default function ExpertResults({ result, onNode, onSource }: {
  result: ExpertResponse; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
}) {
  const nodes = new Map(result.graph.nodes.map(n => [n.id, n]));
  const sources = new Map(result.sources.map(s => [s.id, s]));
  function entity(id: string) {
    const node = nodes.get(id);
    return node ? <button className="impact-entity" onClick={() => onNode(node)}><EntityIcon type={node.type} size={17} />{node.label}</button> : id;
  }
  function proof(e: ExpertEvidence) {
    return <li key={`${e.category}/${e.entity_id}`}>
      <p>{e.category.replaceAll('_', ' ')}: {entity(e.entity_id)}</p>
      <div className="impact-path">{e.path.map((step, i) => <p key={i}>{entity(step.source)}<span> —{step.type}→ </span>{entity(step.target)}</p>)}</div>
      {e.source_ids.map(id => { const source = sources.get(id); return source ? <button className="citation" key={id} onClick={() => onSource(source)}>{id}</button> : null; })}
      {e.category !== 'team_ownership' && !e.source_ids.length && <p className="small muted">Graph evidence only; matching textual provenance was not retrieved.</p>}
    </li>;
  }
  return <div className="impact-results">
    <h2>Who can help</h2>
    <p className="impact-caution">Scores reflect the graph tool's fixed evidence weights. Returned rankings are bounded and are not exhaustive.</p>
    <section className="impact-section" aria-label="Resolved topics"><h3>Resolved topics</h3>
      {result.data.topics.map(t => <p key={t.id}>{entity(t.id)} <code>{t.id}</code></p>)}
      {!result.data.topics.length && <p>No confident topic match. Try a specific service or decision ID.</p>}
      {result.data.topics.length > 1 && <p>Ambiguous topic: specify one canonical topic. No experts were ranked across tied topics.</p>}
    </section>
    <section aria-label="Expert rankings">
      {!result.data.experts.length && <p>No experts returned for the resolved evidence. This does not mean no experts exist.</p>}
      {result.data.experts.map((expert, i) => <article className="impact-finding" key={expert.person.id}>
        <div className="panel-heading"><h3>{i + 1}. {entity(expert.person.id)}</h3><span className="tiny-tag">Score {expert.score}</span></div>
        <code className="impact-id">{expert.person.id}</code>
        <p>{expert.ownership_classification === 'team_membership_with_team_owned_service'
          ? 'Team member of a team that owns the service. Personal ownership is not established.' : 'No current personal ownership evidence returned.'}</p>
        <h4>Evidence-backed ranking reasons</h4><ul>{expert.ranking_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
        {expert.ownership.length > 0 && <><h4>Team membership evidence</h4><ul>{expert.ownership.map(proof)}</ul></>}
        <h4>Historical contributions</h4>
        {expert.historical_contributions.length ? <ul>{expert.historical_contributions.map(proof)}</ul> : <p>No historical contributions returned.</p>}
      </article>)}
    </section>
  </div>;
}
