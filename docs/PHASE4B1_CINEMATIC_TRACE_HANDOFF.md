# Phase 4B.1: cinematic Trace Mode

## Git state and scope

Implemented on `feature/phase4-workspace`, starting from a clean tree at `184a67b593139c44f3e3f595d0a1df981d9d8e86` (`feat: implement graph-grounded Trace Mode`). The user had already committed Phase 4B, after the Phase 4A checkpoint `e9aa09b`; no additional checkpoint was needed. HEAD remains `184a67b`. This UI work is uncommitted for review.

Main, teammate branches and remote refs were not modified. No merge, push, deployment, stash application or destructive checkout occurred. Both original stashes remain intact:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

Read both Phase 4A/4B handoffs and the current App, Trace player, React Flow graph, Change Brief, validators/types, Inspector, WorkspacePanel, chat hook, archive model, styling and tests. Inspected the installed React Flow **12.12.0** implementation and its edge/viewport/control primitives. No package or lockfile changes or animation dependencies were needed.

This is presentation-only. Backend graph tools, paths, Cypher, ingestion, retrieval, LLM clients, public API schemas, citation checks, conservative support semantics, frontend evidence validators and IndexedDB schema are unchanged. The user's reported prior Phase 3 live acceptance is context; this task performs additional offline frontend verification, not a new live database acceptance run.

## Exact files changed

| File | Purpose |
| --- | --- |
| `frontend/src/App.tsx` | Watch intent, shared ephemeral clock, graph-first placement, Trace heading, Inspector collapse on entry and existing scoped playback updates |
| `frontend/src/components/ChangeBrief.tsx` | Prominent Watch Evidence Trace action before the brief sections; contextual shortcuts retained |
| `frontend/src/components/TracePlayer.tsx` | Friendly story selection/explanation, controls, visible evidence qualifications and advanced evidence disclosure |
| `frontend/src/components/EvidenceGraph.tsx` | Existing renderer integration, stable layout, active/earlier/future states, arrival emphasis and camera behavior |
| `frontend/src/components/TraceEdge.tsx` | Motion and illumination on the exact existing Bezier/detour geometry |
| `frontend/src/traceClock.ts` | One elapsed-time clock, pause/resume, deadline invalidation and presentation sampling |
| `frontend/src/useTracePlayback.ts` | Shared player lifecycle, step ownership, reduced motion, visibility cleanup and explicit Watch intent |
| `frontend/src/tracePresentation.ts` | Deterministic friendly names, relationship sentences, sequence titles and genuine default selection |
| `frontend/src/styles/globals.css` | Paper/forest layout, graph emphasis, technical disclosures and responsive transport controls |
| `frontend/src/TracePlayer.test.tsx` | Updated final/single-step animation semantics; remaining-time resume and disclosure tests |
| `frontend/src/TraceWorkspace.test.tsx` | Prominent entry/default/fallback tests and preserved conversation, Inspector and no-request regressions |
| `frontend/src/TraceCamera.test.tsx` | Endpoint framing, stable layout, manual interaction, recenter, pause/resume and reduced motion |
| `frontend/src/TraceEdge.test.tsx` | Exact geometry/identity/arrow, movement, freeze/resume, reverse traversal and cleanup |
| `frontend/src/traceClock.test.ts` | Deterministic elapsed time, remaining deadline, stale callbacks, reduced motion and render isolation |
| `frontend/src/tracePresentation.test.ts` | Actual names, known/unknown relationship language, default selection and independent histories |
| `docs/PHASE4B1_CINEMATIC_TRACE_HANDOFF.md` | This handoff |

## Discovery and layout

**Watch Evidence Trace** now appears near the top of the Change Brief, before the section index and proposed-change details. The graph workspace has the same discoverable action. Both select an existing validated sequence, preferring the returned `decision_to_current_architecture` Decision path; otherwise they choose the first genuine available sequence. No graph walk or replacement sequence is created. Missing/legacy playback disables the action and explains that the original evidence remains available.

Watch is an explicit user play action: it opens the existing graph workspace and starts the selected sequence. Existing contextual historical/impact shortcuts still open paused. Page load, restored conversations, sequence switches and preference changes never start playback automatically.

The existing details panel closes on entry to give the graph room; Inspector buttons reopen it normally. Timed steps keep selection synchronized without repeatedly reopening the panel. At desktop widths, the existing React Flow canvas receives approximately 67% of the trace area, with a compact explanation/control panel beside it. Evidence tabs remain available. No global sidebar was added. Ordinary graph exploration retains its earlier camera padding and behavior.

