import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Clock3, MoreHorizontal, Pencil, Search, Trash2, X } from 'lucide-react';
import type { Conversation } from '../workspace';
import { recentGroup } from '../workspace';
import WorkspacePanel from './WorkspacePanel';

export default function ConversationList({ conversations, activeId, onSelect, onRename, onDelete, onClear }: {
  conversations: Conversation[]; activeId: string; onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void; onDelete: (id: string) => void; onClear: () => void;
}) {
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [menu, setMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuTrigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!menu) return;
    menuRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const close = (event: PointerEvent) => { if (!menuRef.current?.contains(event.target as Node) && !menuTrigger.current?.contains(event.target as Node)) setMenu(null); };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menu]);
  const [action, setAction] = useState<{ kind: 'rename' | 'delete' | 'clear'; id?: string; title?: string } | null>(null);
  const [title, setTitle] = useState('');
  const filtered = [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).filter(c =>
    c.title.toLocaleLowerCase().includes(search.toLocaleLowerCase()) || c.turns.some(t => t.question.toLocaleLowerCase().includes(search.toLocaleLowerCase())));
  const groups = ['Today', 'Yesterday', 'Previous 7 Days', 'Older'];
  return <div className="sidebar-section history-section chat-list">
    <div className="panel-heading"><p className="section-label">Recent Chats</p><div className="history-tools"><button className="icon-button" aria-label={searchOpen ? 'Close chat search' : 'Search chats'} aria-expanded={searchOpen} onClick={() => { setSearchOpen(!searchOpen); setSearch(''); }}>{searchOpen ? <X size={16} /> : <Search size={16} />}</button><button className="icon-button" aria-label="Clear history" title="Clear history" onClick={() => setAction({ kind: 'clear' })}><Trash2 size={15} /></button></div></div>
    {searchOpen && <label className="chat-search"><Search size={15} /><span className="sr-only">Search chats</span><input autoFocus type="search" value={search} maxLength={200} onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); setSearchOpen(false); setSearch(''); } }} onChange={e => setSearch(e.target.value)} placeholder="Search titles and questions…" /></label>}
    {groups.map(group => {
      const items = filtered.filter(c => recentGroup(c.updatedAt) === group);
      return items.length > 0 && <section key={group} aria-label={`${group} chats`}>{filtered.length > 4 && <h2 className="chat-group-label">{group}</h2>}
        {items.map(c => <div className={`chat-list-row ${activeId === c.id ? 'active' : ''}`} key={c.id}>
          <button className="history-item" title={c.title} aria-label={`Open chat: ${c.title}`} aria-current={activeId === c.id ? 'page' : undefined} onClick={() => onSelect(c.id)}>
            <Clock3 size={15} /><span>{c.title}<small>{c.turns.some(t => t.status === 'pending') ? 'Answering…' : `${c.turns.length} ${c.turns.length === 1 ? 'message' : 'messages'}`}</small></span></button>
          <div className="chat-row-actions"><button className="icon-button" aria-label={`Chat actions: ${c.title}`} aria-haspopup="menu" aria-expanded={menu === c.id} onClick={e => { menuTrigger.current = e.currentTarget; setMenu(menu === c.id ? null : c.id); }}><MoreHorizontal size={17} /></button>
            {menu === c.id && <div ref={menuRef} role="menu" aria-label={`Actions for ${c.title}`} className="chat-context-menu" onKeyDown={e => {
              if (e.key === 'Escape') { e.stopPropagation(); setMenu(null); menuTrigger.current?.focus(); }
              if (e.key === 'Tab') setMenu(null);
              if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); const buttons = [...e.currentTarget.querySelectorAll('button')]; const index = buttons.indexOf(document.activeElement as HTMLButtonElement); buttons[(index + (e.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length]?.focus(); }
            }}><button role="menuitem" aria-label={`Rename chat: ${c.title}`} onClick={() => { menuTrigger.current?.focus(); setMenu(null); setTitle(c.title); setAction({ kind: 'rename', id: c.id, title: c.title }); }}><Pencil size={15} />Rename</button>
              <button role="menuitem" aria-label={`Delete chat: ${c.title}`} onClick={() => { menuTrigger.current?.focus(); setMenu(null); setAction({ kind: 'delete', id: c.id, title: c.title }); }}><Trash2 size={15} />Delete</button></div>}
          </div>
        </div>)}
      </section>;
    })}
    {!filtered.length && <p className="small muted">No chats match your search.</p>}
    <p className="chat-local-note">Saved on this browser only. Up to 20 chats / 20 MB. No cloud sync.</p>
    {action && createPortal(<div className="chat-modal-shade" onKeyDownCapture={e => { if (e.key === 'Escape') { e.stopPropagation(); setAction(null); } }}>
      <WorkspacePanel id="chat-management-dialog" className="chat-modal" modal label={action.kind === 'rename' ? 'Rename chat' : action.kind === 'delete' ? 'Delete chat' : 'Clear history'}>
        <h2>{action.kind === 'rename' ? 'Rename chat' : action.kind === 'delete' ? 'Delete this chat?' : 'Clear all chat history?'}</h2>
        {action.kind === 'rename' ? <form onSubmit={e => { e.preventDefault(); if (title.trim()) { onRename(action.id!, title); setAction(null); } }}>
          <label>Chat title<input value={title} maxLength={100} onChange={e => setTitle(e.target.value)} /></label>
          <div className="chat-dialog-actions"><button className="button" type="button" onClick={() => setAction(null)}>Cancel</button><button className="button primary" disabled={!title.trim()} type="submit">Save title</button></div>
        </form> : <><p>{action.kind === 'delete' ? `“${action.title}” and its saved evidence will be removed from this browser.` : 'All conversations and their saved evidence will be removed from this browser.'} This cannot be undone.</p>
          <div className="chat-dialog-actions"><button className="button" onClick={() => setAction(null)}>Cancel</button><button className="button danger" onClick={() => { if (action.kind === 'delete') onDelete(action.id!); else onClear(); setAction(null); }}>{action.kind === 'delete' ? 'Delete chat' : 'Clear history'}</button></div></>}
      </WorkspacePanel>
    </div>, document.body)}
  </div>;
}
