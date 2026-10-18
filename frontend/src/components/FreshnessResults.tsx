import { useState } from 'react';
import type { FreshnessInput, FreshnessPath, FreshnessResponse, GraphNode, Source } from '../types';
import EntityIcon from './EntityIcon';

export function FreshnessControls({ request, disabled, onRun }: {
  request: FreshnessInput; disabled: boolean; onRun: (request: FreshnessInput) => void;
}) {
  const [entity, setEntity] = useState(request.entity);
  return <form className="impact-controls" aria-label="Knowledge Freshness controls" onSubmit={event => {
    event.preventDefault(); if (entity.trim()) onRun({ entity: entity.trim() });
  }}>
    <label>Service name or canonical ID<input value={entity} maxLength={256} required disabled={disabled} onChange={e => setEntity(e.target.value)} /></label>
    <button className="button primary" disabled={disabled || !entity.trim()}>Check freshness</button>
  </form>;
}

export default function FreshnessResults({ result, onNode, onSource }: {
  result: FreshnessResponse; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
}) {
  const nodes = new Map(result.graph.nodes.map(n => [n.id, n]));
  const sources = new Map(result.sources.map(s => [s.id, s]));
  function entity(id: string) {
    const node = nodes.get(id);
    return node ? <button className="impact-entity" onClick={() => onNode(node)}><EntityIcon type={node.type} size={17} />{node.label}</button> : id;
  }
  function paths(path: FreshnessPath[]) {
    return <div className="impact-path">{path.map((p, i) => <p key={i}>{entity(p.source)}<span> —{p.type}→ </span>{entity(p.target)}</p>)}</div>;
  }
  function citations(ids: string[]) {
    return ids.map(id => { const source = sources.get(id); return source ? <button className="citation" key={id} onClick={() => onSource(source)}>{id}</button> : null; });
  }
  return <div className="impact-results">
    <h2>Documents to review</h2>
    <p className="impact-caution">Review recommendations are based on bounded graph evidence. They do not establish that a document is wrong or that other documents are current.</p>
    {result.data.entity ? <p>Resolved target: {entity(result.data.entity.id)} <code>{result.data.entity.id}</code></p>
      : <p>No unambiguous service was resolved. Specify an exact service name or canonical ID.</p>}
    {!result.data.review_candidates.length && <p>No review candidates established. This does not prove the documentation is current.</p>}
    <section aria-label="Document review recommendations">{result.data.review_candidates.map(f => <article className="impact-finding" key={f.document_id}>
      <div className="panel-heading"><h3>{entity(f.document_id)}</h3><span className="tiny-tag">Review recommended</span></div>
      <code className="impact-id">{f.document_id}</code>
      <p>Document updated: <time dateTime={f.updated_at}>{f.updated_at}</time></p>
      <p>{f.reason}</p>{citations(f.source_ids)}
      {!f.source_ids.length && <p className="small muted">Document excerpt unavailable; graph association retained.</p>}
      <h4>Document association</h4>{paths(f.document_path)}
      <h4>Later changes</h4><ul>{f.triggers.map(t => <li key={t.id}>
        <p>{t.type}: {entity(t.id)} <code>{t.id}</code></p>
        <p>Change timestamp: <time dateTime={t.timestamp}>{t.timestamp}</time></p>
        {paths(t.path)}{citations(t.source_ids)}
        {!t.source_ids.length && <p className="small muted">Graph-only change evidence; no textual citation established.</p>}
      </li>)}</ul>
    </article>)}</section>
  </div>;
}
