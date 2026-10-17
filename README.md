# Weave

Company decision intelligence: React → FastAPI → deterministic tool router → graph/source adapter → Context Builder → grounded explanation → sources and an interactive evidence graph.

**Decision Trace and Phase 2 Impact Analysis are integrated with Antony's graph tools and Alen's `weave_data` retrieval. Offline verification passes; live FalkorDB verification remains required on this machine.** Development mode uses explicitly labeled synthetic fixtures. Real mode never falls back to fixtures, local source files or an in-memory graph. See the [Phase 2 handoff](docs/PHASE2_IMPACT_HANDOFF.md) for API schemas, verification results and QA limitations.

## Install

Requires Python 3.11+ and Node.js 20.19+ (Node 22.12+ recommended). From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
npm.cmd --prefix frontend ci
Copy-Item .env.example .env
```

If Python is not on PATH on this workstation, the verified interpreter is:

```powershell
& "$env:LOCALAPPDATA\Python\pythoncore-3.11-64\python.exe" -m venv .venv
```

No PowerShell activation script is required. On macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`, and `npm` instead of `npm.cmd`.

## Run the labeled development workspace

Terminal 1, repository root:

```powershell
$env:WEAVE_GRAPH_MODE = 'fixture'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2, repository root:

```powershell
npm.cmd --prefix frontend run dev
```

Open **http://127.0.0.1:5173** and submit **Why does Payment Service use Redis?**

Fixture mode returns six synthetic source records, 12 nodes, and 14 directed relationships. The mode appears in the UI, health endpoint, response metadata, and source metadata. There are no real connector connections or invented external source URLs. The fixture is an ordinary development input to the same API/context pipeline; the frontend has no hardcoded answers.

You can instead set `WEAVE_GRAPH_MODE=fixture` in the ignored `.env`. Configuration loads from the repository root regardless of the backend working directory. Environment variables take precedence. `.env.example` deliberately defaults to real mode.

On macOS/Linux, start with `WEAVE_GRAPH_MODE=fixture .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`.

## Connect the teammate graph implementation

Set these in `.env` and restart FastAPI (clear any conflicting shell environment variables):

```dotenv
WEAVE_GRAPH_MODE=falkordb
WEAVE_GRAPH_FACTORY=app.antony:create_gateway
WEAVE_SOURCE_BACKEND=weave_data
WEAVE_GRAPH_NAME=novapay
WEAVE_FALKORDB_HOST=localhost
WEAVE_FALKORDB_PORT=6379
```

The factory provides async `trace_decision`, `impact_analysis` and graph-tool health through the existing `weave_graph` namespace. With `WEAVE_SOURCE_BACKEND=weave_data`, the backend independently uses Alen's persisted source retrieval; with `delegate`, the factory also provides `find_sources`. See [the Phase 1 integration handoff](docs/REAL_INTEGRATION_HANDOFF.md) for source IDs and chunk provenance, and the [Phase 2 handoff](docs/PHASE2_IMPACT_HANDOFF.md) for impact semantics. No teammate Cypher was duplicated here.

Select **Impact Analysis** or ask **What depends on Payment Service?** The dedicated `POST /api/tools/impact-analysis` endpoint accepts `{"entity_id":"service:payment-service","max_depth":2}`. The UI shows direct and potential downstream findings, actual directed paths, available owners and related sources. Depth is 1–3, including the technology `USES` hop. Structural impact remains `partially_supported`; a related historical issue does not prove failure propagation. `/api/query` retains its original response schema.

`/api/query` also supports bounded combined questions, such as **What led to Redis being introduced for Payment Service, and what services might be affected if Redis were removed?** Each capability validates independently before Context Builder V2 merges genuine evidence. See the [multi-tool handoff](docs/PHASE2_MULTITOOL_HANDOFF.md) for routing rules, support/failure behavior and future-tool registration. Expert Finder and Knowledge Freshness intents are recognized but never executed until their real implementations are registered.

Without that implementation, the primary query returns HTTP **503 / GRAPH_UNAVAILABLE**. Health separately checks actual FalkorDB graph availability and tool availability; a reachable database alone is insufficient. The health probe only uses `GRAPH.LIST` and a bounded read-only graph query.

## Optional Qwen through Ollama

Install/pull an appropriate Qwen model through Ollama, then configure:

```dotenv
WEAVE_LLM_PROVIDER=ollama
WEAVE_OLLAMA_URL=http://localhost:11434
WEAVE_OLLAMA_MODEL=qwen2.5:7b
WEAVE_LLM_TIMEOUT_SECONDS=30
```

Restart FastAPI. Health checks that the exact model is present. Generation uses a bounded evidence packet, explicit grounding rules, and validated source references. Failure, timeout, malformed output, or invalid citations return the deterministic evidence summary with the graph and sources preserved. Citation validation is a guardrail, not a proof of semantic faithfulness. `WEAVE_LLM_PROVIDER=none` gives deterministic answers without a model.

## Optional GPT-OSS-120B through OpenRouter

Configure the backend `.env` with `WEAVE_LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, and `LLM_MODEL=openai/gpt-oss-120b`, then restart FastAPI. The equivalent prefixed key/model variables are supported. Keep credentials out of frontend configuration.

