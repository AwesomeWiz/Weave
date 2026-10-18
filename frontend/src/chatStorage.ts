import type { WorkspaceArchive } from './workspace';
import { assertStorageBounds, restoreArchive } from './workspace';

export interface ChatRepository { load(): Promise<WorkspaceArchive | null>; save(value: WorkspaceArchive): Promise<void> }
const DATABASE = 'weave-chat-history';
const STORE = 'workspace';

/** One versioned local snapshot, atomically replaced; never localStorage or remote fallback. */
async function transaction(mode: IDBTransactionMode, value?: WorkspaceArchive): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('Browser history storage is unavailable.')); return; }
    let database: IDBDatabase | undefined;
    let settled = false;
    const fail = () => { if (!settled) { settled = true; database?.close(); clearTimeout(timer); reject(new Error('Browser history storage is unavailable or full.')); } };
    const timer = setTimeout(fail, 5000);
    let open: IDBOpenDBRequest;
    try { open = indexedDB.open(DATABASE, 1); } catch { fail(); return; }
    open.onupgradeneeded = () => { if (!open.result.objectStoreNames.contains(STORE)) open.result.createObjectStore(STORE); };
    open.onerror = fail; open.onblocked = fail;
    open.onsuccess = () => {
      database = open.result;
      if (settled) { database.close(); return; }
      database.onversionchange = () => database?.close();
      try {
        const tx = database.transaction(STORE, mode);
        const request = value ? tx.objectStore(STORE).put(value, 'current') : tx.objectStore(STORE).get('current');
        tx.onerror = fail; tx.onabort = fail;
        tx.oncomplete = () => {
          if (settled) return;
          settled = true; clearTimeout(timer); database?.close(); resolve(request.result);
        };
      } catch { fail(); }
    };
  });
}
export const browserChatRepository: ChatRepository = {
  async load() { const value = await transaction('readonly'); return value === undefined ? null : restoreArchive(value); },
  async save(value) { assertStorageBounds(value); await transaction('readwrite', value); },
};
