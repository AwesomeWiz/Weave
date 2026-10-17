# Weave Phase 2 — Independent QA, Real FalkorDB Integration & Sign-Off Report

**Date:** October 18, 2026  
**Auditor / Integration Engineer:** Independent QA Agent (Direct Observation)  
**Branch Tested:** `integration/phase2`  
**Exact Base Commit Tested:** `14ac3e63b5bc026a4306b0631b838debb4942805` (`feat: integrate graph-backed Knowledge Freshness`)  
**Recommendation:** **READY (PASS)** (with documented compatibility fixes applied and verified)

---

## 1. Executive Summary

Phase 2 introduces three new company brain capabilities alongside Phase 1's Decision Trace:
1. **Impact Analysis** (dependency propagation, direct vs. indirect service blast radius)
2. **Expert Finder** (evidence-backed knowledge & contributor ranking from graph relationships)
3. **Knowledge Freshness** (timestamp-anchored staleness detection based on later-occurring architectural changes)
4. **Deterministic Multi-Tool Routing & Context Builder V2** (joint query planning, safe provenance merging, and support-status semantics)

All capabilities were independently audited against a **live, seeded FalkorDB container** (`falkordb/falkordb:latest`) running the expanded NovaPay dataset. No mock gateways, fixture fallbacks, or in-memory persistence adapters were accepted as proof of live acceptance.

### Verification Highlights:
- **Live FalkorDB Seed & Idempotency:** The expanded NovaPay corpus (`dc13e5030d1b8170d0a4ad7cc3816bfd1f9ea98c`) was ingested twice. Entity count remained strictly **20**, chunk count strictly **6**, and relationships strictly **44**. Duplicate canonical IDs: **0**.
- **All 4 Capabilities Verified Against Live Graph:**
  - **Decision Trace:** `test_seeded_falkordb_primary_question` passed against live FalkorDB (`support_status: supported`, 4 canonical sources, 12 nodes, 12 edges).
  - **Impact Analysis:** `test_real_impact_http_paths_provenance_and_depth` passed (`service:payment-service` directly impacts `service:checkout-service` at depth 1, indirectly impacts `service:order-service` at depth 2; `tech:redis` propagates to depths 2 and 3).
  - **Expert Finder:** `test_real_expert_and_three_tool_application` passed (`Who knows Payment Service?` ranks Ravi Nair and Alice Menon with team ownership; `Who approved D-007?` uniquely resolves `decision:D-007` and identifies Alice Menon with `decision_approval`).
  - **Knowledge Freshness:** `test_real_freshness_and_four_tool_application` passed (`doc:architecture-overview` flagged as review candidate due to later events INC-17, accepted D-007, and commit 8fae2; ADR-7 and runbook correctly excluded).
- **Combined Multi-Tool Query:** Four-tool query executed against live FalkorDB, returned `partially_supported`, unioning 5 sources, 23 nodes, and 37 directed edges without fabricating missing facts.
- **Support-Status Semantics:** Verified `supported`, `partially_supported`, and `insufficient_evidence` (unsupported query: *"Why did NovaPay choose MongoDB for the fraud service?"* returned `insufficient_evidence` with 0 sources and honest feedback).
- **React Browser Acceptance:** End-to-end browser subagent session executed on `http://127.0.0.1:5173/` proxying to real FastAPI (`WEAVE_GRAPH_MODE=falkordb`). Desktop (1440×900) and mobile (390×844) layouts verified; citation drawer and graph inspector confirmed agreeing with live API.
- **Regression & Code Quality:**
  - Python tests: **523 passed** (518 offline unit/integration + 5 opt-in live FalkorDB acceptance suites).
  - Ruff: Scoped checks passed with **0 errors**.
  - Vitest: **116 passed** across 6 test files (100%).
  - Frontend ESLint & TypeScript: **0 errors**.
  - Vite production bundle: Clean build in 3.51s.

---

## 2. Environment and Runtime Versions

