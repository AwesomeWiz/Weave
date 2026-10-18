# Phase 4A: persistent chat workspace

## State — October 18, 2026

Implemented on the requested new `feature/phase4-workspace` branch, created from the clean verified Phase 3 merge `fb05d570628fd288cb7ad9b6c7b42712810b1175`. Inspection confirmed this main checkpoint contains `f09ee9740ecff3425501a77ef6c0821378aa61c6` and Antony's merged ordered-path work. Phase 3 was not assumed to be on main without checking ancestry and actual files.

There were no initial local modifications to checkpoint. No existing changes or stashes were discarded, no main edits or merges were performed, and nothing was committed or pushed. HEAD remains `fb05d57`; the implementation is uncommitted for review. Both original stashes remain intact:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

Existing Phase 3 handoffs and other documentation were left untouched to avoid overlapping documentation work. No backend, graph, ingestion, provider or public API schema changes were made.

## Exact changed files

| File | Change |
| --- | --- |
| `frontend/src/App.tsx` | Conversation-scoped message/evidence/UI state, complete response restoration, transcript, request ownership and workspace navigation |
| `frontend/src/api.ts` | Extract existing pure response checks for reuse when restoring; existing network behavior and validation conditions retained |
| `frontend/src/ChangeBrief.test.tsx` | Update the existing history test to the New Chat/recent conversation controls |
| `frontend/src/styles/globals.css` | Paper/forest sidebar search/actions, compact workspace shortcuts, confirmations, transcript and page foundations |
| `frontend/src/workspace.ts` | Versioned conversation types, stable IDs, bounds, archive validation, activity grouping and credential screening |
| `frontend/src/chatStorage.ts` | Native IndexedDB repository and atomic transactions |
| `frontend/src/useChatWorkspace.ts` | Conversation lifecycle, independent in-flight requests, hydration, serialized saves and failure handling |
| `frontend/src/components/ConversationList.tsx` | Recent Chats, title/question search, active state, rename/delete and Clear History confirmation dialogs |
| `frontend/src/components/WorkspacePage.tsx` | Decisions/Services/People/Changes foundations using only the selected answer's existing records |
| `frontend/src/workspace.test.ts` | 23 archive, evidence, bounds, privacy and IndexedDB transaction cases |
| `frontend/src/ChatWorkspace.test.tsx` | 15 workspace, refresh, concurrency, confirmation, storage and responsive interaction cases |
| `docs/PHASE4A_CHAT_WORKSPACE_HANDOFF.md` | This handoff |

No packages were added. Existing `types.ts`, React Flow, Inspector, Change Brief component, capability cards and backend implementations remain in place.

## Conversation and message model

Each conversation has a stable `crypto.randomUUID()` ID, a title, ISO created/updated timestamps, an ordered `turns` list and saved UI state. Each turn records:

- Its own stable ID, original user question and creation time.
- The exact typed Change/Impact/Expert/Freshness request, or an ordinary query request classification.
- Pending/complete/error state, the complete original validated response, and an error code/message when applicable.

A turn is a user question and its associated assistant response, preserving their order without flattening tool data into prose. All returned graph/source objects and structured `data` are retained, including ordered historical paths, source/chunk metadata, classifications, rankings, support states, generation metadata and timestamps. Only the generated conversation title is normalized and bounded to 100 characters; question/evidence content is not rewritten.

New Chat creates a blank independent conversation and preserves previous conversations and drafts. The first question supplies its initial title unless the user has already renamed it. Every submitted question creates a new ordered turn; retrying a failed/interrupted selected question reuses that turn rather than duplicating its message.

The existing full graph-intelligence workspace renders the selected turn. Other turns remain visible in order as their original answer text with original support status and working citations, plus a control to open the full structured evidence for that message. This avoids mounting multiple large graph renderers and duplicate proof/tab IDs simultaneously. Earlier errors can be selected for explicit retry.

Conversation UI stores the selected turn, draft, answer/graph view, evidence tab, focused/full scope, highlighted edge IDs/finding, selected node/source IDs, graph search and desktop details visibility. Node/source selection is resolved from the saved response rather than copied into a new evidence object. Graph pan/zoom coordinates are not persisted.

## Sidebar and navigation

The sidebar provides New Chat, Chat, Knowledge Graph, compact workspace shortcuts, Recent Chats, Search chats, per-row rename/delete and Clear History. Search matches the title or any earlier user question; it does not make a backend request. Chats are sorted by last message completion/submission or rename activity and grouped into Today, Yesterday, Previous 7 Days and Older using local calendar boundaries. Merely opening or inspecting a chat does not rewrite its activity timestamp.

