# Phase 4B: deterministic Trace Mode

## Git and scope

Implemented on `feature/phase4-workspace`. The initial HEAD was `fb05d570628fd288cb7ad9b6c7b42712810b1175`, with the completed Phase 4A changes uncommitted. Reviewed those twelve files and the Phase 4A handoff, checked whitespace, and reran all 241 existing frontend tests before creating the explicitly requested checkpoint:

`e9aa09b4ad8d07ce09bbdc895dcc9691de5662ee` — `Checkpoint Phase 4A persistent chat workspace`.

That checkpoint is the final committed HEAD. Phase 4B changes remain uncommitted for review. Main, teammate branches and remote refs were not changed; no merge, push, reset, stash application or deployment occurred. Both original stashes remain intact:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

Read the actual Phase 3 ordered-path and Phase 4A handoffs, backend Change/models/Antony/context/orchestration contracts, frontend Change validators, graph, Inspector and chat persistence before integration. Antony's Cypher, Alen's ingestion/retrieval, orchestration, grounding, provider clients and conversation storage architecture remain unchanged.

## Exact Phase 4B files

| File | Change |
| --- | --- |
| `backend/app/models.py` | Strict bounded playback models and optional Change Brief field |
| `backend/app/trace_playback.py` | Pure server-authored sequence builder over existing validated local inventories |
| `backend/app/change_intelligence.py` | Build playback after the existing brief and before its existing validation/byte bound |
| `backend/tests/test_trace_playback.py` | Actual-tool offline serialization, ordering, membership, isolation, rejection and compatibility tests |
| `frontend/src/types.ts` | Optional playback and typed sequence/step contracts |
| `frontend/src/traceValidation.ts` | Verify server steps against original paths, tool-local proofs, graph identities and deterministic text |
| `frontend/src/changeValidation.ts` | Apply that validation at the existing dedicated API/restoration boundary |
| `frontend/src/components/TracePlayer.tsx` | Local playback controls, state machine, explanations and Inspector actions |
| `frontend/src/components/ChangeBrief.tsx` | Open validated Decision or Impact sequences from their original paths |
| `frontend/src/components/EvidenceGraph.tsx` | Optional exact current-step endpoint emphasis in the existing renderer |
| `frontend/src/App.tsx` | Integrate graph workspace, original path subgraph, exact highlight, scoped Inspector and chat ownership |
| `frontend/src/workspace.ts` | Minimal optional trace UI state and safe legacy/corrupt-selection restoration |
| `frontend/src/useChatWorkspace.ts` | Optional owner checks for already-queued playback callbacks; existing callers unchanged |
| `frontend/src/styles/globals.css` | Desktop controls beside graph, mobile playback dock, focus and reduced-motion styling |
| `frontend/src/test/tracePlaybackFixture.ts` | Frozen test-only server output from actual merged tools over explicit offline ingested demo data |
| `frontend/src/trace.test.ts` | Display boundary, legacy and persistence rejection tests |
| `frontend/src/TracePlayer.test.tsx` | Local controls, timing, keyboard, reduced-motion and cleanup tests |
| `frontend/src/TraceWorkspace.test.tsx` | Conversation/turn/view/sequence isolation, Inspector, refresh, deletion and queued-callback tests |
| `docs/PHASE4B_TRACE_MODE_HANDOFF.md` | This handoff |

No dependencies were added. Test fixtures are not imported into production code.

## Dedicated API contract

`POST /api/change-intelligence` adds optional `data.trace_playback`. Legacy omission or `null` is accepted by the frontend; unsupported proposals currently return `null`. A supported analysis can return `{ "version": 1, "sequences": [] }` when no playable paths were returned. No legacy graph inventory is converted into an authoritative sequence on the client.

The exact shape, shown for a single step, is:

```json
{
  "version": 1,
  "sequences": [
    {
      "id": "decision_trace/decision_to_current_architecture",
      "path_id": "decision_to_current_architecture",
      "tool": "decision_trace",
      "support_status": "supported",
      "steps": [
        {
          "number": 1,
          "sequence_id": "decision_trace/decision_to_current_architecture",
          "source": "decision:D-007",
          "type": "IMPLEMENTED_BY",
          "target": "commit:8fae2",
          "edge_id": "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
          "tool": "decision_trace",
          "traversal_from": "decision:D-007",
          "traversal_to": "commit:8fae2",
          "evidence": {
            "tool": "decision_trace",
            "node_ids": ["decision:D-007", "commit:8fae2"],
            "edge_ids": ["decision:D-007|IMPLEMENTED_BY|commit:8fae2"],
            "source_ids": [],
            "relationship_paths": [["decision:D-007|IMPLEMENTED_BY|commit:8fae2"]]
          },
          "explanation": "Stored relationship: decision:D-007 —IMPLEMENTED_BY→ commit:8fae2.",
          "citation_ids": []
        }
      ]
    }
  ]
}
```

