# Phase 4C: product redesign handoff

## Scope and Git safety

Implemented on `feature/phase4-workspace`, starting clean at **96916f947963247212b5cc37340af2775f1c633d** (`feat: add cinematic graph-grounded Trace Mode`). The branch tracked the same origin commit. Phase 4A, 4B and 4B.1 were present and committed. Their handoffs and the Phase 3 frontend, hosted synthesis and ordered-path handoffs informed this work.

HEAD remains unchanged. Changes are **uncommitted for review**. No branch switch, fetch, merge, deployment, commit or push occurred. Main remains `fb05d570628fd288cb7ad9b6c7b42712810b1175`. Both original stashes remain intact and unapplied:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

This is frontend presentation and navigation work. Backend tools, Cypher, source retrieval/ingestion, routing, public API schemas, synthesis prompts, source/ordered-path/playback validators, support classifications and IndexedDB archive format are unchanged. No runtime fixtures, authentication, connector integration or alternate player were added.

## Audit and implementation plan

Inspected the running application at desktop/mobile widths before editing, including the landing, Change results, navigation pages, Inspector and failure state. Identified:

1. Full-width and two-column navigation competed with New Chat, repeated workspace names and unfinished Connectors.
2. History search and per-row edit/delete controls consumed permanent space; long titles wrapped.
3. Capability names described implementation rather than a user's question. The mobile landing buried the composer below content.
4. Answers handled paragraphs/citations but not Markdown lists, headings, tables or meaningful soft breaks.
5. Change results exposed a large section index and historical path inventory before progressive proof exploration.
6. Evidence pages were generic record lists; Changes was not a saved-assessment view.
7. Inspector overview showed long parallel cards and hypothetical connector rows. The welcome graph status always rendered `CircleCheck`, including when unavailable, and could infer readiness from the aggregate status.

The implementation plan was shared before edits: unify navigation/history, add safe shared answer formatting, improve Change reading hierarchy, build useful evidence-scoped pages and archive navigation, make Inspector contextual, correct health mapping, then run regression and responsive browser QA. No unrelated working-tree changes were found.

## Exact changed-file inventory

| File | Purpose |
| --- | --- |
| `frontend/package.json` | Pin the small Markdown tokenizer `marked` at 18.1.1 |
| `frontend/package-lock.json` | Lock its single new package; no transitive dependency additions |
| `frontend/src/App.tsx` | Navigation/landing/composer, shared answers, saved-analysis actions, friendly failures, refresh ownership and page-aware Trace Inspector scope |
| `frontend/src/components/AnswerContent.tsx` | Safe Markdown token-to-React renderer and exact-source citation controls |
| `frontend/src/components/KnowledgeStatus.tsx` | Trusted graph/backend/provider status mapping, icons and refresh |
| `frontend/src/components/ConversationList.tsx` | On-demand search, compact titles, keyboard-operable contextual actions and existing confirmations |
| `frontend/src/components/WorkspacePage.tsx` | Decisions, Services, People and all-conversation Saved Change Analyses |
| `frontend/src/components/ChangeBrief.tsx` | Change Assessment, overview, friendly nine-section presentation, original-answer and path disclosures |
| `frontend/src/components/Inspector.tsx` | Contextual overview, metadata disclosure, truthful status and sample-source copy |
| `frontend/src/components/EvidenceGraph.tsx` | Friendly node/relationship labels and a working Fit graph action |
| `frontend/src/components/ImpactResults.tsx` | Friendly capability heading |
| `frontend/src/components/ExpertResults.tsx` | Friendly capability heading |
| `frontend/src/components/FreshnessResults.tsx` | Friendly capability heading |
| `frontend/src/components/WorkspacePanel.tsx` | Include selects and disclosure summaries in the existing drawer focus trap |
| `frontend/src/tracePresentation.ts` | Narrow the relationship sentence input to the three fields it actually reads; shared display only |
| `frontend/src/styles/product.css` | Cohesive product presentation, wrapping, disclosures, health colors, cards and responsive refinements |
| `frontend/src/main.tsx` | Load the product presentation stylesheet after existing styles |
| `frontend/src/App.test.tsx` | Updated presentation journeys plus empty graph and actual health refresh |
| `frontend/src/ChangeBrief.test.tsx` | Updated section labels, disclosure journeys and nonduplicated overview assertions |
| `frontend/src/ChatWorkspace.test.tsx` | Context menus/search, existing persistence journeys and exact saved-turn reopening without replay |
| `frontend/src/TraceWorkspace.test.tsx` | Existing playback ownership checks, disclosure entry and inspection after leaving Trace Mode |
| `frontend/src/AnswerContent.test.tsx` | Markdown, plain breaks, citations, unavailable sources, unsafe content, nesting and long output |
| `frontend/src/KnowledgeStatus.test.tsx` | Connected, unavailable, backend failure, checking, unknown, partial, sample and provider/refresh independence |
| `frontend/src/WorkspacePage.test.tsx` | Returned relationships, exact direction, genuine Trace entry, sources, reviewers, actions and scoped empty states |
| `docs/PHASE4C_PRODUCT_REDESIGN_HANDOFF.md` | This handoff |

