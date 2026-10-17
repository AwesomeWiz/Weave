# Phase 2 Impact Analysis integration handoff

Verified locally on October 17, 2026. The implementation is ready for Arnold's independent **offline QA**. Arnold's QA has not been performed. Successful live FalkorDB acceptance remains required; no live integration success is claimed.

## Branch and integration review

- Started on `main` at `b5824d9`, matching fetched `origin/main`. Phase 1 commit `495415e` is its ancestor.
- Preserved the only untracked file, an empty root npm lockfile, at `.local/phase2-preserved/package-lock.json`. Tracked worktree was clean before branch creation/integration.
- Fetched `origin/main` and `origin/feature/phase2-graph`; verified the latter includes `c2e9cbc`.
- Created `integration/phase2` from `origin/main`. Reviewed the full branch diff, including the preceding dataset expansion merge, then merged without conflicts at `31e47e7`. The local implementation commit follows that merge; use `git log -2 --oneline` for its exact hash.
- `main` and `origin/main` remain `b5824d92f1fdd52bbd4b9e8534d06fca99c55985`. Nothing was pushed or merged into main.
- Existing `stash@{0}` remains intact: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`, `On integration/phase1: WIP before Antony Decision Trace update`. No stash was applied or rewritten.

The reviewed teammate function is `weave_graph.impact.impact_analysis(client, entity_id, max_depth=2)`. It returns the common `{data, sources, nodes, edges, warnings}` envelope. The existing namespace bridge loads `app/graph/impact.py` without colliding with FastAPI's `app.graph` gateway. No graph-tool Cypher, ingestion logic, Phase 1 Context Builder, citation validator, client configuration, or namespace bridge was changed by this implementation.

Antony's implementation:

- Traverses **incoming** `DEPENDS_ON`: `A DEPENDS_ON B` makes A a potential dependent of B. Returned edges retain A → B direction.
- For technologies, starts with `Service USES Technology`, then reverse dependency traversal. This first USES hop counts toward depth.
- Bounds depth to 1–3; breadth-first visitation keeps one shortest path, suppresses duplicate findings and prevents cycles from counting the target as an impacted service. Cycle edges can remain visible as genuine graph relationships.
- Separates depth 1 direct findings from depth 2–3 indirect findings. The target service remains graph context, never its own downstream finding.
- Retrieves Team `OWNS` metadata, Issue/Incident `AFFECTS`, Incident `LED_TO` Issue, and Chunk `FROM_*` provenance for returned related sources.
- Currently retrieves issue/incident context, not arbitrary architecture documents or a textual proof of failure propagation. The expanded corpus does not automatically justify additional citations.

The only upstream-test edits correct imports to `weave_graph.*` and gate its five live cases with `WEAVE_RUN_REAL_IMPACT=1`. There were no merge conflicts or essential Cypher fixes.

## API contract

`POST /api/tools/impact-analysis`, JSON request:

```json
{"entity_id":"service:payment-service","max_depth":2}
```

Extra request fields are forbidden. `entity_id` matches `^(service|tech):[a-z0-9]+(?:-[a-z0-9]+)*$`, at most 128 characters. `max_depth` defaults to 2 and must be an integer 1–3; strings and booleans are rejected.

The successful response is the unchanged QueryResponse fields **plus `data`**:

```typescript
{
  answer: string;
  support_status: "supported" | "partially_supported" | "insufficient_evidence";
  tools_used: ["impact_analysis"];
  sources: Source[];                 // existing public Source schema
  graph: {nodes: GraphNode[]; edges: GraphEdge[]}; // existing public graph schema
  metadata: {
    latency_ms: number;
    graph_mode: "fixture" | "falkordb";
    generation: "deterministic";
    warnings: string[];
  };
  data: {
    entity: GraphNode | null;
    direct_impact: ImpactFinding[];
    indirect_impact: ImpactFinding[];
    related_issues: ImpactRelated[];
    related_incidents: ImpactRelated[];
  };
}

