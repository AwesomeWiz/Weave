# Railway + Vercel + FalkorDB Cloud deployment

Phase 5 starts from merged Phase 4 `main`, commit `33fd3a620add90abff52450ba6d6128997f71309`. Preparation changes are uncommitted on `chore/phase5-deployment-readiness`. No service was provisioned, deployed or modified. Both original stashes and the five untracked source screenshots were preserved.

**Verdict: ready with manual prerequisites.** Public launch is blocked until an owned FalkorDB Cloud instance is provisioned, its connection settings are supplied, initial seeding is approved, and Railway/Vercel accounts and domains are configured. No combined live Cloud acceptance is claimed. This procedure requires no local Docker.

## Architecture and release boundaries

React/Vite on Vercel → HTTPS FastAPI on Railway → deterministic routing, four graph tools and Context Builder V2 → remote FalkorDB and graph-backed source retrieval → optional constrained OpenRouter presentation. Change Intelligence combines historical rationale, direct/downstream impact, reviewers and document review. Trace playback uses validated, directed tool-local paths.

`/api/query` retains its six fields: `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`. `/api/change-intelligence` adds `data`. Existing routes `/api/tools/impact-analysis`, `/api/tools/expert-finder`, `/api/tools/freshness` and `/api/health` remain. No evidence contracts, routing grammar or UI behavior were changed. The Change scenario remains explicit Redis removal from Payment Service.

Deploy only a reviewed, committed release. Phase 4 is merged; do not re-merge teammate branches. Dashboard instructions below are manual release actions after approval, not authorization for automatic commit/push/deployment. Record release SHA, dataset revision, deployment IDs, regions and resolved runtime versions.

## Railway backend

Create a Railway service from the GitHub repository, authorizing repository access. Use the approved release branch. Select `main` for eventual production **after** reviewed preparation changes land; current remote `main` does not contain uncommitted changes. Pause automatic deployment while preparing settings and credentials.

| Setting | Exact value |
| --- | --- |
| Type / builder | Long-running Python service / native **Railpack** |
| Root directory | Repository root `/`, **not** `backend` |
| Python | `RAILPACK_PYTHON_VERSION=3.11`; record resolved patch in logs |
| Dependency install override | `RAILPACK_INSTALL_CMD=python -m pip install -r backend/requirements.lock.txt` |
| Build command | Leave blank; install override supplies dependencies, no backend compilation needed |
| Start command | `python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT` |
| Import | Module-level `app` in `backend/app/main.py` |
| Runtime path | `PYTHONPATH=backend:.` (Linux separator), `PYTHONUTF8=1` |
| Deploy health-check path / timeout | `/healthz` / 60 seconds |
| Replicas / hooks | One initially; no pre-deploy seed, migrations or scheduler |
| Serverless / sleeping | **Disabled** for judging; verify manually |
| Public networking | Generated Railway HTTPS domain targeting assigned `PORT` |

The full checkout is essential: `weave_graph` exposes teammate code under `app/graph` without colliding with FastAPI's `app.graph`. `weave_data` and tracked `data/novapay` must be available. Root `requirements.txt` belongs to the data workstream and does **not** install the API. Use the backend lock. It includes established test/lint dependencies; splitting that lock is outside this preparation.

