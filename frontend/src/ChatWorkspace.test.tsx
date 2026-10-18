import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { analyzeChange, askQuestion, getHealth } from './api';
import type { ChatRepository } from './chatStorage';
import type { WorkspaceArchive } from './workspace';
import { emptyWorkspace, restoreArchive } from './workspace';
import type { QueryResponse } from './types';
import { changeWithOrderedPaths } from './test/orderedTraceFixture';

vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), analyzeChange: vi.fn(), askQuestion: vi.fn(), getHealth: vi.fn() }));
vi.mock('./components/EvidenceGraph', () => ({ default: ({ graph, selectedId, highlightedEdgeIds = [], onSelect }: {
  graph: QueryResponse['graph']; selectedId?: string; highlightedEdgeIds?: string[]; onSelect: (n: QueryResponse['graph']['nodes'][number]) => void;
}) => <div data-testid="saved-graph" data-selected={selectedId} data-edges={highlightedEdgeIds.join(',')}><button onClick={() => onSelect(graph.nodes[0])}>Inspect saved graph node</button></div> }));

function response(answer: string): QueryResponse { return { answer, support_status: 'partially_supported', tools_used: ['trace_decision'], sources: [],
  graph: { nodes: [{ id: 'service:test', type: 'Service', label: 'Saved Service', properties: {} }], edges: [] },
  metadata: { generation: 'deterministic', graph_mode: 'fixture', latency_ms: 1, warnings: [] } }; }