type ImpactFinding = {
  service_id: string;
  service: Record<string, unknown>;  // actual returned Service properties
  impact_depth: number;
  impact_type: "direct" | "indirect";
  path: string[];                    // traversal order from target to dependent
  path_edges: {source: string; type: "USES" | "DEPENDS_ON"; target: string}[];
  owners: {id: string; name: string}[];
  related_issues: ImpactRelated[];
  related_incidents: ImpactRelated[];
  source_ids: string[];              // only verified retrieved, service-linked evidence
};
type ImpactRelated = {
  id: string;
  title: string;
  properties: Record<string, unknown>;
  service_id: string;
};
```

Authoritative schemas: `backend/app/models.py`; running OpenAPI: `/docs` and `/openapi.json`.

`POST /api/query` retains **exactly** `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`; it does not acquire `data`. Both endpoints call the same validated impact workflow. Natural-language queries default to depth 2. The UI selects the dedicated endpoint for its bounded impact aliases, so it receives structured findings in one tool request, without a second traversal. Other clients can use `/api/query` normally.

Supported examples: “What would be affected if Payment Service changed?”, “What depends on Payment Service?”, “What services would be impacted if Redis were removed?”. Decision Trace's primary why question retains its existing route. Ambiguous targets, unknown named services, mixed rationale/impact/ownership questions, and questions about a target's **upstream dependencies** are not misrepresented as answered by this reverse-impact tool. This is a bounded deterministic router, not a full natural-language parser or multi-tool planner.

Errors retain the existing `{ok:false,error:{code,message}}` envelope: 422 `INVALID_REQUEST`, 503 `GRAPH_UNAVAILABLE`, 502 `GRAPH_CONTRACT_ERROR`, sanitized 500 `INTERNAL_ERROR`. Missing/unsupported graph entities return HTTP 200 with `data.entity=null`, empty evidence/findings, warnings and `insufficient_evidence`. A valid target with no returned dependents also reports insufficient evidence; absence from a bounded traversal is not proof of no impact.

## Grounding and mode isolation

The gateway calls the actual merged tool in a worker with the existing client configuration and a 15-second async timeout. Source IDs come only from its returned source references; Alen's existing backend retriever performs exact persisted graph retrieval. Real mode never opens the development examples, local corpus retriever or in-memory adapter. A legacy gateway missing `impact_analysis` returns `GRAPH_UNAVAILABLE` for that tool without changing Phase 1 factory validation.

The impact context validates every reported path hop against actual returned, correctly directed edges, path depth, entity types, node properties, ownership edges and issue/incident linkage. Identical records deduplicate; conflicting IDs, unlinked owners, invented/reversed paths and dangling edges fail closed. The envelope bounds are 60 nodes, 160 edges and 40 chunk references before source retrieval; the context allows at most 20 source records. Oversized results fail as a contract error rather than being silently truncated into misleading findings.

Related citations require the real returned Chunk → Issue/Message provenance path, matching canonical parent/type/index and stored chunk text against the retrieved aggregate. Source IDs, timestamps, chunk metadata and safe URLs are retained. `source_ids` per finding are computed from verified retrieved evidence plus actual related service paths; arbitrary upstream citation associations are not trusted. In the seeded Payment query, PAY-42 relates to **Payment Service**. It is shown as historical context, not attached to Checkout/Order as their supporting source. Adding an actual Issue AFFECTS Checkout relationship in an explicit test graph correctly enables that association.

Nonempty structural findings are deliberately `partially_supported`, even when related historical excerpts exist: those excerpts do not establish failure propagation. No findings/missing entity is `insufficient_evidence`. Phase 1's accepted-decision support semantics and citation validation are unchanged. Impact generation is deterministic, with citations only on retrieved historical excerpts and explicit structural limitations; it does not send raw tool dictionaries through the decision-rationale LLM prompt or use LLM generation to fill gaps.

Source outages preserve the structural graph and partial findings with a warning. Graph failures return a sanitized error without fallback evidence. Genuine empty retrieval remains empty.

Fixture mode is selected only with `WEAVE_GRAPH_MODE=fixture`. Its precomputed examples reuse the original labeled development Payment/Redis/Checkout nodes/edges and contain **no textual impact sources**. They do not represent the expanded real corpus: the fixture has no Order node or owner metadata. Unlisted targets return an honest missing-example result. Real mode never substitutes these examples.

## UI and changed files

| Files | Purpose |
| --- | --- |
| `backend/app/models.py` | Typed bounded impact request, tool envelope, findings and dedicated response. Existing QueryResponse fields unchanged. |
| `backend/app/antony.py`, `graph.py` | Actual `weave_graph.impact` call, envelope normalization, timeout/error boundary, explicit fixture examples. |
| `backend/app/impact.py` | Validate returned paths/provenance; prepare cautious deterministic impact context. No graph discovery or Cypher. |
| `backend/app/router.py`, `main.py` | Single-tool routing and dedicated endpoint; share orchestration with `/api/query`. |
| `backend/app/fixtures/impact.development.json` | Clearly labeled precomputed synthetic development input only. |
| `backend/tests/test_impact_integration.py`, `test_real_impact.py` | Actual merged functions with offline database doubles; opt-in read-only real HTTP acceptance. |
| `tests/test_impact_analysis.py` | Compatibility imports and explicit live-test gate only. |
| `frontend/src/api.ts`, `types.ts`, `impact.ts` | Typed dedicated client, strict response/path validation and bounded UI endpoint selection. |
| `frontend/src/components/ImpactResults.tsx`, `App.tsx`, `styles/globals.css` | Functional card, target/depth controls, separate direct/downstream results, IDs/paths, owners, sources and missing-evidence states. Existing styling and inspectors reused. |
| `frontend/src/components/EvidenceGraph.tsx` | Highlight returned path edges without altering IDs/directions or re-running layout for selection. |
| `frontend/src/App.test.tsx`, `impact.test.ts`, `test/impactFixture.ts` | Interaction, error/retry, routing, response validation and explicit test-only input. |
| `README.md`, `docs/README.md`, this handoff | Current configuration, API, verification and QA handoff. |

Chat graph evidence remains bounded to the question. Existing graph workspace/navigation behavior is retained; no organization-wide graph endpoint or unbounded database browser was introduced. Expert Finder, Knowledge Freshness and Change Intelligence remain unimplemented in the product despite upstream data/tests supporting their future work.

## Configuration and commands

Real mode, restart FastAPI after configuration changes:

```dotenv
WEAVE_GRAPH_MODE=falkordb
WEAVE_GRAPH_FACTORY=app.antony:create_gateway
WEAVE_SOURCE_BACKEND=weave_data
WEAVE_GRAPH_NAME=novapay
WEAVE_FALKORDB_HOST=localhost
WEAVE_FALKORDB_PORT=6379
```

Existing optional auth/TLS settings remain in `.env`; no credentials are hardcoded. For ingestion use Alen's documented real CLI against the same graph; this implementation does not seed or reset a shared database automatically. The Phase 2 expanded corpus must be seeded for Checkout/Order expectations. Use `WEAVE_GRAPH_MODE=fixture` only for explicit development demonstrations.

From the repository root, PowerShell:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
.\.venv\Scripts\python.exe -m pytest backend\tests tests app\graph -q --basetemp=.local/pytest-phase2-handoff
.\.venv\Scripts\python.exe -m ruff check --config backend\pyproject.toml backend app\graph weave_graph tests\test_decision_trace.py tests\test_impact_analysis.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
Remove-Item Env:WEAVE_SOURCE_BACKEND
```

