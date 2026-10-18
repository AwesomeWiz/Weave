import { restoreEvidence } from './api';
import { traceSequences } from './traceValidation';
import type { ChangeInput, ExpertInput, FreshnessInput, ImpactInput, QueryResponse } from './types';

export const MAX_CHATS = 20;
export const MAX_TURNS = 40;
export const MAX_CHAT_BYTES = 4 * 1024 * 1024;
export const MAX_HISTORY_BYTES = 20 * 1024 * 1024;
export type WorkspacePage = 'chat' | 'decisions' | 'services' | 'people' | 'changes';
export const PAGE_LABELS = { chat: 'Chat', decisions: 'Decisions', services: 'Services', people: 'People', changes: 'Changes' };
export interface ToolRequest { change: ChangeInput | null; impact: ImpactInput | null; expert: ExpertInput | null; freshness: FreshnessInput | null }
export interface ChatTurn {
  id: string; question: string; createdAt: string; request: ToolRequest;
  status: 'pending' | 'complete' | 'error'; result: QueryResponse | null; error: { code: string; message: string } | null;
}
export interface ChatUI {
  input: string; selectedTurnId: string | null; view: 'chat' | 'graph';
  tab: 'graph' | 'timeline' | 'sources' | 'relationships'; graphScope: 'focused' | 'all';
  selectedNodeId: string | null; selectedSourceId: string | null;
  highlightedPath: string[]; highlightedFinding: string | null; graphSearch: string; detailsOpen: boolean;
  trace?: { sequenceId: string; step: number } | null;
}
export interface Conversation { id: string; title: string; createdAt: string; updatedAt: string; turns: ChatTurn[]; ui: ChatUI }
export interface WorkspaceArchive { version: 1; activeId: string; conversations: Conversation[] }

export const newId = () => crypto.randomUUID();
export function blankUI(): ChatUI {
  let detailsOpen = true;
  try { detailsOpen = localStorage.getItem('weave.sidebar.right') !== 'collapsed'; } catch { /* Browser may block preferences. */ }
  return { input: '', selectedTurnId: null, view: 'chat', tab: 'graph', graphScope: 'focused', selectedNodeId: null,
    selectedSourceId: null, highlightedPath: [], highlightedFinding: null, graphSearch: '', detailsOpen, trace: null };
}
export function newConversation(): Conversation {
  const now = new Date().toISOString();
  return { id: newId(), title: 'New chat', createdAt: now, updatedAt: now, turns: [], ui: blankUI() };
}
export function emptyWorkspace(): WorkspaceArchive {
  const chat = newConversation(); return { version: 1, activeId: chat.id, conversations: [chat] };
}
export function titleFor(value: string): string { return value.replace(/[\p{Cc}\p{Cf}]/gu, '').trim().replace(/\s+/g, ' ').slice(0, 100); }
export function recentGroup(timestamp: string, now = new Date()): string {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(start); yesterday.setDate(yesterday.getDate() - 1);
  const week = new Date(start); week.setDate(week.getDate() - 7);
  const date = new Date(timestamp);
  return date >= start ? 'Today' : date >= yesterday ? 'Yesterday' : date >= week ? 'Previous 7 Days' : 'Older';
}

const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown, max: number): v is string => typeof v === 'string' && v.length <= max;
const id = (v: unknown): v is string => text(v, 100) && v.length > 0;
const date = (v: unknown): v is string => text(v, 40) && Number.isFinite(Date.parse(v));
const nullable = (v: unknown): v is string | null => v === null || id(v);
export function byteSize(v: unknown) { return new TextEncoder().encode(JSON.stringify(v)).length; }

