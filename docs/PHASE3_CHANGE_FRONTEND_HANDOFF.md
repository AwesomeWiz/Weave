# Phase 3 Stage 2 — React Change Brief handoff

## State — October 18, 2026

Implemented on `integration/phase3`, at HEAD `75e7f7c4c29b169d2737dcc1436ec0ae4953c742`, above the existing uncommitted Stage 1 backend foundation. Stage 1 files were hashed before this task and remain byte-for-byte unchanged, including its tests and documentation. No backend integration changes were necessary.

`main`, `origin/main`, and both starting stashes are unchanged. No stash was applied, no teammate branch was merged, and nothing was committed or pushed. Stage 2 changes remain available for review alongside Stage 1.

The frontend is functional with explicitly configured development data or the existing real endpoint. **This task's browser verification used intercepted offline demonstration data, not live FalkorDB.** No live OpenRouter requests were made.

## Exact Stage 2 files

Modified:

- `frontend/src/App.tsx` — structured endpoint selection, history/retry, Change action, evidence scope and highlighting.
- `frontend/src/api.ts` — typed `analyzeChange()` client using the existing request/error boundary.
- `frontend/src/types.ts` — exact nested Change response interfaces.
- `frontend/src/components/EvidenceGraph.tsx` — optional node emphasis and initial fit to actual Change nodes; existing renderer retained.
- `frontend/src/styles/globals.css` — scoped Change Brief styling and responsive refinements.

Added:

- `frontend/src/components/ChangeBrief.tsx` — nine-section brief with existing entity/source interactions.
- `frontend/src/change.ts` — bounded endpoint selector, response guard, actual-evidence graph focus.
- `frontend/src/changeValidation.ts` — nested display-boundary contract checks.
- `frontend/src/change.test.ts` — 51 client/routing/provenance regressions.
- `frontend/src/ChangeBrief.test.tsx` — 13 workspace/interaction regressions.
- `frontend/src/test/changeFixture.ts` — explicit offline test response derived from the Stage 1 graph double, marked fixture mode.
- `frontend/src/test/changeTestCases.ts` — qualified missing-source and unsupported-response test cases.
- `docs/PHASE3_CHANGE_FRONTEND_HANDOFF.md` — this handoff.

The test data is not imported by production retrieval or application rendering. There is no runtime fixture fallback, extra source retriever, graph renderer, frontend LLM client, new Cypher, ingestion change, or Trace Mode.

## Typed API and validation

The new client uses exactly:

```http
POST /api/change-intelligence
Content-Type: application/json

{"target":"Payment Service","change":"What happens if we remove Redis from Payment Service?"}
```

`ChangeResponse` extends the original grounded `QueryResponse` with `data: ChangeBriefData`. Existing `/api/query` consumers and all existing client functions/validators remain intact. No `any` is used to bypass nested typing.

The interfaces mirror the actual Pydantic models in `backend/app/models.py` and [Stage 1 handoff](PHASE3_CHANGE_BACKEND_HANDOFF.md):

```text
ChangeBriefData = {
  proposed_change: ChangeTarget,
  historical_context: ChangeHistoricalContext,
  impact: ChangeImpact,
  reviewers: ExpertRanking[],
  risks: ChangeRisk[],
  validation_steps: ChangeValidationStep[],
  current_freshness_findings: FreshnessFinding[],
  documents_to_review_if_change_proceeds: ChangeDocumentReview[],
  tool_support: Partial<Record<ChangeTool, ChangeToolSupport>>,
  limitations: string[]
}
```

The display boundary first uses the existing common evidence validator, then verifies:

- Request echo, intent/resolution enums, canonical service/technology node copies and an actual tool-local `Service USES Technology` relationship for resolved proposals.
- Valid support states and tool names, truthful `tools_used` membership, and no obvious overall support upgrade over incomplete tool results.
- Existing canonical node/edge/source IDs, complete edge endpoints, source/entity association, tool-local provenance membership and returned edge-ID proof groups.
- Impact depth/type/path agreement, scoped traversal through the changed service, stored USES/DEPENDS_ON direction, actual owners and related records.
- Existing reviewer identities, roles, positive scores, returned ranking order, evidence categories/direction, ownership/history membership and allowed source IDs. Scores are displayed, not recalculated.
- Historical citations within their own trace source inventory. Graph-only evidence is permitted without invented citations.
- Freshness document/trigger timestamps, strictly later aware instants, actual directed associations, accepted Decision and architecture-change Commit qualifiers, and document/commit-only citations. Decision and Incident triggers cannot acquire textual citations.
- Exact future-review condition `if_change_approved_and_implemented`, an actual local document/service association, valid risk categories, and `performed: false` recommendations.
- Duplicate document IDs and response/list/byte bounds.

Malformed evidence produces an actionable `INVALID_RESPONSE` error before rendering. These checks supplement the authoritative backend validators; they do not recompute company findings, rankings, chronology, or support status.

## Chat, history, loading and errors

`routeChangeQuestion()` mirrors the backend's explicit proposal prefixes. The canonical removal question selects the dedicated structured endpoint **once**, before Phase 2 single-tool shortcuts. It does not call `/api/query` and then replay the four tools to obtain structured data.

The complete removal grammar preserves the user's target text; it does not manufacture canonical IDs. Unsupported proposals also reach the backend for qualification. Where such a proposal supplies no service, `Unspecified service` is an explicit missing-target label rather than a guessed company entity. Backend resolution remains authoritative.

The four Phase 2 cards and routing patterns remain functional. A separate, compact Change Intelligence action below those cards opens the canonical scenario without redesigning the workspace or activating unfinished navigation sections.

The existing composer, in-flight guard, loading state, error/retry flow, session history and navigation are retained. Structured response data stays in history; restoring it or returning from graph view performs no new analysis request. Invalid/unknown/ambiguous proposals show insufficient evidence and empty sections with explicit qualifications. Backend errors preserve their existing sanitized messages.

## Brief presentation

The component shows:

1. Proposed Change — original proposal, resolution and actual service/technology IDs.
2. Historical Context — unchanged validated narrative with clickable citations and its own support status.
3. Direct and Downstream Impact — immediate versus potential downstream findings, exact depths, stored arrows, owners/teams and actual path highlighting.
4. Relevant Reviewers — existing rank order, scores, reasons, person inspection, separate team ownership and historical expertise.
5. Known Facts and Potential Risks — distinct **KNOWN FACT**, **INFERRED RISK** and **RECOMMENDATION** labels, with uncertainty and evidence.
6. Recommended Validation — actions explicitly marked **Not performed**.
7. Current Knowledge Freshness — actual current review candidates, dates, later changes and graph-only labels.
8. Documents to Review if Change Proceeds — a separate conditional section, prominently qualified by approval and implementation.
9. Supporting Evidence — existing `SourceRow` interactions, per-tool support/state and preserved limitations.

Sections use the existing paper/forest palette, typography, buttons and responsive shell. Plain dividers and compact, expandable proof details keep the page readable. Expensive proof bodies mount only when opened, retaining native keyboard-operable disclosure behavior.

Facts use a calm graph-evidence treatment, inferred risks use amber, and recommendations use blue. No risk is styled or worded as a proven outage. Team membership is never relabeled as individual ownership, and proposed validations never appear completed.

ADR-7 appearing in future review is **not** labeled currently stale. Its disclosure is titled “Service-document association,” so the source capability's name cannot be mistaken for a current staleness finding. Current and conditional sections can contain the same document for separate backend-provided reasons.

Every actual source button opens the existing `Inspector`; every entity button uses existing node inspection. Missing textual evidence is labeled rather than replaced. Limitations present in both `data` and metadata are shown once; metadata-only warnings remain visible. Explicit fixture mode retains the existing development banner and inspector labels.

## Graph selection and provenance

The existing React Flow `EvidenceGraph` remains the only renderer. `changeGraphFocus()` selects a subset of actual returned objects using structured history, impact, reviewer and document evidence references. It excludes chunk clutter from the default focus, without deleting the full response from inspectors.

