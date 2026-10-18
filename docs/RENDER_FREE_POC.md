# Render Free: one-container FalkorDB + FastAPI experiment

**Verdict: technically plausible, runtime feasibility unverified.** This is a disposable synthetic demo experiment, not a production hosting recommendation or a successful deployment report. No Docker/container execution or Render deployment occurred on this Windows machine. Peak RAM, CPU behavior, Linux image compatibility and public evidence acceptance must be measured in an approved live trial.

Phase 5 is preserved in merged `main` at `e71eb29f7cf445a317b19396da63bda59cea9d60`. This implementation is isolated on `feature/render-free-poc`, initially at that same HEAD. It changes no API, UI, graph tools, grounding or teammate ingestion code. Both stashes and five original screenshots remain untouched. Nothing was committed, pushed or deployed automatically.

The [Railway + Vercel + Cloud runbook](DEPLOYMENT_RUNBOOK.md) remains the separate hosted-database option. Do not copy its external Cloud settings into this local-only experiment.

## Feasibility and strict cost boundary

Render documents Free Web Service resources as **512 MB RAM / 0.1 CPU**. Docker images can be built remotely from a repository Dockerfile, so the developer does not need local Docker. A tiny 26-node graph and a single API worker make a constrained trial plausible; this is an inference, not a measured memory budget. [Render compute plans](https://render.com/docs/compute-plans), [Docker build support](https://render.com/docs/docker).

For strictly $0: use the **Free service plan**, no disk, no paid database/worker/service, no paid workspace upgrade, and no external LLM. Use the supplied `onrender.com` HTTPS domain and the existing free Vercel frontend. Confirm both accounts' free eligibility before starting. Render's FAQ says overages can be billed when a payment method is present; without one, limits disable services/builds instead. Do not add billing capacity to bypass limits. If account verification requires a payment arrangement that cannot guarantee the $0 constraint, stop the trial. [Render billing FAQ](https://render.com/docs/faq).

Free services sleep after 15 idle minutes; waking takes approximately a minute plus this application's startup/seeding time. Filesystem changes are ephemeral. Restarts rebuild the demo graph from the approved checked-in corpus. Free hours, bandwidth and build quotas can suspend availability. No keepalive workaround or paid upgrade is part of this experiment. [Free service limitations](https://render.com/docs/free).

## Image and production dependencies

`deploy/render/Dockerfile` extends the versioned official **`falkordb/falkordb-server:v4.22.0`** image. Its published tag was checked; it is not `latest`, an edge build or a substitute database. The server-only distribution avoids running the bundled browser/Node service. The upstream runtime supplies Redis, `falkordb.so` at `/var/lib/falkordb/bin/falkordb.so`, and native dependencies including OpenMP (`libgomp1`). We retain that runtime together rather than copying a module into an unrelated OS image. [Official image tags](https://hub.docker.com/r/falkordb/falkordb-server/tags), [upstream server Dockerfile](https://raw.githubusercontent.com/FalkorDB/FalkorDB/master/build/docker/Dockerfile.server).

The Dockerfile installs distro Python/venv and `tini`. Python must be at least 3.11; the actual apt-resolved version is printed at build time, not assumed identical to local 3.11.9. Runtime roots are the five non-test dependencies already declared in `backend/requirements.txt`. Pip resolves their complete transitive closure under existing `backend/requirements.lock.txt` constraints; pytest/Ruff and their test-only dependencies are not installed. Metadata tests verify that production dependency closure retains the pinned required distributions. The image additionally runs `pip check`, checks module shared-library resolution and imports all four tools, API and ingestion preparation. A successful local metadata test does not prove a Linux build: the first Render build must pass those checks.

The Dockerfile-specific `.dockerignore` uses an allowlist: runtime packages, lock, deployment scripts and approved NovaPay corpus only. No local `.env`, `.local`, frontend dependencies or screenshots are copied. The API/graph namespace bridge and dataset aliases stay in their existing portable locations. The final processes run as numeric non-root UID/GID 10001. Record the resolved base-image digest and Python version from the actual build; a version tag alone is not immutable digest pinning.

## Boot, ownership and failure behavior

The default image command runs `start.py` under `tini`:

1. Require `WEAVE_DEMO_BOOTSTRAP=novapay-disposable-v1`. Reject external hosts, non-demo graph names, alternate factories/source backends, fixture mode, credentials, TLS-to-an-external-service settings and any LLM provider other than `none` before spawning children. Require explicit HTTPS CORS origins.
2. Create a new private temporary directory for this boot. Start a genuine Redis/FalkorDB child with a direct argument list, bound **only to `127.0.0.1:6379`**. No database or Bolt public listener, no browser. API is the only listener bound to all interfaces.
3. In a short-lived bootstrap child, poll with bounded connection attempts and a 60-second readiness deadline. Verify Redis's reported PID matches the newly spawned child, then require `GRAPH.LIST` to succeed and return no graphs. Plain Redis, a foreign process, an existing graph or a missing module fails closed. Do not seed an existing server merely because PING succeeds.
4. Validate the approved dataset: 20 entities, 6 chunks, 44 relationships and 29 aliases, no errors. Use existing `run_ingestion()` with an explicit local `FalkorDBGraphAdapter` to create `novapay`. Nothing clears/deletes/resets a graph.
5. Read back exact 26 entity/chunk IDs, 6 Chunk nodes, all 44 directed edges, accepted D-007, and all source text/chunk IDs through the actual adapter-backed `find_sources()`. Missing/reversed/extra evidence or altered source text prevents the API from starting.
6. Exit the bootstrap process to release its Python/ingestion memory. Only then start existing `app.main:app`, with `--app-dir backend`, `0.0.0.0:$PORT` and **one worker**. The supervisor limits the whole bootstrap phase to 120 seconds.
7. Monitor graph/API child exits. Failure of either stops its sibling and exits nonzero. SIGTERM/SIGINT forwards shutdown to owned process groups, waits up to 10 seconds, then kills any remaining children. `tini` reaps orphaned descendants. POSIX signal behavior is mocked locally and still requires a Linux trial.

Persistence files (RDB/AOF) are disabled and the working directory is new on every boot. Records are stored and queried inside the genuine FalkorDB server, but do not survive restart. `WEAVE_GRAPH_MODE=falkordb` and graph-backed source retrieval remain mandatory. There is no runtime file/fixture/memory-adapter fallback. An occupied local port or failed seed is an error, never a reason to reset another database.

## Resource controls and limits

| Control | Initial experimental setting |
| --- | --- |
| Redis allocation threshold | `maxmemory 192mb`, `noeviction`; never discard evidence keys to make space |
| Graph concurrency | `THREAD_COUNT=1`, `OMP_THREAD_COUNT=1`; OpenMP/OpenBLAS environment also 1 |
| Initial graph matrix buffer / cache | `NODE_CREATION_BUFFER=128`, `CACHE_SIZE=10` |
| Query queue / per-query memory | `MAX_QUEUED_QUERIES=8`, `QUERY_MEM_CAPACITY=33554432` (32 MiB) |
| Graph query timeouts | Default 5 seconds, maximum 10 seconds; existing client/gateway timeouts retained |
| Redis clients / Bolt | Maximum 32 clients; Bolt disabled |
| API | One worker, concurrency limit 4, backlog 16, graceful shutdown 8 seconds |
| Allocator | `MALLOC_ARENA_MAX=2`; no extra services or monitoring daemon |

These knobs reduce concurrency and graph allocation headroom; they do **not** prove that combined RSS fits 512 MB. Redis maxmemory is not a hard process/container memory limit, and native allocations, thread stacks, API heap and transient requests still count. The platform can OOM-kill the container. Small matrices/cache may trade memory for CPU; existing evidence queries must succeed with the chosen caps. [FalkorDB configuration](https://docs.falkordb.com/getting-started/configuration), [Redis memory-limit caveat](https://redis.io/faq/doc/1jbxid5qq7/is-maxmemory-the-maximum-value-of-used-memory).

Do not tune by weakening provenance, citations, support statuses or query results. If the approved workflow cannot run under Free limits, report this approach as infeasible for those limits; do not automatically upgrade or manufacture responses.

## Exact Render settings for a manual trial

Only after separate approval to publish/deploy the reviewed changes:

| Dashboard field | Value |
| --- | --- |
| Service | New **Web Service**, Free compute plan (512 MB / 0.1 CPU) |
| Repository / branch | This repository; reviewed/published `feature/render-free-poc` revision; record SHA |
| Language / runtime | **Docker** |
| Root directory | Repository root (leave blank); do not set `backend` or `deploy/render` |
| Docker context | Repository root `.` |
| Dockerfile path | `deploy/render/Dockerfile` |
| Build command | None; Render builds the Dockerfile remotely |
| Docker Command / start override | Leave blank; use image `ENTRYPOINT` + `CMD` |
| Auto-deploy | **Off**; manual trial only |
| Pre-deploy command / disk | None / none |
| Health-check path | `/api/health` |
| Public URL | Render-generated `https://<service-name>.onrender.com` |
| API port | Render `PORT` (normally 10000), bound to `0.0.0.0`; do not assign 6379 |

Render HTTP health checks require timely 2xx/3xx responses. The existing detailed endpoint checks the real graph and disabled-provider state; `/healthz` is only a separate process diagnostic. Health latency must also pass on 0.1 CPU. [Render Docker settings](https://render.com/docs/docker), [health-check behavior](https://render.com/docs/health-checks).

Required dashboard variables:

```text
WEAVE_DEMO_BOOTSTRAP=novapay-disposable-v1
WEAVE_CORS_ORIGINS=["https://your-weave.vercel.app"]
```

The image sets the following existing API settings; normally **do not override** them. If present in Render, they must match exactly or startup refuses:

```text
WEAVE_GRAPH_MODE=falkordb
WEAVE_GRAPH_NAME=novapay
WEAVE_GRAPH_FACTORY=app.antony:create_gateway
WEAVE_SOURCE_BACKEND=weave_data
WEAVE_FALKORDB_HOST=127.0.0.1
WEAVE_FALKORDB_PORT=6379
WEAVE_FALKORDB_SSL=false
WEAVE_FALKORDB_USERNAME=
WEAVE_FALKORDB_PASSWORD=
WEAVE_LLM_PROVIDER=none
```

No database password/Cloud credentials or LLM key is needed. Plain local Redis protocol here is confined to the loopback of this same container; Phase 5's remote TLS verification is untouched. There is no public Redis route or HTTP endpoint accepting arbitrary Cypher. Authentication/rate limiting are not added to the API; expose only this approved synthetic demo and use a limited trial.

Keep frontend on Vercel, same `frontend` root/build/shared-asset settings as the existing runbook. Change **only its deployment variable** `VITE_API_URL` to the Render HTTPS origin, without `/api`, and rebuild Vercel manually. Set matching exact Vercel CORS origin in Render. No frontend source change is needed. Save the old frontend API origin so the experiment can be rolled back without touching Railway configuration.

## Live trial acceptance — not executed

1. Confirm Free plan and $0/no-overage account policy before building. Record SHA, resolved image digest, Python version and build duration; all Docker build checks must pass.
2. Inspect boot logs for genuine graph module startup, exact successful seed/readback message, and one API worker. Record cold-start duration until detailed health succeeds. Any bootstrap rejection or restart loop fails the trial.
3. Public `/api/health` must return 200 with `graph_mode=falkordb`, `graph=novapay`, database connected, tool available and `llm=disabled`. `/healthz` alone is insufficient. Public port is API only; inspect configured bind flags/boot logs for loopback Redis and disabled Bolt.
4. Run the [canonical API checks and all 20 browser acceptance checks](DEPLOYMENT_RUNBOOK.md#health-and-api-smoke-tests), substituting the Render public origin for Railway. Verify the genuine PAY-42, payment-perf-7, 8fae2 and ADR-7 chunks and accepted D-007. Test all four tools, structured Change, ordered playback, citations, Inspector and saved-chat restore without another analysis POST. Preserve historical tool-local path proof and exact stored edge directions.
5. Required architecture path: D-007 IMPLEMENTED_BY 8fae2 CHANGES Payment USES Redis. Dependencies: Checkout DEPENDS_ON Payment, Order DEPENDS_ON Checkout. Missing proof is failure; no fabricated bridging edges.
6. Record Render's **combined** memory and CPU metrics at bootstrap, idle, primary query, all-four-tool Change, repeated single-user queries and an idle/wake cycle. Watch for OOM/restart logs, cap/queue errors, failed health probes, timeouts and sustained CPU throttling. Use platform logs/metrics available on the free account; if necessary memory evidence is unavailable, leave the memory verdict unverified. Free plan has no interactive shell; do not rely on SSH or paid one-off jobs.
7. Under 512 MB, require headroom and no resource-related failures during the chosen trial workload; record the actual peak, not just Redis `used_memory` or a tiny empty-graph sample. A loading page/first cold fetch may require the user to wait and submit again; no provider or app retry service is added.
8. After sleep/restart, confirm a fresh boot reseeds once, public real-mode results remain correct, saved frontend evidence restores, and playback still obeys existing safeguards. Record unsupported/partial outcomes honestly. No final feasibility claim until these pass.

Rollback: restore Vercel's previous API origin and rebuild; stop/delete only this disposable Render service through an approved manual action. Its graph is intentionally lost. Do not clear any external database. Keep Railway/Cloud settings intact. No paid upgrade is part of rollback.

## Offline verification record

Focused tests exercise policy rejection, loopback commands, bounded readiness, PID/module/empty-graph checks, exact seed inventory/directions/source text, supervision failures and mocked POSIX shutdown. They use explicitly labeled offline doubles only in tests; those are not selectable application modes. Production dependency closure is checked against installed distribution metadata, alongside static image/context checks.

Run from repository root, with real opt-in gates disabled:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-render-free-poc
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml deploy/render
git diff --check
```

Results on Windows/Python 3.11.9:

| Check | Result |
| --- | --- |
| Focused Render policy/bootstrap/supervision/dependency tests | **39 passed** |
| Full Python backend + graph + ingestion suites | **732 passed, 11 skipped** (opt-in live database gates); one existing Starlette TestClient deprecation warning |
| Backend Ruff and deployment scripts under backend Ruff configuration | Passed |
| Installed dependency consistency | `pip check` passed |
| Dataset preparation | 20 entities, 6 chunks, 44 relationships, 29 aliases, zero validation errors |
| Docs / whitespace | Markdown references/fences/tables, PowerShell example syntax and whitespace checked |

Docker is unavailable locally, so Docker build/runtime, native signal delivery, actual Redis module loading, memory and Render acceptance remain unverified. No frontend source changed; frontend test/build repetition is not required by this scoped task. All live trial checks above remain pending; no new external LLM calls were made.