The real architecture sequence also contains steps 2 and 3, CHANGES and USES, in the actual original order. The example's edge ID is an actual returned identity, not an ID construction rule: the builder takes IDs from the original capability's normalized proof sequence, matched against its exact directed edges.

Models forbid extra fields and require strict types. Bounds: version exactly 1; at most 140 sequences (80 historical plus 60 impact); sequence ID 1–160 characters; path ID 1–128; 1–10 steps per sequence; step number 1–10; explanation 1–2,000 characters; existing evidence-reference bounds. This version intentionally permits zero textual `citation_ids`. The complete Change data, including playback, still must fit the existing 160,000-byte limit; oversized evidence fails rather than being silently truncated.

`/api/query` remains exactly `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`. No extra endpoint, database call, source retrieval or provider client was introduced. Standalone capability responses retain their existing contracts; playback is delivered through Change Intelligence and its graph workspace.

## Decision and Impact semantics

Decision sequences retain `historical_context.relationship_paths` order, exact path IDs, canonical nodes, stored source/type/target and step order. Their IDs are `decision_trace/<original path id>`. The architecture sequence is:

`decision:D-007 —IMPLEMENTED_BY→ commit:8fae2 —CHANGES→ service:payment-service —USES→ tech:redis`.

The other four actual offline paths remain separate: `incident_to_investigation`, `decision_to_investigation`, `decision_to_discussion`, and `decision_to_documentation`. No Issue→Message→Decision chronology is synthesized.

Impact sequences use the existing scoped direct/indirect findings, including the exact `path` and `path_edges`. Their IDs are `impact_analysis/<finding.service_id>`; `path_id` is that canonical service ID because Impact findings do not supply a named historical path ID. Findings are checked against the original validated `ImpactData`, not reconstructed from the merged graph.

For the Order traversal:

| Step | Traversal order | Stored edge |
| --- | --- | --- |
| 1 | Redis → Payment Service | Payment Service —USES→ Redis |
| 2 | Payment Service → Checkout Service | Checkout Service —DEPENDS_ON→ Payment Service |
| 3 | Checkout Service → Order Service | Order Service —DEPENDS_ON→ Checkout Service |

`traversal_from/to` expose dependency-to-dependent order, while `source/type/target` and graph arrows always retain stored direction. Impact explanations explicitly qualify that traversal does not establish failure propagation.

## Provenance and citations

1. The existing graph tools and Context Builders validate evidence before merging. Antony still requests ordered paths; no teammate query or ingestion logic changed.
2. The playback builder requires a validated owning tool, the original inventory, matching per-tool status, exact local node/edge membership, original edge-ID proof order and connected traversal. Historical paths are revalidated against the Decision-only graph. Impact findings must equal their original validated structured findings. Reversed, disconnected, stale, duplicate, unknown, unavailable or sibling-only evidence fails closed.
3. The graph, original paths, sources, rankings, risk categories, document reviews, support statuses and answer are not rewritten to enable playback.
4. Every step references only its exact two endpoint nodes and one existing edge. These are structural proofs, so `source_ids` and `citation_ids` remain empty. Adjacent ADRs, issues, chunks or a sibling capability's sources are not promoted into rationale citations.
5. While a step is active, the existing Inspector receives only that step's graph proof and validated source references (empty in this version). A source selected from another view cannot remain presented as the current step's citation. Key sources and the original brief retain the complete separately validated source evidence.
6. Frontend API/restoration validation checks schema, version, full sequence inventory/order, canonical IDs, stored orientation, traversal connectivity, original tool-local edge-ID proofs, evidence refs, status and exact server explanation. Invalid supplied playback rejects the response/archive; the UI never repairs it from nearby edges. Absent legacy metadata remains readable without playback.

OpenRouter's finite selection packet remains unchanged. Playback is deterministic and is not added to hosted prompts. No live provider request, health probe or external evidence transmission occurred. Real mode never falls back to fixtures; the existing configuration and unavailability behavior are unchanged.

## Playback state machine and UI

- Opening a returned path starts paused at index 0, opens the graph workspace and selects its traversal destination in Inspector.
- Play advances locally every 2.2 seconds. Reaching the last step pauses. One-step paths remain paused; Play/Next are disabled there.
- Pause stops scheduling. Previous, Next, step-list selection and inspection pause. Replay restarts at index 0 and plays a multi-step path only because the user requested it.
- Sequence switches remount the local run paused. Conversation, selected-turn, workspace-page, answer/graph-view and evidence-tab changes unmount playback and clear its timer. Hidden documents and reduced-motion preference changes pause it.
- The callback captures its scheduling owner/index. The workspace additionally checks active conversation, selected turn, graph view/tab, sequence and step before applying a timed update. Regression tests deliberately invoke canceled-but-previously-queued callbacks after these ownership changes; they cannot alter the new selection. Deleted chats cannot be recreated.
- Refresh always mounts paused. Running state, timers and timer IDs are component-local and never written to IndexedDB.

