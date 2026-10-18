import { CircleCheck, CircleX, Info, LoaderCircle, RefreshCw, TriangleAlert } from 'lucide-react';
import type { Health } from '../types';

function graphStatus(health: Health | null, failed: boolean) {
  if (failed) return { state: 'unavailable', title: 'Backend unavailable', text: 'We can’t reach Weave right now. Try checking again.' };
  if (!health) return { state: 'checking', title: 'Checking connection', text: 'Checking whether your knowledge graph is available.' };
  if (health.graph_mode === 'fixture' && health.graph_tool === 'fixture') return { state: 'sample', title: 'Sample workspace', text: 'Sample data is available for exploration. No live company connection is verified.' };
  if (health.falkordb === 'unavailable' || health.graph_tool === 'unavailable') return { state: 'unavailable', title: 'Knowledge graph unavailable', text: 'We can’t connect to the knowledge graph right now. Try again later.' };
  if (health.falkordb === 'not_checked') return { state: 'unknown', title: 'Graph connection not checked', text: 'A live graph connection has not been verified.' };
  if (health.falkordb === 'connected' && health.graph_tool === 'available') return { state: 'connected', title: 'Knowledge graph connected', text: 'The database and evidence tools are available.' };
  return { state: 'partial', title: 'Knowledge graph partly available', text: 'The database is reachable, but evidence tools are not fully available.' };
}

export default function KnowledgeStatus({ health, failed, onRefresh }: { health: Health | null; failed: boolean; onRefresh: () => void }) {
  const status = graphStatus(health, failed);
  const Icon = status.state === 'connected' ? CircleCheck : status.state === 'unavailable' ? CircleX : status.state === 'checking' ? LoaderCircle : status.state === 'partial' ? TriangleAlert : Info;
  return <section className="panel knowledge-panel" aria-label="Connection status">
    <div className="panel-heading"><h2>Connection status</h2><button className="icon-button" onClick={onRefresh} aria-label="Refresh connection status"><RefreshCw size={17} /></button></div>
    <div className={`knowledge-state health-${status.state}`} role="status"><Icon aria-hidden="true" className={status.state === 'checking' ? 'spin' : undefined} data-status-icon={status.state} size={24} /><div><strong>{status.title}</strong><p>{status.text}</p></div></div>
    <p className="small muted">{failed ? 'Backend unavailable' : health ? 'Backend available' : 'Backend: checking'}</p>
    <p className="small muted">{failed || !health ? 'Answer provider: unknown' : health.llm === 'available' ? 'Answer provider available' : health.llm === 'disabled' ? 'Evidence summaries enabled' : 'Answer provider unavailable · evidence summaries remain available when the graph is connected'}</p>
  </section>;
}