| Component | Version / Identifier |
|:---|:---|
| **OS** | Windows 11 (PowerShell 5.1 / 7) |
| **Python** | 3.13.1 (venv: `.venv`) |
| **Node.js** | v24.13.0 |
| **npm** | 11.6.2 |
| **Docker** | 29.8.2, build 7fc2dff |
| **Docker Compose** | v5.6.0 |
| **FalkorDB Container** | `weave-falkordb` |
| **FalkorDB Image** | `falkordb/falkordb:latest` (`sha256:b0bdcac2cbaff989e77cb0610439b7a9289e86de033ccbbd4368b66fb680ae7a`) |
| **FalkorDB Port** | `127.0.0.1:6379` |
| **FastAPI Backend** | FastAPI 0.115.0+ running via Uvicorn on `127.0.0.1:8000` |
| **Frontend Server** | Vite 6.4.4 running on `127.0.0.1:5173` |

---

## 3. Dataset Ingestion and Graph Shape Audit

### Canonical Dataset Revision
- **Commit:** `dc13e5030d1b8170d0a4ad7cc3816bfd1f9ea98c` (*"feat: expand Phase 2 dataset for graph analysis"*)
- **Graph Name:** `novapay`
- **Ingestion Adapter:** `weave_data.graph_adapter.FalkorDBGraphAdapter`

### File Integrity (SHA256)
- `aliases.json`: `1E008CFB32CF6E0BEC2913D8CF6675A95CE88...`
- `decisions.json`: `0085F7750E2797B7C1C15C9ADCDACDDBA791D...`
- `incidents.json`: `5981D3D6785807BA47430C494891347DDBA70...`
- `people.json`: `F749B1FA4BBFD8B552F02C8EA3892D8C5D0D5...`
- `services.json`: `7E036FEAAEBBECAFB8E2F516E25BEF5CC14C4...`
- `teams.json`: `842F6E4268515C579AFEE7BE792C9A73C3DE2...`
- `technologies.json`: `0176C7F1EFCECE9017EF2BF88DFE24B11BCA4...`
- `docs/ADR-7.md`: `5C17BAD40663530A437360D055C54EA9D5613...`
- `docs/architecture-overview.md`: `BA86A66CCF5B80B7A410D90E3AA46C7033B4E...`
- `docs/runbook-payment-latency.md`: `FA7213C33CF923E108727805FB5FB43610BCD...`
- `github/commits.json`: `3638966B03F6CD0265F041AC3F9DB8EA9013C...`
- `github/repositories.json`: `5A76A2A39A237B58EDA3438D81F21EEA8A3BE...`
- `jira/issues.json`: `90A89422F6174472DE0D7652F7730D0EC6014...`
- `slack/messages.json`: `F8010EB8A93A52E5AE7BF66F5DEC06429A7B0...`

### Ingestion Output & Idempotency Verification
Command:
```powershell
$env:PYTHONPATH = "backend;."
python -m weave_data.ingest --host 127.0.0.1 --port 6379 --graph novapay --json
```

**Run 1 Output:**
```json
{
  "status": "success",
  "records_processed": 20,
  "nodes_created_or_updated": 20,
  "relationships_processed": 44,
  "chunks_created_or_updated": 6,
  "errors": [],
  "persistence": "FalkorDBGraphAdapter"
}
```

**Run 2 (Idempotency Check) Output:**
```json
{
  "status": "success",
  "records_processed": 20,
  "nodes_created_or_updated": 20,
  "relationships_processed": 44,
  "chunks_created_or_updated": 6,
  "errors": [],
  "persistence": "FalkorDBGraphAdapter"
}
```