The original React Flow renderer shows a subset of **unchanged returned graph objects** belonging to the selected sequence. It highlights exactly the current edge and its two endpoints, fitting those endpoints with an instant viewport update. This is display filtering, not path discovery. The full original graph remains available when Trace Mode closes. Separate historical and Impact sequences are not concatenated.

Desktop controls sit beside the graph at wide widths. Mobile controls/progress dock above the composer while Trace Mode is open so the user can watch the graph during playback. The primary brief is available through Back to answer; no playback overlay remains over its sections.

Native buttons/select, explicit labels, disabled end controls, visible focus, semantic progress, polite step announcements and a navigable numbered step list support keyboard access. Existing mobile Inspector dialog, focus handling and Escape are reused. Reduced motion disables graph/panel transitions; viewport updates are instant, and playback never starts on restoration or preference change.

## IndexedDB compatibility

Archive version 1, native IndexedDB repository, atomic snapshot writes, debouncing, failure behavior, credential rejection and 20-chat/40-turn/4-MB-per-chat/20-MB-total bounds remain intact.

Only `ChatUI.trace: { sequenceId: string, step: number } | null` is added (optional for old archives). The persisted index is zero-based; server step numbers are one-based. Restoration validates the full saved response through the existing API checks. Missing legacy UI state, unknown sequences, invalid indices or corrupt selection are cleared to `null` without modifying evidence. Injected running/timer fields inside the trace selection are discarded. Mutated evidence itself rejects the archive and leaves original storage untouched.

Phase 4A's existing single-writer-tab limitation remains; cross-tab merge/synchronization was not added.

## Verification

Python: **686 passed, 11 skipped**, full `backend/tests tests app/graph` suite; **23 new playback tests**. Ruff passed for `backend/app backend/tests`. One existing Starlette/httpx TestClient deprecation warning remains. The eleven opt-in live skips are not acceptance results.

Frontend: **298 passed across 13 files**, including **57 new Trace Mode tests**. ESLint, TypeScript and Vite production build passed. Whitespace checks passed for tracked and newly added files. An initial unrestricted run under simultaneous Python/build load hit three 5-second UI test deadlines; the complete suite passed with two workers, without relaxing assertions, increasing global deadlines or changing production behavior.

Commands:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-phase4b-final
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
npm.cmd --prefix frontend test -- --maxWorkers=2
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

Browser QA used the actual React Flow renderer and real browser IndexedDB at 1440×1000 and 390×844, with explicitly labeled synthetic intercepted responses. The playback fixture was frozen from the backend's actual merged tools over the offline ingested NovaPay graph double, not generated by the frontend.

Verified actual timed progression, manual controls, Decision IMPLEMENTED_BY/CHANGES/USES and Impact stored DEPENDS_ON SVG highlights, exact endpoint emphasis, paused refresh, chat switching, source/Inspector scope, mobile dialog/Escape, reduced motion, mobile dock, Clear History cleanup, no horizontal overflow and no page errors. Total: **one local intercepted Change POST, zero other analysis POSTs, zero non-local HTTP requests**. Non-local requests were blocked throughout. This was not live FalkorDB or OpenRouter verification. Ignored screenshots: `.local/phase4b-desktop.png`, `.local/phase4b-mobile-controls.png`, `.local/phase4b-mobile-graph.png`. Test history was cleared using the UI, interception was removed, and the local QA server was stopped afterward.

## Live acceptance and limitations

The combined workflow has **not** passed live FalkorDB acceptance on this machine. No database was launched, seeded or changed. Antony's independent verification and the offline graph double are not substitutes for combined acceptance.

On an approved seeded database, with actual graph and source adapters and `WEAVE_LLM_PROVIDER=none`:

1. Record application/seed revisions; run the existing opt-in real Change and capability gates without fixture fallback.
2. Compare each dedicated Change sequence against the actual original tool's named paths or Impact finding. Verify accepted D-007, exact directed IDs/order, local proof membership and genuine source/chunk provenance independently of graph-only playback.
3. Confirm conservative overall/per-tool support, rankings, current versus conditional document reviews, exact six-field `/api/query`, one deduplicated retrieval pass and sanitized failures.
4. At desktop/mobile sizes play each real path, inspect actual SVG edges/endpoint highlighting and scoped Inspector, restore paused from IndexedDB, switch chats/turns/views and delete/clear while playing. Confirm no step-level analysis/provider requests.
5. Exercise missing/legacy metadata and stale/reversed/foreign evidence only with approved isolated data or controlled doubles; never mutate shared seed data merely for UI negatives.

Version 1 provides graph-only explanations and no step-level textual rationale citations. Existing source records remain available separately. Standalone legacy Decision/Impact answers without backend playback metadata cannot enter playback, even if their graph looks connected. Large valid briefs can hit the unchanged overall byte bound. Paths establish returned structural relationships, not a complete causal chronology, guaranteed outage, successful validation or change approval.

No live OpenRouter call is needed for Trace Mode. Any future external synthesis test still requires separate reviewed-payload approval.
