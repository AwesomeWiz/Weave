# Phase 1 verification — October 17, 2026

## Retrieved rationale provenance — latest verification

The offline primary query now returns **supported** using the actual merged trace and Alen retrieval functions with explicit database doubles. No live FalkorDB verification was attempted or claimed. Latest Python result: **185 passed, two real database tests skipped**; Ruff passed. The pre-existing Starlette test-client warning remains non-failing. Frontend code was unchanged and its checks were not repeated in this backend-only pass.

The provenance was not lost in normalization or retrieval. Antony's graph preserves `D-007 SUPPORTED_BY issue:PAY-42` / `message:payment-perf-7` and the corresponding `Chunk FROM_* Source` edges. Alen's `SourceRecord` and backend source wrapper preserve parent citation IDs, contributing chunk IDs, timestamps and chunk metadata. Context Builder's `by_entity` / `source_for` lookup previously recognized only direct source-to-Decision linkage, then required `decision.id in source_for`; that excluded this complete multi-hop path.

The focused fix is confined to `backend/app/context.py`: derive an internal rationale source lookup for accepted decisions with the existing service/technology relationships, using only returned SUPPORTED_BY and correctly directed, typed FROM_* paths. It verifies all contributing chunks' canonical parent/type/index/text against the retrieved source and its ordered excerpt. Existing direct-source behavior remains supported. It changes no graph nodes/edges, source IDs, `entity_ids`, teammate queries, API schema, LLM prompt/provider or citation validator. The explanation uses retrieved source text with its actual Issue/Message citation, not the Decision summary relabeled as a source.

New regressions first reproduced the bug: the two valid-path cases failed as partial before the context fix, while all missing-path cases were already rejected. Sixteen focused provenance cases now cover complete paths, missing/reversed/wrong-type relationships, wrong chunk IDs/parent/text/snippet, nonaccepted status, absent USES/AFFECTS/INTRODUCES, multi-chunk ordering/truncation and missing contributing chunks. Three further merged-pipeline cases verify Message-only support and removal of decision-support or chunk-provenance paths. Two earlier partial-result assertions now correctly expect supported evidence while retaining checks against synthetic Decision citations and graph mutation. The older source-only test double without Chunk nodes/edges still returns partial support, as required.

The existing `weave_graph` namespace, graph/source adapters and teammate Cypher were not modified. The stash remains intact. Earlier dated partial-support findings below describe the state before this context fix.

## Latest trace merge and selective stash reconciliation

Reviewed merge `2c05fc0` / Antony's `d3441b8` and all tracked/untracked contents listed in `stash@{0}` before editing. The restored integration adapter, compatibility namespace and tests were retained. Only compatible client/configuration/import changes were reapplied; the older stashed trace and outdated documentation were not restored. The stash remains intact.

The baseline stopped at four **import/collection errors**: absolute `app.graph.*` imports collided with FastAPI's `app.graph` gateway module. Relative imports within the teammate package and `weave_graph.trace` in external tests resolve that collision through the existing compatibility namespace. The client auth/TLS/timeouts/close options expected by the adapter were selectively restored. The adapter now preserves Antony's returned warnings, including missing-path and chunk-provenance warnings. The old database test double was updated to answer the new USES/LED_TO queries rather than replacing those queries with older code.

Latest result: **166 Python tests passed, two opt-in real database tests skipped**; Ruff passed. This includes Antony's latest strengthened smoke assertions executed with an explicit offline database double. AST comparison confirmed that the complete `trace_decision` and teammate smoke `main` function bodies match the latest merged HEAD: query code, USES, LED_TO, SUPPORTED_BY, provenance retrieval and smoke assertions are unchanged. Only their imports differ.

No import or adapter contract test failures remain. No actual FalkorDB query failure has been established: live query execution remains **unverified**, because the current configured `novapay` database probe returned unavailable. The offline API still reports partial support because retrieved sources lack the explicit source-to-Decision rationale linkage required by the unchanged Context Builder. This is a grounding/provenance limitation, not an import failure or a proven database-query error. Public API and grounding safeguards were not modified.