Railpack supports Python version selection and an install override that copies all project files before installation. No Dockerfile, local Docker or Nixpacks migration is needed. No Railway config file is added: documented dashboard settings and Railpack variables cover this service without another configuration source. [Railpack Python](https://railpack.com/languages/python/), [install override semantics](https://railpack.com/config/environment-variables/), [Railway build/start commands](https://docs.railway.com/builds/build-and-start-commands).

Enter the backend variables below. In Settings → Networking → Public Networking, generate a domain and record its HTTPS origin. Railway supplies `PORT`; do not override it with development port 8000. Ensure the domain targets the assigned listener port.

Inspect build logs for Python 3.11 and backend lock installation. Runtime logs should show successful Uvicorn startup on `0.0.0.0:<assigned PORT>`. Check `/healthz`, then separately `/api/health`. Restart the same deployment for a transient process problem, or redeploy after variable/code changes; verify the effective revision/settings. The deploy-time health check is not continuous dependency monitoring. [Railway health checks](https://docs.railway.com/deployments/healthchecks).

Verify Settings → Deploy → Serverless is off. Unexpected sleep/wake events or cold-start delay require checking this setting and logs, not keepalive traffic. A running backend consumes resources while idle. Account eligibility, trial credits, payment method and Cloud capacity are manual prerequisites; no free allocation is assumed. Set Workspace Usage alerts and a considered hard limit, monitor CPU/RAM/egress, and remember hard limits can stop workloads. Stop unused preview services after evaluation. [Cost controls](https://docs.railway.com/pricing/cost-control), [Serverless behavior](https://docs.railway.com/deployments/serverless).

## Backend variables

Enter values individually in Railway Variables. Placeholders are not credentials. Never copy workstation `.env` files into images or paste passwords into shell commands/logs.

| Variable | Production setting |
| --- | --- |
| `RAILPACK_PYTHON_VERSION` | `3.11` |
| `RAILPACK_INSTALL_CMD` | `python -m pip install -r backend/requirements.lock.txt` |
| `PYTHONPATH` | `backend:.` |
| `PYTHONUTF8` | `1` |
| `WEAVE_GRAPH_MODE` | `falkordb` |
| `WEAVE_GRAPH_NAME` | `novapay` |
| `WEAVE_GRAPH_FACTORY` | `app.antony:create_gateway` |
| `WEAVE_SOURCE_BACKEND` | `weave_data` |
| `WEAVE_FALKORDB_HOST` | Cloud DNS hostname only, no scheme or authenticated URL |
| `WEAVE_FALKORDB_PORT` | Cloud client port; do not assume 6379 or browser console port |
| `WEAVE_FALKORDB_USERNAME` | Cloud-provided username if required; otherwise omit |
| `WEAVE_FALKORDB_PASSWORD` | Cloud database password, server secret |
| `WEAVE_FALKORDB_SSL` | `true` for Cloud TLS endpoint |
| `WEAVE_CORS_ORIGINS` | JSON array, e.g. `["https://your-weave.vercel.app"]`; exact origin without path/trailing slash |
| `WEAVE_LLM_PROVIDER` | `none` initially |
| `WEAVE_LLM_TIMEOUT_SECONDS` | `30` |

The API and seed example use `WEAVE_*` through `app.config.Settings`. Standalone CLI `FALKORDB_HOST`, `FALKORDB_PORT` and graph aliases are a different configuration surface; those alone do not configure the API. The bare ingestion CLI does not load the API's authenticated TLS settings. Use the explicit adapter below for Cloud.

## FalkorDB Cloud and TLS

Provision an owned Cloud instance with persistence, region, capacity and access controls suitable for the demo. Obtain actual client hostname, port and credentials from its connectivity details. Confirm outbound reachability from Railway and the authorized seed machine. If Cloud requires an allowlist, coordinate it with actual deployment outbound networking; do not assume Railway-private DNS reaches another provider. Keep Redis protocol access authenticated.

Use a TLS endpoint whose certificate is trusted by the runtime CA store and matches the supplied hostname. Graph client, source adapter and independent health probe explicitly set `ssl_cert_reqs="required"` and `ssl_check_hostname=True`. The installed FalkorDB 1.8.0 default was `ssl_check_hostname=False`; preparation closes that gap. No verification-disable setting was added. Existing socket timeouts remain: connection 2 seconds, graph/source read 5 seconds, health read 2 seconds. Existing graph/source server query deadlines remain. [FalkorDB TLS guidance](https://www.falkordb.com/blog/encryption-in-transit/).

The application exposes username/password and TLS, not mTLS key/certificate settings or a custom CA-path variable. A private-CA/mTLS-only endpoint requires an approved trust-store/connector configuration before launch. Never bypass a failure with disabled verification, non-TLS, or an IP substitution. Actual Cloud authentication, trust, hostname and networking are unverified prerequisites.

Graph tools issue bounded, application-authored read-only Cypher through `GRAPH.QUERY`; source retrieval and the independent health probe use `GRAPH.RO_QUERY`. No user-authored Cypher is accepted. Ingestion alone writes MERGE upserts. Restricted credentials must permit actual listing/schema-discovery commands used by the pinned client as well as tool reads; an ACL permitting only `GRAPH.RO_QUERY` is insufficient for the existing client. Separate seed/runtime credentials where suitable ACLs are available. There is no startup seed/reset.

## Prepare and seed the owned graph

Validate locally from repository root with dependencies installed; this performs no database access:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m weave_data.ingest --prepare-only --json
```

Expected preparation: **20 entity records, 6 chunks, 44 relationship operations, 29 aliases, zero validation errors**. These are not live counts. All corpus files, aliases and Markdown documents are tracked under `data/novapay`; the loader resolves paths relative to the package. Expert resolution uses `aliases.json`. Runtime source retrieval always supplies a real `FalkorDBGraphAdapter` and reads persisted chunks; that branch never reads local excerpts or falls back to memory/files.

Obtain explicit approval to populate an **owned, initially empty** Cloud graph. Set the backend variables above in a private local environment or ignored root `.env`, including `WEAVE_GRAPH_NAME=novapay` and TLS. Never put a password in command history. The supported programmatic seam below refuses localhost/non-TLS and nonempty graphs; two identical upserts in the same approved operation check idempotency. Prevent concurrent writers: the preflight is not a transaction lock.

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
# Set only after the owner approves seeding this empty Cloud graph.
$env:WEAVE_SEED_APPROVED = 'novapay'
@'
import os
from contextlib import suppress
from pathlib import Path
from app.config import Settings
from weave_data.graph_adapter import FalkorDBGraphAdapter
from weave_data.ingest import prepare_ingestion, run_ingestion

adapter = None
def require(condition):
    if not condition:
        raise ValueError("Seed precondition failed")

try:
    config = Settings()
    require(config.graph_mode == "falkordb" and config.graph_name == "novapay")
    require(os.environ.get("WEAVE_SEED_APPROVED") == config.graph_name)
    require(config.falkordb_ssl and config.falkordb_host not in {"localhost", "127.0.0.1", "::1"})
    data = Path("data/novapay")
    records, edges, chunks, aliases, validation = prepare_ingestion(data)
    require(validation.ok and (len(records), len(chunks), len(edges), len(aliases)) == (20, 6, 44, 29))
    adapter = FalkorDBGraphAdapter(
        host=config.falkordb_host, port=config.falkordb_port, graph_name=config.graph_name,
        username=config.falkordb_username or None,
        password=config.falkordb_password.get_secret_value() if config.falkordb_password else None,
        ssl=config.falkordb_ssl,
    )
    if config.graph_name in adapter._client.list_graphs():
        total = adapter._graph.ro_query("MATCH (n) RETURN count(n)", timeout=5000).result_set[0][0]
        require(total == 0)
    first = run_ingestion(data, adapter)
    require(first.status == "success" and not first.errors)
    counts = (adapter.node_count(), adapter.chunk_count(), adapter.relationship_count())
    require(counts == (20, 6, 44))
    second = run_ingestion(data, adapter)
    require(second.status == "success" and not second.errors)
    require(counts == (adapter.node_count(), adapter.chunk_count(), adapter.relationship_count()))
    print("Seed and repeat upsert verified: 20 entities, 6 chunks, 44 relationships")
except Exception:
    raise SystemExit("Seed stopped. Check approval, empty graph, dataset and private connection settings; no reset attempted.") from None
finally:
    if adapter is not None:
        with suppress(Exception):
            adapter.close()
'@ | .\.venv\Scripts\python.exe -
$weaveSeedExit = $LASTEXITCODE
Remove-Item Env:WEAVE_SEED_APPROVED
if ($weaveSeedExit -ne 0) { throw 'Hosted seed did not pass; stop and inspect privately.' }
```

Client/graph handles are used only for read-only preflight, without duplicating ingestion logic. Partial failure may leave partial data: stop and inspect, rather than rerun blindly or reset a shared graph. MERGE identity makes identical upserts idempotent; it does not migrate schema or remove obsolete edges. Repairs/restores require separate approval and a backup.

### Read-only database acceptance

Select `novapay` in the authenticated Cloud browser and run statements separately. Keep credentials out of queries/captures.

```cypher
MATCH (n) RETURN count(n) AS all_nodes;
MATCH (c:Chunk) RETURN count(c) AS chunks;
MATCH ()-[r]->() RETURN count(r) AS relationships;
```

After actual successful seeding, expect 26 total nodes (20 entities + 6 chunks), 6 chunks, 44 relationships. Aliases are a checked-in resolver map, not 29 extra nodes.

```cypher
MATCH (d {id:'decision:D-007'})-[:IMPLEMENTED_BY]->(c {id:'commit:8fae2'})
      -[:CHANGES]->(s {id:'service:payment-service'})-[:USES]->(t {id:'tech:redis'})
RETURN d.id, d.status, c.id, s.id, t.id;
MATCH (o {id:'service:order-service'})-[:DEPENDS_ON]->(c {id:'service:checkout-service'})
      -[:DEPENDS_ON]->(p {id:'service:payment-service'})
RETURN o.id, c.id, p.id;
MATCH (d {id:'decision:D-007'})-[:SUPPORTED_BY]->(s)<-[r]-(c:Chunk)
WHERE s.id IN ['issue:PAY-42','message:payment-perf-7']
  AND type(r) IN ['FROM_ISSUE','FROM_MESSAGE']
RETURN d.id, s.id, type(r), c.id, c.source_id, c.text;
MATCH (c:Chunk)-[r]->(s)
WHERE s.id IN ['issue:PAY-42','message:payment-perf-7','commit:8fae2','doc:ADR-7']
  AND type(r) IN ['FROM_ISSUE','FROM_MESSAGE','FROM_COMMIT','FROM_DOCUMENT']
RETURN s.id, c.id, type(r), c.source_id, c.chunk_index, c.text
ORDER BY s.id, c.chunk_index;
```

Pass: exact architecture/dependency directions above; D-007 `status=accepted`; genuine rationale through `SUPPORTED_BY` to PAY-42/payment-perf-7; all four sources have persisted nonempty text, correct `FROM_*` edges and matching chunk `source_id`. Seed chunk IDs: `chunk:issue:PAY-42:0`, `chunk:message:payment-perf-7:0`, `chunk:commit:8fae2:0`, `chunk:doc:ADR-7:0`. D-007 is also `DOCUMENTED_IN` ADR-7. No direct chunk-to-decision edge is expected. INC-17 `LED_TO` PAY-42 does not establish an invented issue → discussion → decision chronology.

## Vercel frontend

Import the same GitHub repository into a separate Vercel project. Select the approved release revision, with Production Branch `main` only after preparation lands. Check deployment protection so intended judges can access production. These dashboard actions have not been performed.

| Setting | Exact value |
| --- | --- |
| Root directory | `frontend` |
| Framework preset | Vite |
| Install | `npm ci` using committed `frontend/package-lock.json` |
| Build | `npm run build` |
| Output | `dist` |
| Node | Supported Node 24.x; local verification used 24.13.0 |
| Public environment | `VITE_API_URL=https://your-backend.up.railway.app` |
| Outside-root sources | Enable **Include source files outside of the Root Directory in the Build Step** |
| SPA rewrite | None needed for current navigation |

The actual variable is `VITE_API_URL`, documented in `frontend/.env.example`. Supply the backend **origin**, not an `/api` prefix; the client appends paths. Vite's local port-8000 proxy is development-only. Changing the variable requires rebuilding/redeploying the frontend. No database/provider secrets belong in any `VITE_*` variable. [Vite environment behavior](https://vite.dev/guide/env-and-mode).

Existing `publicDir: '../assets'` needs outside-root access for tracked branding. Confirm `/weave-knot.svg` loads. The five untracked workstation screenshots are not app dependencies. [Vercel shared-source option](https://vercel.com/docs/monorepos/monorepo-faq), [build settings](https://vercel.com/docs/builds/configure-a-build), [supported Node versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).

Current views and saved-chat navigation are React state at `/`, with no URL-path router/deep-link scheme. Refreshing `/` requires no catch-all rewrite; no new routing is introduced. IndexedDB stays browser/origin-local. Preview/production origins have separate histories; changing the domain does not migrate chats.

Once Vercel's final HTTPS origin is known, set Railway `WEAVE_CORS_ORIGINS` to its exact JSON array and redeploy/restart with updated variables. Separately approve/list preview origins; no `*` or `*.vercel.app`. Existing CORS permits GET/POST and Content-Type, handles OPTIONS and enables no credentials/cookies. CORS is not authentication.

Inspect Vercel build logs for install/typecheck/Vite success and generated assets. Use Deployments → Redeploy after public-variable changes; confirm revision/environment. Browser Network must show Railway HTTPS calls, without mixed content or localhost API requests.

## Health and API smoke tests

| Signal | Proves | Does not prove |
| --- | --- | --- |
| `/healthz` → 200, `{"status":"ok"}` | FastAPI process responds, no dependency probes | DB/tools/sources/LLM readiness |
| `/api/health` | Existing DB/tool/provider availability; real graph failure returns 503 | Complete seed correctness or source retrieval |
| Primary query with genuine chunks | Decision tool + persisted retrieval + context | All four tools or UI playback |
| Canonical Change and browser QA | Combined workflow on actual release | Safe real-world removal or runtime failover |

Detailed health does **not** probe sources separately; require actual chunks in query results. Its graph probe is availability, not a full capability audit. Provider `none` must report `llm=disabled`, never hosted availability. The UI still uses detailed health and its red graph-unavailable indicator, not `/healthz`.

After deployment, with provider `none`, replace only these public origins and run in PowerShell:

```powershell
$weaveApi = 'https://your-backend.up.railway.app'
$weaveOrigin = 'https://your-weave.vercel.app'
function Assert-Weave($condition, [string]$message) {
    if (-not $condition) { throw $message }
}
function Assert-WeaveEdge($graph, [string]$source, [string]$type, [string]$target) {
    $found = @($graph.edges | Where-Object { $_.source -eq $source -and $_.type -eq $type -and $_.target -eq $target })
    Assert-Weave ($found.Count -gt 0) "Missing directed edge: $source $type $target"
}
$process = Invoke-RestMethod "$weaveApi/healthz" -TimeoutSec 15
Assert-Weave ($process.status -eq 'ok') 'Process unavailable'
$health = Invoke-RestMethod "$weaveApi/api/health" -TimeoutSec 15
Assert-Weave ($health.graph_mode -eq 'falkordb' -and $health.graph -eq 'novapay') 'Wrong mode/name'
Assert-Weave ($health.falkordb -eq 'connected' -and $health.graph_tool -eq 'available') 'Graph unavailable'
Assert-Weave ($health.llm -eq 'disabled') 'Keep provider disabled for initial acceptance'
foreach ($path in @('/api/query', '/api/change-intelligence', '/api/health')) {
    $method = if ($path -eq '/api/health') { 'GET' } else { 'POST' }
    $preflight = Invoke-WebRequest "$weaveApi$path" -Method Options -UseBasicParsing -TimeoutSec 15 -Headers @{
        Origin = $weaveOrigin
        'Access-Control-Request-Method' = $method
        'Access-Control-Request-Headers' = 'content-type'
    }
    Assert-Weave ($preflight.Headers['Access-Control-Allow-Origin'] -eq $weaveOrigin) 'CORS origin mismatch'
}
$primary = Invoke-RestMethod "$weaveApi/api/query" -Method Post -ContentType 'application/json' -TimeoutSec 120 -Body (
    @{ question = 'Why does Payment Service use Redis?' } | ConvertTo-Json
)
Assert-Weave ($primary.metadata.graph_mode -eq 'falkordb') 'Fixture response is not acceptance'
Assert-Weave ($primary.metadata.generation -eq 'deterministic') 'Unexpected provider'
Assert-Weave ($primary.support_status -eq 'supported') 'Primary rationale incomplete; inspect provenance'
foreach ($id in @('issue:PAY-42','message:payment-perf-7','commit:8fae2','doc:ADR-7')) {
    $source = @($primary.sources | Where-Object id -eq $id)
    Assert-Weave ($source.Count -eq 1 -and $source[0].snippet -and $source[0].metadata.chunk_ids.Count -gt 0) "Missing source/chunks: $id"
    foreach ($chunk in $source[0].metadata.chunks) {
        Assert-Weave ($chunk.source_id -eq $id -and $chunk.id -in $source[0].metadata.chunk_ids) 'Chunk parent mismatch'
    }
}
$proposal = @{ target = 'Payment Service'; change = 'Remove Redis from Payment Service' }
$change = Invoke-RestMethod "$weaveApi/api/change-intelligence" -Method Post -ContentType 'application/json' -TimeoutSec 120 -Body ($proposal | ConvertTo-Json)
Assert-Weave ($change.metadata.graph_mode -eq 'falkordb' -and $change.metadata.generation -eq 'deterministic') 'Unexpected mode'
Assert-Weave ($change.data.proposed_change.resolution -eq 'resolved') 'Change not resolved'
Assert-Weave ($change.data.historical_context.support_status -eq 'supported') 'Historical support incomplete'
Assert-Weave ($change.support_status -eq 'partially_supported') 'Review overall support; risks remain inferred'
$decision = @($change.graph.nodes | Where-Object id -eq 'decision:D-007')
Assert-Weave ($decision.Count -eq 1 -and $decision[0].properties.status -eq 'accepted') 'Accepted D-007 missing'
Assert-WeaveEdge $change.graph 'decision:D-007' 'IMPLEMENTED_BY' 'commit:8fae2'
Assert-WeaveEdge $change.graph 'commit:8fae2' 'CHANGES' 'service:payment-service'
Assert-WeaveEdge $change.graph 'service:payment-service' 'USES' 'tech:redis'
Assert-WeaveEdge $change.graph 'service:checkout-service' 'DEPENDS_ON' 'service:payment-service'
Assert-WeaveEdge $change.graph 'service:order-service' 'DEPENDS_ON' 'service:checkout-service'
$architecture = @($change.data.historical_context.relationship_paths | Where-Object id -eq 'decision_to_current_architecture')
Assert-Weave ($architecture.Count -eq 1) 'Ordered architecture path missing'
$ordered = @($architecture[0].steps | ForEach-Object { "$($_.source)|$($_.type)|$($_.target)" })
$expected = @('decision:D-007|IMPLEMENTED_BY|commit:8fae2', 'commit:8fae2|CHANGES|service:payment-service', 'service:payment-service|USES|tech:redis')
Assert-Weave (($ordered -join "`n") -ceq ($expected -join "`n")) 'Step order changed'
foreach ($tool in @('decision_trace','impact_analysis','find_expert','find_stale_knowledge')) {
    Assert-Weave ($change.data.tool_support.$tool.state -eq 'validated') "Tool unavailable: $tool"
}
Assert-Weave (@($change.data.reviewers).Count -gt 0) 'Reviewer evidence missing'
Assert-Weave (@($change.data.documents_to_review_if_change_proceeds | Where-Object { $_.document.id -eq 'doc:ADR-7' }).Count -gt 0) 'Conditional ADR-7 review missing'
Assert-Weave (@($change.data.trace_playback.sequences).Count -gt 0) 'Validated playback missing'
```

These are pending public checks, not passed tests. HTTP errors must stop acceptance, not prompt fixture substitution. Compare excerpts/chunks to independently reviewed persisted seed records; nonempty strings alone are insufficient. Rationale cites PAY-42/payment-perf-7; ADR-7/commit support their own documentation/implementation roles. Do not force overall Change support to `supported`: risks and recommendations remain qualified.

Run existing opt-in gates in [RUNNING.md](RUNNING.md#live-falkordb-checks) against the actual release, with deterministic generation. Review the primary evidence manifest against the seeded revision. The source gate writes/deletes its own uniquely named test graph; obtain permission for that scope and never retarget cleanup to shared `novapay`. Independent teammate QA is not this combined release's acceptance.

## Public frontend acceptance record

All checks below are **pending public deployment**. Record release SHA, URLs, browser/device, timestamp and sanitized proof. Keep secrets out of captures.

| # | Check | Evidence constituting a pass |
| --- | --- | --- |
| 1 | Open Vercel URL | Intended HTTPS production origin reachable by judges without developer access |
| 2 | Frontend loads | Welcome, five question actions, composer, fonts and `/weave-knot.svg` render |
| 3 | Railway health | `/healthz` 200; detailed `/api/health` checked separately |
| 4 | DB connected | Detailed health `falkordb=connected`, `graph=novapay` |
| 5 | Tools/sources | `graph_tool=available`; genuine persisted chunks in primary/Change; four Change tool states validated |
| 6 | Primary query | Submit “Why does Payment Service use Redis?”; successful public backend answer |
| 7 | Historical citations | Accepted D-007, supported rationale, genuine PAY-42/payment-perf-7, ADR-7/8fae2 in proper roles; excerpts match seed |
| 8 | Change query | Submit “What happens if we remove Redis from Payment Service?”; canonical intent resolves |
| 9 | Structured assessment | History, direct/downstream impact, ranked reviewers, facts/risks/recommendations, current vs conditional docs, conservative support |
| 10 | Ordered history | Exact D-007 IMPLEMENTED_BY 8fae2 CHANGES Payment USES Redis; stored IDs/directions/order and Decision Trace tool-local edge proof |
| 11 | Impact dependencies | Checkout DEPENDS_ON Payment; Order DEPENDS_ON Checkout; traversal may reverse stored direction but retains exact edges and separate Impact proof |
| 12 | Inspector | Citations open correct source ID/excerpt/chunk attribution; graph highlighting and Inspector agree |
| 13 | Watch Evidence Trace | Starts from actual Change result; valid sequence and source/relationship/target |
| 14 | Motion | With reduced motion off, current edge/nodes animate in validated order; no invented bridge or textual citation on graph-only steps |
| 15 | Controls | Pause halts; Play resumes; Next/Previous move one step; no new analysis POST |
| 16 | Reopen chat | Saved evidence restores with playback paused; Network shows no repeated query/change POST |
| 17 | Refresh | `/` reload preserves same-origin saved chat/evidence, paused, without POST replay |
| 18 | Responsive layout | Desktop/laptop/tablet/mobile brief, graph, Inspector/composer readable and usable; check keyboard/safe area |
| 19 | Console/CORS | No unexpected console errors, failed preflights, mixed content, asset 404 or localhost API call; actual POSTs work |
| 20 | Real mode | Variables, detailed health and metadata all say `falkordb`; no fixture warning/metadata or file/memory fallback |

Every ordered step must match a directed edge in its Decision Trace evidence reference, not an edge contributed to the combined graph by another tool. Historical ordered paths and Impact traversal paths differ. Server/display validators retain that boundary; live QA must check actual returned proof and UI, not merely the union graph or offline fixtures.

## Optional OpenRouter

Start with `WEAVE_LLM_PROVIDER=none`; deterministic grounded results work without an LLM. No provider calls or evidence transmission are authorized during preparation.

After separate payload review/approval, configure only on Railway: `WEAVE_LLM_PROVIDER=openrouter`, secret `WEAVE_OPENROUTER_API_KEY`, `WEAVE_LLM_MODEL=openai/gpt-oss-120b`, `WEAVE_LLM_TIMEOUT_SECONDS=30`, `WEAVE_OPENROUTER_MAX_TOKENS=1200`. Existing `OPENROUTER_API_KEY`/`LLM_MODEL` aliases remain supported; use `WEAVE_*` consistently. Endpoint: `https://openrouter.ai/api/v1/chat/completions`. Never put the key in Vercel.

Existing transport forbids alternate-provider/model fallback and redirects, bounds time/response size, requires exact model identity and constrained JSON-schema selection. Finite section/context validation preserves evidence, ranks, citations and conservative support. Rejection/unavailability returns deterministic presentation plus sanitized warning; successful synthesis changes authorized presentation and `metadata.generation`, not facts. Fallback is not hosted success.

OpenRouter mode also makes authenticated `/key` and model-endpoint probes from detailed `/api/health`; `/healthz` never does. Provider approval must account for those requests as well as completions. Earlier narrowly scoped smoke approval is not reused. No OpenRouter requests were made in this preparation.

## Safety and known limits

- `.gitignore` excludes `.env` variants, local caches/environments/builds and `.local`; only example env files belong in Git. Review the release diff. Never log settings, authorization headers, authenticated URLs, raw SDK exceptions or source bodies. Normal graph/provider failures cross sanitized application boundaries; hosted logs still require inspection.
- Authentication and rate limiting are not implemented. CORS does not block direct public API access. This deployment is for approved synthetic demonstration data; private data needs a separately approved access-control plan. No security architecture was added here.
- Real outages never select fixtures, files or memory. Source failure may retain qualified graph evidence with warnings/reduced support. Startup initializes adapters lazily and performs no network seed; process health can succeed with dependencies down.
- Existing gateway deadlines: health 4 seconds per graph probe, tools 15 seconds, sources 10 seconds, plus socket/server deadlines. Thread work may briefly outlive async cancellation. Frontend POST deadline is 120 seconds. This is not load-tested capacity or an SLA.
- No local Docker/Railpack container build occurred. Windows regression/import/listener checks do not prove a clean Linux image. First approved Railway build must prove dependency install/full-package artifact; first Vercel build must prove outside-root branding availability.
- Seed count, graph availability or a partial HTTP 200 response is not complete acceptance. Never relax citation/provenance guards to pass evaluation. A proposed removal is not an executed change or runtime-verified PostgreSQL failover.

## Troubleshooting and rollback

| Symptom | Action |
| --- | --- |
| Missing FastAPI/FalkorDB | Root `/`, install override uses backend lock; inspect build logs |
| `app.graph`/`weave_graph` import error | Full checkout, `PYTHONPATH=backend:.`, `--app-dir backend`; preserve namespace bridge |
| Process starts, public 502 | Confirm `0.0.0.0`, assigned `PORT`, domain target, no crash/sleep |
| Process 200, dependency 503 | Check Cloud host/port/auth, graph name, networking/TLS; not fixture mode |
| Certificate failure | Correct DNS/TLS endpoint and trusted chain; never disable checks |
| Sources missing | `WEAVE_SOURCE_BACKEND=weave_data`, actual `Chunk -[:FROM_*]-> Source`; aliases do not supply text |
| Partial primary rationale | Accepted D-007, genuine `SUPPORTED_BY` and chunk provenance; no invented rationale |
| CORS | Exact origin JSON in Railway, redeploy; inspect preflight and actual response |
| Calls hit Vercel/localhost | Correct `VITE_API_URL`, rebuild; proxy is development-only |
| Logo missing | Enable outside-root sources; confirm tracked assets |
| History absent after domain change | IndexedDB is origin/browser-local, no server sync |
| Animation absent | Valid playback sequence, selection and OS reduced-motion setting; do not fabricate steps |
| LLM disabled/rejected | Expected initially; later inspect approved backend config privately; deterministic fallback is intentional |

Before launch, record previous healthy Railway/Vercel deployment IDs/settings and take an authorized Cloud backup. Roll back Railway by selecting/redeploying the known-good deployment/revision; verify effective variables, health and evidence again. Roll back Vercel to its known-good production deployment, checking its baked-in API origin against backend/CORS. Permissions and retained deployments depend on the account. [Vercel rollback](https://vercel.com/docs/instant-rollback).

App rollback does not restore graph contents or IndexedDB history. Never automatically reset/clear/delete the graph or reverse MERGE operations. Stop writes and obtain a separate repair/restore approval if seed/schema data is wrong. Repeat public acceptance after rollback.

## Local verification and manual launch checklist

Run offline checks in a fresh shell with no live opt-in flags enabled. The delegate override isolates existing offline doubles from local real-source configuration. Use another fresh shell for application startup.

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-deployment-readiness
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
npm.cmd --prefix frontend test -- --maxWorkers=2
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

This includes required backend tests plus graph/ingestion suites. New tests cover process-only health, real-mode outage, exact HTTPS CORS for query/change/health, certificate/hostname verification in all three connectors, and the frontend external API origin.

Preparation results on Windows, Python 3.11.9 / Node 24.13.0:

| Check | Result |
| --- | --- |
| Full offline Python (`backend/tests tests app/graph`) | **693 passed, 11 skipped**; skipped checks require a real database; one existing Starlette TestClient deprecation warning |
| Frontend | **371 passed**, 21 test files |
| Backend Ruff (`backend/app backend/tests`) | Passed |
| ESLint / TypeScript / Vite production build | Passed |
| Dataset prepare-only | Passed: 20 records, 6 chunks, 44 relationships, 29 aliases, no validation errors |
| Local native launch shape | Correct full-repo import/listener; `/healthz` 200; detailed health and primary query sanitized 503 with unavailable DB, provider disabled, real mode retained |
| Dependency consistency | `pip check` passed |
| Docs / whitespace | Relative links, Markdown tables/fences, PowerShell/Python example syntax and `git diff --check` checked |
| Hosted Linux build / Cloud / public browser acceptance | **Not run**, pending manual hosting prerequisites |

An additional Ruff run under the root's stricter configuration reports two **pre-existing** `BLE001` findings: broad exception handlers in `app/graph/client.py` and `weave_data/graph_adapter.py`. Both reproduce from unchanged HEAD content; they are outside the established backend lint gate and were left intact. No tests or grounding checks were weakened. Local launch verification used an intentionally unavailable loopback database and no hosted provider, not a real Cloud connection.

1. Review and publish preparation through the approved release process. No automatic commit/push/merge was performed. Confirm both dashboards select the approved revision.
2. Provision FalkorDB Cloud, record networking/TLS/ACL/dataset revision, obtain seed approval, validate then seed only the empty owned graph; check actual counts, provenance and repeat-upsert results.
3. Configure Railway root/Railpack/install/start/`PORT`/health/secrets; disable sleep, configure account/budget controls, run first Linux build, generate HTTPS domain.
4. Configure Vercel root/build/shared sources/public API variable and intended public access; build and record final origin.
5. Configure exact Railway CORS and redeploy; verify process, dependencies, genuine chunks and canonical public queries.
6. Run approved live gates and all 20 browser checks, including ordered motion and restoration without repeated POSTs. Keep provider `none`.
7. Record sanitized evidence, deployment IDs, rollback/backup references and limits; only then declare public acceptance. Optional provider enablement is separate.
