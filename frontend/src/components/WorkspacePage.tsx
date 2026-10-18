import type { GraphNode, QueryResponse, TraceSequence, Source } from '../types';
import type { Conversation, WorkspacePage as Page } from '../workspace';
import { PAGE_LABELS } from '../workspace';
import EntityIcon from './EntityIcon';
import { isChangeResponse } from '../change';
import { isExpertResponse } from '../experts';
import { traceSequences } from '../traceValidation';
import { traceEntityName, traceSentence } from '../tracePresentation';
import { dateLabel } from '../format';

export default function WorkspacePage({ page, result, onNode, onChat, conversations, onSaved, onAsk, onGraph, onTrace, onSource }: {
  page: Exclude<Page, 'chat'>; result: QueryResponse | null; onNode: (node: GraphNode) => void; onChat: () => void;
  conversations: Conversation[]; onSaved: (chatId: string, turnId: string) => void; onAsk: (question: string) => void;
  onGraph: (node: GraphNode) => void; onTrace: (sequence: TraceSequence) => void; onSource: (source: Source) => void;
}) {
  if (page === 'changes') {
    const analyses = conversations.flatMap(chat => chat.turns.flatMap(turn => turn.status === 'complete' && turn.result && isChangeResponse(turn.result)
      ? [{ chat, turn, result: turn.result }] : [])).sort((a, b) => b.turn.createdAt.localeCompare(a.turn.createdAt));
    return <section className="workspace-page" aria-label="Saved Change Analyses workspace"><div className="workspace-page-heading"><div><p className="eyebrow">Understand changes</p><h2>Saved Change Analyses</h2></div><button className="button primary" onClick={() => onAsk('What happens if we remove Redis from Payment Service?')}>Analyze a change</button></div>
      <p className="muted">Assessments saved in this browser, across your conversations. Opening one restores its original evidence without running it again.</p>
      {analyses.length ? <div className="evidence-record-grid">{analyses.map(({ chat, turn, result: assessment }) => <article className="evidence-record" key={`${chat.id}/${turn.id}`}>
        <p className={`support-badge ${assessment.support_status}`}>{assessment.support_status.replaceAll('_', ' ')}</p>
        <h3>{assessment.data.proposed_change.requested_change}</h3><p className="small muted">{chat.title} · <time dateTime={turn.createdAt}>{dateLabel(turn.createdAt)}</time></p>
        <p className="saved-preview">{assessment.data.historical_context.summary}</p>
        <p className="small muted">{traceSequences(assessment).length ? 'Evidence Trace available' : 'No playable trace returned'}</p>
        <button className="button" onClick={() => onSaved(chat.id, turn.id)}>Open saved assessment</button>
      </article>)}</div> : <div className="workspace-empty"><h3>No saved change analyses yet</h3><p>Assess a proposed change in Chat. Completed assessments will appear here.</p></div>}
    </section>;
  }
  const kinds = { decisions: ['Decision'], services: ['Service'], people: ['Person'] };
  const availableNodes = result?.graph.nodes.filter(n => kinds[page].includes(n.type)) ?? [];
  const playback = traceSequences(result);
  const experts = result && isChangeResponse(result) ? result.data.reviewers : result && isExpertResponse(result) ? result.data.experts : [];
  const nodes = page === 'people' && experts.length ? [
    ...experts.flatMap(e => availableNodes.filter(n => n.id === e.person.id)),
    ...availableNodes.filter(n => !experts.some(e => e.person.id === n.id)),
  ] : availableNodes;
  return <section className="workspace-page" aria-label={`${PAGE_LABELS[page]} workspace`}>
    <p className="eyebrow">Explore your company</p><h2>{PAGE_LABELS[page]} in this answer</h2><p className="muted">Available evidence from the selected answer, not a complete company directory. Open another saved answer to explore its records.</p>
    {nodes.length ? <div className="evidence-record-grid">{nodes.map(node => {
      const links = result!.graph.edges.filter(e => e.source === node.id || e.target === node.id);
      const associated = new Set([node.id, ...links.flatMap(e => [e.source, e.target])]);
      const sources = result!.sources.filter(s => associated.has(s.id) || s.entity_ids.some(id => associated.has(id)));
      const sequence = playback.find(s => s.steps.some(step => step.source === node.id || step.target === node.id));
      const expert = experts.find(e => e.person.id === node.id);
      return <article className="evidence-record" key={node.id}><div className="record-heading"><span className={`round-icon type-${node.type.toLowerCase()}`}><EntityIcon type={node.type} /></span><h3>{node.label !== node.id ? node.label : traceEntityName(node, node.id)}</h3></div>
        {['description', 'status', 'role', 'team'].map(key => typeof node.properties[key] === 'string' && <p key={key} className="small"><span className="muted">{key}: </span>{String(node.properties[key])}</p>)}
        {expert && <div className="record-expertise"><h4>Why this person is relevant</h4><ul>{expert.ranking_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><p className="small muted">Returned score: {expert.score}. Team membership does not establish personal ownership.</p></div>}
        {links.length > 0 && <details className="record-connections"><summary>{links.length} verified connections</summary><ul>{links.map(edge => <li key={edge.id}><button onClick={() => { const other = result!.graph.nodes.find(n => n.id === (edge.source === node.id ? edge.target : edge.source)); if (other) onNode(other); }}>{traceSentence(edge, result!.graph.nodes)}</button></li>)}</ul></details>}
        {sources.length > 0 && <details><summary>{sources.length} related sources</summary><p className="small muted">Associated with this record or a returned connection. This does not assign a new rationale citation.</p>{sources.map(source => <button className="source-row" key={source.id} onClick={() => onSource(source)}>{source.title}</button>)}</details>}
        {!links.length && !sources.length && <p className="small muted">No additional connections or textual sources returned for this record.</p>}
        <div className="record-actions"><button className="button small" onClick={() => onNode(node)}>View details</button><button className="button small" onClick={() => onGraph(node)}>Explore relationships</button>
          <button className="button small" onClick={() => onAsk(page === 'people' ? `What evidence explains ${traceEntityName(node, node.id)}’s involvement?` : `What evidence supports ${traceEntityName(node, node.id)}?`)}>Ask about this {node.type.toLowerCase()}</button>
          {page === 'services' && <button className="button small" onClick={() => onAsk(`What depends on ${traceEntityName(node, node.id)}?`)}>Analyze possible impact</button>}
          {sequence && <button className="button small" onClick={() => onTrace(sequence)}>Watch Evidence Trace</button>}</div>
      </article>;
    })}</div> : <div className="workspace-empty"><h3>No {PAGE_LABELS[page].toLowerCase()} in this answer</h3><p>Ask a question or open a saved message to explore its available evidence.</p></div>}
    <button className="button" onClick={onChat}>Return to chat</button>
  </section>;
}