Rename/delete target the specific row's captured stable conversation ID; they do not affect another active conversation. Delete Chat and Clear History require explicit confirmation, with Cancel and Escape support. Clear History removes conversation data only; existing greeting/sidebar preferences remain. A fresh blank conversation replaces the last deleted chat or a cleared history.

Desktop collapse preferences and the existing focus-contained mobile drawer remain functional. Dialogs reuse `WorkspacePanel` focus containment through a portal, so a confirmation does not conflict with the mobile drawer's focus trap. Escape cancels a rename/delete/clear dialog before affecting the underlying navigation. Controls have accessible names and retain visible focus styles.

Decisions, Services, People and Changes are working **local evidence page foundations**, not company-wide directories. They show matching original graph nodes from the selected answer and use the existing inspector. Changes includes returned Decision/Commit/Incident records without computing a new change feed or chronology. Empty states explicitly explain the limited scope. Connectors remains a disabled future entry. No new data discovery or backend requests are performed for these pages.

## Browser-local persistence

Native IndexedDB is used because complete graph/source/Change Brief responses can exceed practical localStorage budgets. Database: `weave-chat-history`, version 1; object store: `workspace`; record key: `current`. The record is a versioned `{version, activeId, conversations}` archive, atomically replaced in a read/write transaction. There is no localStorage transcript fallback or remote history service.

Application storage policy:

- Up to **20 conversations**, including drafts/blank chats.
- Up to **40 turns per conversation** (question/response pairs).
- Up to **4 MiB serialized UTF-8 JSON per conversation**.
- Up to **20 MiB serialized UTF-8 JSON per archive**.

New chat/message operations stop at their count limits and display an explicit notice. Byte bounds and browser quota failures refuse the save rather than truncate evidence or evict old chats. A response that exceeds the save budget remains intact in memory, with a warning. The policy bounds the persisted archive, not the browser's entire memory use or physical IndexedDB overhead. Delete chats to free the application budget; actual browser quota may be lower.

Message lifecycle, rename, delete, clear and conversation selection enqueue immediate saves. Draft/selection/tab/highlight interaction changes are debounced for 150 ms, with page-hide/visibility flush attempts. Writes are serialized so an earlier queued snapshot cannot overtake a later deletion within this mounted workspace. Success means the IndexedDB transaction completed. Abrupt termination before a transaction commits can still lose the most recent unsaved interaction; page-hide flush is best effort.

Hydration completes before evidence submission in browsers with IndexedDB. Restoring history performs **zero analysis/tool/source requests**. The existing independent health check remains; it is not a conversation replay. Stored common evidence and each structured capability response are rechecked through the same existing pure display validators used by live API responses, including strict Change/ordered-path provenance checks. Conversation IDs, selected references, request fields, timestamps, schema version and byte/count limits are checked as well.

An incompatible/corrupt/unreadable archive is left untouched. The app warns and works in memory rather than silently overwriting the original or switching storage systems. A user-confirmed Clear History can explicitly replace that stored archive. A failed save keeps the current in-memory conversation available. A failed deletion warns that previously stored chats may reappear after refresh. Later successful writes can clear storage failure notices; count-limit notices remain until the user takes an action that resolves them.

## Request ownership, refresh and errors

Request initiation synchronously reserves a pending turn in its owning conversation before awaiting HTTP. A second submission in that same conversation is rejected while pending. Users may switch chats or start another chat, and those conversations can have independent requests.

Completion updates only the captured conversation and turn IDs. It does not select that conversation or replace the active chat's result/draft. A response for a deleted/cleared conversation is ignored and cannot resurrect it. Responses arriving after component unmount are ignored by that workspace instance. Existing typed error handling and request retry routing are preserved.

Pending requests cannot resume after refresh. Their saved user messages become an explicit `INTERRUPTED` error with a retry button, never an automatic graph rerun. Retrying reuses the same turn. All other saved answers reopen from local data without repeated API analysis.

Questions remain independent requests to the existing GraphRAG endpoints. This phase does not send earlier messages as model context, add server conversation memory or change deterministic routing. Conversation IDs organize local state; the existing query API/session behavior is unchanged.

## Privacy and evidence integrity

