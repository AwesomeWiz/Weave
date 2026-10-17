# Phase 2 Knowledge Freshness handoff

## Integration state

Implemented and verified offline on `integration/phase2`. Live FalkorDB acceptance is pending; Docker CLI is unavailable on this machine. No new OpenRouter network requests were made. Provider tests use mocked HTTP only. The earlier approval for three frozen Expert Finder requests does not authorize Freshness transmission.

History:

- Starting HEAD: `04629bf` (Expert Finder integration).
- Fetched `origin/feature/phase2-graph` at `dfff528021f20c068a8e14dbb8cebb504bb23253`; confirmed it includes `c0232a8`.
- Reviewed the delta: only `app/graph/freshness.py` and `tests/test_freshness_finder.py` were added.
- Merged with merge commit `0f12593`, without conflicts. Integration changes following that merge remain uncommitted for review.
- Preserved the pre-existing changes in `README.md`, `app/graph/experts.py`, and `tests/test_expert_finder.py` byte for byte, checked against pre-merge SHA256 hashes.
- Stash `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3` is intact. `main` remains at `b5824d92f1fdd52bbd4b9e8534d06fca99c55985`. Nothing was pushed or merged into `main`.

## Actual teammate interface and integration boundary

The implementation, rather than a hypothetical example, defines the nested contract:

```python
weave_graph.freshness.find_stale_knowledge(client: GraphClient, entity: str) -> dict
```

`weave_graph` continues to load the existing `app/graph` directory through its compatibility namespace. The merged test import uses that namespace to avoid the backend `app.graph` collision. No namespace redesign was needed.

`AntonyGateway.find_stale_knowledge(FreshnessInput)` creates and closes a client in its worker thread, calls the actual function, and validates its envelope. `FalkorGateway` applies the existing 15-second async timeout and sanitizes unavailable/invalid results. Source retrieval remains Alen's graph-backed `WeaveDataSourceRetriever`; ingestion and Cypher were not replaced or duplicated.

Real mode never substitutes files, fixtures, or an in-memory graph. Explicit fixture mode returns an empty, qualified Freshness result: no fabricated development review findings are configured. In-memory ingestion and query doubles exist only in tests and the ignored browser QA artifact.

## HTTP and data contracts

`POST /api/tools/freshness` accepts exactly:

```json
{"entity": "Payment Service"}
```

`entity` is a trimmed, nonblank string, at most 256 characters; unknown fields and non-string values are rejected. The tool supports exact canonical IDs or case-insensitive exact stored names/titles. It currently produces findings only for a uniquely resolved **Service**. Unknown, ambiguous, and non-Service targets remain qualified with no findings.

The dedicated response contains the unchanged grounded fields plus `data`:

```text
answer, support_status, tools_used, sources, graph, metadata, data
tools_used = ["find_stale_knowledge"]
data = {
  entity: GraphNode | null,
  review_candidates: FreshnessFinding[]
}
FreshnessFinding = {
  document: GraphNode,
  document_id: string,
  updated_at: string,
  affected_entity_id: string,
  document_path: PathStep[1..2],
  triggers: FreshnessTrigger[1..150],
  reason: string,
  source_ids: string[]
}
FreshnessTrigger = {
  type: "decision" | "commit" | "incident",
  id: string,
  timestamp: string,
  affected_entity_id: string,
  path: PathStep[1],
  source_ids: string[]
}
PathStep = {source: string, type: string, target: string}
```

`GraphNode`, `GraphEdge`, `Source`, and `Metadata` retain their existing schemas. The raw teammate envelope is `{data, sources, nodes, edges, warnings}`. Raw source references contain `id`, `chunk_id`, and optional `title`, `text`, `url`; source IDs added to findings/triggers are derived by the backend validator, never trusted from input. Document findings may cite only their own validated document record. Commit triggers may cite only their own validated commit record. Decision and Incident triggers have empty citation lists.

`POST /api/query` retains **exactly** `answer, support_status, tools_used, sources, graph, metadata`; it never adds `data`. Invalid input uses sanitized `INVALID_REQUEST` / 422, unavailable graph uses `GRAPH_UNAVAILABLE` / 503, invalid evidence uses `GRAPH_CONTRACT_ERROR` / 502. Existing health and exception sanitation behavior is unchanged.

