# Phase 2 OpenRouter handoff

October 17, 2026. Optional backend synthesis for Decision Trace, Impact Analysis, and combined questions on `integration/phase2`, based on `570f59d`. No teammate branches were merged. Graph queries, ingestion, retrieval, grounding validators, deterministic routing, and the existing stash are preserved. Nothing was pushed or merged into `main`.

## Configuration and official API

The pinned model is **`openai/gpt-oss-120b`**, verified against the [official model page](https://openrouter.ai/openai/gpt-oss-120b). Other IDs, including `:free` and automatic model selection, are rejected by configuration. Requests use the [official chat-completions endpoint](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request), `POST https://openrouter.ai/api/v1/chat/completions`, with backend Bearer authentication.

```dotenv
WEAVE_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<set privately in the backend environment or local .env>
LLM_MODEL=openai/gpt-oss-120b
WEAVE_OPENROUTER_MAX_TOKENS=1200
WEAVE_LLM_TIMEOUT_SECONDS=30
```

`WEAVE_OPENROUTER_API_KEY` and `WEAVE_LLM_MODEL` are equivalent repository-prefixed aliases. When both aliases exist within one settings source, the prefixed alias wins; configure only one nonblank key. Environment settings take precedence over dotenv settings, including a blank prefixed dotenv value. The key is a redacted `SecretStr`, excluded from settings repr. Never set it in `VITE_*`, commit it, or send it through a browser request. No local secrets were modified by this task.

`WEAVE_LLM_PROVIDER=none` remains the default. Existing `ollama` configuration still works for its existing single Decision Trace path. Its combined/impact responses remain deterministic. No new dependency is required; the transport uses existing `httpx`.

OpenRouter requests use strict [JSON-schema structured output](https://openrouter.ai/docs/guides/features/structured-outputs). [Provider preferences](https://openrouter.ai/docs/guides/routing/provider-selection) require parameter support and disable provider fallback; no alternate model list, tools, plugins, or model-authored Cypher is sent. A response reporting a different/missing model is rejected. Low reasoning effort and excluded reasoning are requested; reasoning is never rendered.

## Evidence and generation boundary

Existing builders validate each tool first. `ToolProvenance.summary` now retains the builder's complete tool-local narrative without changing the Context Builder V2 packet fields or public API. Single-tool validated contexts pass through the same merge boundary for hosted synthesis. Impact presentation uses only the validator's returned relationship paths and actual edge IDs, never additional traversal.

The hosted packet contains bounded canonical entity IDs/types/labels, decision statuses, actual directed edges, validated source records without their internal metadata, and per-tool completeness/source membership. Arbitrary node properties and raw source metadata are excluded. Public graph/source records retain their original properties and provenance unchanged.

**Synthesis is deliberately constrained.** The model chooses and orders complete server-authored sections and selects a recorded or explanatory rendering. It does not write arbitrary factual prose. Explanatory variants quote validated rationale excerpts and translate validated directed impact paths into readable statements. Accepted status alone cannot establish rationale: the explanation variant requires the rationale already present in the validated tool summary. Missing `SUPPORTED_BY` provenance cannot become a rationale citation.

The returned JSON has only `selections: [{block_id, variant}]` and `source_ids`. Local strict validation rejects unknown fields, missing/duplicated sections, unsupported variants, invented or missing citations, and any attempted `answer`, owner, claim, tool, query, or status field. Complete section coverage prevents the model from suppressing inconvenient evidence. The server appends status, partial-evidence limitations, missing-capability/tool caveats, and the impact-not-guaranteed-failure warning independently of model choices.

The shared citation validator retains Ollama's original defaults, including a genuine citation in every paragraph. Hosted presentation additionally permits explicitly structural **server-rendered** paragraphs without fabricated textual citations. Every bracket citation must still match an actual tool-local retrieved source and the returned citation list exactly. An issue/document excerpt is never promoted into proof of failure propagation. HTML, Markdown links, HTTP URLs, and control characters in hosted presentation are rejected. React continues rendering escaped text and genuine citation controls.

Untrusted question/source strings appear only as data. The system prompt marks that boundary, but safety does not depend on obedience: a prompt injection cannot add factual text through the selection schema. Source text may still contain inaccurate statements; evidence validation establishes provenance, not the objective truth of every excerpt. Quoted evidence retains that limitation.

## Fallback, API, and bounds

Missing key, network/HTTP errors, redirects, timeout, malformed or oversized output, refusal/truncation/tool calls, model substitution, invalid citations, unsupported claims, unsafe presentation, and packet-validation errors return the **exact existing deterministic summary**. No provider error body, exception detail, credential, or full prompt is logged or exposed. Metadata receives only:

> OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.

`graph`, `sources`, `tools_used`, and deterministic `support_status` are unchanged by generation/fallback. `metadata.generation` becomes `openrouter` only after successful validation; otherwise it remains `deterministic`. `insufficient_evidence` skips hosted generation entirely. Real graph failure still returns the existing graph error; it does not invoke OpenRouter or substitute fixtures. Fixture mode remains explicit and visibly labeled.

`POST /api/query` still returns exactly `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`. The dedicated Impact Analysis response retains `data` and all existing fields. The only additive public enum value is `metadata.generation="openrouter"`, recognized by the React validator/types/inspector. Hosted impact text appears above the existing findings; citations, source/entity inspectors, graph controls, and path highlighting remain available.

| Bound | Behavior |
| --- | --- |
| Hosted input | 96,000 UTF-8 bytes; oversize rejects, no silent evidence truncation |
| Sections / selected citations | At most 4 complete capabilities / 30 unique cited IDs |
| Provider response | 65,536 bytes, checked from headers and incremental reads |
| Rendered answer | Shared 6,000-character maximum |
| Completion tokens | Default 1,200; configurable 256–4,096 |
| Generation deadline | Default 30 seconds; configurable positive value up to 90; absolute deadline plus HTTP timeouts |
| HTTP connection | At most 5 seconds, bounded by configured request timeout |
| Retries / redirects | None; no alternate-model or provider fallback |
| Health | Two bounded GETs, 2 seconds each, 4 seconds total; no generation request |

Health authenticates using [GET `/api/v1/key`](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key) and verifies the exact model has endpoints via its public model-endpoints API. `available` means authenticated/catalog-visible, **not** a successful completion, sufficient balance, or verified structured-output compatibility for a particular provider. Generation can still fall back. Missing key returns unavailable locally. HTTP environment proxies are intentionally ignored; restricted/proxy-only deployments may need a reviewed explicit transport configuration.

## Verification

The 58 new offline backend tests mock only the OpenRouter HTTP boundary for provider behavior. Evidence integration cases run the actual merged trace/impact/retrieval pipeline and production validators against an explicitly offline ingested database double. They do not establish live FalkorDB behavior.

Coverage includes three primary questions, direct Impact endpoint compatibility, exact topology/source/status preservation, missing-key behavior, bounded transport, invalid claims/citations/schema, prompt injection, unsafe markup, real-mode graph failure without fixture substitution, missing accepted-decision rationale, partial tool outages, graph-only impact without invented textual citations, metadata privacy, settings aliases, and none/Ollama selection. Frontend tests cover hosted metadata acceptance, unknown-provider rejection, hosted impact findings/inspection, navigable citations, and accurate fallback labeling.

Run from repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate' # keep offline doubles independent of local .env
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-openrouter-final
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend app/graph weave_graph tests/test_decision_trace.py tests/test_impact_analysis.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
Remove-Item Env:WEAVE_SOURCE_BACKEND
```

Final verification results:

| Check | Result |
| --- | --- |
| Full Python suite | **382 passed, 8 skipped** in 10.47 seconds |
| Focused new OpenRouter tests | **58 passed** |
| Scoped Ruff | Passed |
| Frontend Vitest | **74 passed** across 4 files |
| ESLint | Passed |
| TypeScript | Passed |
| Vite production build | Passed |
| `git diff --check` | Passed |

Python emits one existing Starlette TestClient/httpx deprecation warning. The 8 skipped tests require opt-in live services. No existing test was removed or changed to bypass grounding. The initial frontend failure was in a new test attempting graph inspection before opening the graph view; that navigation test was corrected and the complete frontend suite passes.

**Live OpenRouter verification: pending.** A credential-presence check returned false without displaying a secret; no live inference request was made. Official documentation was checked, which is separate from exercising the inference API. **Live FalkorDB: not exercised in this task**; the opt-in live tests remain skipped. Prior Phase 1 verification is not a substitute for a live Phase 2/provider smoke test.

When a key and seeded graph are available, configure `WEAVE_GRAPH_MODE=falkordb`, the existing Antony factory and Alen `weave_data` backend. First run the existing reviewed-manifest real integration tests per `REAL_INTEGRATION_HANDOFF.md`. Then compare `none` versus `openrouter` on these exact queries, restarting FastAPI after provider changes:

1. Why does Payment Service use Redis?
2. What would be affected if Payment Service changed?
3. What led to Redis being introduced for Payment Service, and what services might be affected if Redis were removed?

Make one completion attempt per question (default maximum 30 seconds each), without retries. Compare full `graph`, `sources` including canonical IDs and chunk provenance, `tools_used`, and `support_status` for equality. Confirm genuine inline citations, mandatory uncertainty, accepted D-007 rationale, and directed impact topology. Require `metadata.generation=openrouter` for a successful live provider check; a deterministic fallback is safe application behavior but does not verify live inference. Record sanitized failure categories and leave verification pending when any prerequisite fails. Do not print request headers, secrets, or complete sensitive evidence.

## Files changed

| File | Purpose |
| --- | --- |
| `.env.example` | Optional hosted configuration; deterministic default retained |
| `README.md` | Setup and handoff link |
| `backend/app/config.py` | Provider choice, secret/model aliases, bounded token setting |
| `backend/app/citations.py` | Shared existing citation rules |
| `backend/app/context_v2.py` | Additive retention of validated tool-local narrative |
| `backend/app/llm.py` | Provider abstraction/factory and shared validator |
| `backend/app/openrouter.py` | Bounded transport, health, model/output validation |
| `backend/app/synthesis.py` | Validated presentation packet, schema, grounded renderers |
| `backend/app/main.py` | Optional synthesis and exact fallback across query/impact routes |
| `backend/app/models.py` | Additive generation metadata enum |
| `backend/tests/test_openrouter.py` | Offline provider/evidence regressions |
| `frontend/src/types.ts`, `frontend/src/api.ts` | Accept additive provider metadata |
| `frontend/src/components/Inspector.tsx` | Accurate provider/fallback labeling |
| `frontend/src/App.tsx` | Display hosted impact explanation with existing findings |
| `frontend/src/api.test.ts`, `frontend/src/App.test.tsx` | Compatibility and navigation regressions |
| `docs/PHASE2_OPENROUTER_HANDOFF.md` | This handoff |

No changes were made to `app/graph`, `weave_graph`, `weave_data`, `backend/app/antony.py`, `backend/app/context.py`, `backend/app/impact.py`, `backend/app/router.py`, or `backend/app/orchestration.py`.

## Future capabilities and limitations

Expert Finder and Knowledge Freshness are not implemented here. Keep their actual graph contracts and validators independent. Once their implementations are ready, use the existing `ToolSpec`/routing registration seam and return validated `ToolEvidence` with canonical sources and conservative completeness. Context Builder V2 retains that membership/narrative. Add an explicit capability renderer and title in `prepare_synthesis()` using only that tool's validated fields; currently unknown validated capabilities reject hosted synthesis and safely fall back. Test missing/invalid provenance and mixed-tool failures before enabling it. Never reuse another tool's citations or stronger status as proof.

This implementation offers bounded LLM-assisted organization and rendering choices, **not unrestricted model paraphrasing**. Citation membership alone cannot prove arbitrary new prose, so free-form factual output is rejected even when it cites a genuine source. Supporting broader language generation requires a separately reviewed claim-verification contract and tests. Large packets, unusual bracket text/markup in evidence, stricter provider schemas, credit limits, or output model aliases may conservatively cause fallback. No claim of live provider quality, availability, or end-to-end database verification is made from these offline results.