Decision Trace, Impact Analysis, and combined answers use constrained presentation plans over validated evidence. The server renders factual content, checks genuine citations, retains missing-evidence caveats, and preserves support status. Provider failures return the exact deterministic summary. See the [OpenRouter handoff](docs/PHASE2_OPENROUTER_HANDOFF.md) for configuration, bounds, tests, the constrained-synthesis limitation, and pending live verification.

## Verify

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate' # isolate offline doubles from local .env configuration
.\.venv\Scripts\python.exe -m pytest backend\tests tests app\graph -q --basetemp=.local/pytest-check
.\.venv\Scripts\python.exe -m ruff check --config backend\pyproject.toml backend
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
Remove-Item Env:WEAVE_SOURCE_BACKEND # restore .env selection for the app
```

The optional real integration test is skipped by default. Once the real adapter and seeded graph are available:

```powershell
$env:WEAVE_RUN_REAL_INTEGRATION = '1'
$env:WEAVE_GRAPH_MODE = 'falkordb'
$env:WEAVE_REAL_EVIDENCE_MANIFEST = '<path-to-reviewed-seeded-source-export.json>'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_real_integration.py -v
```

The real test requires an independently reviewed export of Alen's seeded source corpus and checks accepted D-007, directed paths, and matching supporting evidence. See [real integration handoff](docs/REAL_INTEGRATION_HANDOFF.md) for the export schema, mapping rules and unresolved dependencies.

Live endpoint checks while FastAPI runs:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/query -Method Post -ContentType 'application/json' -Body '{"question":"Why does Payment Service use Redis?","session_id":"demo-session"}'
```

API schema: http://127.0.0.1:8000/docs. The Vite development server proxies `/api` to port 8000. A deployed static frontend needs a reverse proxy for `/api`, or a build-time `VITE_API_URL` pointing to FastAPI and matching backend CORS configuration. `vite preview` alone does not provide the production API.

## Implementation map

- `backend/app/models.py`, `config.py`, `main.py`: API contract, environment settings, validation, health, and orchestration.
- `backend/app/graph.py`, `router.py`: replaceable graph/source boundary and bounded deterministic routing.
- `backend/app/context.py`, `llm.py`: normalized evidence, support rules, deterministic explanation, optional Ollama.
- `backend/app/fixtures/novapay.development.json`: explicitly labeled development-only input, never loaded in real mode.
- `frontend/src/App.tsx`, `components/`, `styles/`: screenshot-inspired workspace, original logo, typed API UI, React Flow graph and inspectors.
- `backend/tests/`, `frontend/src/*.test.*`: contract, integration-boundary, failure-path and UI tests.

## Scope and visual fidelity

The implementation follows the warm paper/sage three-column layout, original Weave knot, serif display headings, welcome cards, composer, sources, and colored graph entities from the supplied references. It uses the fonts recommended in `docs/design.md`.

Intentional differences: fixture badges and honest connection status; no signed-in user impersonation; later-phase features visibly unavailable; no attachment action; no persistent conversations; and graph arrows use the documented ontology rather than inconsistent arrows in the mockups. The graph uses a compact decision-focused arrangement, with general Dagre layout for other shapes, and a keyboard-accessible relationship table. At narrower widths the inspector moves below the main content.

See [verification notes](docs/PHASE1_VERIFICATION.md) for actual checks and remaining limitations. AI-assisted implementation: OpenAI Codex.
# Weave — Company Brain (Data & Ingestion)

> **Track 3: Company Brain** — FalkorDB Graph Hacks  
> **Workstream:** Data / Ingestion  
> **Owner:** Alen Abraham Saji

Weave is a company decision-intelligence agent that connects incidents, issues, discussions, decisions, people, commits, repositories, services, technologies, and documents in FalkorDB.

---

## 🎯 Primary Demo Query & Evidence Chain

**Question:** *"Why does Payment Service use Redis?"*