/** Reject the whole save instead of redacting/changing evidence provenance. */
export function containsCredentials(value: unknown): boolean {
  if (typeof value === 'string') return /\bBearer\s+[A-Za-z0-9._~-]{8,}|\bsk-[A-Za-z0-9_-]{16,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY|\b(?:[A-Z0-9_]*(?:API_KEY|PASSWORD|SECRET|ACCESS_TOKEN|PRIVATE_KEY)|api key|authorization)\s*[:=]\s*\S+/i.test(value);
  if (Array.isArray(value)) return value.some(containsCredentials);
  return record(value) && Object.entries(value).some(([key, v]) =>
    /(?:apikey|password|accesstoken|refreshtoken|sessiontoken|clientsecret|privatekey|secretkey|authorization)$|^(?:cookie|setcookie|credentials)$/
      .test(key.toLowerCase().replace(/[^a-z]/g, '')) || containsCredentials(v));
}
export function assertStorageBounds(archive: WorkspaceArchive) {
  if (archive.conversations.length > MAX_CHATS || byteSize(archive) > MAX_HISTORY_BYTES
    || archive.conversations.some(c => c.turns.length > MAX_TURNS || byteSize(c) > MAX_CHAT_BYTES))
    throw new Error('History limit reached. Delete chats to save more; this session remains available.');
  if (containsCredentials(archive)) throw new Error('History was not saved because credential-like data was detected. This session remains available.');
}

function validRequest(v: unknown): v is ToolRequest {
  if (!record(v) || Object.keys(v).length !== 4 || ['change', 'impact', 'expert', 'freshness'].some(k => !(k in v))) return false;
  if (Object.values(v).filter(x => x !== null).length > 1) return false;
  return (v.change === null || record(v.change) && text(v.change.target, 256) && text(v.change.change, 2000))
    && (v.impact === null || record(v.impact) && text(v.impact.entity_id, 128) && /^service:|^tech:/.test(v.impact.entity_id)
      && Number.isInteger(v.impact.max_depth) && Number(v.impact.max_depth) >= 1 && Number(v.impact.max_depth) <= 3)
    && (v.expert === null || record(v.expert) && text(v.expert.query, 2000) && Number.isInteger(v.expert.limit) && Number(v.expert.limit) >= 1 && Number(v.expert.limit) <= 10)
    && (v.freshness === null || record(v.freshness) && text(v.freshness.entity, 256));
}
function validTurn(v: unknown): v is ChatTurn {
  if (!record(v) || !id(v.id) || !text(v.question, 2000) || !v.question.trim() || !date(v.createdAt) || !validRequest(v.request)
    || !['pending', 'complete', 'error'].includes(String(v.status))) return false;
  if (v.status === 'complete') {
    if (v.error !== null) return false;
    try { restoreEvidence(v.result, v.request); } catch { return false; }
    return true;
  }
  return v.result === null && (v.status === 'pending' ? v.error === null
    : record(v.error) && text(v.error.code, 100) && text(v.error.message, 2000));
}
function validChat(v: unknown): v is Conversation {
  if (!record(v) || !id(v.id) || !text(v.title, 100) || !v.title.trim() || !date(v.createdAt) || !date(v.updatedAt)
    || !Array.isArray(v.turns) || v.turns.length > MAX_TURNS || !v.turns.every(validTurn)
    || new Set(v.turns.map(t => t.id)).size !== v.turns.length || v.turns.filter(t => t.status === 'pending').length > 1 || !record(v.ui)) return false;
  const ui = v.ui;
  if (!text(ui.input, 2000) || !nullable(ui.selectedTurnId) || (v.turns.length > 0 && !v.turns.some(t => t.id === ui.selectedTurnId))
    || !['chat', 'graph'].includes(String(ui.view)) || !['graph', 'timeline', 'sources', 'relationships'].includes(String(ui.tab))
    || !['focused', 'all'].includes(String(ui.graphScope)) || !text(ui.graphSearch, 2000) || typeof ui.detailsOpen !== 'boolean'
    || !nullable(ui.selectedNodeId) || !nullable(ui.selectedSourceId) || !nullable(ui.highlightedFinding)
    || !Array.isArray(ui.highlightedPath) || !ui.highlightedPath.every(id)) return false;
  const response = v.turns.find(t => t.id === ui.selectedTurnId)?.result;
  return (!ui.selectedNodeId || !!response?.graph.nodes.some(n => n.id === ui.selectedNodeId))
    && (!ui.selectedSourceId || !!response?.sources.some(s => s.id === ui.selectedSourceId))
    && ui.highlightedPath.every(id => response?.graph.edges.some(e => e.id === id));
}
export function restoreArchive(value: unknown): WorkspaceArchive {
  if (!record(value) || value.version !== 1 || !id(value.activeId) || !Array.isArray(value.conversations)
    || !value.conversations.length || value.conversations.length > MAX_CHATS || byteSize(value) > MAX_HISTORY_BYTES || !value.conversations.every(validChat)
    || new Set(value.conversations.map(c => c.id)).size !== value.conversations.length
    || !value.conversations.some(c => c.id === value.activeId)) throw new Error('Saved history is incompatible. Original storage has been left untouched.');
  const archive = value as unknown as WorkspaceArchive;
  assertStorageBounds(archive);
  // A refresh cannot continue an HTTP request. Keep its user message, permit an explicit retry.
  return { ...archive, conversations: archive.conversations.map(c => ({ ...c,
    ui: { ...c.ui, trace: restoredTrace(c) }, turns: c.turns.map(t => t.status === 'pending'
    ? { ...t, status: 'error', error: { code: 'INTERRUPTED', message: 'This request was interrupted by refresh. Retry to run it again.' } } : t) })) };
}

function restoredTrace(chat: Conversation): ChatUI['trace'] {
  const selected = chat.ui.trace;
  const result = chat.turns.find(t => t.id === chat.ui.selectedTurnId)?.result ?? null;
  if (!record(selected) || typeof selected.sequenceId !== 'string' || !Number.isInteger(selected.step)) return null;
  const sequence = traceSequences(result).find(s => s.id === selected.sequenceId);
  return sequence && selected.step >= 0 && selected.step < sequence.steps.length ? { sequenceId: selected.sequenceId, step: selected.step } : null;
}