### FalkorDB Live Topology Breakdown
- **Total Graph Nodes:** 26 (20 Entity nodes + 6 Text Chunk nodes)
  - `Person`: 4 (`person:alice`, `person:ravi`, `person:maya`, `person:neeraj`)
  - `Service`: 3 (`service:payment-service`, `service:checkout-service`, `service:order-service`)
  - `Document`: 3 (`doc:ADR-7`, `doc:architecture-overview`, `doc:runbook-payment-latency`)
  - `Team`: 2 (`team:payments`, `team:platform`)
  - `Technology`: 2 (`tech:redis`, `tech:postgresql`)
  - `Repository`: 1 (`repo:novapay/payments-api`)
  - `Message`: 1 (`message:payment-perf-7`)
  - `Decision`: 1 (`decision:D-007`)
  - `Issue`: 1 (`issue:PAY-42`)
  - `Incident`: 1 (`incident:INC-17`)
  - `Commit`: 1 (`commit:8fae2`)
  - `Chunk`: 6 (ADR-7, architecture-overview, runbook, commit:8fae2, issue:PAY-42, message:payment-perf-7)
- **Total Relationships:** 44
  - `MEMBER_OF`: 4
  - `DESCRIBES`: 3
  - `FROM_DOCUMENT`: 3
  - `USES`: 3
  - `WROTE`: 3
  - `AFFECTS`: 3
  - `PARTICIPATED_IN`: 3
  - `OWNS`: 3
  - `DEPENDS_ON`: 2
  - `SUPPORTED_BY`: 2
  - `CHANGES`: 1
  - `IMPLEMENTS_DECISION`: 1
  - `IMPLEMENTED_BY`: 1
  - `LED_TO`: 1
  - `FROM_MESSAGE`: 1
  - `FROM_COMMIT`: 1
  - `ADDRESSES`: 1
  - `ASSIGNED_TO`: 1
  - `APPROVED`: 1
  - `DOCUMENTED_IN`: 1
  - `INTRODUCES`: 1
  - `BELONGS_TO`: 1
  - `IMPLEMENTS`: 1
  - `FROM_ISSUE`: 1
  - `AUTHORED`: 1
- **Duplicates Detected:** 0 (Cypher verification: `MATCH (n) WITH n.id AS id, count(n) AS cnt WHERE cnt > 1 RETURN id, cnt` returned `[]`).

---

## 4. Live Capability Test Matrix

All capabilities were exercised directly against the live FalkorDB database.

| Capability | Test File / Command | Live DB Acceptance | Status | Direct Observations & Results |
|:---|:---|:---:|:---:|:---|
| **Decision Trace** | `backend/tests/test_real_integration.py` | Live `novapay` | **PASS** | Verified primary question (*"Why does Payment Service use Redis?"*). Returns `decision:D-007` (accepted), `incident:INC-17`, `issue:PAY-42`, `message:payment-perf-7`, `doc:ADR-7`, `commit:8fae2`. Support status: `supported`. 4 verified sources with matching excerpts. |
| **Impact Analysis** | `backend/tests/test_real_impact.py` | Live `novapay` | **PASS** | Tested `service:payment-service` at depth 1 and 2. Direct impact: `service:checkout-service` (`DEPENDS_ON`); indirect impact: `service:order-service` via path `payment-service -> checkout-service -> order-service`. Tested `tech:redis` with indirect impacts at depths 2 and 3. Shorter depth (1) omits indirect services. Partial support returned honestly. |
| **Expert Finder** | `backend/tests/test_real_expert_integration.py` | Live `novapay` | **PASS** | Evaluated *"Who knows Payment Service?"*: ranks Ravi Nair (score 16, team ownership) and Alice Menon (score 14, team ownership), Maya Joseph (score 5). Evaluated *"Who approved D-007?"*: resolves topic `decision:D-007` and identifies Alice Menon with `decision_approval`. |
| **Knowledge Freshness** | `backend/tests/test_real_freshness_integration.py` | Live `novapay` | **PASS** | Evaluated `service:payment-service`: `doc:architecture-overview` (updated `2026-05-01T12:00:00Z`) correctly flagged as review candidate due to later events (INC-17 `2026-05-10`, D-007 `2026-05-18`, commit 8fae2 `2026-05-19`). ADR-7 (`2026-05-20`) and runbook (`2026-05-22`) excluded as updated after events. |
| **Four-Tool Combined** | `POST /api/query` (4-clause query) | Live `novapay` | **PASS** | Executed 4-clause query across Decision Trace, Impact Analysis, Expert Finder, and Knowledge Freshness. Returns `partially_supported` (reflecting impact analysis graph limitations), deduplicates 5 sources, 23 nodes, 37 edges. |

