import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, ArrowUp, BookOpen, Box, Building2, Check, CircleAlert, Clock3, FileText, GitBranch, History, List, LoaderCircle, Maximize2, MessageSquare, Network, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Pencil, Plug, Plus, Search, Users, X } from 'lucide-react';
import { analyzeImpact, ApiError, askQuestion, findExperts, getHealth } from './api';
import type { ExpertInput, GraphNode, Health, ImpactFinding, ImpactInput, QueryResponse, Source } from './types';
import ExpertResults, { ExpertControls } from './components/ExpertResults';
import { EXPERT_QUESTION, isExpertResponse, routeExpertQuestion } from './experts';
import ImpactResults, { ImpactControls } from './components/ImpactResults';
import { IMPACT_QUESTION, IMPACT_TARGETS, isImpactResponse, routeImpactQuestion } from './impact';
import Inspector, { SourceRow } from './components/Inspector';
import { dateLabel, timestampOrder } from './format';
import EntityIcon from './components/EntityIcon';
import WorkspacePanel from './components/WorkspacePanel';
import { greetingText, NAME_KEY, normalizeName, readPreference, sessionGreeting, useSidebarPreference, writePreference } from './preferences';

const PRIMARY_QUESTION = 'Why does Payment Service use Redis?';
const EvidenceGraph = lazy(() => import('./components/EvidenceGraph'));
const SUGGESTIONS = ['Why was Redis introduced?', 'What evidence supports the Redis decision?', 'Why was Redis chosen for Payment Service?'];
type EvidenceTab = 'graph' | 'timeline' | 'sources' | 'relationships';
type View = 'chat' | 'graph';
type HistoryEntry = { question: string; result: QueryResponse; impactRequest: ImpactInput | null; expertRequest: ExpertInput | null };

