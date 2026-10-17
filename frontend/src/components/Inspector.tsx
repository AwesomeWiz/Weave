import { ArrowUpRight, ChevronRight, CircleCheck, ExternalLink, RefreshCw, X } from 'lucide-react';
import EntityIcon from './EntityIcon';
import { safeSourceUrl } from '../api';
import type { GraphNode, Health, QueryResponse, Source } from '../types';
import { dateLabel, metadataLabel } from '../format';

export function SourceRow({ source, onClick }: { source: Source; onClick: () => void }) {
  return <button className="source-row" onClick={onClick}>
    <span className={`round-icon type-${source.type.toLowerCase()}`}><EntityIcon type={source.type} /></span>
    <span className="row-copy"><strong>{source.title}</strong><code>{source.id}</code>
      <small>{source.type} · {dateLabel(source.timestamp)}</small></span><ChevronRight size={16} />
  </button>;
}

export default function Inspector({ result, health, healthError, selectedSource, selectedNode, onSource, onNode, onClose, onRefresh }: {
  result: QueryResponse | null; health: Health | null; healthError: boolean;
  selectedSource: Source | null; selectedNode: GraphNode | null;
  onSource: (source: Source) => void; onNode: (node: GraphNode) => void; onClose: () => void; onRefresh: () => void;
}) {
  if (selectedSource) {
    const url = safeSourceUrl(selectedSource.url);
    return <aside className="inspector" aria-label="Source inspector"><section className="panel source-detail">
      <div className="detail-header"><div className="panel-heading"><span className={`round-icon type-${selectedSource.type.toLowerCase()}`}><EntityIcon type={selectedSource.type} /></span>
        <button className="icon-button" onClick={onClose} aria-label="Close source"><X size={19} /></button></div>
      <p className="eyebrow">{selectedSource.type} evidence</p><h2>{selectedSource.title}</h2>
      <code>{selectedSource.id}</code><p className="muted small">{dateLabel(selectedSource.timestamp, true)}</p></div>
      {(selectedSource.metadata.dataset === 'development_fixture' || result?.metadata.graph_mode === 'fixture') && <p className="fixture-label">Development fixture</p>}
      <hr /><h3>Source excerpt</h3><p className="source-excerpt">{selectedSource.snippet}</p>
      {url ? <a className="button" href={url} target="_blank" rel="noopener noreferrer">Open original <ExternalLink size={15} /></a>
        : <p className="muted small">No external source URL is available.</p>}
      <hr /><h3>Linked entities</h3>{selectedSource.entity_ids.map(id => {
        const node = result?.graph.nodes.find(n => n.id === id);
        return node ? <button className="source-row" key={id} onClick={() => onNode(node)}><EntityIcon type={node.type} /><span>{node.label}</span><ChevronRight size={16} /></button> : <code key={id}>{id}</code>;
      })}{!selectedSource.entity_ids.length && <p className="muted small">No linked entities were returned.</p>}
      <hr /><h3>Source metadata</h3><dl className="properties">{Object.entries(selectedSource.metadata).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{metadataLabel(value)}</dd></div>)}</dl>
      {!Object.keys(selectedSource.metadata).length && <p className="muted small">No additional metadata available.</p>}
    </section></aside>;
  }
  if (selectedNode) {
    const relationships = result?.graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id) ?? [];
    return <aside className="inspector" aria-label="Entity inspector"><section className="panel">
      <div className="detail-header"><div className="panel-heading"><span className={`round-icon type-${selectedNode.type.toLowerCase()}`}><EntityIcon type={selectedNode.type} size={25} /></span>
        <button className="icon-button" onClick={onClose} aria-label="Close entity"><X size={19} /></button></div>
      <h2>{selectedNode.label}</h2><p className="muted">{selectedNode.type}</p><code>{selectedNode.id}</code></div>
      <hr /><h3>Overview</h3><dl className="properties">{Object.entries(selectedNode.properties).filter(([key]) => key !== 'dataset').map(([key, value]) =>
        <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{metadataLabel(value)}</dd></div>)}</dl>
      {!Object.keys(selectedNode.properties).some(key => key !== 'dataset') && <p className="muted small">No additional properties available.</p>}
      <hr /><h3>Relationships <span className="count">{relationships.length}</span></h3>
      {relationships.map(edge => {
        const id = edge.source === selectedNode.id ? edge.target : edge.source;
        const node = result?.graph.nodes.find(n => n.id === id);
        return node && <button className="relationship-row" key={edge.id} onClick={() => onNode(node)}>
          <span>{edge.source === selectedNode.id ? '→' : '←'} {node.label}</span><code>{edge.type}</code></button>;
      })}
      {!relationships.length && <p className="muted small">No relationships in this evidence graph.</p>}
      <hr /><h3>Supporting sources</h3>{result?.sources.filter(s => s.entity_ids.includes(selectedNode.id) || s.id === selectedNode.id).map(source =>
        <SourceRow key={source.id} source={source} onClick={() => onSource(source)} />)}
      {!result?.sources.some(s => s.entity_ids.includes(selectedNode.id) || s.id === selectedNode.id) && <p className="muted small">No source records linked to this entity.</p>}
    </section></aside>;
  }
  if (result) {
    const related = result.graph.nodes.filter(n => ['Service', 'Technology', 'Person', 'Repository'].includes(n.type));
    return <aside className="inspector" aria-label="Evidence sources">
      <section className="panel"><div className="panel-heading"><h2>Sources</h2><span className="muted small">{result.sources.length} sources</span></div>
        {result.sources.length ? result.sources.map(source => <SourceRow key={source.id} source={source} onClick={() => onSource(source)} />)
          : <p className="muted">No supporting source records were returned.</p>}
      </section>
      {related.length > 0 && <section className="panel"><div className="panel-heading"><h2>Related entities</h2><ArrowUpRight size={17} /></div>
        {related.map(node => <button className="source-row" key={node.id} onClick={() => onNode(node)}>
          <span className={`round-icon type-${node.type.toLowerCase()}`}><EntityIcon type={node.type} /></span>
          <span className="row-copy"><strong>{node.label}</strong><small>{node.type}</small></span><ChevronRight size={16} /></button>)}
      </section>}
      <section className="panel"><h2>Evidence status</h2><p className="status-line"><CircleCheck size={17} />{result.support_status.replaceAll('_', ' ')}</p>
        <p className="muted small">{result.metadata.generation === 'openrouter' ? 'Synthesized with OpenRouter' : result.metadata.generation === 'ollama' ? 'Explained with Ollama' : 'Deterministic evidence summary'} · {(result.metadata.latency_ms / 1000).toFixed(2)}s</p>
        <p className="muted small">{result.metadata.graph_mode === 'fixture' ? 'Synthetic development data. No live sources are connected.' : 'Retrieved through the configured graph tool.'}</p>
      </section>
    </aside>;
  }
  const fixture = health?.graph_mode === 'fixture';
  return <aside className="inspector welcome-inspector" aria-label="Knowledge connections">
    <section className="panel"><div className="panel-heading"><h2>Knowledge sources</h2><span className="tiny-tag">{fixture ? 'Demo' : 'Phase 1'}</span></div>
      {[['Repository', 'GitHub'], ['Issue', 'Jira'], ['Message', 'Slack'], ['Document', 'Documents']].map(([type, label]) =>
        <div className="connection-row" key={label}><EntityIcon type={type} size={25} /><div><strong>{label}</strong><small>{fixture ? 'Synthetic source records' : 'No live connector configured'}</small></div>
          <span className={`connection-status ${fixture ? 'demo' : ''}`}>{fixture ? 'Demo data' : 'Not connected'}</span></div>)}
    </section>
    <section className="panel"><div className="panel-heading"><h2>Knowledge status</h2><button className="icon-button" onClick={onRefresh} aria-label="Refresh connection status"><RefreshCw size={15} /></button></div>
      <div className={`knowledge-state ${healthError || health?.status === 'unavailable' ? 'unavailable' : ''}`}>
        <CircleCheck size={26} /><div><strong>{healthError ? 'Backend unavailable' : !health ? 'Checking connection' : fixture ? 'Development workspace' : health.status === 'unavailable' ? 'Graph not available' : 'Graph ready'}</strong>
          <p>{healthError ? 'Start the FastAPI server to ask a question.' : fixture ? 'Explore a labeled NovaPay fixture.' : health?.status === 'unavailable' ? 'The graph adapter or database is not ready.' : 'Answers are grounded in connected evidence.'}</p></div>
      </div>
      <p className="muted small status-line"><span className={`status-dot ${healthError ? 'offline' : ''}`} />{health ? `Backend available · ${health.llm === 'disabled' ? 'Deterministic answers' : `LLM ${health.llm}`}` : 'Waiting for backend connection'}</p>
    </section>
    <p className="inspector-note">Every answer starts with evidence.<br />Follow the sources to see the full story.</p>
  </aside>;
}
