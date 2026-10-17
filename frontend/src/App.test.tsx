import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { analyzeImpact, ApiError, askQuestion, getHealth } from './api';
import { impactFixture } from './test/impactFixture';
import type { Health, QueryResponse } from './types';

vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), askQuestion: vi.fn(), analyzeImpact: vi.fn(), getHealth: vi.fn() }));
vi.mock('./components/EvidenceGraph', () => ({ default: ({ onSelect, graph, selectedId }: { onSelect: (n: QueryResponse['graph']['nodes'][number]) => void; graph: QueryResponse['graph']; selectedId?: string }) => <button aria-pressed={selectedId === graph.nodes[0]?.id} onClick={() => onSelect(graph.nodes[0])}>Inspect graph test node</button> }));

const health: Health = { status: 'degraded', backend: 'available', falkordb: 'not_checked', graph_tool: 'fixture', llm: 'disabled', graph: 'novapay', graph_mode: 'fixture' };
const result: QueryResponse = {
  answer: 'Test-only evidence summary [decision:test].', support_status: 'supported', tools_used: ['trace_decision'],
  sources: [{ id: 'decision:test', type: 'Decision', title: 'Test decision', snippet: 'Fixture source excerpt', url: null, timestamp: null, entity_ids: ['decision:test'], metadata: { synthetic: true } }],
  graph: { nodes: [{ id: 'decision:test', type: 'Decision', label: 'Test decision', properties: {} }], edges: [] },
  metadata: { latency_ms: 1, graph_mode: 'fixture', generation: 'deterministic', warnings: [] },
};

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); vi.mocked(getHealth).mockResolvedValue(health); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('question workflow', () => {
  it('renders hosted impact explanation alongside validated findings and graph inspection', async () => {
    vi.mocked(analyzeImpact).mockResolvedValue({ ...impactFixture,
      answer: 'Hosted explanation: Checkout Service could be affected; failure is not guaranteed.',
      metadata: { ...impactFixture.metadata, generation: 'openrouter' },
    });
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: /Impact Analysis/ }));
    expect(await screen.findByText(/Hosted explanation: Checkout Service/)).toBeInTheDocument();
    expect(screen.getByText(/Synthesized with OpenRouter/)).toBeInTheDocument();
    expect(screen.getByText('partially supported', { selector: '.support-badge' })).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Direct Impact' })).getByText('service:checkout-service')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Explore in graph' }));
    await user.click(screen.getByRole('button', { name: 'Inspect graph test node' }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('service:payment-service');
  });
  it('keeps hosted decision citations navigable and labels fallback accurately', async () => {
    vi.mocked(askQuestion).mockResolvedValue({ ...result,
      metadata: { ...result.metadata, generation: 'openrouter' },
    });
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: /Decision Trace/ }));
    expect(await screen.findByText(/Synthesized with OpenRouter/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'test' }));
    expect(screen.getByLabelText('Source inspector')).toHaveTextContent('Fixture source excerpt');
    await user.keyboard('{Escape}');
    vi.mocked(askQuestion).mockResolvedValue({ ...result, metadata: { ...result.metadata,
      warnings: ['OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.'],
    } });
    await user.type(screen.getByRole('textbox'), 'Why Redis?{Enter}');
    expect(await screen.findByText(/Deterministic evidence summary/)).toBeInTheDocument();
    expect(screen.queryByText(/Synthesized with OpenRouter/)).not.toBeInTheDocument();
  });
  it('renders a combined answer through /api/query with citations and the existing graph inspector', async () => {
    const combined = 'What led to Redis being introduced for Payment Service, and what services might be affected if Redis were removed?';
    vi.mocked(askQuestion).mockResolvedValue({ ...result, support_status: 'partially_supported',
      tools_used: ['trace_decision', 'impact_analysis'],
      answer: 'Historical decision evidence: retrieved rationale [decision:test].\n\nPotential downstream impact: structural evidence only. Missing textual proof of failure propagation.',
    });
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('textbox'));
    await user.paste(combined); await user.keyboard('{Enter}');
    expect(await screen.findByText(/Historical decision evidence/)).toBeInTheDocument();
    expect(screen.getByText(/Potential downstream impact: structural evidence only/)).toBeInTheDocument();
    expect(screen.getByText('partially supported', { selector: '.support-badge' })).toBeInTheDocument();
    expect(askQuestion).toHaveBeenCalledWith(combined);
    expect(analyzeImpact).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Impact Analysis controls')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'test' }));
    expect(screen.getByLabelText('Source inspector')).toHaveTextContent('Fixture source excerpt');
    await user.click(screen.getByRole('button', { name: 'Inspect graph test node' }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('decision:test');
  });
  it('runs Impact Analysis from the card, separates findings, and inspects a highlighted path', async () => {
    vi.mocked(analyzeImpact).mockResolvedValue(impactFixture);
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: /Impact Analysis/ }));
    expect(await screen.findByRole('heading', { name: 'Impact Analysis' })).toBeInTheDocument();
    expect(analyzeImpact).toHaveBeenCalledWith({ entity_id: 'service:payment-service', max_depth: 2 });
    expect(askQuestion).not.toHaveBeenCalled();
    expect(within(screen.getByRole('region', { name: 'Direct Impact' })).getByText('service:checkout-service')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Potential Downstream Impact' })).getByText('service:order-service')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Direct Impact' })).queryByText('service:payment-service')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Highlight path to Order Service' }));
    expect(screen.getByRole('button', { name: 'Highlight path to Order Service' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('service:order-service');
    await user.selectOptions(screen.getByLabelText('Traversal depth'), '1');
    await user.click(screen.getByRole('button', { name: 'Analyze impact' }));
    expect(analyzeImpact).toHaveBeenLastCalledWith({ entity_id: 'service:payment-service', max_depth: 1 });
  });
  it('routes natural impact questions and retries with the selected target and depth', async () => {
    vi.mocked(analyzeImpact).mockRejectedValue(new ApiError('No graph connection.', 'GRAPH_UNAVAILABLE'));
    const user = userEvent.setup(); render(<App />);
    await user.type(screen.getByRole('textbox'), 'What services would be impacted if Redis were removed?{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('No graph connection.');
    expect(analyzeImpact).toHaveBeenCalledWith({ entity_id: 'tech:redis', max_depth: 2 });
    await user.click(screen.getByRole('button', { name: /Try again/ }));
    expect(analyzeImpact).toHaveBeenCalledTimes(2);
    expect(askQuestion).not.toHaveBeenCalled();
  });
  it('submits on Enter and renders labeled fixture evidence and citation inspector', async () => {
    vi.mocked(askQuestion).mockResolvedValue(result);
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole('textbox', { name: 'Ask about your company knowledge' }), 'Why does Payment Service use Redis?{Enter}');
    await screen.findByText(/Test-only evidence summary/);
    expect(askQuestion).toHaveBeenCalledWith('Why does Payment Service use Redis?');
    expect(screen.getByText('Development fixture')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'test' }));
    expect(screen.getByText('Fixture source excerpt')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByText('Fixture source excerpt')).not.toBeInTheDocument();
  });
  it('preserves the question and offers retry after an API error', async () => {
    vi.mocked(askQuestion).mockRejectedValue(new ApiError('Configure the graph adapter.', 'GRAPH_UNAVAILABLE'));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole('textbox'), 'Why was Redis introduced?');
    await user.click(screen.getByRole('button', { name: 'Ask question' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Configure the graph adapter.');
    expect(screen.getByRole('textbox')).toHaveValue('Why was Redis introduced?');
    vi.mocked(askQuestion).mockResolvedValue(result);
    await user.click(screen.getByRole('button', { name: /Try again/ }));
    await screen.findByText(/Test-only evidence summary/);
  });
  it('prevents duplicate requests and disables the composer while loading', async () => {
    let resolve: (response: QueryResponse) => void = () => {};
    vi.mocked(askQuestion).mockImplementation(() => new Promise(done => { resolve = done; }));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Decision Trace/ }));
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Ask question' })).toBeDisabled();
    expect(askQuestion).toHaveBeenCalledTimes(1);
    resolve(result);
    await waitFor(() => expect(screen.getByRole('textbox')).not.toBeDisabled());
  });
  it('Shift+Enter inserts a newline without submitting', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByRole('textbox'), 'Why Redis?{Shift>}{Enter}{/Shift}More context');
    expect(askQuestion).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox')).toHaveValue('Why Redis?\nMore context');
  });
});