## Navigation and chat

The sidebar now has a static NovaPay workspace identity, prominent New Chat, Chat, Knowledge Graph, Changes, then single-column Explore entries for Decisions, Services and People. Connectors is removed. Workspace names no longer repeat in the header/composer. Collapsed navigation retains accessible labels/titles; mobile uses the existing focus-managed drawer.

Recent Chats retains activity sorting and title/question search. Search opens from its icon, closes/resets with its close action or Escape, and reports empty matches. Titles use one-line ellipsis with complete accessible labels. A per-row ellipsis opens Rename/Delete; Arrow keys move through the menu, Escape returns focus, and existing confirmation dialogs remain. Date headings appear only for longer lists. Existing local-storage limits, privacy screening, independent conversations, persistence warnings and clear/delete behavior are preserved.

The landing says **Ask Weave about your company**, with the requested explanatory subtitle and actual supported NovaPay question actions. The composer stays outside the scrolling content, accessible at desktop and mobile sizes. Optional name personalization remains as a smaller greeting and in the sidebar preference controls. Loading and graph/network/incompatible-response failures use concise user-facing copy; the original stored result/error and API contract are not rewritten.

## Answer readability and safety

The shared renderer handles ordinary and saved answers, successful hosted presentations, original deterministic capability answers and Change history/overview. Structured capability results retain their existing evidence-specific rendering. Deterministic structured answers expose the original full answer on demand instead of duplicating it on initial display.

