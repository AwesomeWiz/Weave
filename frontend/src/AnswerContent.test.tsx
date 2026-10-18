import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AnswerContent from './components/AnswerContent';
import { changeWithPlayback } from './test/tracePlaybackFixture';

afterEach(cleanup);
const sources = changeWithPlayback().sources;
const renderAnswer = (text: string, onSource = vi.fn()) => render(<AnswerContent text={text} sources={sources} onSource={onSource} />);
describe('safe answer presentation', () => {
  it('preserves plain paragraphs and meaningful line breaks', () => {
    const { container } = renderAnswer('First line\nSecond line\n\nAnother paragraph.');
    expect(container.querySelectorAll('p')).toHaveLength(2);
    expect(container.querySelectorAll('br')).toHaveLength(1);
    expect(container.textContent).toBe('First lineSecond lineAnother paragraph.');
  });
  it('renders headings, emphasis, numbered and bullet lists without rewriting facts', () => {
    renderAnswer('# Short answer\n**Payment Service** uses *Redis*.\n\n## Why\n- One fact\n- Another fact\n\n### Checks\n1. Run a test\n2. Request review');
    expect(screen.getByRole('heading', { name: 'Short answer' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Why' })).toBeInTheDocument();
    expect(screen.getAllByRole('list')).toHaveLength(2);
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByText('Payment Service').tagName).toBe('STRONG');
    expect(screen.getByText('Redis').tagName).toBe('EM');
  });
  it('opens only an exact returned source from a keyboard-accessible citation', () => {
    const select = vi.fn(); renderAnswer('Rationale [issue:PAY-42].', select);
    const citation = screen.getByRole('button', { name: 'issue:PAY-42' });
    citation.focus(); expect(citation).toHaveFocus(); fireEvent.click(citation);
    expect(select).toHaveBeenCalledWith(sources.find(s => s.id === 'issue:PAY-42'));
  });
  it('labels missing or sibling-only citations unavailable without creating a button', () => {
    const select = vi.fn(); renderAnswer('Missing [issue:foreign]. Graph-only [service:payment-service].', select);
    expect(screen.getByText('issue:foreign · source unavailable')).toBeInTheDocument();
    expect(screen.getByText('service:payment-service · source unavailable')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument(); expect(select).not.toHaveBeenCalled();
  });
  it('treats raw HTML, scripts, images and event handlers as inert text', () => {
    const { container } = renderAnswer('<script>alert(1)</script>\n<img src=x onerror=alert(2)>\n<iframe src="private"></iframe>');
    expect(container.querySelector('script,img,iframe')).toBeNull();
    expect(container).toHaveTextContent('<script>alert(1)</script>');
  });
  it.each(['javascript:alert', 'data:text/html,unsafe', 'vbscript:unsafe', 'file:///secret'])('rejects unsafe link %s', url => {
    renderAnswer(`[Open](${url})`); expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText('(link unavailable)')).toBeInTheDocument();
  });
  it('renders only safe external links and keeps code inert', () => {
    renderAnswer('[ADR](https://example.com/adr) and `service:payment-service`.');
    expect(screen.getByRole('link', { name: 'ADR' })).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('service:payment-service').tagName).toBe('CODE');
  });
  it('handles nested lists and literal code without turning code into evidence', () => {
    const { container } = renderAnswer('- First\n  - Nested\n\n```text\n[issue:PAY-42]\n```');
    expect(screen.getAllByRole('list')).toHaveLength(2);
    expect(container.querySelector('pre code')).toHaveTextContent('[issue:PAY-42]');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
  it('prevents Markdown links from redirecting a verified citation to another destination', () => {
    const select = vi.fn(); renderAnswer('[issue:PAY-42](https://example.com/unrelated)', select);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'issue:PAY-42' }));
    expect(select).toHaveBeenCalledWith(sources.find(s => s.id === 'issue:PAY-42'));
  });
  it('renders a supplied table in an independently scrollable region', () => {
    renderAnswer('Service | Status\n--- | ---\nPayment | Partial');
    expect(screen.getByRole('region', { name: 'Answer table' })).toHaveAttribute('tabindex', '0');
    expect(screen.getAllByRole('columnheader')).toHaveLength(2);
    expect(screen.getByRole('cell', { name: 'Partial' })).toBeInTheDocument();
  });
  it.each(['deterministic', 'openrouter'])('retains a long %s answer and exact qualifiers', generation => {
    const text = `## ${generation}\n` + ('A potential risk, not guaranteed failure. '.repeat(400)) + '\n\n[issue:PAY-42]';
    const { container } = renderAnswer(text);
    expect(container.querySelector('.rich-answer')).toBeInTheDocument();
    expect(container.textContent!.match(/not guaranteed failure/g)).toHaveLength(400);
    expect(screen.getByRole('button', { name: 'issue:PAY-42' })).toBeInTheDocument();
  });
});