## Graph, timestamp, and citation validation

The new independent validator checks returned proof, without discovering additional findings:

- Canonical IDs, stored identity/labels, duplicate conflicts, edge identities and existing endpoints.
- A resolved service matching the requested exact ID or name/title.
- The candidate Document and `updated_at` exactly matching their returned graph node.
- Either `Document -DESCRIBES-> Service`, or `Decision -DOCUMENTED_IN-> Document` together with the same `Decision -AFFECTS-> Service`. Both actual directed edges must be returned.
- Accepted Decision `-AFFECTS-> Service`, architecture-changing Commit `-CHANGES-> Service`, or Incident `-AFFECTS-> Service` for each claimed trigger. Wrong direction, absent edges, different services, duplicated triggers, and confident rewritten reasons fail closed.
- Raw timestamp fields `Document.updated_at`, `Decision.decided_at`, `Commit.timestamp`, and `Incident.started_at`. Claimed values must match stored fields; timezone-aware ISO timestamps compare by actual instant, and the event must be strictly later. Equal, earlier, missing, malformed, or timezone-free claimed event times cannot support a finding.
- Missing comparable timestamps elsewhere in the returned evidence, graph caps, source gaps and excerpt truncation qualify completeness. Findings remain review recommendations, never proof of factual incorrectness.
- Genuine `Chunk -FROM_DOCUMENT-> Document` and `Chunk -FROM_COMMIT-> Commit` paths. Reference title/text/URL, chunk parent/type/index, complete chunk membership, joined source text, entity association and retrieval metadata must match. Source timestamps must match both chunk metadata and the parent Document/Commit timestamp. Unsupported records are excluded from citations; conflicting source payloads fail closed.

The current ingestion schema provides no Decision or Incident chunks. Their actual graph paths and dates may support a structural review finding, explicitly labeled **graph-only change evidence**. No direct Chunk-to-Decision/Incident link, borrowed source, or invented excerpt is created.

One verified teammate bug was fixed without changing Cypher: a timezone-free document timestamp compared with a UTC event raised `TypeError: can't compare offset-naive and offset-aware datetimes`. The parser now reports timezone-free values as not comparable; it does not assume a timezone. The new integration tests cover this case.

Bounds: 50 candidate documents, 150 triggers per finding, 100 raw chunk references, 80 nodes, 200 edges, 200 raw warnings. Larger envelopes are rejected, not silently truncated into a complete result. Accepted source excerpts are limited to 1,600 characters with an explicit truncation warning and partial status. Existing orchestration/context/synthesis bounds remain unchanged.

## Routing, Context Builder V2, and hosted presentation

Freshness is the fourth registered `ToolSpec`. Examples with explicit service targets:

- `Is the Payment Service documentation outdated?`
- `Which documents about Payment Service need review?`
- `Are Payment Service docs up to date?`
- `Check freshness for service:payment-service`

`Is our architecture documentation still current?` and `Are the docs up to date?` lack an unambiguous service target and return a qualified routing limitation. No Payment Service ID is guessed from those questions. The endpoint permits other exact stored entity names; unsupported entity types receive the actual tool's warning.

An independently resolvable four-clause query is supported:

```text
Why does Payment Service use Redis?; What would be affected if Redis changed?;
Who knows Payment Service?; Which documents about Payment Service need review?
```

Each tool is validated before merging; siblings cannot repair missing Freshness paths or citations. Context Builder preserves canonical nodes, directed edge sequences, timestamps in properties and narratives, tool-local citations, completeness and warnings. The public response remains stable.

OpenRouter may select/order complete server-validated Freshness sections. It cannot generate new dates, findings, prose assertions, or citations. Both Freshness presentation variants retain the same cautious validated content. Existing output/schema/citation validation and deterministic fallback remain in force, including when a large four-tool narrative exceeds the existing answer bound. No bounds were weakened to force hosted success.

## React and observed offline result