**Canonical Evidence Chain:**
```
incident:INC-17  ("Payment requests timing out during peak traffic")
       │ LED_TO
       ▼
issue:PAY-42     ("Reduce payment latency under burst traffic")
       │ SUPPORTED_BY (reverse)
       ▼
decision:D-007   ("Introduce Redis caching" — status: accepted)
       │
       ├── AFFECTS          ──► service:payment-service
       ├── INTRODUCES       ──► tech:redis
       ├── SUPPORTED_BY     ──► issue:PAY-42
       ├── SUPPORTED_BY     ──► message:payment-perf-7
       ├── IMPLEMENTED_BY   ──► commit:8fae2
       ├── DOCUMENTED_IN    ──► doc:ADR-7
       ├── PARTICIPATED_IN  ◄── person:alice, person:ravi, person:maya
       └── APPROVED         ◄── person:alice (approver)

commit:8fae2 ──► BELONGS_TO ──► repo:novapay/payments-api
                                       │ IMPLEMENTS
                                       ▼
                               service:payment-service ◄── USES ── tech:redis
                                       ▲
                                       │ DEPENDS_ON
                               service:checkout-service
```

---

## 🚀 Quickstart

### 1. Requirements

Install minimal dependencies (Python 3.10+):
```bash
pip install -r requirements.txt
```

### 2. Run Ingestion CLI

**Validate & prepare data without graph persistence:**
```bash
python -m weave_data.ingest --prepare-only
```

**Output prepared dataset as JSON:**
```bash
python -m weave_data.ingest --prepare-only --json
```

**Full ingestion run (FalkorDB required; failure exits nonzero):**
```bash
python -m weave_data.ingest
```

**Explicit offline development run (no database persistence):**
```bash
python -m weave_data.ingest --in-memory
```

**Connect to FalkorDB:**
```bash
python -m weave_data.ingest --host localhost --port 6379 --graph novapay
```
*(Or set environment variables `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH`)*

### 3. Run Test Suite

```bash
python -m pytest -q
```
*(The suite covers schema validation, referential integrity, temporal ordering, relationship extraction, text chunking, local and graph-backed source retrieval, determinism, and idempotency.)*

---

## 📦 Package Architecture (`weave_data/`)

| Module | Purpose |
|---|---|
| [`models.py`](weave_data/models.py) | Pydantic v2 schemas for all canonical records (`Person`, `Team`, `Service`, `Technology`, `Repository`, `Commit`, `Issue`, `Message`, `Decision`, `Incident`, `Document`, `Chunk`). Enforces prefixed IDs, required fields, URLs, and ISO-8601 timestamps. |
| [`loader.py`](weave_data/loader.py) | Discovers and loads source files (`JSON`, `Markdown`) from `data/novapay/`. |
| [`validation.py`](weave_data/validation.py) | Validates unique IDs, entity type bounds, foreign reference resolution, and temporal consistency. |
| [`relationships.py`](weave_data/relationships.py) | Maps entity fields and chunks to 33 Cypher graph edge operations (`RelationshipOp`) adhering to the knowledge graph ontology. |
| [`chunks.py`](weave_data/chunks.py) | Generates normalized text chunks with source provenance (`url`, `timestamp`, `chunk_index`) and chunk-to-source relationships (`FROM_*`). |
| [`retrieval.py`](weave_data/retrieval.py) | Deterministic `find_sources(source_ids)` exact-source retrieval interface resolving canonical entity IDs to structured evidence. |
| [`graph_adapter.py`](weave_data/graph_adapter.py) | Abstraction over graph storage: `InMemoryGraphAdapter` (mock) and `FalkorDBGraphAdapter` (Cypher MERGE queries). |
| [`ingest.py`](weave_data/ingest.py) | Pipeline orchestrator & CLI entry point. Provides `prepare_ingestion()` and `run_ingestion()`. |

---

## 🤝 Team Handoff & Contracts

- [**Ingestion Contract**](docs/ingestion-contract.md) — Canonical IDs, schema fields, relationship mappings, and chunk specifications.
- [**Graph Handoff (Antony)**](docs/handoff-antony.md) — Node labels, Cypher MERGE patterns, and how to consume `prepare_ingestion()`.
- [**AI Integration Handoff (Abhishikth)**](docs/handoff-abhishikth.md) — Retrieval chunks, `find_sources` interface, entity aliases, and provenance metadata.
- [**Frontend & Demo Handoff (Arnold)**](docs/handoff-arnold.md) — Redis decision chain, evidence timeline, and causality demo edge.
