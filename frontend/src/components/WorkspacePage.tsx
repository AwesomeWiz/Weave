import type { GraphNode, QueryResponse } from '../types';
import type { WorkspacePage as Page } from '../workspace';
import { PAGE_LABELS } from '../workspace';
import EntityIcon from './EntityIcon';

export default function WorkspacePage({ page, result, onNode, onChat }: {
  page: Exclude<Page, 'chat'>; result: QueryResponse | null; onNode: (node: GraphNode) => void; onChat: () => void;
}) {
  const kinds = { decisions: ['Decision'], services: ['Service'], people: ['Person'], changes: ['Decision', 'Commit', 'Incident'] };
  const nodes = result?.graph.nodes.filter(n => kinds[page].includes(n.type)) ?? [];
  return <section className="workspace-page" aria-label={`${PAGE_LABELS[page]} workspace`}>
    <p className="eyebrow">Workspace · {PAGE_LABELS[page]}</p>
    <h2>Evidence in the selected answer</h2><p className="muted">These are existing returned records in this chat, not a company-wide directory. Open a record to inspect its evidence.</p>
    {nodes.length ? <div className="workspace-records">{nodes.map(node => <button className="source-row" key={node.id} onClick={() => onNode(node)}><EntityIcon type={node.type} /><span><strong>{node.label}</strong><code>{node.id}</code><small>{node.type}</small></span></button>)}</div>
      : <p>No {PAGE_LABELS[page].toLowerCase()} records in the selected answer. Ask a question or open another saved message to explore its returned evidence.</p>}
    <button className="button" onClick={onChat}>Return to chat</button>
  </section>;
}
