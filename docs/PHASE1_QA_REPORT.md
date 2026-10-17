# Weave Phase 1 — QA & Real FalkorDB Integration Report

**Date:** October 17, 2026  
**Auditor:** Engineering Copilot (QA & Demo Readiness)  
**Repository:** [https://github.com/AwesomeWiz/Weave](https://github.com/AwesomeWiz/Weave)  
**Branch Under Test:** `integration/phase1`  
**Exact Commit Hash:** `495415e3b63b5905aad91710f5abd090572aa894`  
**Commit Message:** `fix: validate decision rationale through graph provenance`

---

## 1. Executive Summary & Recommendation

| Component / Verification Area | Status | Notes |
| :--- | :--- | :--- |
| **Git & Repository Structure** | **PASS** | `integration/phase1` exists remotely, checked out cleanly at `495415e`. |
| **Python Environment & Dependencies** | **PASS** | Python 3.13.1, `.venv` created, `requirements.lock.txt` installed cleanly. |
| **Node.js & Frontend Build/Tests** | **PASS** | Node 24.13.0, npm 11.6.2; Vitest (41 passed), ESLint, tsc, and Vite build all PASS. |
| **Offline Ingestion & Validation** | **PASS** | `prepare_ingestion()` validates 15 canonical entities, 33 edges, 4 chunks, 17 aliases. |
| **Offline Backend & Graph Tests** | **PASS** | 185 tests passed, Ruff clean (0 linter errors). |
| **Docker Desktop / Local Database** | **PASS** | Docker Desktop 4.95.0, Engine 29.8.2, Docker Compose v5.6.0, WSL2 active. |
| **Real FalkorDB Connectivity** | **PASS** | Container `weave-falkordb` listening on 127.0.0.1:6379 (`TcpTestSucceeded: True`). |
| **Real NovaPay Ingestion** | **PASS** | Ingested into live FalkorDB: 15 nodes, 33 edges, 4 chunks; verified idempotent. |
| **Real Decision Trace (`trace_decision`)**| **PASS** | `app.graph.test_trace` passed against live FalkorDB; all decision, edge, source assertions met. |
| **Real Source Retrieval (`find_sources`)** | **PASS** | `test_real_sources.py` passed against live FalkorDB (100% real retrieval, no mocks). |
| **Documented Real Integration Tests** | **PASS** | `test_seeded_falkordb_primary_question` passed with `WEAVE_REAL_EVIDENCE_MANIFEST`. |
| **FastAPI Real-Mode Endpoints** | **PASS** | `GET /api/health` returns 200 (`falkordb: connected`); `POST /api/query` returns `supported` with genuine citations. |
| **React Browser Real-Mode Acceptance** | **PASS** | Browser subagent verified live UI, knowledge graph render, citation drawer, and grounded answer. |

**Final Phase 1 Recommendation:** **READY (PASS)**. All components and integration contracts are verified end-to-end with real FalkorDB and real NovaPay dataset. No fixtures were substituted in real mode.

---

## 2. Environment Audit & Tool Versions

| Tool | Version / Status | Path / Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 (AMD64) | Development workstation |
| **Git** | `2.53.0.windows.1` | Remote origin tracking active |
| **Python** | `3.13.1` (64-bit) | `.venv` created at repository root |
| **Node.js** | `v24.13.0` | Frontend tooling compatible |
| **npm** | `11.6.2` | Clean `npm ci` completed |
| **Docker Desktop** | `4.95.0` (Engine `29.8.2`) | Installed and running |
| **Docker Compose** | `v5.6.0` | Active CLI binary |
| **WSL** | `6.18.54.1-microsoft-standard-WSL2` | Active WSL2 backend for Docker Desktop |
| **FalkorDB Container** | `falkordb/falkordb:latest` | Running (`weave-falkordb`, port 6379) |

---

## 3. Repository Architecture & Implementation Mapping

- **Backend Entry Point:** `backend/app/main.py` (`app.main:app`), executed via:
  ```powershell
  .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
  ```
- **Configuration:** `backend/app/config.py` (`Settings`, loads `.env` or environment variables with prefix `WEAVE_`).
- **Antony's Decision Trace Implementation:**
  - Core implementation: `app/graph/trace.py` (`trace_decision(client, service_id, technology_id)`).
  - FalkorDB client: `app/graph/client.py` (`GraphClient`).
  - Import bridge: `weave_graph/__init__.py`.
  - Gateway adapter: `backend/app/antony.py` (`AntonyGateway`, `create_gateway`).
  - Factory reference: `app.antony:create_gateway`.
- **Alen's Ingestion & Source Retrieval Implementation:**
  - Core package: `weave_data/` (`models.py`, `loader.py`, `validation.py`, `relationships.py`, `chunks.py`, `retrieval.py`, `graph_adapter.py`, `ingest.py`).
  - Gateway integration: `backend/app/sources.py` (`WeaveDataSourceRetriever` calling `find_sources` with `FalkorDBGraphAdapter`).
- **Frontend Architecture:**
  - Vite + React 19 + TypeScript + React Flow (`@xyflow/react`) + Dagre (`@dagrejs/dagre`) in `frontend/`.
  - Production build: `npm.cmd --prefix frontend run build` (outputs to `frontend/dist/`).

---

## 4. Dataset Inspection (NovaPay)

Canonical dataset inspected at `data/novapay/`:
1. `incident:INC-17` (`incidents.json`): "Payment requests timing out during peak traffic", relates to `issue:PAY-42`.
2. `issue:PAY-42` (`jira/issues.json`): "Reduce payment latency under burst traffic", relates to `incident:INC-17`.
3. `message:payment-perf-7` (`slack/messages.json`): Slack thread in `#payments-engineering` with Alice, Ravi, Maya.
4. `decision:D-007` (`decisions.json`): "Introduce Redis caching" (status: `accepted`).
5. `person:alice`, `person:ravi`, `person:maya` (`people.json`): Alice Menon (Lead/Approver), Ravi Nair (Implementer), Maya Joseph (Platform).
6. `commit:8fae2` (`github/commits.json`): `8fae2d4a1b3c5e6f7890abcdef1234567890abcd`, repo `repo:novapay/payments-api`.
7. `repo:novapay/payments-api` (`github/repositories.json`): Payments API repository.
8. `service:payment-service` (`services.json`): Uses `tech:redis`.
9. `service:checkout-service` (`services.json`): Depends on `service:payment-service`.
10. `tech:redis` (`technologies.json`): Redis cache technology.
11. `doc:ADR-7` (`docs/ADR-7.md`): Architectural decision record documenting D-007.

**Offline Ingestion CLI Verification:**
```powershell
python -m weave_data.ingest --prepare-only
```
- Validation: **PASSED**
- Entities: 15 canonical records
- Relationships: 33 edges extracted
- Text Chunks: 4 retrieval chunks
- Aliases: 17 alias mappings

```powershell
python -m weave_data.ingest --in-memory
```
- Status: **SUCCESS**
- Nodes: 15
- Relationships: 33
- Chunks: 4
- Persistence: `InMemoryGraphAdapter`

---

## 5. Offline Regression Suite Results

### Backend & Graph Suite
Command:
```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
.\.venv\Scripts\python.exe -m pytest backend\tests tests app\graph -q --basetemp=.local/pytest-check
```
- **Passed:** 185
- **Skipped:** 2 (`test_real_ingestion_and_source_retrieval`, `test_seeded_falkordb_primary_question` — opt-in real tests requiring live FalkorDB)
- **Warnings:** 1 (Starlette httpx deprecation notice, non-failing)

### Linter (Ruff)
Command:
```powershell
.\.venv\Scripts\python.exe -m ruff check --config backend\pyproject.toml backend app\graph weave_graph tests\test_decision_trace.py
```
- **Result:** `All checks passed!` (0 errors)

### Frontend Suite
Commands:
```powershell
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```
- **Vitest:** 3 test files, 41 passed (100%)
- **ESLint:** Passed (0 errors)
- **TypeScript (`tsc -b`):** Passed (0 errors)
- **Vite Production Build:** Successfully generated bundles in `dist/` (0 errors)

---

## 6. Real Mode Resolution & Verified Execution
 
All previous blockers have been completely resolved:
1. Docker Desktop 4.95.0 and WSL2 are active on the host.
2. `falkordb/falkordb:latest` container was started via `docker compose up -d` as `weave-falkordb` listening on `127.0.0.1:6379`.
3. Connectivity was verified via `Test-NetConnection -ComputerName 127.0.0.1 -Port 6379` (`TcpTestSucceeded: True`).
 
---
 
## 7. Real Integration Verification Results
 
### Step 1: Real NovaPay Ingestion & Idempotency Verification
- **Command:** `python -m weave_data.ingest --host localhost --port 6379 --graph novapay`
- **First Run:** Status: `SUCCESS`, Nodes: 15, Relationships: 33, Chunks: 4, Persistence: `FalkorDBGraphAdapter`.
- **Second Run:** Status: `SUCCESS`, Nodes: 15, Relationships: 33, Chunks: 4 (idempotent, no duplicated nodes or edges).
 
### Step 2: Antony's Decision Trace Smoke
- **Command:** `python -m app.graph.test_trace`
- **Result:** `PASS`.
- **Verifications:**
  - Selected decision: `decision:D-007` (status: `accepted`).
  - Target entities: `service:payment-service`, `tech:redis`.
  - Canonical graph edges verified: `AFFECTS`, `INTRODUCES`, `USES`, `LED_TO`, `SUPPORTED_BY`, `DOCUMENTED_IN`, `IMPLEMENTED_BY`.
  - Chunk provenance: 4 chunks linked via `FROM_ISSUE`, `FROM_MESSAGE`, `FROM_DOCUMENT`, `FROM_COMMIT`.
 
### Step 3: Alen's Real Source Retrieval Smoke
- **Command:** `$env:WEAVE_RUN_REAL_SOURCES = '1'; pytest backend/tests/test_real_sources.py -v`
- **Result:** `1 passed in 4.50s`.
- **Verifications:**
  - Created isolated ephemeral test graph (`weave_source_smoke_<uuid>`).
  - Ran ingestion twice, verified stability.
  - Retrieved all 4 canonical parent sources (`issue:PAY-42`, `message:payment-perf-7`, `commit:8fae2`, `doc:ADR-7`) with verified snippets, chunk IDs, and timestamps.
  - Cleanly tore down the test graph without touching `novapay`.
 
### Step 4: Documented Real Integration Acceptance
- **Command:** `$env:WEAVE_RUN_REAL_INTEGRATION = '1'; $env:WEAVE_REAL_EVIDENCE_MANIFEST = 'tests/novapay_evidence_manifest.json'; pytest backend/tests/test_real_integration.py -v`
- **Result:** `1 passed, 1 warning (Starlette httpx) in 8.67s`.
- **Verifications:**
  - Confirmed `FixtureGateway` was NOT instantiated (forbidden fixture guard passed).
  - Confirmed `GET /api/health` returned `falkordb: connected`, `graph_tool: available`.
  - Confirmed `POST /api/query` returned `support_status: supported` with authoritative source text, safe URLs, and canonical graph topology.
 
### Step 5: Full Regression & Linter Suite
- **Pytest:** 185 passed (`$env:WEAVE_SOURCE_BACKEND = 'delegate'`).
- **Ruff:** All checks passed (0 linter errors).
- **Vitest:** 3 test files, 41 tests passed (100%).
- **ESLint & TypeScript:** 0 errors.
- **Vite Build:** Production bundle built cleanly (`dist/` generated in 3.78s).
 
### Step 6: Real-Mode End-to-End Browser Workflow
- **FastAPI Daemon:** Running on `http://127.0.0.1:8000` (`WEAVE_GRAPH_MODE=falkordb`).
- **Vite Dev Server:** Running on `http://127.0.0.1:5173` proxying `/api` to FastAPI.
- **Browser Subagent Verification:**
  - System status pill shows real mode active and connected.
  - Query executed: *"Why does Payment Service use Redis?"*.
  - Grounded answer rendered with full historical and architectural rationale (INC-17, PAY-42, ADR-7, commit 8fae2).
  - Support badge displayed **Supported** (green).
  - Active citations rendered: `issue:PAY-42`, `doc:ADR-7`, `commit:8fae2`.
  - Citation inspector drawer opens excerpt and metadata on click.
  - Knowledge graph rendered 12 nodes and 12 directed edges via React Flow canvas.

