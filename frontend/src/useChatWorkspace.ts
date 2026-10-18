import { useEffect, useRef, useState } from 'react';
import { browserChatRepository } from './chatStorage';
import type { ChatRepository } from './chatStorage';
import { assertStorageBounds, blankUI, emptyWorkspace, MAX_CHATS, MAX_TURNS, newConversation, newId, titleFor } from './workspace';
import type { ChatTurn, ChatUI, Conversation, ToolRequest, WorkspaceArchive } from './workspace';
import type { QueryResponse } from './types';

export function useChatWorkspace(repository: ChatRepository = browserChatRepository) {
  const [archive, setArchive] = useState(emptyWorkspace);
  const current = useRef(archive);
  const [ready, setReady] = useState(() => repository === browserChatRepository && typeof indexedDB === 'undefined');
  const [storageWarning, setStorageWarning] = useState('');
  const [workspaceNotice, setWorkspaceNotice] = useState('');
  const writable = useRef(false);
  const writes = useRef<Promise<void>>(Promise.resolve());
  const revision = useRef(0);
  const pendingDeletion = useRef(false);
  const mounted = useRef(true);

  function enqueue(snapshot: WorkspaceArchive, deletion = false) {
    if (!writable.current) return;
    try { assertStorageBounds(snapshot); } catch (cause) {
      setStorageWarning(cause instanceof Error ? cause.message : 'History could not be saved.'); return;
    }
    const sequence = ++revision.current;
    if (deletion) pendingDeletion.current = true;
    writes.current = writes.current.catch(() => {}).then(() => repository.save(snapshot)).then(() => {
      if (sequence === revision.current) { pendingDeletion.current = false; if (mounted.current) setStorageWarning(''); }
    }, () => {
      if (mounted.current && sequence === revision.current) setStorageWarning(pendingDeletion.current
        ? 'Deletion could not be saved. Previously stored chats may reappear after refresh.'
        : 'Chat history could not be saved. This session remains available; browser storage may be full or restricted.');
    });
  }
  function commit(next: WorkspaceArchive, immediate = false, deletion = false) {
    current.current = next; setArchive(next); if (immediate) enqueue(next, deletion);
  }
  useEffect(() => {
    let cancelled = false; mounted.current = true;
    void repository.load().then(saved => {
      if (cancelled) return;
      const next = saved ?? current.current; current.current = next; setArchive(next);
      writable.current = true; setReady(true);
    }).catch(() => {
      if (!cancelled) { setReady(true); setStorageWarning('Saved history could not be opened. Chats work for this session only; existing storage is untouched.'); }
    });
    return () => { cancelled = true; mounted.current = false; };
  }, [repository]);
  useEffect(() => {
    if (!ready) return;
    // Interaction state is debounced; messages and destructive actions save immediately.
    const timer = setTimeout(() => enqueue(current.current), 150);
    return () => clearTimeout(timer);
    // enqueue reads the current archive and the fixed repository.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [archive, ready]);
  useEffect(() => {
    const flush = () => enqueue(current.current);
    const hidden = () => { if (document.visibilityState === 'hidden') flush(); };
    window.addEventListener('pagehide', flush); document.addEventListener('visibilitychange', hidden);
    return () => { window.removeEventListener('pagehide', flush); document.removeEventListener('visibilitychange', hidden); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repository]);

  function update(id: string, fn: (chat: Conversation) => Conversation, immediate = false) {
    if (!mounted.current) return;
    const state = current.current;
    if (!state.conversations.some(c => c.id === id)) return; // Deleted requests cannot resurrect a conversation.
    commit({ ...state, conversations: state.conversations.map(c => c.id === id ? fn(c) : c) }, immediate);
  }
  function ui(id: string, patch: Partial<ChatUI>, playbackOwner?: { turnId: string; sequenceId: string; step: number }) {
    update(id, c => {
      // Also guard callbacks already queued when a playback component unmounts.
      if (playbackOwner && (current.current.activeId !== id || c.ui.selectedTurnId !== playbackOwner.turnId
        || c.ui.view !== 'graph' || c.ui.tab !== 'graph' || c.ui.trace?.sequenceId !== playbackOwner.sequenceId
        || c.ui.trace.step !== playbackOwner.step)) return c;
      return { ...c, ui: { ...c.ui, ...patch } };
    });
  }
  function create() {
    if (!ready) return;
    if (current.current.conversations.length >= MAX_CHATS) { setWorkspaceNotice(`The ${MAX_CHATS}-chat limit is reached. Delete a chat before starting another.`); return; }
    setWorkspaceNotice('');
    const chat = newConversation(); commit({ ...current.current, activeId: chat.id, conversations: [...current.current.conversations, chat] }, true);
  }
  function select(id: string) {
    if (current.current.conversations.some(c => c.id === id)) commit({ ...current.current, activeId: id }, true);
  }
  function selectTurn(chatId: string, turnId: string, patch: Partial<ChatUI> = {}) {
    update(chatId, c => c.turns.some(t => t.id === turnId) ? { ...c, ui: { ...blankUI(), input: c.ui.input, selectedTurnId: turnId, ...patch } } : c);
  }
  function start(chatId: string, question: string, request: ToolRequest): string | null {
    const chat = current.current.conversations.find(c => c.id === chatId);
    if (!ready || !chat || chat.turns.some(t => t.status === 'pending')) return null;
    const retry = chat.turns.find(t => t.id === chat.ui.selectedTurnId && t.status === 'error' && t.question === question
      && JSON.stringify(t.request) === JSON.stringify(request));
    if (!retry && chat.turns.length >= MAX_TURNS) { setWorkspaceNotice(`This chat has reached ${MAX_TURNS} messages. Start a new chat to continue.`); return null; }
    const now = new Date().toISOString();
    const turn: ChatTurn = { id: retry?.id ?? newId(), question, createdAt: retry?.createdAt ?? now, request, status: 'pending', result: null, error: null };
    update(chatId, c => ({ ...c, title: !c.turns.length && c.title === 'New chat' ? titleFor(question) : c.title,
      updatedAt: now, turns: retry ? c.turns.map(t => t.id === retry.id ? turn : t) : [...c.turns, turn],
      ui: { ...blankUI(), detailsOpen: c.ui.detailsOpen, input: question, selectedTurnId: turn.id } }), true);
    return turn.id;
  }
  function finish(chatId: string, turnId: string, result: QueryResponse | null, error: ChatTurn['error'] = null) {
    update(chatId, c => ({ ...c, updatedAt: new Date().toISOString(),
      turns: c.turns.map(t => t.id === turnId && t.status === 'pending' ? { ...t, result, error, status: error ? 'error' : 'complete' } : t),
      ui: { ...c.ui, input: result && c.ui.selectedTurnId === turnId ? '' : c.ui.input } }), true);
  }
  function rename(id: string, title: string) {
    const clean = titleFor(title); if (clean) update(id, c => ({ ...c, title: clean, updatedAt: new Date().toISOString() }), true);
  }
  function remove(id: string) {
    setWorkspaceNotice('');
    const state = current.current; const remaining = state.conversations.filter(c => c.id !== id);
    if (remaining.length === state.conversations.length) return;
    const conversations = remaining.length ? remaining : [newConversation()];
    commit({ ...state, conversations, activeId: state.activeId === id ? [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0].id : state.activeId }, true, true);
  }
  function clear() {
    setWorkspaceNotice(''); writable.current = true; commit(emptyWorkspace(), true, true);
  }
  return { archive, conversation: archive.conversations.find(c => c.id === archive.activeId)!, ready, storageWarning: workspaceNotice || storageWarning,
    ui, create, select, selectTurn, start, finish, rename, remove, clear };
}