Marked's lexer supplies headings, paragraphs, hard/soft breaks, emphasis, nested lists, code, quotes and supplied tables. Rendering uses an explicit React element allowlist. **Marked's HTML output is never used.** Raw HTML and images remain inert text, code stays literal, and links pass the existing HTTP(S)-only URL guard with safe external-link attributes. No embedded images, HTML attributes, script content or event handlers are injected. See [Marked's documentation and security guidance](https://marked.js.org/): its default HTML output is not a sanitizer; this implementation deliberately does not consume that output. The dependency is pinned, has no transitive dependencies, and requires Node 20 or newer; checks ran on Node 24.13.0.

Citation controls resolve exact identifiers against that answer's returned `sources`. Unknown canonical handles show **source unavailable**, without an action or invented source. A Markdown URL cannot redirect a recognized source handle away from the Inspector. No graph node, adjacent record or sibling capability is converted to a new textual citation. Formatting does not paraphrase facts or upgrade support.

Long text wraps, tables have a bounded scrollable region, and line lengths/spacing remain readable on mobile. Formatting is presentation-only for deterministic and OpenRouter metadata alike; no frontend generation call or prompt change occurs.

## Change Assessment and cinematic Trace

Change Brief is presented as **Change Assessment**, retaining all nine underlying sections and data:

| Existing section | Presentation |
| --- | --- |
| Proposed Change | Proposed Change |
| Historical Context | Why the system works this way |
| Direct and Downstream Impact | What could be affected |
| Relevant Reviewers | Who should review this |
| Known Facts and Potential Risks | Known facts and potential risks |
| Recommended Validation | Recommended checks |
| Current Knowledge Freshness | Documents to review now |
| Documents to Review if Change Proceeds | Documents to review if the change proceeds |
| Supporting Evidence | Supporting evidence |

The overview shows conservative support, the complete successful hosted presentation or the exact opening paragraph of the deterministic answer. The complete deterministic original remains available in a lazy disclosure. Historical rationale retains its own full validated summary and citations. Section navigation and the ordered historical path inventory are expandable. Facts, inferred risks, recommendations, unperformed checks, per-tool limitations, reviewer scores/order and current versus conditional document reviews remain distinct and unchanged.

**Watch Evidence Trace** stays prominent near the overview; contextual historical/impact entries remain available only for validated sequences. The existing clock, SVG edge motion, camera, reverse Impact travel, step order, controls, reduced motion and paused restoration are preserved. No second player was introduced. Changing to an evidence page now releases the current-step Inspector restriction; while Trace is active, its Inspector still receives only the current tool-local step proof. A regression test covers inspection of a record outside that step after leaving playback.

## Evidence pages, graph and Inspector

- **Decisions:** actual returned decision titles/properties, adjacent stored connections, related sources and inspection/question/graph actions. Watch appears only when a real validated sequence includes the record.
- **Services:** returned services, actual directed dependencies/technology/ownership connections, graph and inspection actions, and an impact-question preparation action. Stored source/type/target are never reversed.
- **People:** actual returned names/roles/properties and contribution connections. When Expert/Change reviewer data exists, its original ranking order, scores and reasons are preserved. Team membership is explicitly not personal ownership.
- **Saved Change Analyses:** all completed Change turns in the existing conversation archive, with proposal, conversation, date, conservative status, a visually bounded exact historical preview and genuine playback availability. Open restores the exact original conversation and turn without POST replay. Analyze a change prepares the existing Chat workflow.

The first three pages explicitly describe the selected answer's available evidence, rather than claiming a complete directory. Related source lists follow only the record itself or an actual adjacent returned relationship; their qualification states that association does **not** assign a new rationale citation. Sources keep their original IDs and metadata. Empty pages do not manufacture records.

Knowledge Graph opens a helpful empty state before an answer exists. Existing answers expose Find entity, Fit graph, the original Change focus/all scope, legend and Inspector interactions. Friendly labels are display-only; canonical IDs and raw relationships remain in evidence/Inspector details. The graph is explicitly returned evidence, not a company-wide graph.

Inspector prioritizes the selected source/entity, retains canonical IDs, properties, stored connections, excerpts, safe original-source links, source/chunk metadata and graph-only qualifications. Unselected overview is shorter, connections/generation details are expandable, and arbitrary GitHub/Jira/Slack connection claims are removed. Closing/reopening and mobile Escape/focus behavior remain available.

## Health bug: before and after

**Before:** the welcome knowledge-state block always rendered `CircleCheck`, including alongside “Graph not available.” Its aggregate-status branch could also describe a degraded dependency as ready.

**After:** trusted, already-validated `/api/health` fields drive graph availability independently of FastAPI and the answer provider:

| State | Display |
| --- | --- |
| Database connected and graph tool available | Green check circle |
| Database or graph tool unavailable | Red X circle, “Knowledge graph unavailable” |
| Backend request fails | Red X circle, “Backend unavailable” |
| Check pending | Neutral spinner |
| Connection not checked | Neutral information circle |
| Other partial/mixed graph state | Amber triangle |
| Explicit fixture workspace | Neutral information circle and sample qualification |

Provider degradation does not turn an actually connected graph into an outage. Provider/backend text is separate. Refresh performs the existing health request, displays checking, and ignores a stale earlier refresh completion. Actual returned failures never silently select fixtures. Desktop/mobile browser checks measured the unavailable icon as red `rgb(166, 63, 63)`, not green; the connected icon was green, unknown neutral and partial amber. Status text carries meaning independently of color.

The compact disclosure reads **“Sample data — results are for exploration, not live company records.”** For an existing answer, its own `metadata.graph_mode` governs this banner; current health cannot relabel real evidence as sample. Source inspection also identifies sample records. No real connection is implied by a sample workspace.

## Verification

Final frontend: **370 tests passed across 20 files** (37 new tests, plus updated UI journeys). Existing evidence validators, exact directed paths, tool-local membership, citation rejection, conservative support, reviewer/document semantics, IndexedDB bounds/privacy, playback clocks and stale-owner checks remain covered.

Passed:

```powershell
npm.cmd --prefix frontend test -- --maxWorkers=2
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

Two workers keep the Windows UI suites within their existing deadlines; no global timeout increase or evidence-assertion relaxation was used. ESLint passed without warnings. Production build completed successfully; the existing graph remains a separate lazy chunk. Final test/build logs are ignored local artifacts. New files also received whitespace checks. No backend files changed, so Python checks were not rerun; prior Python/live results are not claimed as new results here.

## Actual browser QA and screenshots

Used the actual local Vite frontend, Chromium, React Flow SVG and native IndexedDB at **1440×1000, 1280×800, 820×1180 and 390×844**. Responses were deliberately intercepted, explicitly labeled existing offline NovaPay fixtures. The Decision-formatting packet projected the existing fixture's historical narrative/proof inventory; a hosted-formatting presentation was locally simulated, not generated by a provider. Non-local application HTTP was blocked. No live FalkorDB or OpenRouter request/probe occurred.

Verified landing/composer, Decision/Impact/Expert/Freshness/Change rendering, sources by keyboard, source/entity drawers and Escape, search empty/reset behavior, contextual rename, evidence page navigation/inspection, original reviewer ordering, graph controls, saved-assessment reopening and refresh without analysis replay. Tested graph/backend outage and retry, pending/unknown/partial/connected states and icon colors at desktop/mobile widths. Expected 503 resource logs occurred during deliberate outage probes. A transient Vite HMR reload during editing was resolved; the final clean-load pass had **zero unexpected console/page errors** and **zero non-local application requests**.

Trace's real SVG progress advanced `0.04318 → 0.16364`; Pause held exactly `0.19182` across a further observation interval. Reduced motion removed the moving marker and retained step navigation. The mobile transport ended at y=741 and the composer began at y≈752.6, so they did not overlap. Recenter correctly framed endpoints after viewport resize. No page-level horizontal overflow was found at any of the four sizes. The final instrumented session used five local intercepted analysis POSTs (Freshness, Expert, Change, then a deliberately failing Decision request and successful retry); source/page/history/Trace actions added none. Earlier audit and capability checks used separate intercepted requests.

Before/after artifacts are intentionally ignored and available locally for review:

- [Before desktop landing](../.local/phase4c-before-desktop.png) → [After desktop landing](../.local/phase4c-after-desktop.png)
- [Before Change result](../.local/phase4c-before-assessment.png) → [After Change Assessment](../.local/phase4c-after-assessment-desktop.png)
- [Before mobile result](../.local/phase4c-before-mobile.png) → [After mobile assessment](../.local/phase4c-after-assessment-mobile.png)
- [After mobile landing](../.local/phase4c-after-mobile-home.png)
- [Desktop Trace](../.local/phase4c-after-trace-desktop.png) / [Mobile Trace](../.local/phase4c-after-trace-mobile.png)
- [Unavailable graph status](../.local/phase4c-after-graph-unavailable.png)
- [Mobile formatted answer](../.local/phase4c-after-answer-mobile.png)
- [Laptop](../.local/phase4c-after-laptop.png) / [Tablet](../.local/phase4c-after-tablet.png)
- [Decisions](../.local/phase4c-after-decisions.png) / [People](../.local/phase4c-after-people.png) / [Saved analyses](../.local/phase4c-after-saved-analyses.png)

QA used a dedicated local origin. Its generated test history was cleared through the actual confirmation UI; existing user history on other origins was untouched. Browser interception and the local QA server are removed/stopped after verification.

## Limits and deployment readiness

This frontend pass is ready for code/product review, **not a deployment or live-provider acceptance claim**. Repeat these flows against the approved seeded FalkorDB and actual FastAPI responses before release. Any live OpenRouter verification still needs the existing explicit reviewed-payload approval process. No external evidence transmission is authorized or performed by this work.

Directories remain scoped to the selected answer; no global graph/company directory or connector-management endpoint was invented. Ask/impact actions prepare questions within the existing bounded backend capabilities and do not broaden supported entities or execute a change. Saved analyses are browser-local snapshots, not a company activity feed. The existing single-writer-tab, no-cloud-sync, bounded archive and nonpersisted playback-progress limitations remain.

Markdown is formatted from returned text without a frontend summarizer. Deterministic overview intentionally uses its exact opening paragraph; full rationale and the complete original are available separately. Raw HTML/images and unsupported embedded content remain inert. Dense full graphs still require pan/zoom or relationship inspection. Physical touch-device and screen-reader hardware testing remains additional release QA beyond Chromium viewport emulation and automated keyboard/ARIA coverage.

No backend, provenance, support or API blocker was discovered by this presentation task. Combined live database/provider verification remains outside these offline results.