function repository(seed: WorkspaceArchive | null = null) {
  let stored = seed;
  return { snapshot: () => stored, load: vi.fn(async () => stored ? restoreArchive(structuredClone(stored)) : null),
    save: vi.fn(async (value: WorkspaceArchive) => { stored = structuredClone(value); }) } satisfies ChatRepository & { snapshot: () => WorkspaceArchive | null };
}
function deferred<T>() { let resolve!: (v: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
const question = 'Explain the payment system';
async function ready(repo: ChatRepository) { const app = render(<App repository={repo} />); await waitFor(() => expect(screen.getByRole('button', { name: 'New Chat' })).toBeEnabled()); return app; }
async function send(user: ReturnType<typeof userEvent.setup>, text = question) {
  const box = screen.getByRole('textbox', { name: 'Ask about your company knowledge' });
  await user.clear(box); await user.click(box); await user.paste(text); await user.keyboard('{Enter}');
}
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear();
  vi.mocked(getHealth).mockResolvedValue({ status: 'degraded', backend: 'available', graph_mode: 'fixture', graph: 'test', graph_tool: 'fixture', falkordb: 'not_checked', llm: 'disabled' });
  vi.mocked(askQuestion).mockImplementation(async text => response(`Answer to ${text}`));
  vi.mocked(analyzeChange).mockImplementation(async request => {
    const result = changeWithOrderedPaths(); result.data.proposed_change.requested_change = request.change; result.data.proposed_change.requested_target = request.target; return result;
  });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

describe('persistent multi-conversation workspace', () => {
  it('starts independent chats, switches without requests, and keeps ordered messages', async () => {
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    await send(user); await screen.findByText(`Answer to ${question}`);
    await send(user, 'Explain follow-up evidence'); await screen.findByText('Answer to Explain follow-up evidence');
    expect(screen.getByRole('article', { name: `Saved message: ${question}` })).toHaveTextContent(`Answer to ${question}`);
    const firstId = repo.snapshot()!.activeId;
    await user.click(screen.getByRole('button', { name: 'New Chat' }));
    expect(screen.queryByText('Answer to Explain follow-up evidence')).not.toBeInTheDocument();
    await send(user, 'Explain another system'); await screen.findByText('Answer to Explain another system');
    expect(repo.snapshot()!.activeId).not.toBe(firstId);
    await user.click(screen.getByRole('button', { name: `Open chat: ${question}` }));
    expect(screen.getByText('Answer to Explain follow-up evidence')).toBeInTheDocument();
    expect(askQuestion).toHaveBeenCalledTimes(3);
    expect(repo.snapshot()!.conversations.find(c => c.id === firstId)!.turns.map(t => t.question)).toEqual([question, 'Explain follow-up evidence']);
  });
  it('persists graph selection and restores after refresh with no evidence request', async () => {
    const repo = repository(); const user = userEvent.setup(); const app = await ready(repo);
    await send(user); await screen.findByText(`Answer to ${question}`);
    await user.click(screen.getByRole('button', { name: 'Inspect saved graph node' }));
    await waitFor(() => expect(repo.snapshot()?.conversations[0].ui.selectedNodeId).toBe('service:test'));
    app.unmount(); await ready(repo);
    expect(await screen.findByLabelText('Entity inspector')).toHaveTextContent('service:test');
    expect(screen.getByTestId('saved-graph')).toHaveAttribute('data-selected', 'service:test');
    expect(askQuestion).toHaveBeenCalledTimes(1);
  });
  it('restores the complete Change Brief, ordered highlight and source inspector', async () => {
    const repo = repository(); const user = userEvent.setup(); let app = await ready(repo);
    await user.click(screen.getByRole('button', { name: /Change Intelligence/ })); await screen.findByRole('heading', { name: 'Change Brief' });
    await user.click(screen.getByRole('button', { name: 'Highlight historical path decision_to_current_architecture' }));
    await waitFor(() => expect(repo.snapshot()?.conversations[0].ui.view).toBe('graph'));
    app.unmount(); app = await ready(repo);
    expect(await screen.findByRole('heading', { name: 'Knowledge Graph' })).toBeInTheDocument();
    expect(screen.getByTestId('saved-graph').getAttribute('data-edges')).toContain('CHANGES');
    await user.click(screen.getByRole('button', { name: 'Back to answer' }));
    await user.click(within(screen.getByRole('region', { name: 'Historical Context' })).getAllByRole('button', { name: 'issue:PAY-42' })[0]);
    await waitFor(() => expect(repo.snapshot()?.conversations[0].ui.selectedSourceId).toBe('issue:PAY-42'));
    const before = structuredClone(repo.snapshot()!.conversations[0].turns[0].result);
    app.unmount(); await ready(repo);
    expect(await screen.findByLabelText('Source inspector')).toHaveTextContent('PAY-42');
    expect(screen.getByRole('region', { name: 'Relevant Reviewers' })).toHaveTextContent('Score 16');
    expect(repo.snapshot()!.conversations[0].turns[0].result).toEqual(before);
    expect(analyzeChange).toHaveBeenCalledTimes(1); expect(askQuestion).not.toHaveBeenCalled();
  }, 15000);
  it('searches titles and earlier questions, renames one selected row only', async () => {
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    await send(user); await screen.findByText(`Answer to ${question}`);
    await send(user, 'A unique earlier phrase'); await screen.findByText('Answer to A unique earlier phrase');
    await user.click(screen.getByRole('button', { name: 'New Chat' }));
    await user.click(screen.getByRole('button', { name: `Rename chat: ${question}` }));
    await user.clear(screen.getByRole('textbox', { name: 'Chat title' })); await user.type(screen.getByRole('textbox', { name: 'Chat title' }), 'Payment review');
    await user.click(screen.getByRole('button', { name: 'Save title' }));
    expect(screen.getByRole('button', { name: 'Open chat: New chat' })).toHaveAttribute('aria-current', 'page');
    await user.type(screen.getByRole('searchbox', { name: 'Search chats' }), 'unique earlier');
    expect(screen.getByRole('button', { name: 'Open chat: Payment review' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open chat: New chat' })).not.toBeInTheDocument();
    expect(repo.snapshot()!.conversations).toHaveLength(2);
  });
  it('confirms deletion and clear history, preserving other conversations', async () => {
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    await send(user); await screen.findByText(`Answer to ${question}`); await user.click(screen.getByRole('button', { name: 'New Chat' }));
    await user.click(screen.getByRole('button', { name: `Delete chat: ${question}` })); await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: `Open chat: ${question}` })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: `Delete chat: ${question}` }));
    await user.click(within(screen.getByRole('dialog', { name: 'Delete chat' })).getByRole('button', { name: 'Delete chat' }));
    await waitFor(() => expect(repo.snapshot()?.conversations).toHaveLength(1));
    expect(screen.getByRole('button', { name: 'Open chat: New chat' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear history' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Clear history' })).getByRole('button', { name: 'Clear history' }));
    await waitFor(() => expect(repo.snapshot()?.conversations[0].turns).toEqual([]));
  });
  it('isolates simultaneous requests by initiating conversation and prevents duplicates', async () => {
    const first = deferred<QueryResponse>(); const second = deferred<QueryResponse>();
    vi.mocked(askQuestion).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    await send(user); expect(screen.getByRole('textbox')).toBeDisabled();
    await user.keyboard('{Enter}'); expect(askQuestion).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole('button', { name: 'New Chat' })); await send(user, 'Second pending chat');
    await act(async () => first.resolve(response('First result')));
    expect(screen.queryByText('First result')).not.toBeInTheDocument(); expect(screen.getByRole('textbox')).toBeDisabled();
    await act(async () => second.resolve(response('Second result'))); expect(await screen.findByText('Second result')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: `Open chat: ${question}` }));
    expect(screen.getByText('First result')).toBeInTheDocument(); expect(askQuestion).toHaveBeenCalledTimes(2);
  });
  it('does not resurrect a cleared pending chat when its response arrives', async () => {
    const pending = deferred<QueryResponse>(); vi.mocked(askQuestion).mockReturnValueOnce(pending.promise);
    const repo = repository(); const user = userEvent.setup(); await ready(repo); await send(user);
    await user.click(screen.getByRole('button', { name: 'Clear history' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Clear history' })).getByRole('button', { name: 'Clear history' }));
    await act(async () => pending.resolve(response('Deleted result')));
    expect(screen.queryByText('Deleted result')).not.toBeInTheDocument();
    await waitFor(() => expect(repo.snapshot()?.conversations.every(c => !c.turns.length)).toBe(true));
  });
  it('recovers an interrupted request with explicit retry and no duplicate message', async () => {
    const pending = deferred<QueryResponse>(); vi.mocked(askQuestion).mockReturnValueOnce(pending.promise);
    const repo = repository(); const user = userEvent.setup(); const app = await ready(repo); await send(user);
    await waitFor(() => expect(repo.snapshot()?.conversations[0].turns[0].status).toBe('pending'));
    app.unmount(); await ready(repo);
    expect(await screen.findByRole('alert')).toHaveTextContent('interrupted by refresh'); expect(askQuestion).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(response('Old unmounted result')));
    expect(screen.queryByText('Old unmounted result')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Try again/ })); await screen.findByText(`Answer to ${question}`);
    expect(repo.snapshot()!.conversations[0].turns).toHaveLength(1); expect(askQuestion).toHaveBeenCalledTimes(2);
  });
  it('keeps chats usable when loading or saving storage fails, without raw errors', async () => {
    const repo = repository(); repo.load.mockRejectedValueOnce(new Error('private storage detail'));
    const user = userEvent.setup(); await ready(repo); await send(user); await screen.findByText(`Answer to ${question}`);
    expect(screen.getByText(/existing storage is untouched/)).toBeInTheDocument(); expect(repo.save).not.toHaveBeenCalled();
    expect(screen.queryByText(/private storage detail/)).not.toBeInTheDocument();
  });
  it('reports quota failure and unsuccessful deletion without losing in-memory results', async () => {
    const repo = repository(); repo.save.mockRejectedValue(new Error('quota private detail'));
    const user = userEvent.setup(); await ready(repo); await send(user); await screen.findByText(`Answer to ${question}`);
    expect(await screen.findByText(/Chat history could not be saved/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: `Delete chat: ${question}` }));
    await user.click(within(screen.getByRole('dialog', { name: 'Delete chat' })).getByRole('button', { name: 'Delete chat' }));
    expect(await screen.findByText(/Previously stored chats may reappear/)).toBeInTheDocument();
  });
  it('opens responsive navigation, switches chats, and dismisses with Escape', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    await send(user); await screen.findByText(`Answer to ${question}`);
    await user.click(screen.getByRole('button', { name: 'Open navigation' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Main navigation' })).getByRole('button', { name: 'New Chat' }));
    expect(screen.queryByRole('dialog', { name: 'Main navigation' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Open navigation' }));
    await user.click(screen.getByRole('button', { name: `Open chat: ${question}` }));
    expect(screen.getByText(`Answer to ${question}`)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Open navigation' })); await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Main navigation' })).not.toBeInTheDocument();
  });
  it('navigates workspace foundations using only records in the selected response', async () => {
    const user = userEvent.setup(); await ready(repository()); await send(user); await screen.findByText(`Answer to ${question}`);
    await user.click(screen.getByRole('button', { name: 'Services' }));
    const page = screen.getByRole('region', { name: 'Services workspace' }); expect(page).toHaveTextContent('not a company-wide directory');
    await user.click(within(page).getByRole('button', { name: /Saved Service/ }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('service:test');
    await user.click(screen.getByRole('button', { name: 'People' })); expect(screen.getByRole('region', { name: 'People workspace' })).toHaveTextContent('No people records');
    expect(askQuestion).toHaveBeenCalledTimes(1);
  });
  it('keeps the bounded 20-chat policy explicit with no automatic eviction', async () => {
    const archive = emptyWorkspace(); archive.conversations = Array.from({ length: 20 }, () => { const s = emptyWorkspace(); return s.conversations[0]; }); archive.activeId = archive.conversations[0].id;
    const repo = repository(archive); const user = userEvent.setup(); await ready(repo);
    await user.click(screen.getByRole('button', { name: 'New Chat' })); expect(screen.getByText(/20-chat limit/)).toBeInTheDocument();
    expect(repo.snapshot()!.conversations).toHaveLength(20);
  });
  it('keeps credential-like evidence in memory and never writes it to history', async () => {
    const repo = repository(); const user = userEvent.setup(); await ready(repo);
    const value = response('Evidence stays unchanged in memory');
    value.graph.nodes[0].properties.api_key = 'test-only-do-not-store';
    vi.mocked(askQuestion).mockResolvedValueOnce(value);
    await send(user); await screen.findByText('Evidence stays unchanged in memory');
    expect(await screen.findByText(/credential-like data was detected/)).toBeInTheDocument();
    expect(repo.save.mock.calls.every(([archive]) => !JSON.stringify(archive).includes('test-only-do-not-store'))).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Inspect saved graph node' }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('test-only-do-not-store');
  });
  it('enforces the turn limit without deleting existing messages or sending a request', async () => {
    const archive = emptyWorkspace(); const chat = archive.conversations[0];
    chat.turns = Array.from({ length: 40 }, (_, i) => ({ id: `turn-${i}`, question: `Saved question ${i}`, createdAt: chat.createdAt,
      status: 'complete', result: response(`Saved answer ${i}`), error: null, request: { impact: null, expert: null, freshness: null, change: null } }));
    chat.ui.selectedTurnId = 'turn-39';
    const repo = repository(archive); const user = userEvent.setup(); await ready(repo);
    await send(user, 'One more question');
    expect(screen.getByText('This chat has reached 40 messages. Start a new chat to continue.')).toBeInTheDocument();
    expect(askQuestion).not.toHaveBeenCalled(); expect(repo.snapshot()!.conversations[0].turns).toHaveLength(40);
  });
});
