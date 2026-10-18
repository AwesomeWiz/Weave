import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { analyzeChange, analyzeImpact, ApiError, askQuestion, checkFreshness, findExperts, getHealth } from './api';
import { CHANGE_QUESTION } from './change';
import { changeFixture } from './test/changeFixture';
import { changeWithoutSources, unresolvedChange } from './test/changeTestCases';
import { changeWithOrderedPaths } from './test/orderedTraceFixture';
import type { EvidenceGraph, GraphNode } from './types';

vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), analyzeChange: vi.fn(),
  analyzeImpact: vi.fn(), askQuestion: vi.fn(), checkFreshness: vi.fn(), findExperts: vi.fn(), getHealth: vi.fn() }));
vi.mock('./components/EvidenceGraph', () => ({ default: ({ graph, highlightedEdgeIds = [], onSelect }: {
  graph: EvidenceGraph; highlightedEdgeIds?: string[]; onSelect: (n: GraphNode) => void;
}) => <div data-testid="change-graph" data-highlighted={highlightedEdgeIds.join(',')} data-nodes={graph.nodes.map(n => n.id).join(',')}>
  {graph.nodes[0] && <button onClick={() => onSelect(graph.nodes[0])}>Inspect returned graph node</button>}
</div> }));

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear();
  vi.mocked(getHealth).mockResolvedValue({ status: 'degraded', backend: 'available', falkordb: 'not_checked',
    graph_tool: 'fixture', llm: 'disabled', graph: 'offline-demo', graph_mode: 'fixture' });
  vi.mocked(analyzeChange).mockResolvedValue(changeFixture);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });
async function openBrief() {
  const user = userEvent.setup(); render(<App />);
  await user.click(screen.getByRole('button', { name: /Assess a change/ }));
  await screen.findByRole('heading', { name: 'Change Assessment' });
  await user.click(screen.getByText('Ordered historical evidence paths'));
  return user;
}