Only conversation fields, original typed requests/responses and UI reference state are persisted. HTTP clients, configuration, API keys, authorization headers and backend settings are not part of the conversation model. There is no automatic upload, cloud history, telemetry addition, authentication or hosted-model integration in this phase.

As an additional guard, save screening rejects credential-like fields/assignments, authorization/cookie values, common token/key patterns and private-key blocks. It rejects the **whole snapshot** rather than redacting or changing evidence. The user is informed, and the result remains in memory. Removing the affected chat can permit other history to save again. This conservative screen can have false positives and is not a universal secret detector; do not enter secrets or rely on browser history as a secret vault.

History includes potentially sensitive user questions and retrieved excerpts, stored without application-level encryption in the current browser profile/origin. Other authorized users of that profile and same-origin scripts may access it. Clear History deletes the app's current IndexedDB record contents through replacement; it cannot promise forensic removal from browser/OS backups. Clearing browser site data or changing origin/profile removes or separates access to the history. No credentials or complete payloads are logged by the added code.

Saved answers retain their original graph mode and generation metadata. A currently configured development server does not relabel a saved real-mode response as fixture evidence. Saving/restoring evidence does not make it current, rerun freshness checks, upgrade support or establish live verification. The response's original dates, warnings and limitations remain authoritative.

## Verification

Final frontend checks:

- **241 tests passed across 10 files**: all 203 existing Phase 3 tests plus 38 workspace/storage cases.
- ESLint: passed without warnings.
- TypeScript: passed.
- Vite production build: passed.
- `git diff --check`: passed; new-file whitespace was checked separately.

Tests cover New Chat, multi-message ordering, switching without requests, refresh persistence, complete Change Brief data and ordered paths, graph/source selection, search, rename isolation, confirmation/cancellation, deletion and Clear History, concurrent request ownership, duplicate prevention, late responses after clear/unmount, interrupted retry, corrupt archives, storage availability/quota/blocked transactions, credential refusal, count/byte limits, local date grouping, responsive navigation and workspace page foundations.

The existing history regression now selects the New Chat and named recent-chat controls instead of the removed six-question in-memory list. Existing evidence assertions were preserved. One complex full Change Brief remount test has a 15-second timeout for the shared Windows runner; its evidence/request-count assertions are unchanged.

This task changed no Python/backend/graph code, so Python tests and Ruff were not rerun. A Git comparison confirmed `backend`, `app`, `weave_graph` and `weave_data` remain identical to the starting main checkpoint. Prior Phase 3 verification is recorded in its handoffs, not claimed as a new live result here.

Reproduce from the repository root:

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

## Desktop/mobile browser QA

Used local Vite on a dedicated origin with **real IndexedDB and the real React Flow renderer**, at 1440×1000 and 390×844. GraphRAG and health responses were explicitly intercepted with labeled synthetic NovaPay demonstration data. Non-local HTTP was blocked. There were no live OpenRouter requests, provider probes or real FalkorDB operations.

Verified:

- One Change POST and one ordinary query POST for the two submitted QA questions.
- No analysis replay when switching conversations or refreshing repeatedly.
- Rename, title/question search, independent New Chat, active indication and workspace Services navigation.
- Full Change Brief persisted, including five historical paths and the three-edge architecture highlight.
- Source citation inspection and graph state survived reopening/refresh.
- Responsive drawer switching, rename cancellation with Escape retaining the drawer, delete confirmation, Clear History cancellation and confirmed clear across refresh.
- No page errors or page-level horizontal overflow at either viewport.

The dedicated QA origin initially had no saved conversations. Its generated test history was cleared through the actual confirmation UI, and reload confirmed one blank chat with zero turns. No existing user history was cleared. Ignored screenshots: `.local/phase4a-desktop.png` and `.local/phase4a-mobile-navigation.png`. The QA server was stopped afterward.

## Remaining limits

The MVP assumes one active writer tab per browser origin. There is no live cross-tab merge/coordination; concurrent independent tabs can overwrite snapshots, so use one writer tab. There is no cross-device sync, export/import, account isolation or backend conversation service. Browser-local storage is not a backup.

Only the selected message mounts full structured evidence and React Flow at a time; other messages retain their exact original answer and can reopen their complete data. Graph viewport pan/zoom is reset by the existing renderer. Workspace pages are foundations scoped to the selected answer. Full directories, backend history, conversational model memory, Trace Mode and authentication remain out of scope.

No outstanding frontend test failures remain. Real graph/provider acceptance was not performed by this frontend persistence task and cannot be inferred from its synthetic browser checks.