At mobile widths the graph appears before the explanation. A compact transport/progress dock stays above the existing composer, with all controls accessible without horizontal scrolling. The main workspace is the scrolling surface; no additional scroll container was introduced. The friendly explanation and full qualifications remain in the normal content flow, and advanced evidence is expandable. Mobile typography/spacing avoids duplicating the global Trace Mode heading.

## Motion on actual edges

`TraceEdge` uses React Flow's installed `getBezierPath` and `BaseEdge`. `TraceDetourEdge` preserves the existing custom same-column curve and label placement. Each motion overlay uses **the identical `d` path** as its base edge. No alternate graph renderer or invented edge geometry is used.

The active edge draws a subtle green illumination stroke using normalized SVG dash length. A small gold marker samples the actual SVG path using `getTotalLength()` / `getPointAtLength()`. The stored edge ID, endpoints and arrow marker are retained. Source emphasis begins immediately; the traversal destination gains arrival emphasis at 85% progress. Earlier path relationships remain quieter; future relationships are subdued. These are presentation states and do not modify support or claim that a change was approved or tested.

For Decision Trace, the marker follows the declared ordered step. For Impact, the marker can travel **against** the stored source-to-target direction. Only the marker/illumination progression reverses; the base curve, canonical source/type/target and arrow still represent the stored relationship. The explanation uses the stored relation, for example “Checkout Service depends on Payment Service.” Advanced evidence explains the dependency-to-dependent playback direction separately.

React frame sampling writes only the active SVG marker/stroke and destination emphasis. It does not rebuild graph objects or issue React state updates every frame. React Flow view models keep stable IDs, and Dagre layout depends on graph identity rather than the changing selection callback or playback frame. Tests verify one layout across step changes.

## One playback clock

The previous local player is extended through `useTracePlayback` and `TraceClock`; Decision and Impact share it. Each step has the existing **2,200 ms** duration:

- One monotonic elapsed-time value is authoritative. A completion deadline advances the step. RAF only samples that same value for presentation; SVG motion has no independent looping animation or completion handler.
- Pause records elapsed time, cancels both the deadline and frame sampling, and freezes the exact SVG position. Resume schedules only the remaining duration and continues from that position.
- Next, Previous and step-list selection pause and rewind visual progress. Replay rewinds to step zero, resets camera ownership and starts by explicit user request.
- Every step, including the final edge and one-edge sequences, now has a visible animation interval. The player pauses after the final edge completes. This deliberately extends Phase 4B's timing, which had stopped immediately upon entering the final step; it does not add or reorder evidence.
- Generation checks invalidate canceled-but-already-queued callbacks. The existing workspace owner guard still checks chat, turn, view/tab, sequence and step. Sequence/chat/turn/view changes and deletion unmount and dispose the clock. Hidden documents and reduced-motion preference changes pause it.

There are no per-frame or per-step graph, API, source or LLM requests. Playback speed remains fixed at 1×; the optional speed selector was not added.

## Camera behavior

React Flow's existing viewport API frames the current two endpoints with bounded zoom and comfortable padding. Normal automatic motion takes 450 ms; reduced motion uses an instant fit. Source/target positions are not recomputed when steps change.

Deliberate pan, wheel/touch zoom, and the existing zoom/fit controls suspend automatic following. Programmatic viewport events do not count as user gestures. A queued automatic frame also checks whether the user has taken control. **Recenter trace**, Replay or a new sequence returns to automatic framing.

Pause freezes an in-progress automatic camera at its current viewport. Resume reframes the current endpoints unless the user has taken manual camera ownership. There are no camera completion callbacks that can advance a path or race the playback deadline.

## Friendly explanations and audit disclosure

Names come from returned node names/labels. Decision and Commit display labels use their returned record IDs without canonical prefixes (for example “Decision D-007” and “Commit 8fae2”), using the existing ID formatter. Production components contain no hardcoded NovaPay entity IDs or Redis-specific animation rules.

Known stored relationships have finite deterministic sentences: uses, depends on, was implemented through, changed, is supported by, is documented in, introduced, led to, affects, approved and was decided by. Unknown types fall back to a neutral “is linked to … by [actual relationship type]” statement rather than guessing a meaning. This is display formatting of validated steps, not a replacement for the backend-authored sequence or raw explanation.

Potential-impact language remains qualified: connected services may be affected, not guaranteed to fail. Partial/insufficient overall or sequence support remains visible outside the advanced disclosure. The original support values are also preserved inside it.

**View evidence** pauses playback when opened and exposes:

- Original path ID and step's exact edge ID.
- Canonical stored source/type/target and arrow direction.
- Tool provenance, support status and original server explanation.
- Declared playback direction, with an explicit explanation when it differs.
- Existing source/target Inspector actions and actual citation buttons if the validated contract permits them.
- Graph-only qualification when no textual citation exists.

