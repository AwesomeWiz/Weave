# Phase 3 ordered Decision Trace path integration

## Git state and integration — October 18, 2026

Work is on `integration/phase3`. The working tree was clean when this task began. All Stage 1–3 work had already been committed, and Antony's finalized branch had already been merged by the user:

- Verified teammate commit: `d0dfd2c2cc32dcea3d4e9595434ca42ebff3a59b`.
- Existing merge commit and final branch HEAD: `b6225153c4e973be5f340d6d3d2160582262460e`.
- Merge parents: `f14285c` (existing completed Phase 3) and `d0dfd2c` (Antony).
- `git fetch origin feature/phase3-change-intelligence-graph` completed and the remote-tracking SHA exactly matched the required commit. An ancestry check confirmed it is already included in HEAD.

No new merge, checkpoint commit, or conflict resolution was necessary. Inspection of the overlapping files confirmed that `models.py` preserves both Antony's path models and the existing Change models; `orchestration.py` preserves Antony's path mapping and the validated Impact/Expert/Freshness structured data; `antony.py` preserves the actual latest trace call with `include_relationship_paths=True`. No wholesale ours/theirs replacement was performed.

The integration changes below remain **uncommitted for review**, so final HEAD remains the existing merge commit. No main modification, reset, teammate branch merge, automatic push, or stash operation was performed. Local `main` and `origin/main` remain `75e7f7c4c29b169d2737dcc1436ec0ae4953c742`. Stashes remain intact:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

## Files changed in this task

| File | Purpose |
| --- | --- |
| `backend/app/models.py` | Strict bounded existing trace path models; optional-by-default historical path list |
| `backend/app/antony.py` | Reuse the shared directed-path check; reject orphan path evidence without a selected decision |
| `backend/app/context.py` | Validate/copy ordered paths against the original trace graph, including mutated typed results |
| `backend/app/context_v2.py` | Keep named paths separate from existing edge-ID sequences, with independent local validation and copies |
| `backend/app/orchestration.py` | Preserve path objects/names; reject invalid supplied paths instead of silently filtering them |
| `backend/app/change_intelligence.py` | Revalidate local paths/sequences and expose them in historical context |
| `backend/app/change_synthesis.py` | Reject presentation history differing from validated ordered provenance |
| `backend/tests/test_ordered_change_paths.py` | 21 new actual-tool offline integration and rejection cases |
| `backend/tests/test_antony_adapter.py` | Coherent reduced-path test inputs for existing missing-rationale scenarios |
| `backend/tests/test_multitool.py` | Coherent missing-USES test input |
| `backend/tests/test_change_intelligence.py` | Coherent missing-document-association test input |
| `backend/tests/test_change_openrouter.py` | Coherent missing-rationale test input |
| `backend/tests/test_openrouter.py` | Coherent missing-rationale test input |
| `frontend/src/types.ts` | Typed ordered historical paths, optional for earlier responses |
| `frontend/src/changeValidation.ts` | Exact directed edge, tool membership, step order and proof-sequence checks |
| `frontend/src/change.ts` | Resolve only an actual returned historical path to existing graph edge IDs |
| `frontend/src/components/ChangeBrief.tsx` | Historical path names, numbered steps, inspectors and existing highlighting |
| `frontend/src/styles/globals.css` | Scoped list numbering, spacing, separators and wrapping |
| `frontend/src/test/orderedTraceFixture.ts` | Small explicit test-only fixture from actual merged tools over the offline graph double |
| `frontend/src/change.test.ts` | 18 path contract, compatibility, highlighting and invalid-response cases |
| `frontend/src/ChangeBrief.test.tsx` | Three historical display, inspector, highlight and legacy UI cases |
| `docs/PHASE3_ORDERED_PATH_INTEGRATION_HANDOFF.md` | This handoff |
| `docs/README.md` | Latest integration link |

Antony's `app/graph/trace.py`, graph client, Cypher, ingestion and source retrieval are unchanged by this task. No alternate graph implementation or reconstruction algorithm was added.

## Exact dedicated API addition

`POST /api/change-intelligence` retains its existing response fields and structured data. Named paths now appear at `data.historical_context.relationship_paths`:

```json
{
  "relationship_paths": [
    {
      "id": "decision_to_current_architecture",
      "steps": [
        {"source": "decision:D-007", "type": "IMPLEMENTED_BY", "target": "commit:8fae2"},
        {"source": "commit:8fae2", "type": "CHANGES", "target": "service:payment-service"},
        {"source": "service:payment-service", "type": "USES", "target": "tech:redis"}
      ]
    }
  ]
}
```

