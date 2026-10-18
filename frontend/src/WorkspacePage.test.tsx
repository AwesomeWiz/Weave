import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import WorkspacePage from './components/WorkspacePage';
import { changeWithPlayback } from './test/tracePlaybackFixture';

afterEach(cleanup);
function setup(page: 'decisions' | 'services' | 'people', empty = false) {
  const result = changeWithPlayback();
  if (empty) { result.graph = { nodes: [], edges: [] }; result.sources = []; delete result.data.trace_playback; }
  const handlers = { onNode: vi.fn(), onChat: vi.fn(), onSaved: vi.fn(), onAsk: vi.fn(), onGraph: vi.fn(), onTrace: vi.fn(), onSource: vi.fn() };
  render(<WorkspacePage page={page} result={result} conversations={[]} {...handlers} />);
  return { result, ...handlers };
}
describe('evidence-scoped workspace pages', () => {
  it('shows actual decision connections, source actions and only genuine trace entry', () => {
    const { result, onNode, onGraph, onTrace, onSource, onAsk } = setup('decisions');
    expect(screen.getByText(/not a complete company directory/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View details' }));
    expect(onNode).toHaveBeenCalledWith(result.graph.nodes.find(n => n.id === 'decision:D-007'));
    fireEvent.click(screen.getByRole('button', { name: 'Explore relationships' })); expect(onGraph).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Watch Evidence Trace' })); expect(onTrace.mock.calls[0][0].tool).toBe('decision_trace');
    fireEvent.click(screen.getByRole('button', { name: 'Ask about this decision' })); expect(onAsk).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByText(/related sources$/));
    const first = result.sources.find(s => s.id === 'issue:PAY-42')!;
    fireEvent.click(screen.getByRole('button', { name: first.title })); expect(onSource).toHaveBeenCalledWith(first);
  });
  it('keeps stored service direction and makes inspection and impact preparation work', () => {
    const { onAsk, onNode } = setup('services');
    const checkout = screen.getByRole('heading', { name: 'Checkout Service' }).closest('article')!;
    fireEvent.click(within(checkout).getByText(/verified connections/));
    const relationship = within(checkout).getByRole('button', { name: 'Checkout Service depends on Payment Service.' });
    fireEvent.click(relationship); expect(onNode.mock.calls[0][0].id).toBe('service:payment-service');
    fireEvent.click(within(checkout).getByRole('button', { name: 'Analyze possible impact' }));
    expect(onAsk).toHaveBeenCalledWith('What depends on Checkout Service?');
  });
  it('retains returned person relevance and scores without inventing personal ownership', () => {
    const { result } = setup('people');
    const ravi = screen.getByRole('heading', { name: 'Ravi Nair' }).closest('article')!;
    expect(ravi).toHaveTextContent('Team membership does not establish personal ownership');
    expect(ravi).toHaveTextContent(`Returned score: ${result.data.reviewers.find(e => e.person.id === 'person:ravi')!.score}`);
    expect(ravi).toHaveTextContent('commit authorship');
  });
  it.each(['decisions', 'services', 'people'] as const)('provides truthful %s empty state', page => {
    setup(page, true); expect(screen.getByText(`No ${page} in this answer`)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Watch Evidence Trace' })).not.toBeInTheDocument();
  });
});