Reproduce from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'backend;.'
.\.venv\Scripts\python.exe -m pytest backend\tests tests app\graph -q --basetemp=.local/pytest-restored-check
.\.venv\Scripts\python.exe -m ruff check --config backend\pyproject.toml backend app\graph weave_graph tests\test_decision_trace.py
```

Older dated verification notes below retain their original context.

The later frontend refinement is documented in [UI_REFINEMENT_VERIFICATION.md](UI_REFINEMENT_VERIFICATION.md), including updated browser checks, personalization, collapsible panels and viewport scrolling. Earlier browser notes below describe the original Phase 1 layout.

## Verified locally

| Check | Result |
| --- | --- |
| Backend/ingestion/graph pytest | 185 passed; 2 real database tests skipped after rationale provenance fix |
| Backend Ruff | Passed |
| Frontend Vitest | 41 passed after UI refinement; see linked report |
| Frontend ESLint | Passed |
| TypeScript strict check | Passed |
| Vite production build | Passed |
| Fixture `GET /api/health` | HTTP 200, degraded, graph tool fixture, FalkorDB not checked |
| Fixture `POST /api/query` | HTTP 200, supported, six source records, 12 nodes, 14 edges |
| Real-mode `GET /api/health`, no graph/tool | HTTP 503, graph and tool unavailable |
| Real-mode primary `POST /api/query`, no graph/tool | HTTP 503, GRAPH_UNAVAILABLE, no fabricated evidence |

Automated checks were last run on October 16. The live HTTP and browser checks below ran on October 15. The real-mode HTTP checks ran on an isolated local FastAPI server with no adapter configured and no FalkorDB server listening. They verify failure behavior, **not successful real graph integration**.

Backend tests cover input validation, canonical IDs and envelope shape, fixture labeling, real-mode failure, configured factory normalization, duplicate records, dangling edges, missing relationships and sources, graph preservation on source/LLM failures, routing boundaries, safe source URLs, CORS, and mocked Ollama response/model checks. Removing `INTRODUCES` removes the grounded rationale and prevents model generation.

Frontend tests cover network and API errors, unreadable/malformed responses, health 503 handling, URL safety, Enter submission, Shift+Enter, disabled/loading state, retry, and citation inspection. Component tests stub the canvas; the real React Flow renderer was exercised separately in the browser.

## October 16 integration regressions

### Alen merged package integration (latest)

Verified merge `26ae66a` on `integration/phase1` with a clean starting worktree. Baseline: 137 backend/ingestion tests passed, one real test skipped; 41 frontend tests passed. The initial test run hit Windows temp-directory permissions; using a workspace-owned `--basetemp` resolved that without changing application behavior.

The source boundary now consumes Alen's actual graph-backed `find_sources` and `FalkorDBGraphAdapter`. Ten additional offline cases cover the four canonical sources, multi-chunk provenance/order, source failure without fallback, public HTTP shape and sanitized failures, explicit ingestion CLI failure/memory behavior, fixture isolation, and read-only parameterized client configuration. Test graph doubles are explicitly offline; no source query/Cypher or ingestion implementation was duplicated. All prior citation, decision-status, health and error regressions continue to pass.

Latest full Python result: **147 passed, 2 skipped**. Backend plus changed package-file Ruff checks passed. Frontend remained unchanged: **41 tests passed**, ESLint, TypeScript and production build passed.

The two skipped tests cover (1) full seeded primary query through Antony's missing trace tool and (2) independent real ingestion/retrieval using a unique test graph. Docker is not installed, no local port 6379 listener was found, and the configured real database probe returned unavailable. An actual source package HTTP test correctly returns partial evidence because there is no retrieved rationale source explicitly linked to accepted D-007. [Current configuration, provenance mapping and blockers](REAL_INTEGRATION_HANDOFF.md) document the distinction. No successful live-database or full GraphRAG workflow is claimed.

Five new backend regressions failed before the fixes and now pass: source-native IDs differing from graph IDs, proposed decisions incorrectly explaining current use, failed LLM health probes incorrectly marking the graph unavailable, malformed trace payloads, and malformed source payloads. Two additional HTTP cases confirm malformed adapter output returns a sanitized 502 `GRAPH_CONTRACT_ERROR` without leaking payload details.

Six additional frontend cases cover incomplete health responses, non-string edge endpoints, duplicate node and edge IDs, array properties, and dangling endpoints. The client rejects these before rendering the graph. Frontend lint, strict TypeScript checks, and the production build also pass. No visual components changed in this pass; browser checks were not repeated.

## Real integration preparation — October 16

Reviewed the graph ontology, pipeline, API and ingestion contracts against the implemented boundary. The public response and production code remain unchanged. [REAL_INTEGRATION_HANDOFF.md](REAL_INTEGRATION_HANDOFF.md) documents exact source/chunk ID mapping, provenance, signature uncertainties and branch/seed blockers.

Nine new offline tests exercise the configured real-mode factory with independently constructed graph and source-store doubles, never the development JSON: full records, canonical chunks (including two chunks from one ADR), missing-chunk support degradation, and six negative checks for the smoke-test oracle. The negative checks reject a proposed D-007, missing path, missing PAY-42 evidence, altered text, changed provenance, and development-fixture metadata. These are offline contract tests, not real FalkorDB results.

The strengthened opt-in smoke test checks live database/tool health, accepted D-007 and directed paths, and PAY-42, payment-perf-7, ADR-7 and 8fae2 evidence against an independently reviewed seeded-corpus export. It remains skipped because Antony's adapter, Alen's retrieval/seeded data and that export are unavailable locally. No real end-to-end success is claimed. Frontend files were unchanged in this pass; the 22 frontend tests and build checks above retain their previously recorded results.

## Browser verification — October 15

Used the available Playwright browser because the in-app Browser runtime reported no connected browser. The browser called the running Vite proxy and real FastAPI process in **explicit fixture mode**, with no intercepted responses or frontend mock server.

Confirmed:

- Welcome view, original logo and bundled fonts load.
- Enter submission of “Why does Payment Service use Redis?” performs `POST /api/query` and renders answer, six source records, and actual response graph.
- Source citation opens its excerpt and metadata; Escape closes it.
- Explore in graph and D-007 node inspection work.
- The accessible relationship table contains all 14 directed edges, including `Payment Service USES Redis` and `Checkout Service DEPENDS_ON Payment Service`.
- Unsupported Fraud Service / MongoDB question renders insufficient evidence and zero sources.
- Desktop layouts inspected at 1440×1000, 1440×900 and 1280×800; mobile at 390×844.
- Mobile navigation opens and closes with Escape. Inspector reflows below the main column; the relationship table scrolls horizontally inside its container.
- Fixed a mobile overflow caused by the decorative welcome wave; document scroll width now equals its client width.
- No browser console errors or warnings in the final checked workflow.

Local QA screenshots are in the ignored `.local/` directory, including `weave-welcome.png`, `weave-desktop-1280.png`, `weave-explorer-1280.png`, and mobile screenshots. They are development artifacts, not source fixtures.

## Remaining verification limits

- **Real FalkorDB success is blocked on database availability, Antony's trace tool and explicit decision-rationale provenance.** Alen's source retriever is integrated and verified offline. Use `WEAVE_RUN_REAL_SOURCES=1` for the independent ingestion/source smoke once a database is available; use `WEAVE_RUN_REAL_INTEGRATION=1` only after completing the trace integration, then repeat the browser acceptance question in real mode.
- Ollama `/api/tags` responded with an empty model list. No Qwen model was installed or downloaded. Actual LLM generation was not verified; the provider protocol, mocked success/validation and failure fallback were tested.
- A non-failing upstream Starlette warning reports that its current test client is deprecating `httpx` in favor of `httpx2`. The pinned development environment passes its tests.
- No deployment, authentication, production connectors, persistent conversations, expert finder, impact analysis, or freshness implementation is included.

## Visual comparison

The shell, sage sidebar selection, paper surfaces, original knot, editorial heading, four welcome cards, composer, source rail, graph tabs and colored nodes follow the supplied screenshots. The implementation uses explicit fixture labeling, generic provider-type icons, actual ontology directions, and a compact decision-focused layout. It does not copy mockup-only connection claims, user identity, unsupported feature actions, or invented ownership. Content scrolls vertically on shorter desktop viewports, and the inspector moves below the main area on narrow screens.
