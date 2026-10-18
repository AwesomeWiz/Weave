import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import KnowledgeStatus from './components/KnowledgeStatus';
import type { Health } from './types';

const connected: Health = { status: 'ok', backend: 'available', falkordb: 'connected', graph_tool: 'available', llm: 'available', graph: 'novapay', graph_mode: 'falkordb' };
afterEach(cleanup);
describe('trusted graph health presentation', () => {
  it.each([
    ['connected', connected, false, 'Knowledge graph connected'],
    ['unavailable', { ...connected, falkordb: 'unavailable' }, false, 'Knowledge graph unavailable'],
    ['unavailable', { ...connected, graph_tool: 'unavailable' }, false, 'Knowledge graph unavailable'],
    ['unavailable', null, true, 'Backend unavailable'],
    ['checking', null, false, 'Checking connection'],
    ['unknown', { ...connected, falkordb: 'not_checked' }, false, 'Graph connection not checked'],
    ['partial', { ...connected, graph_tool: 'fixture' }, false, 'Knowledge graph partly available'],
    ['sample', { ...connected, graph_mode: 'fixture', graph_tool: 'fixture', falkordb: 'not_checked' }, false, 'Sample workspace'],
  ] as const)('maps %s to a matching accessible icon and status', (state, health, failed, title) => {
    const { container } = render(<KnowledgeStatus health={health} failed={failed} onRefresh={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent(title);
    expect(container.querySelector(`[data-status-icon="${state}"]`)).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('.knowledge-state')).toHaveClass(`health-${state}`);
    if (state !== 'connected') expect(container.querySelector('.lucide-circle-check,.health-connected')).toBeNull();
  });
  it('keeps provider degradation separate from an actually connected graph', () => {
    render(<KnowledgeStatus health={{ ...connected, status: 'degraded', llm: 'unavailable' }} failed={false} onRefresh={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Knowledge graph connected');
    expect(screen.getByText(/Answer provider unavailable/)).toBeInTheDocument();
  });
  it('offers a working refresh and transitions checking → unavailable → connected', () => {
    const refresh = vi.fn(); const props = { failed: false, onRefresh: refresh };
    const app = render(<KnowledgeStatus {...props} health={null} />);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh connection status' })); expect(refresh).toHaveBeenCalledOnce();
    app.rerender(<KnowledgeStatus {...props} health={{ ...connected, falkordb: 'unavailable' }} />);
    expect(screen.getByRole('status')).toHaveTextContent('Knowledge graph unavailable');
    expect(screen.getByText('Backend available')).toBeInTheDocument();
    app.rerender(<KnowledgeStatus {...props} health={connected} />);
    expect(screen.getByRole('status')).toHaveTextContent('Knowledge graph connected');
  });
});