---

## 5. API Endpoint Acceptance Matrix

Direct observations from live HTTP requests against Uvicorn (`http://127.0.0.1:8000`) in real FalkorDB mode:

| Method & Path | Scenario / Input | Status | Support Status | Tools Used | Sources | Graph Nodes/Edges | Observations |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `GET /api/health` | Service health probe | **200** | — | — | — | — | `falkordb: connected`, `graph_tool: available`, `graph: novapay`, `graph_mode: falkordb` |
| `POST /api/query` | *"Why does Payment Service use Redis?"* | **200** | `supported` | `["trace_decision"]` | 4 | 12 nodes, 12 edges | Accurate grounded answer detailing INC-17, PAY-42, ADR-7, commit 8fae2 |
| `POST /api/query` | 4-clause combined query | **200** | `partially_supported` | 4 tools | 5 | 23 nodes, 37 edges | Preserves tool-local provenance; no facts fabricated to bridge gaps |
| `POST /api/query` | 3-clause showcase query | **200** | `partially_supported` | 3 tools | 4 | 19 nodes, 29 edges | Decision trace + impact on Redis + expert finder (`Who can explain the Redis decision?`) |
| `POST /api/query` | *"Why did NovaPay choose MongoDB for the fraud service?"* | **200** | `insufficient_evidence` | `[]` | 0 | 0 / 0 | Honestly reports missing evidence; refuses to fabricate history |
| `POST /api/query` | Empty body `{}` / invalid schema | **422** | — | — | — | — | Sanitized `INVALID_REQUEST` validation error |
| `POST /api/tools/impact-analysis` | `{"entity_id": "service:payment-service", "max_depth": 2}` | **200** | `partially_supported` | `["impact_analysis"]` | 1 | 3 nodes, 2 edges | Direct: checkout-service; Indirect: order-service |
| `POST /api/tools/expert-finder` | `{"query": "Who knows Payment Service?", "limit": 5}` | **200** | `supported` | `["find_expert"]` | 3 | 11 nodes, 15 edges | Topic: payment-service; Experts: Ravi (16), Alice (14), Maya (5) |
| `POST /api/tools/expert-finder` | `{"query": "Who approved D-007?", "limit": 5}` | **200** | `supported` | `["find_expert"]` | 3 | 7 nodes, 8 edges | Topic: decision:D-007; Expert: Alice (approval: decision:D-007) |
| `POST /api/tools/freshness` | `{"entity": "Payment Service"}` | **200** | `supported` | `["find_stale_knowledge"]` | 2 | 8 nodes, 7 edges | Review candidate: architecture-overview with 3 triggers |
| `POST /api/tools/freshness` | `{"entity": "unknown-service"}` | **200** | `insufficient_evidence` | `["find_stale_knowledge"]` | 0 | 0 / 0 | Qualified warning: *"No graph entity found for unknown-service."* |
| `POST /api/tools/freshness` | `{"entity": "Redis"}` | **200** | `insufficient_evidence` | `["find_stale_knowledge"]` | 0 | 0 / 0 | Qualified warning: *"Knowledge freshness currently supports Service entities only."* |

---

## 6. Context Builder V2 and Evidence Provenance