function AnswerText({ result, onSource }: { result: QueryResponse; onSource: (source: Source) => void }) {
  const sources = new Map(result.sources.map(s => [s.id, s]));
  return <div className="answer-text">{result.answer.split('\n\n').map((paragraph, index) =>
    <p key={index}>{paragraph.split(/(\[[^\]]+\])/g).map((part, i) => {
      const source = sources.get(part.slice(1, -1));
      return source ? <button className="citation" key={i} onClick={() => onSource(source)}>{source.id.slice(source.id.indexOf(':') + 1)}</button> : part;
    })}</p>)}</div>;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [impactRequest, setImpactRequest] = useState<ImpactInput | null>(null);
  const [expertRequest, setExpertRequest] = useState<ExpertInput | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [highlightedFinding, setHighlightedFinding] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [view, setView] = useState<View>('chat');
  const [tab, setTab] = useState<EvidenceTab>('graph');
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [mobileInspector, setMobileInspector] = useState(false);
  const [narrow, setNarrow] = useState(() => window.matchMedia?.('(max-width: 1100px)').matches ?? false);
  const [leftCollapsed, setLeftCollapsed] = useSidebarPreference('left');
  const [rightCollapsed, setRightCollapsed] = useSidebarPreference('right');
  const [greeting] = useState(() => sessionGreeting());
  const [name, setName] = useState(() => normalizeName(readPreference(NAME_KEY) ?? ''));
  const [nameDraft, setNameDraft] = useState(name);
  const [editingName, setEditingName] = useState(false);
  const greetingCopy = greetingText(greeting, name);
  const [graphSearch, setGraphSearch] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inspectorTrigger = useRef<HTMLElement | null>(null);
  const inFlight = useRef(false);
  const refreshHealth = useCallback(() => {
    void getHealth().then(data => { setHealth(data); setHealthError(false); })
      .catch(() => { setHealth(null); setHealthError(true); });
  }, []);
  useEffect(refreshHealth, [refreshHealth]);
  useEffect(() => {
    const media = window.matchMedia?.('(max-width: 1100px)');
    if (!media) return;
    const change = () => { setNarrow(media.matches); if (!media.matches) { setMobileNav(false); setMobileInspector(false); } };
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (editingName) { setEditingName(false); return; }
        if (mobileNav) { setMobileNav(false); return; }
        if (selectedNode || selectedSource || mobileInspector) {
          setSelectedSource(null); setSelectedNode(null); setMobileInspector(false); setRightCollapsed(true);
          inspectorTrigger.current?.focus({ preventScroll: true });
        }
      }
    }
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [editingName, mobileNav, selectedNode, selectedSource, mobileInspector, setRightCollapsed]);

  const rememberInspectorTrigger = useCallback(() => {
    const target = document.activeElement as HTMLElement | null;
    if (!target?.closest('#details-panel')) inspectorTrigger.current = target;
  }, []);
  const selectSource = useCallback((source: Source) => { rememberInspectorTrigger(); setSelectedSource(source); setSelectedNode(null); setRightCollapsed(false); setMobileInspector(true); }, [setRightCollapsed, rememberInspectorTrigger]);
  const selectNode = useCallback((node: GraphNode) => { rememberInspectorTrigger(); setSelectedNode(node); setSelectedSource(null); setRightCollapsed(false); setMobileInspector(true); }, [setRightCollapsed, rememberInspectorTrigger]);
  function clearSelection() { setSelectedNode(null); setSelectedSource(null); setHighlightedPath([]); setHighlightedFinding(undefined); }
  async function submit(value: string, impactOverride?: ImpactInput, expertOverride?: ExpertInput) {
    const text = value.trim();
    if (!text || inFlight.current) return;
    inFlight.current = true;
    setLoading(true); setQuestion(text); setInput(text); setResult(null); setError(null);
    setView('chat'); clearSelection(); setTab('graph');
    const expert = impactOverride ? null : expertOverride ?? routeExpertQuestion(text);
    const impact = expert ? null : impactOverride ?? routeImpactQuestion(text);
    setImpactRequest(impact); setExpertRequest(expert);
    try {
      const response = expert ? await findExperts(expert) : impact ? await analyzeImpact(impact) : await askQuestion(text);
      setResult(response); setInput('');
      setHistory(previous => [{ question: text, result: response, impactRequest: impact, expertRequest: expert }, ...previous.filter(h => h.question !== text)].slice(0, 6));
    } catch (cause) { setError(cause instanceof ApiError ? cause : new ApiError('Something went wrong. Please retry.')); }
    finally { inFlight.current = false; setLoading(false); refreshHealth(); }
  }
  function newChat() {
    if (loading) return;
    setResult(null); setQuestion(''); setInput(''); setError(null); setView('chat'); setImpactRequest(null); setExpertRequest(null); clearSelection();
    inputRef.current?.focus();
  }
  function onSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }
  const active = Boolean(question || result || loading || error);
  const fixture = result?.metadata.graph_mode === 'fixture' || health?.graph_mode === 'fixture';
  const graphAvailable = Boolean(result?.graph.nodes.length);
  function highlightImpact(finding: ImpactFinding) {
    const node = result?.graph.nodes.find(n => n.id === finding.service_id);
    if (node) selectNode(node);
    setHighlightedFinding(finding.service_id);
    setHighlightedPath(result?.graph.edges.filter(e => finding.path_edges.some(p => p.source === e.source && p.type === e.type && p.target === e.target)).map(e => e.id) ?? []);
    setTab('graph');
  }
  const matchedNodes = result?.graph.nodes.filter(n => `${n.label} ${n.id} ${n.type}`.toLowerCase().includes(graphSearch.toLowerCase())) ?? [];
  const inspectorOpen = narrow ? mobileInspector : !rightCollapsed;
  function closeInspector() { clearSelection(); setRightCollapsed(true); setMobileInspector(false); inspectorTrigger.current?.focus({ preventScroll: true }); }
  function toggleInspector() { if (narrow) setMobileInspector(!mobileInspector); else setRightCollapsed(!rightCollapsed); }
  const composer = <div className={`composer-area ${active ? 'docked-composer' : 'welcome-composer'}`}><form onSubmit={onSubmit} className="composer">
    <MessageSquare size={22} className="composer-icon" aria-hidden="true" /><label className="sr-only" htmlFor="question-input">Ask about your company knowledge</label>
    <textarea id="question-input" ref={inputRef} value={input} disabled={loading} maxLength={2000} rows={Math.min(4, input.split('\n').length)}
      onChange={event => setInput(event.target.value)} placeholder={active ? 'Ask a follow-up question…' : 'Ask about your company knowledge…'}
      onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(input); } }} />
    <span className="composer-workspace">NovaPay</span>
    <button className="submit-button" disabled={loading || !input.trim()} aria-label="Ask question" type="submit">{loading ? <LoaderCircle className="spin" size={23} /> : <ArrowUp size={25} />}</button>
  </form><p className="composer-hint">Enter to ask · Shift + Enter for a new line<span>Answers grounded in evidence</span></p></div>;

  return <div className={`app-shell ${view === 'graph' ? 'graph-view' : ''} ${leftCollapsed ? 'left-collapsed' : ''} ${rightCollapsed ? 'right-collapsed' : ''}`}>
    {(mobileNav || narrow && mobileInspector) && <button className="drawer-backdrop" tabIndex={-1} aria-label="Dismiss panel" onClick={() => { setMobileNav(false); setMobileInspector(false); }} />}
    <WorkspacePanel id="navigation-panel" modal={mobileNav} className={`sidebar ${mobileNav ? 'mobile-open' : ''}`} label="Main navigation">
      <div className="brand"><img src="/weave-knot.svg" alt="" /><div><span>Weave</span><small>Company Intelligence</small></div>
        <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={19} /></button>
        <button className="icon-button sidebar-toggle" title={leftCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-label={leftCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!leftCollapsed} aria-controls="navigation-panel" onClick={() => setLeftCollapsed(!leftCollapsed)}>{leftCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}</button></div>
      <nav>
        <button aria-label="Chat" title="Chat" className={`nav-item ${view === 'chat' ? 'active' : ''}`} onClick={() => { setView('chat'); setMobileNav(false); }}><MessageSquare /><span className="nav-label">Chat</span></button>
        <button aria-label="Knowledge Graph" className={`nav-item ${view === 'graph' ? 'active' : ''}`} disabled={!graphAvailable || loading} title={!graphAvailable ? 'Ask a question to explore its evidence graph' : 'Knowledge Graph'} onClick={() => { setView('graph'); setMobileNav(false); }}><Network /><span className="nav-label">Knowledge Graph</span></button>
        {[[FileText, 'Decisions'], [Box, 'Services'], [Users, 'People'], [History, 'Changes'], [Plug, 'Connectors']].map(([Icon, name]) => {
          const NavIcon = Icon as typeof FileText;
          return <button className="nav-item future" aria-label={`${String(name)} — coming later`} disabled key={String(name)} title={`${String(name)} — coming later`}><NavIcon /><span className="nav-label">{String(name)}</span><span className="later-nav">Later</span></button>;
        })}
      </nav>
      <div className="sidebar-section"><p className="section-label">Workspace</p><div className="workspace-row"><Building2 size={21} />NovaPay<span className="tiny-tag">{fixture ? 'Demo' : 'Local'}</span></div></div>
      {history.length > 0 && <div className="sidebar-section history-section"><div className="panel-heading"><p className="section-label">Recent questions</p><button className="icon-button" disabled={loading} aria-label="New question" onClick={newChat}><Plus size={16} /></button></div>
        {history.map(entry => <button key={entry.question} className={`history-item ${question === entry.question ? 'active' : ''}`} disabled={loading} onClick={() => {
          setQuestion(entry.question); setResult(entry.result); setImpactRequest(entry.impactRequest); setExpertRequest(entry.expertRequest); setError(null); setView('chat'); setInput(''); clearSelection();
        }}><Clock3 size={17} /><span>{entry.question}<small>This session</small></span></button>)}
      </div>}
      <div className="sidebar-footer"><button className="icon-button" aria-label="Personalize greeting" title="Personalize greeting" aria-expanded={editingName} aria-controls="name-preference" onClick={() => { setNameDraft(name); setEditingName(!editingName); setLeftCollapsed(false); if (narrow) setMobileNav(true); }}><Pencil size={18} /></button><div className="profile-copy"><strong>{name || 'Local workspace'}</strong><small>Personalize your greeting</small></div></div>
      {editingName && <form id="name-preference" className="name-preference" onSubmit={event => { event.preventDefault(); const clean = normalizeName(nameDraft); setName(clean); writePreference(NAME_KEY, clean); setEditingName(false); }}>
        <label htmlFor="preferred-name">Preferred name <span className="muted">(optional)</span></label>
        <input id="preferred-name" value={nameDraft} maxLength={32} autoComplete="given-name" onChange={event => setNameDraft(event.target.value)} />
        <small>Up to 32 characters. Saved on this browser.</small><div><button className="button primary" type="submit">Save</button><button className="button" type="button" onClick={() => { setName(''); setNameDraft(''); writePreference(NAME_KEY, ''); setEditingName(false); }}>Clear name</button></div>
      </form>}
    </WorkspacePanel>

    <main inert={mobileNav || narrow && mobileInspector} className={`main-workspace ${active ? 'has-answer' : 'welcome-workspace'}`}>
      <header className="page-header"><div className="header-heading"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNav} aria-controls="navigation-panel" onClick={() => setMobileNav(true)}><List size={22} /></button>
        {active && <div><h1>{view === 'graph' ? 'Knowledge Graph' : 'Chat'}</h1><p>{view === 'graph' ? 'Explore the returned evidence for this question.' : 'Ask questions about your company’s systems, decisions, people and documents.'}</p></div>}</div>
        <div className="header-actions">{active && <span className="workspace-chip"><Building2 size={16} />NovaPay</span>}
        {(!inspectorOpen || narrow) && <button className="icon-button" title="Expand details panel" aria-label="Expand details panel" aria-controls="details-panel" aria-expanded={inspectorOpen} onClick={toggleInspector}><PanelRightOpen size={20} /></button>}</div>
      </header>
      {fixture && <div className="mode-banner" role="status"><span className="status-dot" />Development fixture <span>· Synthetic NovaPay evidence</span></div>}

      <div className={`workspace-scroll ${!active ? 'home-scroll' : ''}`}><div className={!active ? 'home-stack' : 'conversation-stack'}>
      {!active ? <section className="welcome-content">
        <div className="welcome-waves" aria-hidden="true"><svg viewBox="0 0 900 280" preserveAspectRatio="none">{Array.from({ length: 22 }, (_, i) => <path key={i} d={`M-80 ${40 + i * 4} C180 ${-180 + i * 9} 340 ${440 - i * 5} 940 ${-90 + i * 7}`} />)}</svg></div>
        <img className="welcome-mark" src="/weave-knot.svg" alt="Weave" />
        <h1>{greetingCopy.title}</h1><p className="welcome-subtitle">{greetingCopy.subtitle}</p>
        <div className="feature-grid">
          <button className="feature-card" onClick={() => void submit(PRIMARY_QUESTION)}><span className="feature-icon"><FileText /></span><span><strong>Decision Trace</strong><small>Understand why <br />things happened</small></span><ArrowRight size={19} /></button>
          <button className="feature-card" onClick={() => void submit(EXPERT_QUESTION)}><span className="feature-icon"><Users /></span><span><strong>Expert Finder</strong><small>See who knows <br />what and why</small></span><ArrowRight size={19} /></button>
          <button className="feature-card" onClick={() => void submit(IMPACT_QUESTION)}><span className="feature-icon"><GitBranch /></span><span><strong>Impact Analysis</strong><small>Explore what would <br />be affected</small></span><ArrowRight size={19} /></button>
          <div className="feature-card unavailable-feature"><span className="feature-icon"><History /></span><span><strong>Knowledge Freshness</strong><small>Find information <br />that needs review</small></span><span className="later-tag">Coming later</span></div>
        </div>
        <div className="try-label"><span />Try asking<span /></div>
        <div className="suggestions"><button onClick={() => void submit(SUGGESTIONS[0])}>{SUGGESTIONS[0]}</button><button onClick={() => void submit(PRIMARY_QUESTION)}>Why does Payment Service use Redis?</button></div>
      </section> : <section className="conversation" aria-label="Question and answer">
        {view === 'chat' && <div className="question-message"><div>{question}</div><span className="avatar small-avatar">Y</span></div>}
        {impactRequest && <ImpactControls key={`${impactRequest.entity_id}/${impactRequest.max_depth}`} request={impactRequest} disabled={loading} onRun={request => {
          const label = IMPACT_TARGETS.find(([id]) => id === request.entity_id)?.[1] ?? request.entity_id;
          void submit(`What would be affected if ${label} changed?`, request);
        }} />}
        {expertRequest && <ExpertControls key={`${expertRequest.query}/${expertRequest.limit}`} request={expertRequest} disabled={loading} onRun={request => void submit(request.query, undefined, request)} />}
        {loading && <div className="loading-card" role="status"><img src="/weave-knot.svg" alt="" /><div><strong>Following the evidence…</strong><p>{expertRequest ? 'Following contribution paths and retrieving their sources.' : impactRequest ? 'Following bounded dependencies and retrieving their sources.' : 'Tracing the decision and retrieving its sources.'}</p><div className="skeleton" /><div className="skeleton short" /></div></div>}
        {error && <div className="error-card" role="alert"><CircleAlert size={24} /><div><h2>{error.code === 'GRAPH_UNAVAILABLE' ? 'The knowledge graph is not ready' : 'We couldn’t complete this question'}</h2><p>{error.message}</p><button className="button" onClick={() => void submit(question, impactRequest ?? undefined, expertRequest ?? undefined)}>Try again <ArrowRight size={15} /></button></div></div>}
        {result && <>
          {view === 'chat' && <div className="answer-row"><img className="answer-mark" src="/weave-knot.svg" alt="Weave" /><article className="answer-card">
            <div className="answer-meta"><span className={`support-badge ${result.support_status}`}>
              {result.support_status === 'supported' ? <Check size={13} /> : <CircleAlert size={13} />}{result.support_status.replaceAll('_', ' ')}</span>
              <span className="small muted">{result.sources.length} sources{fixture ? ' · Demo data' : ''}</span></div>
            {isExpertResponse(result) ? <>{result.metadata.generation === 'openrouter' && <AnswerText result={result} onSource={selectSource} />}<ExpertResults result={result} onNode={selectNode} onSource={selectSource} /></> : isImpactResponse(result) ? <>{result.metadata.generation === 'openrouter' && <AnswerText result={result} onSource={selectSource} />}<ImpactResults result={result} onNode={selectNode} onSource={selectSource} onPath={highlightImpact} highlightedId={highlightedFinding} /></> : <AnswerText result={result} onSource={selectSource} />}
          </article></div>}
          {view === 'graph' && <div className="graph-toolbar"><label className="graph-search"><Search size={17} /><input value={graphSearch} onChange={event => setGraphSearch(event.target.value)} placeholder="Find an entity in this evidence graph…" aria-label="Find graph entity" /></label><button className="button" onClick={() => { setView('chat'); setGraphSearch(''); }}>Back to answer</button></div>}
          {view === 'graph' && graphSearch && <div className="search-results">{matchedNodes.length ? matchedNodes.map(node => <button className="button" key={node.id} onClick={() => selectNode(node)}><EntityIcon type={node.type} size={16} />{node.label}</button>) : <p>No matching entities in this evidence.</p>}</div>}
          <section className="evidence-card">
            <div className="evidence-tabs" role="tablist" aria-label="Evidence views">{([
              ['graph', Network, 'Evidence graph'], ['timeline', Clock3, 'Timeline'], ['sources', FileText, `Key sources (${result.sources.length})`], ['relationships', List, 'Relationships'],
            ] as const).map(([id, Icon, label]) => <button key={id} role="tab" id={`tab-${id}`} tabIndex={tab === id ? 0 : -1} aria-selected={tab === id} aria-controls={`panel-${id}`} className={tab === id ? 'active' : ''} onClick={() => setTab(id)} onKeyDown={event => {
              const ids: EvidenceTab[] = ['graph', 'timeline', 'sources', 'relationships'];
              const index = ids.indexOf(id);
              const next = event.key === 'ArrowRight' ? ids[(index + 1) % 4] : event.key === 'ArrowLeft' ? ids[(index + 3) % 4] : event.key === 'Home' ? ids[0] : event.key === 'End' ? ids[3] : null;
              if (next) { event.preventDefault(); setTab(next); document.getElementById(`tab-${next}`)?.focus({ preventScroll: true }); }
            }}><Icon size={17} />{label}</button>)}</div>
            <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
              <div hidden={tab !== 'graph'}><Suspense fallback={<div className="graph-empty" role="status">Loading evidence graph…</div>}><EvidenceGraph graph={result.graph} onSelect={selectNode} selectedId={selectedNode?.id} highlightedEdgeIds={highlightedPath} expanded={view === 'graph'} visible={tab === 'graph'} /></Suspense></div>
              {tab === 'timeline' && <div className="timeline">{result.sources.length ? [...result.sources].sort((a, b) => timestampOrder(a.timestamp) - timestampOrder(b.timestamp)).map(source =>
                <button className="timeline-event" key={source.id} onClick={() => selectSource(source)}><span className={`round-icon type-${source.type.toLowerCase()}`}><EntityIcon type={source.type} /></span><span><small>{dateLabel(source.timestamp)}</small><strong>{source.title}</strong><p>{source.snippet}</p></span></button>) : <p>No dated sources are available.</p>}</div>}
              {tab === 'sources' && <div className="source-list">{result.sources.length ? result.sources.map(source => <SourceRow source={source} key={source.id} onClick={() => selectSource(source)} />) : <p>No source records were returned.</p>}</div>}
              {tab === 'relationships' && <div className="relationship-table"><table><caption className="sr-only">Directed evidence relationships</caption><thead><tr><th>From</th><th>Relationship</th><th>To</th></tr></thead><tbody>{result.graph.edges.map(edge => <tr key={edge.id}>
                <td><button onClick={() => { const node = result.graph.nodes.find(n => n.id === edge.source); if (node) selectNode(node); }}>{result.graph.nodes.find(n => n.id === edge.source)?.label ?? edge.source}</button></td><td><code>{edge.type}</code><span aria-hidden="true"> →</span></td>
                <td><button onClick={() => { const node = result.graph.nodes.find(n => n.id === edge.target); if (node) selectNode(node); }}>{result.graph.nodes.find(n => n.id === edge.target)?.label ?? edge.target}</button></td></tr>)}</tbody></table>{!result.graph.edges.length && <p>No relationships returned.</p>}</div>}
            </div>
          </section>
          {view === 'chat' && graphAvailable && <div className="answer-actions"><button className="button primary" onClick={() => { setView('graph'); setTab('graph'); }}><Maximize2 size={16} />Explore in graph<ArrowRight size={16} /></button><button className="button" onClick={() => setTab('sources')}><BookOpen size={17} />Inspect sources</button><button className="button" onClick={newChat}><Plus size={17} />New question</button></div>}
          {result.metadata.warnings.filter(w => !w.startsWith('Development fixture')).map(warning => <p key={warning} className="evidence-warning"><CircleAlert size={15} />{warning}</p>)}
        </>}
      </section>}
      {!active && composer}</div></div>
      {active && composer}
    </main>
    <WorkspacePanel id="details-panel" label="Details panel" modal={narrow && inspectorOpen} hidden={!inspectorOpen} className={`right-panel ${narrow && inspectorOpen ? 'drawer-open' : ''}`}>
      <div className="right-panel-toolbar"><span>{selectedNode ? 'Entity details' : selectedSource ? 'Source details' : active ? 'Evidence' : 'Workspace'}</span><button className="icon-button" title="Collapse details panel" aria-label="Collapse details panel" aria-expanded={inspectorOpen} aria-controls="details-panel" onClick={toggleInspector}><PanelRightClose size={20} /></button></div>
      <div className="inspector-scroll" key={selectedNode?.id ?? selectedSource?.id ?? 'overview'}><Inspector result={result} health={health} healthError={healthError} selectedSource={selectedSource} selectedNode={selectedNode} onSource={selectSource} onNode={selectNode} onClose={closeInspector} onRefresh={refreshHealth} /></div>
    </WorkspacePanel>
    <div className="sr-only" aria-live="polite">{result ? `Answer ready. ${result.support_status.replaceAll('_', ' ')}. ${result.sources.length} sources.` : ''}</div>
  </div>;
}