The verified offline example has **16 focus nodes / 27 edges**, versus **23 returned nodes** in the full view. The initial Change viewport frames actual primary service/technology/dependency nodes. Surrounding rationale/reviewer/document context remains available through pan/zoom or “All returned evidence.” Primary dependency nodes/edges receive emphasis; other context is quieter. Normal node selection takes precedence over default edge emphasis.

“Highlight path” uses exact backend `path_edges`, preserving `Payment USES Redis`, `Checkout DEPENDS_ON Payment`, and `Order DEPENDS_ON Checkout`. Evidence disclosures can highlight their actual returned edge IDs. The relationship table and inspectors keep the complete verified response available.

Document association proof groups can branch from the same Decision. They are rendered as separate stored relationships, not reconstructed as a linear historical walk. No new edge, timeline, causal link, or ordered Decision Trace path is inferred.

The optional focus-fit/emphasis props leave ordinary Phase 2 graph callers compatible. A Change focus refits when its graph scope or viewport dimensions change; user selection itself does not change graph data or layout.

## Verification

Frontend baseline before changes: **116 passing tests**.

Final Stage 2 checks:

- `npm.cmd --prefix frontend test`: **180 passed**, across eight test files.
- ESLint: passed.
- TypeScript: passed.
- Production build: passed.
- `git diff --check`: passed.
- All starting Stage 1 file hashes: unchanged.

The 64 added tests cover typed requests, nested invalid evidence and support states, unknown citations, local provenance membership, dependency direction/depth, reviewer identities/ownership, risk classifications, recommendation status, current/future document semantics, explicit proposal selection, network/graph errors, graph-only responses, history restoration, source/person inspection, path highlighting, graph scope switching, narrow-viewport drawers and all four Phase 2 regressions.

No backend files changed during Stage 2, so Python tests were not rerun for this frontend-only change. Stage 1's recorded result remains 578 passed / 11 live tests skipped; that earlier result is not a new live acceptance claim.

## Browser verification

Used local Vite with the **real React Flow renderer and existing inspectors**, at 1440×1000 and 390×844. API responses were intercepted from the explicitly labeled offline test response. Non-local HTTP was blocked; no hosted provider was contacted. The QA-only browser imported the test fixture deliberately; production code does not import it.

Verified:

- All nine sections render, with explicit partial support and fixture labeling.
- One Change POST for a canonical submission, no query replay or duplicate analysis.
- Historical citation opens its source; mobile inspector opens as the existing modal drawer and Escape dismisses it.
- Checkout highlighting selects two actual path edges; Order highlighting selects three.
- Focus/full evidence switching works; primary framing adapts to mobile dimensions.
- Current and conditional document review remain visibly distinct, including ADR-7's conditional wording.
- No page-level horizontal overflow at either size; no browser console errors or warnings.

Ignored QA artifacts under `.local/` include `change-brief-desktop.png`, `change-graph-desktop.png`, `change-graph-focused-desktop.png`, `change-documents-desktop.png`, `change-brief-mobile.png`, `change-source-mobile.png`, `change-documents-mobile.png`, and `change-graph-mobile-fitted.png`. These are offline QA artifacts, not evidence of live FalkorDB acceptance or runtime fallback data. On narrow screens the graph supports pan/zoom and the accessible relationship table; dense full evidence is not intended to be read at a single zoom level.

## Remaining live QA and future ordered paths

Before live Phase 3 sign-off, run the Stage 1 opt-in real Change acceptance test against the recorded seeded FalkorDB revision, with the real source adapter and fixture mode disabled. Then repeat this browser flow against actual FastAPI responses: canonical question, partial tool/source failures, unsupported/ambiguous targets, graph directions, reviewer ownership, current versus conditional review, citation inspection, desktop/mobile interaction and request counts.

This task did not execute live Phase 3 FalkorDB acceptance. The prior Phase 2 sign-off does not verify the new workflow automatically. Hosted Change presentation remains Stage 3 work and requires a separate safe renderer and any necessary reviewed payload approval.

Antony's unfinished ordered-path branch was not merged. When its normalized contract is available, integrate it at the existing backend history/provenance seam and add typed display/validation for explicitly supplied ordered paths. Do not infer order from the current edge inventories or document association groups. Trace Mode remains out of scope.