Context Builder V2 was validated across both unit tests and live multi-tool runs:
- **Deduplication:** When merging results from multiple tools (e.g., Decision Trace and Freshness both citing `commit:8fae2` and `doc:architecture-overview`), sources and graph nodes are deduplicated while preserving all incoming and outgoing directed edges.
- **Edge Direction & Endpoints:** All edge endpoints exist within the returned graph. For example:
  - `(service:order-service, DEPENDS_ON, service:checkout-service)`
  - `(service:checkout-service, DEPENDS_ON, service:payment-service)`
  - `(decision:D-007, AFFECTS, service:payment-service)`
  - `(chunk:commit:8fae2:0, FROM_COMMIT, commit:8fae2)`
- **Chunk-to-Source Provenance:**
  - `chunk:issue:PAY-42:0` -> `issue:PAY-42`
  - `chunk:message:payment-perf-7:0` -> `message:payment-perf-7`
  - `chunk:commit:8fae2:0` -> `commit:8fae2`
  - `chunk:doc:ADR-7:0` -> `doc:ADR-7`
  - `chunk:doc:architecture-overview:0` -> `doc:architecture-overview`
- **Graph-Only Change Evidence:** Incident `incident:INC-17` and Decision `decision:D-007` do not possess text chunks in the ingestion schema; their graph paths and timestamps participate in freshness review triggers without fabricating chunk citations.

---

## 7. Knowledge Freshness Timestamp Verification

- **Candidate Document:** `doc:architecture-overview`
  - Canonical Title: `NovaPay Core Architecture Overview`
  - Document Updated At: `2026-05-01T12:00:00Z`
  - Relationship to Service: `(doc:architecture-overview)-[:DESCRIBES]->(service:payment-service)`
- **Later Events Triggering Review:**
  1. Incident: `incident:INC-17` (`started_at: 2026-05-10T11:00:00Z` > `2026-05-01T12:00:00Z`)
  2. Decision: `decision:D-007` (`decided_at: 2026-05-18T14:30:00Z` > `2026-05-01T12:00:00Z`)
  3. Commit: `commit:8fae2` (`timestamp: 2026-05-19T10:15:00Z` > `2026-05-01T12:00:00Z`)
- **Non-Stale Documents Verified:**
  - `doc:ADR-7`: `updated_at: 2026-05-20T10:00:00Z` (after all 3 events) -> **Not a candidate**
  - `doc:runbook-payment-latency`: `updated_at: 2026-05-22T10:00:00Z` (after all 3 events) -> **Not a candidate**

---

## 8. React Browser Acceptance Results

Conducted via autonomous browser subagent on `http://127.0.0.1:5173/` proxying to real Uvicorn backend with FalkorDB active.

- **System Status Indicator:** Verified green pill displaying `falkordb` connected in real mode.
- **Capability Cards:** All four cards (Decision Trace, Impact Analysis, Expert Finder, Knowledge Freshness) rendered cleanly with interactive examples.
- **Interactive Queries Tested:**
  1. *Decision Trace:* Renders answer, 4 sources, and knowledge graph canvas. Clicking citation row opens the slide-out Citation Inspector displaying full excerpt and source metadata.
  2. *Impact Analysis:* Renders direct impact (`Checkout Service`, depth 1) and indirect impact (`Order Service`, depth 2).
  3. *Expert Finder:* Renders ranked cards (Ravi Nair score 16, Alice Menon score 14) with evidence-backed breakdown tags and team ownership classification.
  4. *Knowledge Freshness:* Renders `doc:architecture-overview` as review candidate with exact `2026-05-01` timestamp and later triggers list.
  5. *Combined 4-Tool Query:* Renders merged answer with `partially_supported` badge, citations, and 23-node graph.
  6. *Unsupported Query:* Returns `Insufficient Evidence` status, 0 citations, and clear guidance without UI crashing or hallucinations.