The explicit delegate environment isolates legacy offline factory doubles from this workstation's `.env` selection of `weave_data`. Tests specifically exercising real graph-backed retrieval explicitly select `weave_data` themselves. The initial baseline with local `.env` contamination had nine failures from unintended database attempts; selecting the intended offline backend resolved them without changing runtime integration behavior.

| Check | Final result |
| --- | --- |
| Full Python tests, including merged graph/data tests | **270 passed, 0 failed, 8 skipped**, one existing Starlette deprecation warning |
| Scoped Ruff command above | Passed |
| Frontend Vitest | **64 passed, 0 failed, 0 skipped**, four test files |
| ESLint / TypeScript / Vite production build | All passed |
| Full Ruff over `backend app/graph weave_graph tests weave_data` | **76 F401 findings** in seven unchanged teammate files; not a passing repository-wide lint result |
| Configured bounded FalkorDB probe | Unavailable; successful live acceptance not run |

All 76 broad lint findings were verified against merged HEAD in files untouched by this implementation: `tests/test_freshness.py` (1), `test_ingestion.py` (12), `test_validation_negative.py` (9), `weave_data/__init__.py` (32), `loader.py` (11), `relationships.py` (10), `validation.py` (1). No unrelated import cleanup was applied.

Browser verification used an actual local Vite process and FastAPI in explicit fixture mode, with no intercepted responses. Existing ports 8000/5173 were occupied, so owned QA processes used backend 8012/frontend 5174 with matching CORS and `VITE_API_URL`; those temporary settings were process-local. Checked card submission, changing target, Redis depth 1/direct and depth 2/downstream sections, correct stored edge directions, path stroke highlighting, entity inspector, desktop 1440×1000 and mobile 390×844 with no horizontal overflow. Returning to the primary why question produced **supported**, six fixture sources and working citations, with impact controls removed. No browser errors or warnings. Ignored screenshots: `.local/phase2-impact-desktop.png`, `.local/phase2-impact-mobile.png`.

## Live acceptance and QA blockers

The configured FalkorDB read-only health probe returned false and Docker was not found on PATH. No seed, graph replacement or database installation was attempted. Eight live cases remain skipped: the two existing Phase 1 source/trace acceptances, Antony's five live impact cases, and the new real HTTP impact acceptance.

Once an actual expanded `novapay` graph is available, configure the host/auth/graph above and run:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_RUN_REAL_IMPACT = '1'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_real_impact.py tests\test_impact_analysis.py -v --basetemp=.local/pytest-phase2-live
Remove-Item Env:WEAVE_RUN_REAL_IMPACT
```

Enabling the flag makes unavailable prerequisites **fail**, not silently skip or load local evidence. The new smoke is read-only: checks actual database/tool health, calls the HTTP adapter, verifies Payment → traversal Checkout → Order while checking original Checkout DEPENDS_ON Payment and Order DEPENDS_ON Checkout edges, validates real PAY-42 text against independent checked-in corpus chunks and preserved chunk provenance, verifies depth 1 and Redis depth 3. It forbids fixture, local-source and memory fallback. It does not ingest or delete anything. Re-run the existing opt-in Phase 1 source and manifest-based primary trace acceptances separately as documented in `REAL_INTEGRATION_HANDOFF.md`.

Ready for Arnold to independently review and run offline tests and the UI; **not yet verified for live FalkorDB execution**. Also review the documented repository-wide lint debt. Remaining tool limitations are bounded alias resolution, one shortest path per service, team-only owner extraction in the current graph query, no textual proof of propagation, result-size rejection for high fan-out graphs, and async timeout cancellation not terminating an already running worker thread (individual graph queries retain existing socket/query timeouts). No multi-tool planning or unrelated Phase 2 feature was added.