Phase 4B version 1 still supplies zero step-level textual citations. This task does not attach neighboring issues, documents, chunks or sibling tools' sources. The full original sources/citations remain available through Key sources and the brief. The scoped Inspector and all existing API/restoration validation remain in force.

## Persistence and accessibility

IndexedDB version, complete response snapshots, bounds, credential screening, deletion behavior and existing owner checks are unchanged. Only the existing selected sequence/step UI state is persisted. Clocks, Watch intent, elapsed progress, frame IDs, camera motion and running state are ephemeral. Refresh restores paused at the saved step with that edge's visual progress reset to its start; no analysis is rerun.

Native buttons/select/disclosures, explicit Previous/Next labels, visible focus, semantic progress, polite step explanations and the existing Inspector focus/Escape handling remain available. Friendly story titles are headings, and animation is not the sole source of meaning.

`prefers-reduced-motion: reduce` removes the traveling marker and illumination animation, makes camera framing instant and preserves static step/node/edge highlights. Explicit Play still advances the verified steps. A preference change pauses playback; reduced motion does not start playback on load or restoration.

## Verification

Baseline: all **298** existing frontend tests passed before edits.

Final frontend suite: **333 tests across 17 files**, with 35 new tests plus updates for the final-edge timing, single-step animation, disclosure and Watch action behavior. ESLint, TypeScript, Vite production build and whitespace checks passed. New graph tests use deterministic clocks; unit animation assertions do not depend on wall-clock sleeps.

```powershell
npm.cmd --prefix frontend test -- --maxWorkers=2
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

Two workers keep the existing UI suites within their normal deadlines on this Windows machine. No backend files changed, so Python was not rerun, as requested for this presentation-only task. The prior Phase 4B Python result remains 686 passed / 11 live skipped; it is not a new result of this task.

## Browser verification

Actual local Chromium, React Flow SVG rendering and native IndexedDB were exercised at **1440×1000** and **390×844**. All responses were explicitly labeled synthetic NovaPay development data from the existing frozen backend-produced test fixture. Non-local HTTP was blocked. No real database or provider was contacted.

Verified:

- Prominent Watch entry and genuine architecture default, with no replayed analysis.
- Actual movement along the SVG path: measured progress advanced from 0.29455 to 0.47636; paused/frozen marker position remained exactly equal at 0.47727; resume continued to 0.74727.
- Correct full IMPLEMENTED_BY → CHANGES → USES Decision step order, final-edge completion and target arrival emphasis.
- Reverse Impact marker movement on the stored Payment Service USES Redis edge, with its original arrow retained; multiple-step Impact and reduced-motion advancement.
- Manual wheel zoom remained unchanged across the next step; Recenter framed the new endpoints.
- Pause froze an in-flight camera, with identical measured viewport transforms before and after advancing the browser test clock.
- Real source citation opening, scoped Inspector, mobile dialog/Escape and paused refresh without new analysis.
- Graph above explanation at mobile width, accessible transport controls, no page horizontal overflow, no observed page errors or console errors in final QA.

The browser clock was controlled for deterministic motion/freeze measurements; native rendering and SVG geometry were real. Normal-time playback and visual screenshots were also inspected. The custom detour's identical geometry, arrow and sampled motion are covered by automated SVG tests; the canonical browser fixture uses ordinary Bezier edges.

Only **one intercepted local Change POST** was needed across browser QA; other analysis POSTs and non-local HTTP requests remained zero. Repeated local health/restoration checks used the same explicitly intercepted synthetic environment. Ignored artifacts: `.local/phase4b1-entry.png`, `.local/phase4b1-desktop.png`, `.local/phase4b1-mobile.png`. Synthetic browser history was cleared after QA, interception removed and the QA server stopped.

## Remaining acceptance and limits

This task does not establish new live FalkorDB acceptance. On the approved real seeded environment, repeat Watch/Decision/Impact, exact edge/provenance inspection, pause/resume/replay, camera interaction, saved-chat restoration and mobile checks against actual returned paths. Confirm no per-step network calls. Test detour motion if real returned sequences produce that layout, and test physical touch-device pinch/pan beyond viewport emulation.

No step citations were added, no missing/legacy paths were repaired and separate histories remain independent. Very long returned labels can wrap; canonical IDs remain available in the disclosure. The existing one-writer-tab storage limitation remains. Playback has fixed timing, does not persist frame progress or manual camera position, and does not represent a complete causal chronology, guaranteed outage, completed validation or change approval.
