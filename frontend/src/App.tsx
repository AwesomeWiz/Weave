import { lazy, Suspense, useCallback, useEffect, useRef, useState, useMemo } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, ArrowUp, BookOpen, Box, Building2, Check, CircleAlert, Clock3, FileText, GitBranch, History, List, LoaderCircle, Maximize2, MessageSquare, Network, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Pencil, Plus, Search, Users, X } from 'lucide-react';
import AnswerContent from './components/AnswerContent';
import { analyzeImpact, ApiError, askQuestion, analyzeChange, checkFreshness, findExperts, getHealth } from './api';
import type { ChangeEvidenceReference, ExpertInput, FreshnessInput, GraphNode, Health, ImpactFinding, ImpactInput, QueryResponse, Source, TraceSequence } from './types';
import TracePlayer from './components/TracePlayer';
import { traceSequences } from './traceValidation';
import { preferredTrace } from './tracePresentation';
import type { TraceClock } from './traceClock';
import ChangeBrief from './components/ChangeBrief';
import { CHANGE_QUESTION, changeGraphFocus, isChangeResponse, routeChangeQuestion } from './change';
import FreshnessResults, { FreshnessControls } from './components/FreshnessResults';
import { FRESHNESS_QUESTION, isFreshnessResponse, routeFreshnessQuestion } from './freshness';
import ExpertResults, { ExpertControls } from './components/ExpertResults';
import { EXPERT_QUESTION, isExpertResponse, routeExpertQuestion } from './experts';
import ImpactResults, { ImpactControls } from './components/ImpactResults';
import { IMPACT_QUESTION, IMPACT_TARGETS, isImpactResponse, routeImpactQuestion } from './impact';
import Inspector, { SourceRow } from './components/Inspector';
import { dateLabel, timestampOrder } from './format';
import EntityIcon from './components/EntityIcon';
import WorkspacePanel from './components/WorkspacePanel';
import ConversationList from './components/ConversationList';
import WorkspacePage from './components/WorkspacePage';
import { PAGE_LABELS } from './workspace';
import { useChatWorkspace } from './useChatWorkspace';
import type { ChatRepository } from './chatStorage';
import type { ChatTurn, ChatUI, WorkspacePage as Page } from './workspace';
import { greetingText, NAME_KEY, normalizeName, readPreference, sessionGreeting, useSidebarPreference, writePreference } from './preferences';

const PRIMARY_QUESTION = 'Why does Payment Service use Redis?';
const EvidenceGraph = lazy(() => import('./components/EvidenceGraph'));
type EvidenceTab = 'graph' | 'timeline' | 'sources' | 'relationships';

function AnswerText({ result, onSource }: { result: QueryResponse; onSource: (source: Source) => void }) {
  return <AnswerContent text={result.answer} sources={result.sources} onSource={onSource} />;
}
function OriginalAnswer({ result, onSource }: { result: QueryResponse; onSource: (source: Source) => void }) {
  const [open, setOpen] = useState(false);
  return <details className="original-answer" onToggle={event => setOpen(event.currentTarget.open)}><summary>Read the original full answer</summary>{open && <AnswerText result={result} onSource={onSource} />}</details>;
}

