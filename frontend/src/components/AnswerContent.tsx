import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { Lexer } from 'marked';
import type { MarkedToken, Token } from 'marked';
import { safeSourceUrl } from '../api';
import type { Source } from '../types';

/** Tokenize Markdown with Marked, then render an explicit React element allowlist.
 * Never use Marked's HTML output, raw HTML, images or dangerouslySetInnerHTML. */
export default function AnswerContent({ text, sources, onSource }: {
  text: string; sources: Source[]; onSource: (source: Source) => void;
}) {
  const inventory = new Map(sources.map(source => [source.id, source]));
  function citation(id: string): ReactNode {
    const source = inventory.get(id);
    return source ? <button className="citation" title={source.title} onClick={() => onSource(source)}>{id}</button>
      : <span className="citation unavailable" title="This source was not returned">{id} · source unavailable</span>;
  }
  function content(value: string): ReactNode {
    return value.split(/(\[[^\]\n]+\])/g).map((part, index) => {
      const id = part.slice(1, -1);
      return <Fragment key={index}>{part.startsWith('[') && part.endsWith(']') && (inventory.has(id) || /^[a-zA-Z][\w-]*:/.test(id))
        ? citation(id) : part}</Fragment>;
    });
  }
  function render(tokens: Token[], depth = 0): ReactNode {
    // Unknown/very deeply nested syntax remains visible as inert original text.
    if (depth > 30) return tokens.map(token => token.raw).join('');
    return tokens.map((entry, index) => {
      // This Lexer has no extensions; its output consists only of built-in tokens.
      const token = entry as MarkedToken;
      const child = (items: Token[]) => render(items, depth + 1);
      let node: ReactNode;
      switch (token.type) {
        case 'space': case 'def': node = null; break;
        case 'heading': {
          const Tag = token.depth <= 2 ? 'h3' : 'h4'; node = <Tag>{child(token.tokens)}</Tag>; break;
        }
        case 'paragraph': node = <p>{child(token.tokens)}</p>; break;
        case 'text': node = token.tokens ? child(token.tokens) : content(token.text); break;
        case 'escape': node = token.text; break;
        case 'strong': node = <strong>{child(token.tokens)}</strong>; break;
        case 'em': node = <em>{child(token.tokens)}</em>; break;
        case 'del': node = <del>{child(token.tokens)}</del>; break;
        case 'br': node = <br />; break;
        case 'hr': node = <hr />; break;
        case 'codespan': node = <code>{token.text}</code>; break;
        case 'code': node = <pre><code>{token.text}</code></pre>; break;
        case 'html': node = token.raw; break;
        case 'image': node = token.raw; break;
        case 'blockquote': node = <blockquote>{child(token.tokens)}</blockquote>; break;
        case 'list': {
          const items = token.items.map((item, i) => <li key={i}>{item.task && <span>{item.checked ? '[x] ' : '[ ] '}</span>}{child(item.tokens)}</li>);
          node = token.ordered ? <ol start={Number(token.start)}>{items}</ol> : <ul>{items}</ul>; break;
        }
        case 'list_item': node = <li>{child(token.tokens)}</li>; break;
        case 'checkbox': node = token.checked ? '[x]' : '[ ]'; break;
        case 'link': {
          // A Markdown URL cannot replace a source handle's verified Inspector action.
          if (inventory.has(token.text) || /^[a-zA-Z][\w-]*:(?!\/\/)[^\s]+$/.test(token.text) && token.raw.startsWith('[')) node = citation(token.text);
          else {
            const url = safeSourceUrl(token.href);
            // Link text stays text: never nest a citation button inside an anchor.
            node = url ? <a href={url} target="_blank" rel="noopener noreferrer">{token.text}</a>
              : <span>{token.text} <span className="muted">(link unavailable)</span></span>;
          }
          break;
        }
        case 'table': node = <div className="answer-table" tabIndex={0} role="region" aria-label="Answer table"><table>
          <thead><tr>{token.header.map((cell, i) => <th key={i} scope="col">{child(cell.tokens)}</th>)}</tr></thead>
          <tbody>{token.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{child(cell.tokens)}</td>)}</tr>)}</tbody>
        </table></div>; break;
        default: node = entry.raw;
      }
      return <Fragment key={index}>{node}</Fragment>;
    });
  }
  return <div className="answer-text rich-answer">{render(new Lexer({ gfm: true, breaks: true }).lex(text))}</div>;
}