describe('structured Change Brief in the existing workspace', () => {
  it('renders ordered historical steps and inspects their actual nodes', async () => {
    vi.mocked(analyzeChange).mockResolvedValue(changeWithOrderedPaths());
    const user = await openBrief();
    const path = screen.getByRole('article', { name: 'Historical path decision_to_current_architecture' });
    const steps = within(path).getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    for (const [i, relation] of ['IMPLEMENTED_BY', 'CHANGES', 'USES'].entries()) expect(steps[i]).toHaveTextContent(relation);
    expect(steps[0]).toHaveTextContent('decision:D-007'); expect(steps[0]).toHaveTextContent('commit:8fae2');
    expect(steps[1]).toHaveTextContent('service:payment-service'); expect(steps[2]).toHaveTextContent('tech:redis');
    expect(path).toHaveTextContent('this path assigns no additional textual citations');
    expect(screen.getByText(/Separate paths do not form a single timeline or an impact traversal/)).toBeInTheDocument();
    await user.click(within(path).getAllByRole('button', { name: 'Payment Service' })[0]);
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('service:payment-service');
    expect(analyzeChange).toHaveBeenCalledTimes(1);
  });
  it('highlights the exact historical sequence separately from impact paths', async () => {
    const result = changeWithOrderedPaths(); vi.mocked(analyzeChange).mockResolvedValue(result);
    const user = await openBrief();
    await user.click(screen.getByRole('button', { name: 'Highlight historical path decision_to_current_architecture' }));
    const graph = screen.getByTestId('change-graph');
    expect(graph.getAttribute('data-highlighted')?.split(',')).toEqual([
      'decision:D-007|IMPLEMENTED_BY|commit:8fae2',
      'commit:8fae2|CHANGES|service:payment-service',
      'service:payment-service|USES|tech:redis',
    ]);
    expect(graph.getAttribute('data-highlighted')).not.toContain('DEPENDS_ON');
    await user.click(screen.getByRole('button', { name: 'Back to answer' }));
    expect(screen.getByRole('article', { name: 'Historical path decision_to_current_architecture' })).toBeInTheDocument();
    expect(analyzeChange).toHaveBeenCalledTimes(1); expect(result.data.reviewers).toEqual(changeFixture.data.reviewers);
  });
  it('keeps legacy historical evidence without inventing ordered paths', async () => {
    await openBrief();
    expect(screen.getByText('No ordered historical paths were returned. No sequence has been inferred from the graph.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Highlight historical path/ })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Why the system works this way' })).toHaveTextContent('issue:PAY-42');
  });
  it('surfaces a hosted overview with working citations and unchanged structured sections', async () => {
    const hosted = structuredClone(changeFixture);
    hosted.metadata.generation = 'openrouter';
    hosted.answer = 'INFERRED RISK: Removing Redis may reintroduce latency pressure; this is not a benchmark. [issue:PAY-42]\n\nRecommended validation has not been performed.';
    vi.mocked(analyzeChange).mockResolvedValue(hosted);
    const user = await openBrief();
    const overview = screen.getByRole('region', { name: 'Overview' });
    expect(overview).toHaveTextContent(hosted.answer.split(' [')[0]);
    expect(overview).toHaveTextContent('The structured evidence below remains authoritative.');
    expect(within(overview).queryByRole('region', { name: 'Who should review this' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('region', { name: 'Who should review this' })).toHaveLength(1);
    expect(screen.getByRole('region', { name: 'Who should review this' })).toHaveTextContent('Score 16');
    expect(screen.getByRole('region', { name: 'Documents to review if the change proceeds' })).toHaveTextContent('If this change is approved and implemented');
    await user.click(within(overview).getByRole('button', { name: 'issue:PAY-42' }));
    expect(screen.getByLabelText('Source inspector')).toHaveTextContent('PAY-42');
    expect(analyzeChange).toHaveBeenCalledTimes(1); expect(askQuestion).not.toHaveBeenCalled();
    expect(hosted.data).toEqual(changeFixture.data); expect(hosted.graph).toEqual(changeFixture.graph);
    expect(hosted.sources).toEqual(changeFixture.sources);
  });
  it('keeps deterministic fallback warnings visible without duplicating the brief narrative', async () => {
    const fallback = structuredClone(changeFixture);
    const warning = 'OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.';
    fallback.metadata.warnings.push(warning);
    vi.mocked(analyzeChange).mockResolvedValue(fallback);
    await openBrief();
    const overview = screen.getByRole('region', { name: 'Overview' });
    expect(overview).toHaveTextContent(fallback.answer.split('\n\n')[0]);
    expect(within(overview).queryByText(/Historical context \(supported\)/)).not.toBeInTheDocument();
    expect(screen.getByText(warning)).toBeInTheDocument();
    expect(screen.getAllByRole('region', { name: 'Why the system works this way' })).toHaveLength(1);
    expect(screen.getByRole('region', { name: 'Known facts and potential risks' })).toHaveTextContent('INFERRED RISK');
    expect(analyzeChange).toHaveBeenCalledTimes(1);
  });
  it('routes the canonical chat question through exactly one structured request', async () => {
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('textbox', { name: 'Ask about your company knowledge' }));
    await user.paste(CHANGE_QUESTION); await user.keyboard('{Enter}');
    expect(await screen.findByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
    expect(analyzeChange).toHaveBeenCalledExactlyOnceWith({ target: 'Payment Service', change: CHANGE_QUESTION });
    expect(askQuestion).not.toHaveBeenCalled(); expect(analyzeImpact).not.toHaveBeenCalled();
    expect(findExperts).not.toHaveBeenCalled(); expect(checkFreshness).not.toHaveBeenCalled();
    expect(screen.getByText('partially supported', { selector: '.answer-meta .support-badge' })).toBeInTheDocument();
  });
  it('shows all nine sections and separates facts, inferences, and unperformed validation', async () => {
    await openBrief();
    for (const name of ['Proposed Change', 'Why the system works this way', 'What could be affected', 'Who should review this',
      'Known facts and potential risks', 'Recommended checks', 'Documents to review now',
      'Documents to review if the change proceeds', 'Supporting evidence']) expect(screen.getByRole('region', { name })).toBeInTheDocument();
    const risks = screen.getByRole('region', { name: 'Known facts and potential risks' });
    expect(within(risks).getAllByText('KNOWN FACT')).toHaveLength(3);
    expect(within(risks).getByText('INFERRED RISK')).toBeInTheDocument();
    expect(within(risks).getByText('RECOMMENDATION')).toBeInTheDocument();
    expect(screen.getByText('Recommended actions only. These checks have not been performed.')).toBeInTheDocument();
    expect(screen.getAllByText('Recommendation · Not performed').length).toBeGreaterThan(0);
    expect(screen.getByText(/Sample data/, { selector: '.mode-banner' })).toBeInTheDocument();
  });
  it('keeps current freshness distinct from conditional ADR review', async () => {
    await openBrief();
    const current = screen.getByRole('region', { name: 'Documents to review now' });
    const future = screen.getByRole('region', { name: 'Documents to review if the change proceeds' });
    expect(within(current).getByText('Review recommended')).toBeInTheDocument();
    expect(within(current).getByText('2026-05-01T12:00:00Z')).toBeInTheDocument();
    expect(within(current).queryByText('doc:ADR-7')).not.toBeInTheDocument();
    expect(within(future).getByText('doc:ADR-7')).toBeInTheDocument();
    expect(within(future).getByText('If this change is approved and implemented')).toBeInTheDocument();
    expect(within(future).queryByText('Review recommended')).not.toBeInTheDocument();
  });
  it('preserves reviewers and inspects existing historical citations and people', async () => {
    const user = await openBrief();
    const reviewers = screen.getByRole('region', { name: 'Who should review this' });
    for (const score of [16, 14, 5]) expect(within(reviewers).getByText(`Score ${score}`)).toBeInTheDocument();
    expect(within(reviewers).getAllByText(/Personal ownership is not established/).length).toBeGreaterThan(0);
    const history = screen.getByRole('region', { name: 'Why the system works this way' });
    await user.click(within(history).getAllByRole('button', { name: 'issue:PAY-42' })[0]);
    expect(screen.getByLabelText('Source inspector')).toHaveTextContent('PAY-42');
    await user.keyboard('{Escape}');
    const heading = within(reviewers).getByRole('heading', { name: '1. Ravi Nair' });
    await user.click(within(heading).getByRole('button'));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('person:ravi');
  });
  it('highlights actual dependency edges and returns to the same brief without another request', async () => {
    const user = await openBrief();
    const graph = await screen.findByTestId('change-graph');
    const focusedNodes = graph.getAttribute('data-nodes');
    expect(focusedNodes).not.toContain('chunk:');
    await user.click(screen.getByRole('button', { name: 'Highlight path to Checkout Service' }));
    expect(screen.getByTestId('change-graph').getAttribute('data-highlighted')).toContain('DEPENDS_ON');
    expect(screen.getByRole('heading', { name: 'Knowledge Graph' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'All returned evidence' }));
    expect(screen.getByTestId('change-graph').getAttribute('data-nodes')).toContain('chunk:');
    await user.click(screen.getByRole('button', { name: 'Change focus' }));
    expect(screen.getByTestId('change-graph').getAttribute('data-nodes')).toBe(focusedNodes);
    await user.click(screen.getByRole('button', { name: 'Back to answer' }));
    expect(screen.getByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
    expect(analyzeChange).toHaveBeenCalledTimes(1);
  });
  it('restores a Change Brief from history with its structured data and controls', async () => {
    const user = await openBrief();
    await user.click(within(screen.getByLabelText('Main navigation')).getByRole('button', { name: 'New Chat' }));
    await user.click(screen.getByRole('button', { name: 'Open chat: What happens if we remove Redis from Payment Service?' }));
    expect(screen.getByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Who should review this' })).toHaveTextContent('Score 16');
    expect(analyzeChange).toHaveBeenCalledTimes(1);
  });
  it('keeps missing sources visible as qualified graph-only evidence', async () => {
    vi.mocked(analyzeChange).mockResolvedValue(changeWithoutSources());
    const user = await openBrief();
    expect(screen.getByText('The retrieved rationale is incomplete because matching source provenance is missing.')).toBeInTheDocument();
    const section = screen.getByRole('region', { name: 'Documents to review now' });
    await user.click(within(section).getByText('Document association and later changes'));
    expect(within(section).getAllByText('Graph-only change evidence; no textual citation established.').length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Supporting evidence' })).toHaveTextContent('No supporting textual sources were retrieved.');
    expect(screen.getByText(/Matching textual provenance was not retrieved/)).toBeInTheDocument();
  });
  it.each(['unsupported', 'unresolved', 'ambiguous'] as const)('shows qualified %s proposals without invented findings', async resolution => {
    vi.mocked(analyzeChange).mockResolvedValue(unresolvedChange('Upgrade Redis in Payment Service', resolution));
    await openBrief();
    expect(screen.getByText('insufficient evidence', { selector: '.answer-meta .support-badge' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Documents to review now' })).toHaveTextContent('No current review findings established');
    expect(screen.queryByText('Score 16')).not.toBeInTheDocument();
  });
  it('preserves retry and the proposed question after graph errors', async () => {
    vi.mocked(analyzeChange).mockRejectedValue(new ApiError('The graph is unavailable.', 'GRAPH_UNAVAILABLE'));
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: /Assess a change/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Knowledge graph unavailable');
    expect(screen.getByRole('textbox')).toHaveValue(CHANGE_QUESTION);
    vi.mocked(analyzeChange).mockResolvedValue(changeFixture);
    await user.click(screen.getByRole('button', { name: /Try again/ }));
    expect(await screen.findByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
    expect(analyzeChange).toHaveBeenCalledTimes(2);
  });
  it('routes unsupported chat proposals to the structured endpoint for qualification', async () => {
    const change = 'Upgrade Redis in Payment Service';
    vi.mocked(analyzeChange).mockResolvedValue(unresolvedChange(change));
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('textbox')); await user.paste(change); await user.keyboard('{Enter}');
    expect(await screen.findByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
    expect(analyzeChange).toHaveBeenCalledWith({ target: 'Payment Service', change });
    expect(askQuestion).not.toHaveBeenCalled();
    expect(screen.getByRole('region', { name: 'Proposed Change' })).toHaveTextContent('outside the validated Redis-removal scenario');
  });
  it('uses the existing modal inspector and Escape dismissal at a narrow viewport', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    const user = await openBrief();
    const history = screen.getByRole('region', { name: 'Why the system works this way' });
    await user.click(within(history).getAllByRole('button', { name: 'issue:PAY-42' })[0]);
    expect(screen.getByRole('dialog', { name: 'Details panel' })).toHaveTextContent('PAY-42');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Details panel' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Change Assessment' })).toBeInTheDocument();
  });
});