export default function App({ repository }: { repository?: ChatRepository } = {}) {
  const workspace = useChatWorkspace(repository);
  const chat = workspace.conversation;
  const ui = chat.ui;
  const turn = chat.turns.find(t => t.id === ui.selectedTurnId);
  const question = turn?.question ?? '';
  const result = turn?.result ?? null;
  const [page, setPage] = useState<Page>('chat');
  const sequences = useMemo(() => traceSequences(result), [result]);
  const traceSequence = sequences.find(s => s.id === ui.trace?.sequenceId);
  const traceStep = page === 'chat' && ui.view === 'graph' && ui.tab === 'graph' && traceSequence && ui.trace
    ? traceSequence.steps[ui.trace.step] : undefined;
  const traceGraph = useMemo(() => {
    if (!traceSequence || !result) return null;
    const edges = new Set(traceSequence.steps.map(s => s.edge_id));
    const nodes = new Set(traceSequence.steps.flatMap(s => [s.source, s.target]));
    return { nodes: result.graph.nodes.filter(n => nodes.has(n.id)), edges: result.graph.edges.filter(e => edges.has(e.id)) };
  }, [traceSequence, result]);
  const impactRequest = turn?.request.impact ?? null;
  const expertRequest = turn?.request.expert ?? null;
  const freshnessRequest = turn?.request.freshness ?? null;
  const loading = chat.turns.some(t => t.status === 'pending');
  const error = turn?.error ? new ApiError(turn.error.message, turn.error.code) : null;
  const [traceClock, setTraceClock] = useState<TraceClock | null>(null);
  const [watchRequest, setWatchRequest] = useState<string | null>(null);
  const traceOwner = `${chat.id}/${turn?.id}/${traceSequence?.id}`;
  const attachMotion = useCallback((clock: TraceClock) => {
    setTraceClock(clock);
    return () => setTraceClock(current => current === clock ? null : current);
  }, []);
  const watchStarted = useCallback(() => setWatchRequest(null), []);
  const { input, graphScope, highlightedPath, view, tab, graphSearch } = ui;
  const highlightedFinding = ui.highlightedFinding ?? undefined;
  const selectedSource = result?.sources.find(s => s.id === ui.selectedSourceId) ?? null;
  const selectedNode = result?.graph.nodes.find(n => n.id === ui.selectedNodeId) ?? null;
  const inspectedNode = traceStep ? selectedNode && traceStep.evidence.node_ids.includes(selectedNode.id) ? selectedNode
    : result?.graph.nodes.find(n => n.id === traceStep.traversal_to) ?? null : selectedNode;
  const inspectedSource = traceStep ? null : selectedSource;
  const rightCollapsed = !ui.detailsOpen;
  function field<K extends keyof ChatUI>(key: K, value: ChatUI[K]) { workspace.ui(chat.id, { [key]: value }); }
  const setInput = (v: string) => field('input', v);
  const setGraphScope = (v: ChatUI['graphScope']) => field('graphScope', v);
  const setHighlightedPath = (v: string[]) => field('highlightedPath', v);
  const setHighlightedFinding = (v: string | undefined) => field('highlightedFinding', v ?? null);
  const setView = (v: ChatUI['view']) => field('view', v);
  const setTab = (v: EvidenceTab) => field('tab', v);
  const setGraphSearch = (v: string) => field('graphSearch', v);
  const setSelectedSource = (v: Source | null) => field('selectedSourceId', v?.id ?? null);
  const setSelectedNode = (v: GraphNode | null) => field('selectedNodeId', v?.id ?? null);
  const setRightCollapsed = (v: boolean) => { field('detailsOpen', !v); writePreference('weave.sidebar.right', v ? 'collapsed' : 'expanded'); };
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const healthRequest = useRef(0);
  const changeFocus = useMemo(() => result && isChangeResponse(result) ? changeGraphFocus(result) : null, [result]);
  const displayedGraph = changeFocus && graphScope === 'focused' ? changeFocus.graph : result?.graph;
  const [mobileNav, setMobileNav] = useState(false);
  const [mobileInspector, setMobileInspector] = useState(false);
  const [narrow, setNarrow] = useState(() => window.matchMedia?.('(max-width: 1100px)').matches ?? false);
  const [leftCollapsed, setLeftCollapsed] = useSidebarPreference('left');
  const [greeting] = useState(() => sessionGreeting());
  const [name, setName] = useState(() => normalizeName(readPreference(NAME_KEY) ?? ''));
  const [nameDraft, setNameDraft] = useState(name);
  const [editingName, setEditingName] = useState(false);
  const greetingCopy = greetingText(greeting, name);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inspectorTrigger = useRef<HTMLElement | null>(null);
  const refreshHealth = useCallback(() => {
    const request = ++healthRequest.current;
    setHealth(null); setHealthError(false);
    void getHealth().then(data => { if (request === healthRequest.current) { setHealth(data); setHealthError(false); } })
      .catch(() => { if (request === healthRequest.current) { setHealth(null); setHealthError(true); } });
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
          workspace.ui(chat.id, { selectedSourceId: null, selectedNodeId: null, detailsOpen: false });
          writePreference('weave.sidebar.right', 'collapsed'); setMobileInspector(false);
          inspectorTrigger.current?.focus({ preventScroll: true });
        }
      }
    }
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [editingName, mobileNav, selectedNode, selectedSource, mobileInspector, workspace, chat.id]);

  const rememberInspectorTrigger = useCallback(() => {
    const target = document.activeElement as HTMLElement | null;
    if (!target?.closest('#details-panel')) inspectorTrigger.current = target;
  }, []);
  const selectSource = (source: Source) => { rememberInspectorTrigger(); setSelectedSource(source); setSelectedNode(null); setRightCollapsed(false); setMobileInspector(true); };
  const selectNode = (node: GraphNode) => { rememberInspectorTrigger(); setSelectedNode(node); setSelectedSource(null); setRightCollapsed(false); setMobileInspector(true); };
  function clearSelection() { setSelectedNode(null); setSelectedSource(null); setHighlightedPath([]); setHighlightedFinding(undefined); }
  function traceChange(sequence: TraceSequence, step: number, owned = false) {
    if (!sequences.includes(sequence) || !sequence.steps[step]) return;
    const current = sequence.steps[step];
    workspace.ui(chat.id, { trace: { sequenceId: sequence.id, step }, view: 'graph', tab: 'graph', graphScope: 'all',
      highlightedPath: [current.edge_id], selectedNodeId: current.traversal_to, selectedSourceId: null },
    owned && turn && ui.trace ? { turnId: turn.id, sequenceId: ui.trace.sequenceId, step: ui.trace.step } : undefined);
  }
  function openTrace(sequence: TraceSequence, watch = false) {
    traceChange(sequence, 0); setMobileInspector(false);
    workspace.ui(chat.id, { detailsOpen: false });
    setWatchRequest(watch ? `${chat.id}/${turn?.id}/${sequence.id}` : null);
  }
  function closeTrace() { workspace.ui(chat.id, { trace: null, highlightedPath: [] }); }
  async function submit(value: string, impactOverride?: ImpactInput, expertOverride?: ExpertInput, freshnessOverride?: FreshnessInput) {
    const text = value.trim();
    if (!text) return;
    const change = impactOverride || expertOverride || freshnessOverride ? null : routeChangeQuestion(text);
    const freshness = change || impactOverride || expertOverride ? null : freshnessOverride ?? routeFreshnessQuestion(text);
    const expert = change || impactOverride || freshness ? null : expertOverride ?? routeExpertQuestion(text);
    const impact = change || expert || freshness ? null : impactOverride ?? routeImpactQuestion(text);
    const chatId = chat.id;
    const turnId = workspace.start(chatId, text, { change, freshness, expert, impact });
    if (!turnId) return;
    setPage('chat'); setMobileNav(false); setMobileInspector(false);
    try {
      const response = change ? await analyzeChange(change) : freshness ? await checkFreshness(freshness) : expert ? await findExperts(expert) : impact ? await analyzeImpact(impact) : await askQuestion(text);
      workspace.finish(chatId, turnId, response);
    } catch (cause) { const problem = cause instanceof ApiError ? cause : new ApiError('Something went wrong. Please retry.'); workspace.finish(chatId, turnId, null, { code: problem.code, message: problem.message }); }
    finally { refreshHealth(); }
  }
  function newChat() {
    workspace.create(); setPage('chat'); setMobileNav(false); setMobileInspector(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }
  function onSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }
  const active = Boolean(question || result || loading || error);
  const fixture = result ? result.metadata.graph_mode === 'fixture' : health?.graph_mode === 'fixture';
  const graphAvailable = Boolean(result?.graph.nodes.length);
  function highlightImpact(finding: ImpactFinding) {
    const node = result?.graph.nodes.find(n => n.id === finding.service_id);
    if (node) selectNode(node);
    setHighlightedFinding(finding.service_id);
    setHighlightedPath(result?.graph.edges.filter(e => finding.path_edges.some(p => p.source === e.source && p.type === e.type && p.target === e.target)).map(e => e.id) ?? []);
    setTab('graph');
  }
  function showChangeEvidence(ref: ChangeEvidenceReference) {
    field('trace', null);
    setHighlightedPath(ref.edge_ids); setTab('graph'); setView('graph');
    setGraphScope('all'); setSelectedNode(null); setMobileInspector(false);
  }
  function highlightChangeImpact(finding: ImpactFinding) {
    field('trace', null);
    setHighlightedFinding(finding.service_id);
    setHighlightedPath(result?.graph.edges.filter(e => finding.path_edges.some(p => p.source === e.source && p.type === e.type && p.target === e.target)).map(e => e.id) ?? []);
    setTab('graph'); setView('graph'); setSelectedNode(null); setMobileInspector(false);
  }
  const matchedNodes = result?.graph.nodes.filter(n => `${n.label} ${n.id} ${n.type}`.toLowerCase().includes(graphSearch.toLowerCase())) ?? [];
  const inspectorOpen = narrow ? mobileInspector : !rightCollapsed;
  const inspectorResult = traceStep && result ? { ...result,
    graph: { nodes: result.graph.nodes.filter(n => traceStep.evidence.node_ids.includes(n.id)),
      edges: result.graph.edges.filter(e => traceStep.evidence.edge_ids.includes(e.id)) },
    sources: result.sources.filter(s => traceStep.evidence.source_ids.includes(s.id)) } : result;
  function closeInspector() { clearSelection(); setRightCollapsed(true); setMobileInspector(false); inspectorTrigger.current?.focus({ preventScroll: true }); }
  function toggleInspector() { if (narrow) setMobileInspector(!mobileInspector); else setRightCollapsed(!rightCollapsed); }
  function openTurn(item: ChatTurn, source?: Source) {
    workspace.selectTurn(chat.id, item.id, source ? { selectedSourceId: source.id, detailsOpen: true } : {});
    if (source) { setMobileInspector(true); writePreference('weave.sidebar.right', 'expanded'); }
  }
  function otherTurns(items: ChatTurn[]) {
    return view === 'chat' && items.map(item => <article className="thread-turn" key={item.id} aria-label={`Saved message: ${item.question}`}>
      <div className="question-message"><div>{item.question}</div><span className="avatar small-avatar">Y</span></div>
      {item.result ? <div className="answer-card"><div className="answer-meta"><span className={`support-badge ${item.result.support_status}`}>{item.result.support_status.replaceAll('_', ' ')}</span><span className="small muted">{item.result.sources.length} saved sources</span></div>
        <AnswerText result={item.result} onSource={source => openTurn(item, source)} />
        <button className="button small" onClick={() => openTurn(item)}>Open full evidence for this message</button></div>
        : <div><p className="small muted">{item.status === 'pending' ? 'Following the evidence…' : item.error?.message}</p>
          <button className="button small" onClick={() => openTurn(item)}>{item.status === 'pending' ? 'View pending message' : 'Open message to retry'}</button></div>}
    </article>);
  }
  const turnIndex = chat.turns.findIndex(t => t.id === ui.selectedTurnId);
  const composer = <div className={`composer-area ${active ? 'docked-composer' : 'welcome-composer'}`}><form onSubmit={onSubmit} className="composer">
    <MessageSquare size={22} className="composer-icon" aria-hidden="true" /><label className="sr-only" htmlFor="question-input">Ask about your company knowledge</label>
    <textarea id="question-input" ref={inputRef} value={input} disabled={loading || !workspace.ready} maxLength={2000} rows={Math.min(4, input.split('\n').length)}
      onChange={event => setInput(event.target.value)} placeholder={active ? 'Ask a follow-up question…' : 'Ask Weave a question…'}
      onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(input); } }} />
    <button className="submit-button" disabled={loading || !workspace.ready || !input.trim()} aria-label="Ask question" type="submit">{loading ? <LoaderCircle className="spin" size={23} /> : <ArrowUp size={25} />}</button>
  </form><p className="composer-hint">Enter to ask · Shift + Enter for a new line<span>Answers grounded in evidence</span></p></div>;

  return <div className={`app-shell ${view === 'graph' ? 'graph-view' : ''} ${leftCollapsed ? 'left-collapsed' : ''} ${rightCollapsed ? 'right-collapsed' : ''}`}>
    {(mobileNav || narrow && mobileInspector) && <button className="drawer-backdrop" tabIndex={-1} aria-label="Dismiss panel" onClick={() => { setMobileNav(false); setMobileInspector(false); }} />}
    <WorkspacePanel id="navigation-panel" modal={mobileNav} className={`sidebar ${mobileNav ? 'mobile-open' : ''}`} label="Main navigation">
      <div className="brand"><img src="/weave-knot.svg" alt="" /><div><span>Weave</span><small>Company Intelligence</small></div>
        <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={19} /></button>
        <button className="icon-button sidebar-toggle" title={leftCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-label={leftCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!leftCollapsed} aria-controls="navigation-panel" onClick={() => setLeftCollapsed(!leftCollapsed)}>{leftCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}</button></div>
      <div className="workspace-identity"><Building2 size={16} /><span>NovaPay <small>workspace</small></span></div>
      <nav aria-label="Workspace">
        <button className="nav-item new-chat-action" aria-label="New Chat" title="New Chat" disabled={!workspace.ready} onClick={newChat}><Plus /><span className="nav-label">New Chat</span></button>
        <button aria-label="Chat" title="Chat" className={`nav-item ${page === 'chat' && view === 'chat' ? 'active' : ''}`} onClick={() => { setPage('chat'); setView('chat'); setMobileNav(false); }}><MessageSquare /><span className="nav-label">Chat</span></button>
        <button aria-label="Knowledge Graph" className={`nav-item ${page === 'chat' && view === 'graph' ? 'active' : ''}`} disabled={loading} title="Knowledge Graph" onClick={() => { setPage('chat'); setView('graph'); setMobileNav(false); }}><Network /><span className="nav-label">Knowledge Graph</span></button>
        <button className={`nav-item ${page === 'changes' ? 'active' : ''}`} aria-label="Changes" title="Saved Change Analyses" onClick={() => { setPage('changes'); setMobileNav(false); }}><History /><span className="nav-label">Changes</span></button>
        <p className="nav-section-label">Explore</p><div className="workspace-shortcuts">{([[FileText, 'decisions'], [Box, 'services'], [Users, 'people']] as const).map(([Icon, name]) =>
          <button className={`nav-item ${page === name ? 'active' : ''}`} aria-label={PAGE_LABELS[name]} title={PAGE_LABELS[name]} key={name} onClick={() => { setPage(name); setMobileNav(false); }}><Icon /><span className="nav-label">{PAGE_LABELS[name]}</span></button>)}</div>
      </nav>
      {workspace.ready && <ConversationList conversations={workspace.archive.conversations} activeId={chat.id}
        onSelect={id => { workspace.select(id); setPage('chat'); setMobileNav(false); setMobileInspector(false); }}
        onRename={workspace.rename} onDelete={id => { workspace.remove(id); setMobileInspector(false); }} onClear={() => { workspace.clear(); setPage('chat'); setMobileInspector(false); }} />}
      <div className="sidebar-footer"><button className="icon-button" aria-label="Personalize greeting" title="Personalize greeting" aria-expanded={editingName} aria-controls="name-preference" onClick={() => { setNameDraft(name); setEditingName(!editingName); setLeftCollapsed(false); if (narrow) setMobileNav(true); }}><Pencil size={18} /></button><div className="profile-copy"><strong>{name || 'Local workspace'}</strong><small>Personalize your greeting</small></div></div>
      {editingName && <form id="name-preference" className="name-preference" onSubmit={event => { event.preventDefault(); const clean = normalizeName(nameDraft); setName(clean); writePreference(NAME_KEY, clean); setEditingName(false); }}>
        <label htmlFor="preferred-name">Preferred name <span className="muted">(optional)</span></label>
        <input id="preferred-name" value={nameDraft} maxLength={32} autoComplete="given-name" onChange={event => setNameDraft(event.target.value)} />
        <small>Up to 32 characters. Saved on this browser.</small><div><button className="button primary" type="submit">Save</button><button className="button" type="button" onClick={() => { setName(''); setNameDraft(''); writePreference(NAME_KEY, ''); setEditingName(false); }}>Clear name</button></div>
      </form>}
    </WorkspacePanel>

    <main inert={mobileNav || narrow && mobileInspector} className={`main-workspace ${active || page !== 'chat' ? 'has-answer' : 'welcome-workspace'}`}>
      <header className="page-header"><div className="header-heading"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNav} aria-controls="navigation-panel" onClick={() => setMobileNav(true)}><List size={22} /></button>
        {(active || view === 'graph' || page !== 'chat') && <div><h1>{page === 'changes' ? 'Saved Change Analyses' : page !== 'chat' ? PAGE_LABELS[page] : traceStep ? 'Trace Mode' : view === 'graph' ? 'Knowledge Graph' : 'Chat'}</h1><p>{page === 'changes' ? 'Return to assessments saved in this browser.' : page !== 'chat' ? 'Explore the evidence in your selected answer.' : traceStep ? 'Watch how your systems connect, one step at a time.' : view === 'graph' ? 'Connections returned for this question, not the entire company graph.' : 'Answers with sources you can explore.'}</p></div>}</div>
        <div className="header-actions">
        {(!inspectorOpen || narrow) && <button className="icon-button" title="Expand details panel" aria-label="Expand details panel" aria-controls="details-panel" aria-expanded={inspectorOpen} onClick={toggleInspector}><PanelRightOpen size={20} /></button>}</div>
      </header>
      {fixture && <div className="mode-banner" role="status">Sample data — results are for exploration, not live company records.</div>}
      {!workspace.ready && <p className="chat-storage-notice" role="status">Opening local chat history…</p>}
      {workspace.storageWarning && <p className="chat-storage-notice" role="status">{workspace.storageWarning}</p>}

      {page !== 'chat' ? <WorkspacePage page={page} result={result} onNode={selectNode} onSource={selectSource} onChat={() => setPage('chat')}
        conversations={workspace.archive.conversations} onSaved={(chatId, turnId) => { workspace.select(chatId); workspace.selectTurn(chatId, turnId); setPage('chat'); setMobileInspector(false); }}
        onAsk={text => { setPage('chat'); setView('chat'); setInput(text); requestAnimationFrame(() => inputRef.current?.focus()); }}
        onGraph={node => { setPage('chat'); setView('graph'); setTab('graph'); field('trace', null); selectNode(node); }}
        onTrace={sequence => { setPage('chat'); openTrace(sequence, true); }} /> : <>
      <div className={`workspace-scroll ${!active ? 'home-scroll' : ''}`}><div className={!active ? 'home-stack' : 'conversation-stack'}>
      {otherTurns(chat.turns.slice(0, Math.max(0, turnIndex)))}
      {!active && view === 'graph' ? <section className="workspace-empty"><h2>Start with an answer</h2><p>Ask a question or open a saved conversation to explore its returned connections. No company-wide graph has been loaded.</p><button className="button" onClick={() => setView('chat')}>Ask a question</button></section> : !active ? <section className="welcome-content">
        <div className="welcome-waves" aria-hidden="true"><svg viewBox="0 0 900 280" preserveAspectRatio="none">{Array.from({ length: 22 }, (_, i) => <path key={i} d={`M-80 ${40 + i * 4} C180 ${-180 + i * 9} 340 ${440 - i * 5} 940 ${-90 + i * 7}`} />)}</svg></div>
        <img className="welcome-mark" src="/weave-knot.svg" alt="Weave" />
        {name && <p className="welcome-greeting">{greetingCopy.title}</p>}
        <h1>Ask Weave about your company</h1><p className="welcome-subtitle">Explore decisions, understand dependencies, find the right people, and assess changes.</p>
        <div className="feature-grid">
          <button className="feature-card" onClick={() => void submit(PRIMARY_QUESTION)}><span className="feature-icon"><FileText /></span><span><strong>Why this decision was made</strong><small>Why does Payment Service use Redis?</small></span><ArrowRight size={19} /></button>
          <button className="feature-card" onClick={() => void submit(EXPERT_QUESTION)}><span className="feature-icon"><Users /></span><span><strong>Who can help</strong><small>Who knows Payment Service?</small></span><ArrowRight size={19} /></button>
          <button className="feature-card" onClick={() => void submit(IMPACT_QUESTION)}><span className="feature-icon"><GitBranch /></span><span><strong>What could be affected</strong><small>What depends on Payment Service?</small></span><ArrowRight size={19} /></button>
          <button className="feature-card" onClick={() => void submit(FRESHNESS_QUESTION)}><span className="feature-icon"><History /></span><span><strong>Documents to review</strong><small>Which documents need review?</small></span><ArrowRight size={19} /></button>
        </div>
        <button className="change-action" onClick={() => void submit(CHANGE_QUESTION)}><GitBranch size={24} /><span><strong>Assess a change</strong><small>What happens if we remove Redis from Payment Service?</small></span><ArrowRight size={19} /></button>
      </section> : <section className="conversation" aria-label="Question and answer">
        {view === 'chat' && <div className="question-message"><div>{question}</div><span className="avatar small-avatar">Y</span></div>}
        {impactRequest && <ImpactControls key={`${impactRequest.entity_id}/${impactRequest.max_depth}`} request={impactRequest} disabled={loading} onRun={request => {
          const label = IMPACT_TARGETS.find(([id]) => id === request.entity_id)?.[1] ?? request.entity_id;
          void submit(`What would be affected if ${label} changed?`, request);
        }} />}
        {freshnessRequest && <FreshnessControls key={freshnessRequest.entity} request={freshnessRequest} disabled={loading} onRun={request => void submit(`Which documents about ${request.entity} need review?`, undefined, undefined, request)} />}
        {expertRequest && <ExpertControls key={`${expertRequest.query}/${expertRequest.limit}`} request={expertRequest} disabled={loading} onRun={request => void submit(request.query, undefined, request)} />}
        {loading && <div className="loading-card" role="status"><img src="/weave-knot.svg" alt="" /><div><strong>Following the evidence…</strong><p>Finding relevant sources and connections. Some questions take a little longer.</p><div className="skeleton" /><div className="skeleton short" /></div></div>}
        {error && <div className="error-card" role="alert"><CircleAlert size={24} /><div><h2>{error.code === 'GRAPH_UNAVAILABLE' ? 'Knowledge graph unavailable' : 'We couldn’t complete this question'}</h2><p>{error.code === 'GRAPH_UNAVAILABLE' ? 'We can’t connect to your company’s knowledge graph right now. Try again later.' : error.code === 'NETWORK_ERROR' ? 'We can’t reach Weave right now. Check your connection and try again.' : error.code === 'INVALID_RESPONSE' ? 'We couldn’t read this answer safely. Try again or ask another question.' : error.message}</p><button className="button" onClick={() => void submit(question, impactRequest ?? undefined, expertRequest ?? undefined, freshnessRequest ?? undefined)}>Try again <ArrowRight size={15} /></button></div></div>}
        {result && <>
          {view === 'chat' && <div className="answer-row"><img className="answer-mark" src="/weave-knot.svg" alt="Weave" /><article className="answer-card">
            <div className="answer-meta"><span className={`support-badge ${result.support_status}`}>
              {result.support_status === 'supported' ? <Check size={13} /> : <CircleAlert size={13} />}{result.support_status.replaceAll('_', ' ')}</span>
              <span className="small muted">{result.sources.length} supporting sources</span></div>
            {isChangeResponse(result) ? <ChangeBrief result={result} onNode={selectNode} onSource={selectSource} onPath={highlightChangeImpact} onEvidence={showChangeEvidence} onTrace={openTrace} onWatch={sequence => openTrace(sequence, true)} /> : isFreshnessResponse(result) ? <>{result.metadata.generation === 'openrouter' && <AnswerText result={result} onSource={selectSource} />}<FreshnessResults result={result} onNode={selectNode} onSource={selectSource} /></> : isExpertResponse(result) ? <>{result.metadata.generation === 'openrouter' && <AnswerText result={result} onSource={selectSource} />}<ExpertResults result={result} onNode={selectNode} onSource={selectSource} /></> : isImpactResponse(result) ? <>{result.metadata.generation === 'openrouter' && <AnswerText result={result} onSource={selectSource} />}<ImpactResults result={result} onNode={selectNode} onSource={selectSource} onPath={highlightImpact} highlightedId={highlightedFinding} /></> : <AnswerText result={result} onSource={selectSource} />}
            {!isChangeResponse(result) && result.metadata.generation !== 'openrouter' && (isImpactResponse(result) || isExpertResponse(result) || isFreshnessResponse(result)) && <OriginalAnswer key={turn?.id} result={result} onSource={selectSource} />}
          </article></div>}
          {view === 'graph' && <div className={`graph-toolbar ${traceStep ? 'trace-toolbar' : ''}`}>{!traceStep && <label className="graph-search"><Search size={17} /><input value={graphSearch} onChange={event => setGraphSearch(event.target.value)} placeholder="Find an entity in this evidence graph…" aria-label="Find graph entity" /></label>}<button className="button" onClick={() => { setView('chat'); setGraphSearch(''); }}>Back to answer</button></div>}
          {view === 'graph' && graphSearch && <div className="search-results">{matchedNodes.length ? matchedNodes.map(node => <button className="button" key={node.id} onClick={() => selectNode(node)}><EntityIcon type={node.type} size={16} />{node.label}</button>) : <p>No matching entities in this evidence.</p>}</div>}
          <section className={`evidence-card ${view === 'graph' && traceStep ? 'trace-active' : ''}`}>
            {view === 'graph' && tab === 'graph' && !ui.trace && <div className="trace-entry"><button className="button primary" disabled={!sequences.length} onClick={() => { const sequence = preferredTrace(sequences); if (sequence) openTrace(sequence, true); }}>Watch Evidence Trace</button>
                {!sequences.length && <span className="small muted">No playable path was returned. Explore the original graph evidence below.</span>}</div>}
            {changeFocus && graphAvailable && !traceStep && <div className="change-graph-controls" aria-label="Change evidence graph scope">
              <span className="small muted">Focused on the change and its returned evidence. Stored directions are preserved.</span>
              <button className="button small" aria-pressed={graphScope === 'focused'} onClick={() => setGraphScope('focused')}>Change focus</button>
              <button className="button small" aria-pressed={graphScope === 'all'} onClick={() => setGraphScope('all')}>All returned evidence</button>
            </div>}

            <div className="evidence-tabs" role="tablist" aria-label="Evidence views">{([
              ['graph', Network, 'Connected evidence'], ['timeline', Clock3, 'Timeline'], ['sources', FileText, `Key sources (${result.sources.length})`], ['relationships', List, 'Relationships'],
            ] as const).map(([id, Icon, label]) => <button key={id} role="tab" id={`tab-${id}`} tabIndex={tab === id ? 0 : -1} aria-selected={tab === id} aria-controls={`panel-${id}`} className={tab === id ? 'active' : ''} onClick={() => setTab(id)} onKeyDown={event => {
              const ids: EvidenceTab[] = ['graph', 'timeline', 'sources', 'relationships'];
              const index = ids.indexOf(id);
              const next = event.key === 'ArrowRight' ? ids[(index + 1) % 4] : event.key === 'ArrowLeft' ? ids[(index + 3) % 4] : event.key === 'Home' ? ids[0] : event.key === 'End' ? ids[3] : null;
              if (next) { event.preventDefault(); setTab(next); document.getElementById(`tab-${next}`)?.focus({ preventScroll: true }); }
            }}><Icon size={17} />{label}</button>)}</div>
            <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
              <div hidden={tab !== 'graph'}><Suspense fallback={<div className="graph-empty" role="status">Loading evidence graph…</div>}><EvidenceGraph graph={traceStep && traceGraph ? traceGraph : displayedGraph ?? result.graph} onSelect={selectNode} selectedId={inspectedNode?.id} traceNodeIds={traceStep ? [traceStep.source, traceStep.target] : undefined} highlightedEdgeIds={traceStep ? [traceStep.edge_id] : highlightedPath.length ? highlightedPath : selectedNode ? undefined : changeFocus?.primaryEdgeIds} emphasizedNodeIds={traceStep ? [traceStep.source, traceStep.target] : changeFocus?.primaryNodeIds} fitNodeIds={traceStep ? [traceStep.source, traceStep.target] : graphScope === 'focused' ? changeFocus?.primaryNodeIds : undefined} expanded={view === 'graph'} visible={tab === 'graph'} trace={traceStep && traceSequence && ui.trace ? { sequence: traceSequence, index: ui.trace.step } : undefined} clock={traceStep ? traceClock : null} /></Suspense></div>
              {tab === 'timeline' && <div className="timeline">{result.sources.length ? [...result.sources].sort((a, b) => timestampOrder(a.timestamp) - timestampOrder(b.timestamp)).map(source =>
                <button className="timeline-event" key={source.id} onClick={() => selectSource(source)}><span className={`round-icon type-${source.type.toLowerCase()}`}><EntityIcon type={source.type} /></span><span><small>{dateLabel(source.timestamp)}</small><strong>{source.title}</strong><p>{source.snippet}</p></span></button>) : <p>No dated sources are available.</p>}</div>}
              {tab === 'sources' && <div className="source-list">{result.sources.length ? result.sources.map(source => <SourceRow source={source} key={source.id} onClick={() => selectSource(source)} />) : <p>No source records were returned.</p>}</div>}
              {tab === 'relationships' && <div className="relationship-table"><table><caption className="sr-only">Directed evidence relationships</caption><thead><tr><th>From</th><th>Relationship</th><th>To</th></tr></thead><tbody>{result.graph.edges.map(edge => <tr key={edge.id}>
                <td><button onClick={() => { const node = result.graph.nodes.find(n => n.id === edge.source); if (node) selectNode(node); }}>{result.graph.nodes.find(n => n.id === edge.source)?.label ?? edge.source}</button></td><td><code>{edge.type}</code><span aria-hidden="true"> →</span></td>
                <td><button onClick={() => { const node = result.graph.nodes.find(n => n.id === edge.target); if (node) selectNode(node); }}>{result.graph.nodes.find(n => n.id === edge.target)?.label ?? edge.target}</button></td></tr>)}</tbody></table>{!result.graph.edges.length && <p>No relationships returned.</p>}</div>}
            </div>
            {view === 'graph' && tab === 'graph' && ui.trace && <TracePlayer key={`${chat.id}/${turn?.id}`}
              sequences={sequences} selection={ui.trace} onChange={(sequence, step) => traceChange(sequence, step, true)} onClose={closeTrace}
              nodes={result.graph.nodes} sources={result.sources} onNode={selectNode} onSource={selectSource}
              onMotion={attachMotion} autoPlay={watchRequest === traceOwner} onStarted={watchStarted} overallSupport={result.support_status} />}
          </section>
          {view === 'chat' && graphAvailable && <div className="answer-actions"><button className="button primary" onClick={() => { setView('graph'); setTab('graph'); }}><Maximize2 size={16} />Explore in graph<ArrowRight size={16} /></button><button className="button" onClick={() => setTab('sources')}><BookOpen size={17} />Inspect sources</button><button className="button" onClick={newChat}><Plus size={17} />New question</button></div>}
          {result.metadata.warnings.filter(w => !w.startsWith('Development fixture') && (!isChangeResponse(result) || !result.data.limitations.includes(w))).map(warning => <p key={warning} className="evidence-warning"><CircleAlert size={15} />{warning}</p>)}
        </>}
      </section>}
      {otherTurns(chat.turns.slice(turnIndex + 1))}
      </div></div>
      {composer}
      </>}
    </main>
    <WorkspacePanel id="details-panel" label="Details panel" modal={narrow && inspectorOpen} hidden={!inspectorOpen} className={`right-panel ${narrow && inspectorOpen ? 'drawer-open' : ''}`}>
      <div className="right-panel-toolbar"><span>{inspectedNode ? 'Entity details' : inspectedSource ? 'Source details' : active ? 'Evidence' : 'Workspace'}</span><button className="icon-button" title="Collapse details panel" aria-label="Collapse details panel" aria-expanded={inspectorOpen} aria-controls="details-panel" onClick={toggleInspector}><PanelRightClose size={20} /></button></div>
      <div className="inspector-scroll" key={inspectedNode?.id ?? inspectedSource?.id ?? 'overview'}><Inspector result={inspectorResult} health={health} healthError={healthError} selectedSource={inspectedSource} selectedNode={inspectedNode} onSource={selectSource} onNode={selectNode} onClose={closeInspector} onRefresh={refreshHealth} /></div>
    </WorkspacePanel>
    <div className="sr-only" aria-live="polite">{result ? `Answer ready. ${result.support_status.replaceAll('_', ' ')}. ${result.sources.length} sources.` : ''}</div>
  </div>;
}
