import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { analyzeChange, askQuestion, getHealth } from './api';
import type { ChatRepository } from './chatStorage';
import type { WorkspaceArchive } from './workspace';
import { emptyWorkspace, newConversation, restoreArchive } from './workspace';
import { changeWithPlayback } from './test/tracePlaybackFixture';

vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), getHealth: vi.fn(), askQuestion: vi.fn(), analyzeChange: vi.fn() }));
vi.mock('./components/EvidenceGraph', () => ({ default: (p: { highlightedEdgeIds?: string[]; traceNodeIds?: string[]; selectedId?: string }) =>
  <div data-testid="trace-graph" data-edges={p.highlightedEdgeIds?.join(',')} data-nodes={p.traceNodeIds?.join(',')} data-selected={p.selectedId} /> }));
const sequenceId = 'decision_trace/decision_to_current_architecture';
function seed() {
  const archive = emptyWorkspace(); const chat = archive.conversations[0]; chat.title = 'Trace saved change';
  chat.turns = [{ id: 'turn-1', createdAt: chat.createdAt, question: 'Remove Redis from Payment Service', status: 'complete', error: null,
    request: { change: { target: 'Payment Service', change: 'Remove Redis from Payment Service' }, impact: null, expert: null, freshness: null }, result: changeWithPlayback() }];
  chat.ui.selectedTurnId = 'turn-1'; return archive;
}
function repository(initial = seed()) {
  let snapshot: WorkspaceArchive = structuredClone(initial);
  return { load: vi.fn(async () => restoreArchive(structuredClone(snapshot))), save: vi.fn(async value => { snapshot = structuredClone(value); }), snapshot: () => snapshot } satisfies ChatRepository & { snapshot(): WorkspaceArchive };
}
async function ready(repo: ChatRepository) {
  const app = render(<App repository={repo} />); await waitFor(() => expect(screen.getByRole('button', { name: 'New Chat' })).toBeEnabled()); return app;
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
async function ticking(ms = 2200) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear();
  vi.mocked(getHealth).mockResolvedValue({ status: 'degraded', backend: 'available', graph_mode: 'fixture', graph: 'test', graph_tool: 'fixture', falkordb: 'not_checked', llm: 'disabled' });
});
afterEach(() => { cleanup(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

describe('Trace Mode in persistent conversations', () => {
  it('opens both historical and Impact paths, highlights exact nodes/edge, and synchronizes Inspector without requests', async () => {
    const repo = repository(); await ready(repo);
    click('Trace historical path decision_to_current_architecture');
    expect(await screen.findByLabelText('Trace Mode')).toBeInTheDocument();
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-edges', 'decision:D-007|IMPLEMENTED_BY|commit:8fae2');
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-nodes', 'decision:D-007,commit:8fae2');
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('commit:8fae2');
    expect(within(screen.getByLabelText('Entity inspector')).getByText('No source records linked to this entity.')).toBeInTheDocument();
    click('Next step');
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-edges', 'commit:8fae2|CHANGES|service:payment-service');
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('service:payment-service');
    click('Inspect source entity'); expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('commit:8fae2');
    click('Back to answer'); expect(screen.getByRole('heading', { name: 'Change Brief' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Relevant Reviewers' })).toHaveTextContent('Score 16');
    click('Trace impact path service:order-service'); click('Next step');
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-edges', 'service:checkout-service|DEPENDS_ON|service:payment-service');
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-selected', 'service:checkout-service');
    expect(askQuestion).not.toHaveBeenCalled(); expect(analyzeChange).not.toHaveBeenCalled();
    expect(getHealth).toHaveBeenCalledTimes(1);
  });
  it('cancels on chat switches and restores paused at the saved step after refresh', async () => {
    const archive = seed(); const second = newConversation(); second.title = 'Other conversation'; archive.conversations.push(second);
    const repo = repository(archive); const app = await ready(repo);
    click('Trace historical path decision_to_current_architecture'); vi.useFakeTimers(); click('Play'); await ticking();
    expect(screen.getByText('Step 2 of 3 · Playing')).toBeInTheDocument();
    click('Open chat: Other conversation'); await ticking(9000);
    expect(repo.snapshot().conversations[0].ui.trace).toEqual({ sequenceId, step: 1 });
    click('Open chat: Trace saved change'); expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
    await ticking(300); app.unmount(); vi.useRealTimers();
    await ready(repo); expect(screen.getByText('Step 2 of 3 · Paused')).toBeInTheDocument();
    expect(screen.getByTestId('trace-graph')).toHaveAttribute('data-edges', 'commit:8fae2|CHANGES|service:payment-service');
    expect(Object.keys(repo.snapshot().conversations[0].ui.trace!)).toEqual(['sequenceId', 'step']);
    expect(askQuestion).not.toHaveBeenCalled(); expect(analyzeChange).not.toHaveBeenCalled();
  });
  it('pauses on evidence tab, view and workspace-page changes', async () => {
    await ready(repository()); click('Trace historical path decision_to_current_architecture'); vi.useFakeTimers(); click('Play');
    fireEvent.click(screen.getByRole('tab', { name: 'Relationships' })); await ticking(9000);
    fireEvent.click(screen.getByRole('tab', { name: 'Evidence graph' })); expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    click('Play'); click('Back to answer'); await ticking(9000); click('Knowledge Graph');
    expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
    click('Play'); click('Services'); await ticking(9000); click('Knowledge Graph');
    expect(screen.getByText('Step 1 of 3 · Paused')).toBeInTheDocument();
  });
  it.each(['delete', 'clear'])('cancels playback on %s and cannot recreate deleted history', async action => {
    const repo = repository(); await ready(repo); click('Trace historical path decision_to_current_architecture'); vi.useFakeTimers(); click('Play');
    click(action === 'delete' ? 'Delete chat: Trace saved change' : 'Clear history');
    const dialog = screen.getByRole('dialog'); fireEvent.click(within(dialog).getByRole('button', { name: action === 'delete' ? 'Delete chat' : 'Clear history' }));
    await ticking(9000); expect(screen.queryByLabelText('Trace Mode')).not.toBeInTheDocument();
    expect(repo.snapshot().conversations.every(c => c.title !== 'Trace saved change')).toBe(true);
    expect(repo.snapshot().conversations[0].turns).toEqual([]);
  });
  it('cancels when a different saved turn is opened', async () => {
    const archive = seed(); const chat = archive.conversations[0]; chat.turns.push({ ...structuredClone(chat.turns[0]), id: 'turn-2', question: 'Other saved question' });
    const repo = repository(archive); await ready(repo); click('Trace historical path decision_to_current_architecture'); vi.useFakeTimers(); click('Play');
    click('Back to answer');
    fireEvent.click(within(screen.getByRole('article', { name: 'Saved message: Other saved question' })).getByRole('button', { name: 'Open full evidence for this message' }));
    await ticking(9000); expect(repo.snapshot().conversations[0].ui.selectedTurnId).toBe('turn-2');
    expect(repo.snapshot().conversations[0].ui.trace).toBeNull();
  });
  it('allows opening and closing from the graph workspace without covering the brief', async () => {
    await ready(repository()); click('Knowledge Graph'); click('Open Trace Mode');
    expect(screen.getByLabelText('Trace Mode')).toBeInTheDocument(); click('Close Trace Mode');
    expect(screen.queryByLabelText('Trace Mode')).not.toBeInTheDocument(); click('Back to answer');
    expect(screen.getByRole('heading', { name: 'Change Brief' })).toBeInTheDocument();
  });
  it('does not promote a source inspected in another evidence view into a graph-only step citation', async () => {
    await ready(repository()); click('Trace historical path decision_to_current_architecture');
    fireEvent.click(screen.getByRole('tab', { name: 'Key sources (5)' }));
    fireEvent.click(within(screen.getByRole('tabpanel')).getByRole('button', { name: /PAY-42/ }));
    expect(screen.getByLabelText('Source inspector')).toHaveTextContent('issue:PAY-42');
    fireEvent.click(screen.getByRole('tab', { name: 'Evidence graph' }));
    expect(screen.queryByLabelText('Source inspector')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('commit:8fae2');
    expect(within(screen.getByLabelText('Entity inspector')).getByText('No source records linked to this entity.')).toBeInTheDocument();
  });
  it.each(['view', 'turn', 'chat', 'sequence', 'step'])('rejects a previously queued callback after %s ownership changes', async owner => {
    const archive = seed(); const chat = archive.conversations[0];
    chat.turns.push({ ...structuredClone(chat.turns[0]), id: 'turn-2', question: 'Other saved question' });
    const repo = repository(archive); await ready(repo); click('Trace historical path decision_to_current_architecture');
    vi.useFakeTimers(); const scheduled = vi.spyOn(globalThis, 'setTimeout'); click('Play');
    const callback = scheduled.mock.calls.find(([, delay]) => delay === 2200)![0] as () => void;
    if (owner === 'view' || owner === 'turn') click('Back to answer');
    if (owner === 'turn') fireEvent.click(within(screen.getByRole('article', { name: 'Saved message: Other saved question' })).getByRole('button', { name: 'Open full evidence for this message' }));
    if (owner === 'chat') click('New Chat');
    if (owner === 'sequence') fireEvent.change(screen.getByLabelText('Trace sequence'), { target: { value: 'impact_analysis/service:order-service' } });
    if (owner === 'step') { click('Next step'); click('Next step'); }
    await ticking(300); const before = structuredClone(repo.snapshot());
    act(() => callback()); await ticking(300);
    expect(repo.snapshot()).toEqual(before);
    scheduled.mockRestore();
  });
  it('shows legacy paths normally but cannot manufacture playback metadata', async () => {
    const archive = seed(); delete (archive.conversations[0].turns[0].result as ReturnType<typeof changeWithPlayback>).data.trace_playback;
    await ready(repository(archive)); expect(screen.queryByRole('button', { name: 'Trace historical path decision_to_current_architecture' })).not.toBeInTheDocument();
    click('Knowledge Graph'); expect(screen.getByRole('button', { name: 'Open Trace Mode' })).toBeDisabled();
  });
});