- **Mobile Responsive Layout (390×844):** UI reflows cleanly, sidebar collapses into hamburger menu, cards stack vertically, citations and graph tabs remain fully operable without horizontal viewport overflow.
- **Evidence Artifacts:**
  - Full browser session video: `phase2_react_acceptance_1792263864191.webp`
  - Screenshots captured:
    - Homepage: `initial_home_1792263875803.png`
    - Decision Trace: `decision_trace_result_1792263892076.png`
    - Citation Drawer: `citation_drawer_1792263905797.png`
    - Impact Analysis: `impact_analysis_result_1792263961594.png`
    - Expert Finder: `expert_finder_result_1792264020111.png`
    - Knowledge Freshness: `knowledge_freshness_result_1792264091120.png`
    - Combined Query: `combined_query_result_1792264155539.png`
    - Unsupported Query: `unsupported_query_result_1792264220329.png`
    - Mobile Viewport: `mobile_layout_1792264245400.png`

---

## 9. Regression and Quality Audit Summary

### Python Test Suite
- **Offline Suite:** `pytest backend/tests tests app/graph -q`
  - **518 passed, 10 skipped, 1 warning** (Starlette httpx deprecation) in 7.61s.
- **Live FalkorDB Acceptance Suite:**
  - `backend/tests/test_real_integration.py`: **PASSED** (8.93s)
  - `backend/tests/test_real_sources.py`: **PASSED** (4.63s)
  - `backend/tests/test_real_impact.py`: **PASSED** (16.86s)
  - `backend/tests/test_real_expert_integration.py`: **PASSED** (24.98s)
  - `backend/tests/test_real_freshness_integration.py`: **PASSED** (18.89s)
  - **Combined real suite:** 5 passed in 71.76s.
- **Ruff Linter:** Scoped check on backend and graph modules: **0 errors**.

### Frontend Quality Suite
- **Vitest:** `npm.cmd --prefix frontend test`
  - **116 passed across 6 test files** in 12.16s.
- **ESLint:** `npm.cmd --prefix frontend run lint`: **0 errors**.
- **TypeScript:** `npm.cmd --prefix frontend run typecheck`: **0 errors**.
- **Vite Production Build:** `npm.cmd --prefix frontend run build`: **Built cleanly in 3.51s** (`dist/` generated).

---

## 10. Defects Identified and Resolved

### DEFECT 1: Missing Topic Resolution for Explicit Decision Keys & Technology Decisions in `app/graph/experts.py`
- **TITLE:** Topic resolution failed for explicit decision queries (`Who approved D-007?` and `Who can explain the Redis decision?`)
- **SEVERITY:** Medium (Caused failure in `test_real_expert_integration.py` against live FalkorDB)
- **BLOCKER:** YES (prior to fix)
- **ENVIRONMENT AND COMMIT:** Commit `14ac3e63b5bc026a4306b0631b838debb4942805`, Windows 11, Python 3.13.1, FalkorDB latest
- **STEPS TO REPRODUCE:**
  1. Ingest expanded NovaPay dataset into FalkorDB.
  2. Run `$env:WEAVE_RUN_REAL_EXPERT_INTEGRATION = '1'; pytest backend/tests/test_real_expert_integration.py`
- **EXPECTED:** `POST /api/tools/expert-finder` resolves `decision:D-007` as the matched topic.
- **ACTUAL:** `data.topics` returned `[]`, failing the assertion `assert [t["id"] for t in data["topics"]] == ["decision:D-007"]`.
- **ROOT CAUSE:** Although documented by Abhishikth in `PHASE2_EXPERT_FINDER_HANDOFF.md` line 11 as a required compatibility fix, the changes were omitted from commit `04629bf` and not present in `app/graph/experts.py`.
- **LIKELY OWNER:** Integration/backend owner (`app/graph/experts.py`)
- **FIX IMPLEMENTED:**
  1. Allow terms matching `d-\d+` to participate as canonical decision lookup candidates (`f"decision:{term.upper()}"`).
  2. Allow `Decision` nodes whose title contains a requested technology alias to resolve when `decision` is in query terms.
- **REGRESSION TEST:** `test_real_expert_and_three_tool_application` passed in 24.98s; all 59 tests in `test_expert_integration.py` passed.

---

