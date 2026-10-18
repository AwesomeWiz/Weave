import { afterEach, describe, expect, it, vi } from 'vitest';
import { assertStorageBounds, blankUI, containsCredentials, emptyWorkspace, MAX_CHAT_BYTES, MAX_HISTORY_BYTES, newConversation, recentGroup, restoreArchive } from './workspace';
import type { WorkspaceArchive } from './workspace';
import { changeWithOrderedPaths } from './test/orderedTraceFixture';
import { impactFixture } from './test/impactFixture';
import { expertFixture } from './test/expertFixture';
import { freshnessFixture } from './test/freshnessFixture';
import { restoreEvidence } from './api';
import { browserChatRepository } from './chatStorage';

afterEach(() => vi.unstubAllGlobals());
function saved(): WorkspaceArchive {
  const archive = emptyWorkspace(); const chat = archive.conversations[0];
  const result = changeWithOrderedPaths();
  chat.turns = [{ id: 'turn-1', question: 'Remove Redis from Payment Service', createdAt: chat.createdAt, status: 'complete', result, error: null,
    request: { change: { target: 'Payment Service', change: 'Remove Redis from Payment Service' }, impact: null, expert: null, freshness: null } }];
  chat.ui.selectedTurnId = 'turn-1'; return archive;
}
describe('versioned local conversation model', () => {
  it('round-trips complete structured evidence, paths, sources and generation without changing it', () => {
    const original = saved();
    const restored = restoreArchive(JSON.parse(JSON.stringify(original)));
    expect(restored).toEqual(original);
    expect(restored.conversations[0].turns[0].result).toEqual(changeWithOrderedPaths());
    expect(newConversation().id).not.toBe(original.activeId);
  });
  it('reuses all existing tool validators without a request', () => {
    const empty = { change: null, impact: null, expert: null, freshness: null };
    expect(restoreEvidence(impactFixture, { ...empty, impact: { entity_id: 'service:payment-service', max_depth: 2 } })).toEqual(impactFixture);
    expect(restoreEvidence(expertFixture, { ...empty, expert: { query: expertFixture.data.query, limit: 5 } })).toEqual(expertFixture);
    expect(restoreEvidence(freshnessFixture, { ...empty, freshness: { entity: 'Payment Service' } })).toEqual(freshnessFixture);
  });
  it('keeps interrupted messages for explicit retry without auto-running tools', () => {
    const archive = saved(); const turn = archive.conversations[0].turns[0];
    turn.status = 'pending'; turn.result = null;
    const restored = restoreArchive(archive).conversations[0].turns[0];
    expect(restored.id).toBe(turn.id); expect(restored.status).toBe('error');
    expect(restored.error?.code).toBe('INTERRUPTED'); expect(turn.status).toBe('pending');
  });
  it.each(['version', 'active', 'duplicate chat', 'duplicate message', 'date', 'request', 'paths', 'selection', 'source', 'too many chats'])('rejects corrupt saved %s without repairing evidence', damage => {
    const archive = saved(); const chat = archive.conversations[0];
    if (damage === 'version') archive.version = 99 as never;
    if (damage === 'active') archive.activeId = 'missing';
    if (damage === 'duplicate chat') archive.conversations.push(structuredClone(chat));
    if (damage === 'duplicate message') chat.turns.push(structuredClone(chat.turns[0]));
    if (damage === 'date') chat.updatedAt = 'invalid';
    if (damage === 'request') chat.turns[0].request.change = { target: 'Other', change: 'Other' };
    if (damage === 'paths') (chat.turns[0].result as ReturnType<typeof changeWithOrderedPaths>).data.historical_context.relationship_paths![0].steps[0].type = 'INVENTED';
    if (damage === 'selection') chat.ui.selectedNodeId = 'person:invented';
    if (damage === 'source') chat.ui.selectedSourceId = 'doc:invented';
    if (damage === 'too many chats') archive.conversations.push(...Array.from({ length: 20 }, newConversation));
    expect(() => restoreArchive(archive)).toThrow();
  });
  it('bounds storage and rejects credentials without redacting returned evidence', () => {
    const archive = saved(); const original = structuredClone(archive);
    archive.conversations[0].turns[0].result!.sources[0].metadata.api_key = 'do-not-store';
    expect(() => assertStorageBounds(archive)).toThrow(/credential/);
    expect(archive.conversations[0].turns[0].result!.sources[0].metadata.api_key).toBe('do-not-store');
    expect(containsCredentials('Authorization: Bearer test-secret-value')).toBe(true);
    expect(containsCredentials({ WEAVE_OPENROUTER_API_KEY: 'test-only-value' })).toBe(true);
    expect(containsCredentials({ Cookie: 'test-only-session' })).toBe(true);
    expect(containsCredentials('WEAVE_FALKORDB_PASSWORD=test-only-value')).toBe(true);
    expect(containsCredentials('token validation with Redis')).toBe(false);
    const large = structuredClone(original); large.conversations[0].ui.input = 'a'.repeat(MAX_CHAT_BYTES);
    expect(() => assertStorageBounds(large)).toThrow(/limit/);
    expect(MAX_HISTORY_BYTES).toBe(20 * 1024 * 1024);
  });
  it.each([['2026-10-18T01:00:00', 'Today'], ['2026-10-17T23:00:00', 'Yesterday'],
    ['2026-10-12T12:00:00', 'Previous 7 Days'], ['2026-10-01T12:00:00', 'Older']])('groups local calendar activity %s', (date, group) => {
    expect(recentGroup(date, new Date('2026-10-18T13:00:00'))).toBe(group);
  });
});