The array preserves the actual tool's path order, names, source/type/target strings and step order. Path names are not translated into an invented chronology. The actual offline tool also returns separate `incident_to_investigation`, `decision_to_investigation`, `decision_to_discussion`, and `decision_to_documentation` paths. These include the real LED_TO and Decision SUPPORTED_BY directions, not a fabricated Issue→Message→Decision chain. The renderer accepts other valid returned names; it does not hardcode these five paths.

Limits: at most 80 paths; a nonempty path ID of at most 128 characters; 1–10 steps per path; strict string source/type/target fields; no extra path or step fields. Path IDs must be unique. The structured Change Brief's existing 160,000-byte bound remains enforced.

Backend legacy/default behavior is `relationship_paths: []`. Older responses may omit the field; the TypeScript interface and display validator accept omission or an empty list. No named path is synthesized from the older edge inventory.

`historical_context.evidence.relationship_paths` remains the existing **edge-ID proof sequences**, not this named object list. Internal `ToolEvidence` and `ToolProvenance` retain those sequences and now separately carry `ordered_paths`. Impact traversal paths remain in `data.impact` and keep their existing semantics.

`POST /api/query` remains exactly six fields: `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`. It does not acquire `data` or a top-level ordered-path field. It uses the same core analysis once. The dedicated endpoint is the structured UI integration boundary.

## Provenance and grounding

1. Antony's actual gateway still calls `trace_decision(..., include_relationship_paths=True)` and normalizes the original payload.
2. Shared path validation requires every source and target node and every exact `(source, type, target)` edge to exist in **that trace result's graph**. Consecutive steps must be directed and contiguous. A disconnected/reordered/reversed path, stale edge, unknown entity, duplicate name or invalid schema is rejected.
3. The trace Context Builder repeats validation even for alternate typed delegates, including mutated Pydantic instances. It retains the original graph without manufacturing edges. Orchestration no longer silently drops an invalid supplied ordered path or replaces it with legacy singleton groups.
4. Context Builder V2 checks the named paths against the tool-local graph and their corresponding edge-ID sequences, deep-copies the validated objects and retains names/order. Other tools cannot supply named Decision Trace paths. Merged sibling edges cannot repair a missing trace relationship.
5. The Change builder repeats local membership and sequence checks before copying named paths to historical context. This rejects stale post-merge changes rather than exposing a path that disagrees with its proof inventory.
6. Frontend display validation independently checks bounds, duplicate names, exact graph membership, historical tool-local node/edge membership, directed contiguity, and the same step sequence in the historical edge-ID proof. The graph highlight resolver uses only that returned sequence.

Invalid trace evidence follows the existing conservative orchestration policy: exclude that capability and record its invalid/insufficient state if other validated capabilities remain; retain truthful partial support and missing-evidence warnings. It does not borrow a sibling's path or rationale. All-invalid or direct trace contract errors retain the existing sanitized error handling.

The old missing-source tests previously deleted edges from a typed result while retaining newly added path annotations. Those inputs now correctly represent stale evidence and must be rejected. Their missing-evidence scenarios were made coherent by omitting annotations for the deliberately removed edges; their assertions about rationale, conservative status, source provenance and sibling isolation were retained. Separate new tests explicitly cover stale annotations and rejection.

Historical rationale still requires the accepted decision and actual retrieved SUPPORTED_BY / Chunk FROM_* provenance. Ordered structural paths add **no textual citation** and do not upgrade support. The offline canonical result remains `partially_supported`, with supported history and conservatively qualified impact.

## Preserved Phase 3 and hosted behavior

Four-tool deterministic orchestration, one deduplicated source retrieval, structured brief, actual source/chunk provenance, reviewer rankings, risk classifications, unperformed validations, current freshness versus conditional future document review, health behavior and error sanitization remain intact.

OpenRouter still receives only the existing bounded finite presentation packet. Named path IDs/steps are not added to its external payload in this task. The packet builder additionally checks that historical path objects equal the validated trace provenance. A mutation causes deterministic fallback; no free-form provider claim or path rewrite is accepted. Successful generation changes only presentation metadata/answer, not path objects, graph, sources, classifications or support. Existing provider failure/fallback and Phase 2 tests pass.

No live OpenRouter request or provider probe occurred. All provider tests were mocked. Previous hosted approvals do not authorize a new live payload. Any later hosted test requires separate exact frozen/redacted payload review and explicit bounded approval.

## React integration and browser verification

The existing Historical Context section now shows **Ordered historical evidence paths**. Each returned path has its exact ID, numbered steps, stored direction/type, clickable existing entities, canonical IDs, and a button to highlight that precise path through the existing React Flow renderer. A label distinguishes these separate historical proof paths from a single timeline and from Impact Analysis traversal. No textual citations are attached to the structural path list.

