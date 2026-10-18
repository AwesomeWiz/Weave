import type { ChangeEvidenceReference, ChangeResponse, ExpertEvidence, FreshnessPath, GraphNode, ImpactFinding, Source } from '../types';
import { CHANGE_TOOL_LABELS } from '../change';
import EntityIcon from './EntityIcon';
import { SourceRow } from './Inspector';
import { useState } from 'react';
import type { ReactNode } from 'react';

function ProofDetails({ summary, children }: { summary: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <details className="change-proof" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{summary}</summary>{open && children}
  </details>;
}

export default function ChangeBrief({ result, onNode, onSource, onPath, onEvidence }: {
  result: ChangeResponse; onNode: (node: GraphNode) => void; onSource: (source: Source) => void;
  onPath: (finding: ImpactFinding) => void; onEvidence: (ref: ChangeEvidenceReference) => void;
}) {
  const { data } = result;
  const nodes = new Map(result.graph.nodes.map(n => [n.id, n]));
  const sources = new Map(result.sources.map(s => [s.id, s]));
  const sectionNames = ['Proposed Change', 'Historical Context', 'Direct and Downstream Impact', 'Relevant Reviewers',
    'Known Facts and Potential Risks', 'Recommended Validation', 'Current Knowledge Freshness', 'Documents to Review if Change Proceeds', 'Supporting Evidence'];
  function entity(id: string) {
    const n = nodes.get(id);
    return n ? <button className="impact-entity" onClick={() => onNode(n)}><EntityIcon type={n.type} size={16} />{n.label}</button> : <code>{id}</code>;
  }
  function citations(ids: string[]) {
    return <span className="change-citations">{ids.map(id => { const source = sources.get(id); return source
      ? <button className="citation" key={id} onClick={() => onSource(source)}>{id}</button> : null; })}</span>;
  }
  function narrative(text: string) {
    return text.split('\n\n').map((paragraph, i) => <p key={i}>{paragraph.split(/(\[[^\]]+\])/g).map((part, index) => {
      const source = sources.get(part.slice(1, -1));
      return source ? <button className="citation" key={index} onClick={() => onSource(source)}>{source.id}</button> : part;
    })}</p>);
  }
  function directed(path: FreshnessPath[]) {
    return <div className="impact-path">{path.map((p, i) => <p key={i}>{entity(p.source)}<span> —{p.type}→ </span>{entity(p.target)}</p>)}</div>;
  }
  function evidence(refs: ChangeEvidenceReference[], label?: string) {
    return refs.map((ref, i) => <ProofDetails key={`${ref.tool}/${i}`} summary={<>{label ?? CHANGE_TOOL_LABELS[ref.tool]} · {ref.edge_ids.length} {ref.edge_ids.length === 1 ? 'relationship' : 'relationships'} · {ref.source_ids.length} citations</>}>
      {ref.edge_ids.length > 0 && <><button className="button small" onClick={() => onEvidence(ref)}>Highlight these relationships</button>
        {directed(ref.edge_ids.flatMap(id => { const e = result.graph.edges.find(e => e.id === id); return e ? [e] : []; }))}</>}
      {citations(ref.source_ids)}
      {!ref.source_ids.length && <p className="small muted">Graph-only evidence; no textual citation assigned.</p>}
    </ProofDetails>);
  }
  function contribution(proof: ExpertEvidence) {
    return <li key={`${proof.category}/${proof.entity_id}`}><p>{proof.category.replaceAll('_', ' ')}: {entity(proof.entity_id)}</p>
      {directed(proof.path)}{citations(proof.source_ids)}
      {!proof.source_ids.length && <p className="small muted">Graph-only contribution evidence; no textual citation assigned.</p>}</li>;
  }
  function impacts(title: string, findings: ImpactFinding[]) {
    return <div className="change-impact-group"><h4>{title}</h4>{findings.length ? findings.map(f => <div className="change-impact" key={f.service_id}>
      <div className="panel-heading"><strong>{entity(f.service_id)}</strong><span className="tiny-tag">Depth {f.impact_depth} · {f.impact_type}</span></div>
      <code>{f.service_id}</code>{directed(f.path_edges)}
      <p className="small muted">Returned owners / teams: {f.owners.length ? f.owners.map(o => <span key={o.id}>{entity(o.id)} </span>) : 'Not returned'}</p>
      <button className="button small" onClick={() => onPath(f)}>Highlight path to {nodes.get(f.service_id)?.label ?? f.service_id}</button>
      {f.source_ids.length ? <p className="small muted">Related historical sources; they do not establish failure propagation. {citations(f.source_ids)}</p>
        : <p className="small muted">Structural graph evidence; no textual propagation evidence returned.</p>}
    </div>) : <p className="muted">No independently validated {title.toLowerCase()} findings returned.</p>}</div>;
  }
  return <div className="change-brief">
    <header className="change-brief-header"><p className="eyebrow">Change Intelligence</p><h2>Change Brief</h2>
      <p className="muted">A proposal review assembled from retrieved evidence. No change or validation has been performed.</p></header>
    {result.metadata.generation === 'openrouter' && <section className="change-section" aria-label="Grounded overview">
      <h3>Grounded overview</h3><p className="small muted">Hosted selection of validated statements. The structured evidence below remains authoritative.</p>
      <div className="change-narrative">{narrative(result.answer)}</div>
    </section>}
    <nav className="change-contents" aria-label="Change Brief sections">{sectionNames.map((name, i) => <a href={`#change-section-${i}`} key={name}>{name}</a>)}</nav>

    <section id="change-section-0" className="change-section" aria-label={sectionNames[0]}><h3>01 <span>Proposed Change</span></h3>
      <p className="change-proposal">{data.proposed_change.requested_change}</p>
      <p className="small muted">Resolution: {data.proposed_change.resolution.replaceAll('_', ' ')}</p>
      <div className="change-targets">{[data.proposed_change.service, data.proposed_change.technology].map(n => n && <span key={n.id}>{entity(n.id)}<code>{n.id}</code></span>)}</div>
      {data.proposed_change.limitation && <p className="change-caution" role="status">{data.proposed_change.limitation}</p>}
    </section>
    <section id="change-section-1" className="change-section" aria-label={sectionNames[1]}><h3>02 <span>Historical Context</span></h3>
      <p className={`support-badge ${data.historical_context.support_status}`}>{data.historical_context.support_status.replaceAll('_', ' ')}</p>
      <div className="change-narrative">{narrative(data.historical_context.summary)}</div>
      {data.historical_context.evidence && evidence([data.historical_context.evidence])}
    </section>
    <section id="change-section-2" className="change-section" aria-label={sectionNames[2]}><h3>03 <span>Direct and Downstream Impact</span></h3>
      <p className="change-caution">Potential impact from stored relationships, within {data.impact.max_depth} hops. This is not a prediction of guaranteed failure.</p>
      <p className="small muted">Impact support: {data.impact.support_status.replaceAll('_', ' ')}. Arrows below retain the stored direction.</p>
      {impacts('Immediate impact', data.impact.direct_impact)}{impacts('Potential downstream impact', data.impact.indirect_impact)}
    </section>
    <section id="change-section-3" className="change-section" aria-label={sectionNames[3]}><h3>04 <span>Relevant Reviewers</span></h3>
      <p className="small muted">Existing evidence rankings, without rescoring. Historical contributions do not establish current personal ownership.</p>
      {!data.reviewers.length && <p>No independently validated reviewer rankings returned. This does not establish that no reviewers exist.</p>}
      {data.reviewers.map((person, i) => <div className="change-reviewer" key={person.person.id}>
        <div className="panel-heading"><h4>{i + 1}. {entity(person.person.id)}</h4><span className="tiny-tag">Score {person.score}</span></div>
        <p className="small muted"><code>{person.person.id}</code>{person.person.role && ` · ${person.person.role}`}</p>
        <p>{person.ownership_classification === 'team_membership_with_team_owned_service' ? 'Team member of a team that owns the service. Personal ownership is not established.' : 'No current personal ownership evidence returned.'}</p>
        <p className="small muted">Evidence-backed reasons</p><ul className="change-reasons">{person.ranking_reasons.map(r => <li key={r}>{r}</li>)}</ul>
        <ProofDetails summary={<>Team ownership evidence ({person.ownership.length})</>}>{person.ownership.length
          ? <ul>{person.ownership.map(contribution)}</ul> : <p>No team ownership evidence returned.</p>}</ProofDetails>
        <ProofDetails summary={<>Historical expertise ({person.historical_contributions.length})</>}><ul>{person.historical_contributions.map(contribution)}</ul>
          {!person.historical_contributions.length && <p>No historical contributions returned.</p>}</ProofDetails>
      </div>)}
    </section>
    <section id="change-section-4" className="change-section" aria-label={sectionNames[4]}><h3>05 <span>Known Facts and Potential Risks</span></h3>
      {!data.risks.length && <p>No evidence-backed facts or risk recommendations established for this proposal.</p>}
      {data.risks.map((risk, i) => <div className={`change-risk ${risk.classification.toLowerCase()}`} key={i}>
        <span className="change-classification">{risk.classification.replaceAll('_', ' ')}</span><p>{risk.description}</p>
        <p className="small muted">{risk.uncertainty}</p>{citations([...new Set(risk.evidence.flatMap(r => r.source_ids))])}{evidence(risk.evidence)}
      </div>)}
    </section>
    <section id="change-section-5" className="change-section" aria-label={sectionNames[5]}><h3>06 <span>Recommended Validation</span></h3>
      <p className="change-caution">Recommended actions only. These checks have not been performed.</p>
      <ol className="change-validation">{data.validation_steps.map((step, i) => <li key={i}><p>{step.description}</p><span className="small muted">Recommendation · Not performed</span>{evidence(step.evidence)}</li>)}</ol>
      {!data.validation_steps.length && <p>No evidence-constrained validation steps available.</p>}
    </section>
    <section id="change-section-6" className="change-section change-current" aria-label={sectionNames[6]}><h3>07 <span>Current Knowledge Freshness</span></h3>
      <p>Existing review recommendations based on actual document and later-change timestamps. They do not establish that a document is wrong.</p>
      {!data.current_freshness_findings.length && <p className="muted">No current review findings established. This does not prove the documentation is current.</p>}
      {data.current_freshness_findings.map(f => <div className="change-document" key={f.document_id}>
        <div className="panel-heading"><h4>{entity(f.document_id)}</h4><span className="tiny-tag">Review recommended</span></div><code>{f.document_id}</code>
        <p className="small">Document updated: <time dateTime={f.updated_at}>{f.updated_at}</time></p><p>{f.reason}</p>{citations(f.source_ids)}
        {!f.source_ids.length && <p className="small muted">Document excerpt unavailable; graph association retained.</p>}
        <ProofDetails summary="Document association and later changes">{directed(f.document_path)}
          {f.triggers.map(t => <div key={t.id}><p>{t.type}: {entity(t.id)} <code>{t.id}</code></p><time className="small" dateTime={t.timestamp}>{t.timestamp}</time>
            {directed(t.path)}{citations(t.source_ids)}{!t.source_ids.length && <p className="small muted">Graph-only change evidence; no textual citation established.</p>}</div>)}
        </ProofDetails>
      </div>)}
    </section>
    <section id="change-section-7" className="change-section change-conditional" aria-label={sectionNames[7]}><h3>08 <span>Documents to Review if Change Proceeds</span></h3>
      <p className="change-condition">If this change is approved and implemented</p><p>Conditional future review, separate from current freshness. A recommendation here does not mean a document is currently stale.</p>
      {!data.documents_to_review_if_change_proceeds.length && <p className="muted">No documents with validated conditional review associations returned.</p>}
      {data.documents_to_review_if_change_proceeds.map(d => <div className="change-document" key={d.document.id}>
        <h4>{entity(d.document.id)}</h4><code>{d.document.id}</code><p>{d.reason}</p>{evidence(d.evidence, 'Service-document association')}
      </div>)}
    </section>
    <section id="change-section-8" className="change-section" aria-label={sectionNames[8]}><h3>09 <span>Supporting Evidence</span></h3>
      <p className="small muted">Each capability retains its own evidence and support status.</p>
      <dl className="change-support">{Object.entries(data.tool_support).map(([tool, state]) => <div key={tool}>
        <dt>{CHANGE_TOOL_LABELS[tool as keyof typeof CHANGE_TOOL_LABELS]}</dt><dd>{state.support_status.replaceAll('_', ' ')} · {state.state}</dd>
      </div>)}</dl>
      {result.sources.length ? result.sources.map(s => <SourceRow key={s.id} source={s} onClick={() => onSource(s)} />) : <p>No supporting textual sources were retrieved. Graph-only evidence is labeled above.</p>}
      {data.limitations.length > 0 && <div className="change-limitations"><h4>Evidence limitations</h4><ul>{data.limitations.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
    </section>
  </div>;
}