/** Event-level IndexedDB double exercises the actual repository, including transaction completion. */
function indexedDatabase(mode: 'normal' | 'blocked' | 'quota' | 'open-error' = 'normal') {
  let value: unknown;
  const close = vi.fn();
  const database = { close, objectStoreNames: { contains: () => false }, createObjectStore: vi.fn(), transaction: () => {
    const tx = { oncomplete: () => {}, onerror: () => {}, onabort: () => {}, objectStore: () => ({
      get: () => { const request = { result: value }; queueMicrotask(() => tx.oncomplete()); return request; },
      put: (next: unknown) => { const request = { result: 'current' }; queueMicrotask(() => { if (mode === 'quota') tx.onerror(); else { value = structuredClone(next); tx.oncomplete(); } }); return request; },
    }) }; return tx;
  } };
  vi.stubGlobal('indexedDB', { open: () => {
    const request = { result: database, onerror: () => {}, onblocked: () => {}, onsuccess: () => {}, onupgradeneeded: () => {} };
    queueMicrotask(() => { if (mode === 'blocked') request.onblocked(); else if (mode === 'open-error') request.onerror(); else { request.onupgradeneeded(); request.onsuccess(); } }); return request;
  } });
  return { close };
}
describe('IndexedDB repository', () => {
  it('atomically saves and reloads the real archive, not localStorage', async () => {
    const db = indexedDatabase(); const archive = saved();
    expect(await browserChatRepository.load()).toBeNull();
    await browserChatRepository.save(archive);
    expect(await browserChatRepository.load()).toEqual(archive);
    expect(db.close).toHaveBeenCalledTimes(3);
  });
  it.each(['blocked', 'open-error', 'quota'] as const)('reports %s failures instead of silently falling back', async mode => {
    indexedDatabase(mode);
    await expect(browserChatRepository.save({ version: 1, activeId: 'test', conversations: [{ ...newConversation(), id: 'test', ui: blankUI() }] })).rejects.toThrow(/storage/);
  });
  it('reports unavailable IndexedDB', async () => {
    vi.stubGlobal('indexedDB', undefined);
    await expect(browserChatRepository.load()).rejects.toThrow(/unavailable/);
  });
});