The existing `onEvidence`/graph selection flow is reused. Highlighting the architecture path selects only its IMPLEMENTED_BY, CHANGES and USES edge IDs; it does not highlight downstream DEPENDS_ON edges. Returning to the brief performs no new analysis. Existing source citations, proof disclosures, reviewer details, support labels, hosted overview and all nine structured sections remain available.

Legacy responses explicitly state that no ordered historical sequence was returned; the UI does not infer one. No playback controls, Trace Mode state machine or animation was implemented.

Browser QA used the real local React Flow renderer at 1440×1000 and 390×844, with intercepted **explicit development fixture** responses. The small new test fixture was generated from actual merged tools over the existing offline ingested graph double; every referenced graph object was checked for exact equality with existing frontend test graph evidence. Production imports no test fixture.

Verified five returned paths, exact three-step architecture order, the three actual SVG edges highlighted, one Change POST, zero query replay, entity inspectors/Escape on desktop and mobile, no page errors and no horizontal overflow. Non-local browser HTTP was blocked. Ignored artifacts: `.local/ordered-path-desktop.png` and `.local/ordered-path-mobile.png`. The local QA server was stopped afterward.

## Verification

Merged baseline before edits: **642 Python tests passed, 11 live tests skipped**.

Final offline results:

- Python: **663 passed, 11 skipped**, full `backend/tests tests app/graph` suite.
- Ruff: passed for `backend/app backend/tests`.
- Frontend: **203 passed**, across eight test files.
- ESLint: passed.
- TypeScript: passed.
- Vite production build: passed.
- Whitespace checks: passed, including new untracked files.

One existing Starlette/httpx TestClient deprecation warning remains. No remaining offline import, adapter-contract or graph-query test failures were observed. The 11 live skips are not acceptance results.

Reproduce:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-phase3-ordered
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

## Live QA requirements and limitations

**The combined workflow has not passed live FalkorDB QA.** Antony's independent branch verification and these offline tools/tests do not establish combined acceptance. Arnold must record the actual application/seed revisions and use an already approved seeded database with the real graph/source adapters and hosted generation disabled. Do not launch, reseed, truncate or mutate a shared graph automatically; coordinate preparation with Alen and Antony.

1. Run the existing opt-in real Phase 3 acceptance gate and Phase 2 gates on the same actual database. Configure `WEAVE_GRAPH_FACTORY=app.antony:create_gateway`, `WEAVE_GRAPH_MODE=falkordb`, `WEAVE_SOURCE_BACKEND=weave_data`, `WEAVE_LLM_PROVIDER=none`. The existing test itself forces the real graph/source settings and forbids fixture construction.
2. Inspect the canonical dedicated Change response against the actual trace response: identical path names/order/steps, accepted D-007, actual IMPLEMENTED_BY→commit CHANGES→Payment USES→Redis architecture path, exact directed graph edges, and tool-local historical proof membership. Do not require an unavailable relationship or invent one to satisfy the UI.
3. Confirm real PAY-42, payment-perf-7, ADR-7 and 8fae2 source/chunk provenance, supported historical rationale, actual Checkout/Order dependencies, unchanged reviewer ranking, current Architecture Overview review and conditional ADR-7 review. Verify conservative overall/per-tool statuses, no fixture contamination and no fabricated citations.
4. Verify the dedicated endpoint, exact six-field canonical `/api/query`, one analysis/retrieval pass per request, and browser historical display, inspectors, source citations, three-edge highlight and back navigation at desktop/mobile sizes.
5. Use authorized isolated test data or a controlled local double for missing/reversed relationships, disconnected order, duplicate names, stale annotations, missing source/chunk provenance, unavailable tools and legacy no-path output. Check exclusion/errors without sibling repair. Do not alter a shared seed for negative cases.
6. Exercise deterministic hosted fallback and successful finite selection with a local mocked provider against the validated response; confirm path/evidence/support immutability. A live hosted test needs separate reviewed approval before any transmission.
7. Record actual results, application/seed identifiers and screenshots before sign-off. Real schema/provenance differences remain blockers to report and resolve with the teammates, not evidence to fabricate in the renderer.

Existing opt-in gate, not run in this task:

```powershell
$env:WEAVE_RUN_REAL_CHANGE_INTEGRATION = '1'
$env:WEAVE_GRAPH_FACTORY = 'app.antony:create_gateway'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_change_intelligence.py -m integration -v
Remove-Item Env:WEAVE_RUN_REAL_CHANGE_INTEGRATION
```

The named-path inspection in steps 2–5 is additional to that existing baseline gate. Missing ordered metadata is supported for compatibility; it does not prove the new real path workflow has passed. Paths prove stored graph relationships, not a complete historical chronology, guaranteed runtime failure, successful cache-removal validation, or safe change approval. The canonical scenario and existing response-size limits are unchanged. Trace Mode remains future work requiring a separate request.