describe('workspace preferences and evidence navigation', () => {
  it('sets, retains and clears a local name without changing the greeting pair on rerender', async () => {
    localStorage.setItem('weave.preferredName', 'Mira');
    const user = userEvent.setup();
    const { rerender } = render(<App />);
    const heading = screen.getByRole('heading', { level: 1 }).textContent;
    expect(heading).toContain('Mira');
    rerender(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(heading!);
    await user.click(screen.getByRole('button', { name: 'Personalize greeting' }));
    await user.clear(screen.getByLabelText(/Preferred name/));
    await user.type(screen.getByLabelText(/Preferred name/), '  Ana  ');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(localStorage.getItem('weave.preferredName')).toBe('Ana');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ana');
    await user.click(screen.getByRole('button', { name: 'Personalize greeting' }));
    await user.click(screen.getByRole('button', { name: 'Clear name' }));
    expect(localStorage.getItem('weave.preferredName')).toBe('');
  });
  it('collapses sidebars independently and restores saved preferences', async () => {
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }));
    await user.click(screen.getByRole('button', { name: 'Collapse details panel' }));
    expect(document.querySelector('.app-shell')).toHaveClass('left-collapsed', 'right-collapsed');
    await user.click(screen.getByRole('button', { name: 'Expand navigation' }));
    expect(document.querySelector('.app-shell')).not.toHaveClass('left-collapsed');
    expect(document.querySelector('.app-shell')).toHaveClass('right-collapsed');
    unmount(); render(<App />);
    expect(screen.getByRole('button', { name: 'Expand details panel' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Collapse navigation' })).toBeInTheDocument();
  });
  it('opens a selected node, preserves selection through collapse, and dismisses on Escape', async () => {
    vi.mocked(askQuestion).mockResolvedValue(result);
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: /Decision Trace/ }));
    await screen.findByText(/Test-only evidence summary/);
    await user.click(screen.getByRole('button', { name: 'Collapse details panel' }));
    await user.click(screen.getByRole('button', { name: 'Inspect graph test node' }));
    expect(screen.getByLabelText('Entity inspector')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Collapse details panel' }));
    expect(screen.getByRole('button', { name: 'Inspect graph test node' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: 'Expand details panel' }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('decision:test');
    await user.keyboard('{Escape}');
    expect(screen.queryByLabelText('Entity inspector')).not.toBeInTheDocument();
  });
  it('shares the composer and supports arrow-key tabs and linked entity navigation', async () => {
    vi.mocked(askQuestion).mockResolvedValue(result);
    const user = userEvent.setup(); render(<App />);
    expect(document.querySelector('.welcome-composer')).toContainElement(screen.getByRole('textbox'));
    await user.click(screen.getByRole('button', { name: /Decision Trace/ }));
    await screen.findByText(/Test-only evidence summary/);
    expect(document.querySelector('.docked-composer')).toContainElement(screen.getByRole('textbox'));
    const graphTab = screen.getByRole('tab', { name: 'Evidence graph' });
    graphTab.focus(); await user.keyboard('{ArrowRight}{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Key sources (1)' })).toHaveAttribute('aria-selected', 'true');
    await user.click(within(screen.getByRole('tabpanel')).getByRole('button', { name: /Test decision/ }));
    await user.click(within(screen.getByLabelText('Source inspector')).getByRole('button', { name: 'Test decision' }));
    expect(screen.getByLabelText('Entity inspector')).toHaveTextContent('decision:test');
  });
});