The existing Knowledge Freshness card now calls the endpoint. Service controls, loading, retry, history, review recommendations, canonical IDs, timestamps, directed paths, graph-only labels, source citations and entity inspection reuse the existing design and responsive components. Combined answers continue through `/api/query` and its shared evidence graph/source navigation.

Using actual teammate functions over the explicitly ingested offline NovaPay database double:

- `doc:architecture-overview` is a **supported review recommendation**: updated `2026-05-01T12:00:00Z`, before INC-17 (`2026-05-10T11:00:00Z`), accepted D-007 (`2026-05-18T14:30:00Z`), and commit 8fae2 (`2026-05-19T10:15:00Z`).
- The document's DESCRIBES edge and the events' AFFECTS/CHANGES edges are actual returned relationships.
- Only `doc:architecture-overview` and `commit:8fae2` supply textual citations through retrieved chunks.
- ADR-7 and `doc:runbook-payment-latency` are not review candidates because their comparable update dates follow these events. This does not prove either document is current.
- The four-tool answer remains **partially_supported**, preserving existing Impact Analysis limitations. Freshness's independent status is supported for this bounded demonstration result.

These are offline results, not evidence of a working live FalkorDB deployment.

## Verification

Final checks:

- Full Python suite: **521 passed, 10 skipped**. The additional skipped test is the opt-in real Freshness acceptance test. One pre-existing Starlette/httpx deprecation warning remains.
- Frontend: **116 passed** across six test files.
- Scoped Ruff, ESLint, TypeScript and production build: passed.
- Browser QA at 1440×1000 and 390×844: review finding renders, source inspection works, no page overflow, no console errors. API responses were intercepted locally from the explicitly generated offline integration response, with external HTTP blocked. This was not live backend/database verification.
- QA artifacts are ignored under `.local/`: `freshness_offline_ui.json`, `freshness-desktop.png`, `freshness-mobile.png`.

Regressions cover API validation/error sanitation, actual gateway normalization, exact public query fields, four tools, both document association paths, reversed/missing paths, ambiguity and non-Service targets, timestamp conflicts and equal-offset instants, graph-only events, source/chunk conflicts and gaps, query/provenance caps, explicit truncation, malformed/oversize envelopes, fixture isolation, constrained hosted success/rejection/fallback, and React inspection/retry workflows.

Reproduce offline Python checks from the repository root:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-freshness
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests app/graph/freshness.py tests/test_freshness_finder.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

## Live acceptance and remaining Arnold QA

Live acceptance is explicitly unfinished. When a real seeded database is available:

1. Record the actual seed revision and verify the configured graph/source adapters target that graph. Use Alen's documented ingestion path; do not enable in-memory fallback or substitute browser/test artifacts.
2. Run `backend/tests/test_real_freshness_integration.py` with `WEAVE_RUN_REAL_FRESHNESS_INTEGRATION=1`, `PYTHONPATH=backend;.`, `WEAVE_GRAPH_FACTORY=app.antony:create_gateway`, real host/port/graph settings, and `WEAVE_LLM_PROVIDER=none`. It forces real graph/source modes, forbids fixture construction, and tests the dedicated endpoint plus all four tools.
3. Require actual graph/database health, the expected candidate and later event paths, accepted D-007, document/commit chunk provenance, canonical sources, and the unchanged query schema. Repeat the existing real Decision Trace, Impact Analysis and Expert Finder acceptance suites against the same seed.
4. Arnold should repeat browser acceptance with a real FastAPI/FalkorDB process, inspect both textual and graph-only evidence, test ambiguity/missing dates/source outages/caps, and check keyboard/mobile navigation and combined answers. Record runtime/seed versions and results here before declaring live integration complete.
5. Any live Freshness or four-tool OpenRouter smoke needs a **new frozen payload review and explicit approval**. The previous Expert Finder approval is consumed and cannot be reused.

Known scope limits: service-only exact resolution; bounded review detection rather than semantic contradiction analysis; no Decision/Incident textual provenance; no guarantee that a document is current; no full Change Intelligence. No ingestion schema changes, deployments, pushes or automatic main merge were performed.
