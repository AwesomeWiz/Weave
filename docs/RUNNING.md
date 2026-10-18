# Running and verifying Weave

The [root quick start](../README.md#quick-start-the-real-graph-workflow) is the recommended local demo path. All commands below run from the repository root. Use an owned local graph for ingestion and keep hosted generation disabled until any data transmission has been reviewed.

## Windows PowerShell

Install Python 3.11+ and Node.js 20.19+ or 22.12+, then use a new clone or a fresh virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
npm.cmd --prefix frontend ci
Copy-Item .env.example .env
```

Skip `Copy-Item` if `.env` already exists. Environment activation is optional: the commands explicitly select the virtual-environment interpreter. If `python` is unavailable, install/configure a compatible interpreter rather than copying another machine's `.venv`; virtual environments contain paths to their base interpreter.

Configure the real settings shown in the root README. Start Docker with Compose support, then:

```powershell
docker compose config --quiet
docker compose up -d falkordb
.\.venv\Scripts\python.exe -m weave_data.ingest --prepare-only
.\.venv\Scripts\python.exe -m weave_data.ingest --host localhost --port 6379 --graph novapay
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start `npm.cmd --prefix frontend run dev` in a second terminal. The Compose file exposes only `127.0.0.1:6379` and uses a named data volume. Wait for the database to be ready if ingestion initially reports a connection failure; a failure is not a successful seed. No reset/delete command is required for repeat ingestion.

## macOS / Linux (POSIX shell)

The same Python modules and npm scripts are platform-independent; interpreter paths and shell environment syntax differ:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
npm --prefix frontend ci
cp .env.example .env
docker compose up -d falkordb
.venv/bin/python -m weave_data.ingest --prepare-only
.venv/bin/python -m weave_data.ingest --host localhost --port 6379 --graph novapay
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Do not overwrite an existing `.env`. In a second terminal, run `npm --prefix frontend run dev`.

For a limited fixture preview instead of real mode:

```sh
WEAVE_GRAPH_MODE=fixture WEAVE_LLM_PROVIDER=none .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

This is not the full real four-tool workflow: runtime fixture Expert/Freshness results are qualified empty outputs. Use the ingested FalkorDB corpus to evaluate reviewer rankings and freshness associations.

## Configuration boundaries

The FastAPI [settings loader](../backend/app/config.py) reads the root `.env`; environment overrides win. Real mode requires the merged `app.antony:create_gateway` factory and `WEAVE_SOURCE_BACKEND=weave_data` for persisted source retrieval.

The ingestion CLI does **not** load that settings file. Its `--host`, `--port` and `--graph` flags override its `FALKORDB_HOST`, `FALKORDB_PORT` and `FALKORDB_GRAPH` process-variable defaults. Explicit flags in the quick start avoid ambiguity. The backend uses `WEAVE_FALKORDB_*` and `WEAVE_GRAPH_NAME`. Both must address the same graph. The CLI has no username/password/TLS flags.

### Authenticated or TLS ingestion

For a database requiring credentials/TLS, configure `WEAVE_FALKORDB_USERNAME`, `WEAVE_FALKORDB_PASSWORD` and `WEAVE_FALKORDB_SSL` in the ignored `.env`, along with real mode, host/port/graph. The existing adapter accepts those values programmatically. This PowerShell example reads them through the same settings as FastAPI and does not print credentials:

```powershell
$env:PYTHONPATH = 'backend;.'
@'
from pathlib import Path
from app.config import Settings
from weave_data.graph_adapter import FalkorDBGraphAdapter
from weave_data.ingest import run_ingestion

settings = Settings()
if settings.graph_mode != "falkordb":
    raise SystemExit("Select real graph mode before ingestion.")
adapter = FalkorDBGraphAdapter(
    host=settings.falkordb_host,
    port=settings.falkordb_port,
    graph_name=settings.graph_name,
    username=settings.falkordb_username or None,
    password=(settings.falkordb_password.get_secret_value()
              if settings.falkordb_password else None),
    ssl=settings.falkordb_ssl,
)
try:
    result = run_ingestion(Path("data/novapay"), adapter)
    if result.status != "success":
        raise SystemExit("Ingestion failed; inspect the configured database and dataset.")
    print(result.status, result.nodes_created_or_updated,
          result.chunks_created_or_updated, result.relationships_processed)
finally:
    adapter.close()
'@ | .\.venv\Scripts\python.exe -
```

Use this only for a database you are authorized to populate. Repeated upserts preserve canonical identity; they are not a general schema migration or a cleanup of obsolete relationships. There is no implicit in-memory persistence fallback. `--in-memory` is an explicitly separate offline ingestion test option, not an application real-mode configuration.

## Offline verification

Run in a fresh shell with no `WEAVE_RUN_REAL_*` flags enabled:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-offline
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
npm.cmd --prefix frontend test -- --maxWorkers=2
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

The Ruff scope matches the verified backend integration gate; it is not a claim that every historical teammate file is lint-clean. Start normal application sessions in a new terminal to avoid retaining test configuration overrides.

POSIX Python equivalents:

```sh
PYTHONPATH=backend:. WEAVE_SOURCE_BACKEND=delegate WEAVE_LLM_PROVIDER=none .venv/bin/python -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-offline
.venv/bin/python -m ruff check backend/app backend/tests
```

Use `npm` in place of `npm.cmd` for the frontend commands. Tests do not authorize a live hosted-provider run.

## Live FalkorDB checks

These require a reachable seeded database, actual graph/source adapters, the approved NovaPay corpus and deterministic generation. From a fresh PowerShell:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_GRAPH_MODE = 'falkordb'
$env:WEAVE_GRAPH_FACTORY = 'app.antony:create_gateway'
$env:WEAVE_SOURCE_BACKEND = 'weave_data'
$env:WEAVE_LLM_PROVIDER = 'none'
$env:WEAVE_RUN_REAL_CHANGE_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_change_intelligence.py -m integration -v --basetemp=.local/pytest-live-change
```

The Change gate checks accepted D-007, historical support, real source/chunk records, Checkout/Order impact, conditional ADR-7 review and conservative overall support. Final release QA should additionally compare the actual ordered architecture path (`IMPLEMENTED_BY`, `CHANGES`, `USES`) with returned tool-local proof and repeat browser playback/restoration against the live endpoint. That additional acceptance is not implied by an older passing capability gate.

Other opt-in checks:

| File | Environment flag | Requirement |
| --- | --- | --- |
| [Primary Decision Trace](../backend/tests/test_real_integration.py) | `WEAVE_RUN_REAL_INTEGRATION=1` | Set `WEAVE_REAL_EVIDENCE_MANIFEST=tests/novapay_evidence_manifest.json` only after independently checking the manifest matches the seeded revision. |
| [Source ingestion/retrieval](../backend/tests/test_real_sources.py) | `WEAVE_RUN_REAL_SOURCES=1` | Write permission for a unique test graph; the test seeds twice and deletes only its own graph. |
| [Impact HTTP workflow](../backend/tests/test_real_impact.py) | `WEAVE_RUN_REAL_IMPACT=1` | Actual seeded service/technology dependencies. |
| [Expert workflow](../backend/tests/test_real_expert_integration.py) | `WEAVE_RUN_REAL_EXPERT_INTEGRATION=1` | Actual contribution and ownership paths. |
| [Freshness workflow](../backend/tests/test_real_freshness_integration.py) | `WEAVE_RUN_REAL_FRESHNESS_INTEGRATION=1` | Actual document associations and comparable timestamps. |
| [Additional graph Impact tests](../tests/test_impact_analysis.py) | `WEAVE_RUN_REAL_IMPACT=1` | Real graph traversal; include this file when evaluating the full live suite. |

After enabling the relevant flag, pass the corresponding file to the same `python -m pytest ... -v --basetemp=...` command. Unset opt-ins before running offline tests again. A skipped live test is not a successful database check.

## Optional presentation provider

For OpenRouter, set the following only after reviewing the external data flow:

```dotenv
WEAVE_LLM_PROVIDER=openrouter
WEAVE_OPENROUTER_API_KEY=<your-backend-only-key>
WEAVE_LLM_MODEL=openai/gpt-oss-120b
WEAVE_OPENROUTER_MAX_TOKENS=1200
WEAVE_LLM_TIMEOUT_SECONDS=30
```

The completion endpoint is `https://openrouter.ai/api/v1/chat/completions`. Backend health also performs provider availability requests when OpenRouter is enabled. No key belongs in browser bundles, logs or a request body. Missing/invalid generation retains deterministic evidence and support. Hosted testing is separate from graph testing; this guide does not claim live model acceptance. [Finite Change presentation protocol](PHASE3_CHANGE_OPENROUTER_HANDOFF.md).

`ollama` remains available for the existing single-tool Decision explanation through `WEAVE_OLLAMA_URL`, `WEAVE_OLLAMA_MODEL` and `WEAVE_LLM_TIMEOUT_SECONDS`; it is not the finite four-section Change presentation protocol. `WEAVE_LLM_PROVIDER=none` is sufficient for all canonical deterministic analysis.

## Deployment and verification status

No deployment is performed by these instructions. Serve the built frontend and API over HTTPS, restrict graph access, keep graph data persistent, configure CORS and backend-only secrets, and add an appropriate access-control layer before exposing private records. Verify real health, sources, paths, partial/error behavior and desktop/mobile interaction on the chosen host. There is no built-in authentication or PostgreSQL runtime failover.

During this documentation review, Python 3.11.9 CLI help, prepare-only ingestion and offline endpoint/schema inspection were executed successfully. The dataset prepared 20 entities, 6 chunks and 44 relationships, and the README's directed graph examples matched the ingestion output. Docker was not available on PATH, so Compose validation/startup, actual ingestion and a new clean-clone/live-database startup were not executed. POSIX commands are source-checked equivalents, not a new macOS/Linux acceptance run. Existing Phase 1–4 verification records remain revision-specific; no skipped or unexecuted live check is reported as passed.