### DEFECT 2: Namespace Collision on `from app.graph.experts import find_expert` in `tests/test_expert_finder.py`
- **TITLE:** ModuleNotFoundError when importing `test_expert_finder` under `PYTHONPATH="backend;."`
- **SEVERITY:** Low / Developer Tooling
- **BLOCKER:** NO (did not affect live runtime, only test collection when `backend` preceded root in path)
- **ENVIRONMENT AND COMMIT:** Commit `14ac3e63b5bc026a4306b0631b838debb4942805`
- **STEPS TO REPRODUCE:**
  `$env:PYTHONPATH="backend;."; pytest backend/tests/test_expert_integration.py`
- **EXPECTED:** `tests/test_expert_finder.py` imports from `weave_graph.experts` (as documented in `PHASE2_EXPERT_FINDER_HANDOFF.md` line 11).
- **ACTUAL:** Imported from `app.graph.experts`, which collided with single file module `backend/app/graph.py`.
- **LIKELY OWNER:** Integration QA owner
- **FIX IMPLEMENTED:** Updated line 6 in `tests/test_expert_finder.py` to `from weave_graph.experts import find_expert`.
- **REGRESSION TEST:** `pytest backend/tests/test_expert_integration.py` collected and passed all 59 tests.

---

## 11. Reproduction Commands

To reproduce the complete verification suite from repository root:

```powershell
# 1. Start Docker FalkorDB and verify reachability
docker compose up -d falkordb
python -c "import redis; r = redis.Redis('127.0.0.1', 6379); print('PONG:', r.ping())"

# 2. Seed expanded NovaPay dataset (idempotent run)
$env:PYTHONPATH = "backend;."
python -m weave_data.ingest --host 127.0.0.1 --port 6379 --graph novapay --json

# 3. Run all opt-in live FalkorDB acceptance suites
$env:PYTHONUTF8 = "1"
$env:WEAVE_RUN_REAL_INTEGRATION = "1"
$env:WEAVE_REAL_EVIDENCE_MANIFEST = "tests/novapay_evidence_manifest.json"
$env:WEAVE_RUN_REAL_SOURCES = "1"
$env:WEAVE_RUN_REAL_IMPACT = "1"
$env:WEAVE_RUN_REAL_EXPERT_INTEGRATION = "1"
$env:WEAVE_RUN_REAL_FRESHNESS_INTEGRATION = "1"
pytest backend/tests/test_real_integration.py backend/tests/test_real_sources.py backend/tests/test_real_impact.py backend/tests/test_real_expert_integration.py backend/tests/test_real_freshness_integration.py -v

# 4. Run offline Python test suite & linters
$env:WEAVE_LLM_PROVIDER = "none"
$env:WEAVE_SOURCE_BACKEND = "delegate"
pytest backend/tests tests app/graph -q
ruff check backend/app backend/tests app/graph tests/test_freshness_finder.py tests/test_expert_finder.py

# 5. Run Frontend test suite & production build
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

---

## 12. Final Sign-Off Recommendation

### Verdict: **READY (PASS)**

All final sign-off criteria have been verified directly:
1. Exact tested commit recorded (`14ac3e63b5bc026a4306b0631b838debb4942805`).
2. Expanded NovaPay dataset seeded and verified (`dc13e5030d1b8170d0a4ad7cc3816bfd1f9ea98c`, 20 entity nodes, 6 chunk nodes, 44 relationships, idempotency confirmed).
3. All four capabilities passed live FalkorDB acceptance tests without fixtures or in-memory doubles.
4. Combined multi-tool query passed against real graph data with sound evidence merging.
5. Citations, source/chunk provenance, directed graph relationships, and support-status semantics verified.
6. Knowledge Freshness timestamp comparisons and later-change triggers verified.
7. Health, query, and dedicated capability endpoints verified.
8. React browser acceptance completed in real mode across desktop and mobile layouts.
9. Full regression suites, linters, typechecks, and production bundle builds pass with 0 errors.
10. No unresolved blockers remain.
