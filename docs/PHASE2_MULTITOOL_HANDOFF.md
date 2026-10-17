# Multi-tool routing and Context Builder V2

October 17, 2026. Started with a clean `integration/phase2` at `2874a71`. No branches were fetched/merged, no stash was applied, and nothing was pushed. `main` remains `b5824d9`; the Phase 1 stash remains `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`. The implementation commit follows `2874a71`; see `git log -2 --oneline` for its exact hash.

## Routing and execution

`POST /api/query` accepts its existing request and returns exactly its existing fields: **answer, support_status, tools_used, sources, graph, metadata**. No schema/model/configuration migration is required. The dedicated Impact Analysis endpoint remains unchanged.

```json
{"question":"What led to Redis being introduced for Payment Service, and what services might be affected if Redis were removed?"}
```

`plan_question()` produces typed `ToolCall` arguments and a `RoutingPlan`. It splits at semicolons, question boundaries, or “and” followed by an explicit question/intent starter. Up to four clauses are allowed. Each clause must resolve to one rule and explicit target; no pronoun resolution, guessed entities, arbitrary Cypher, or model routing occurs. More than four clauses execute nothing. Duplicate capability/argument pairs deduplicate using sorted JSON arguments. Multiple distinct targets for one capability are treated as ambiguous and excluded, with a limitation; independently resolvable clauses can still run.

| Intent | Routing rule | Execution |
| --- | --- | --- |
| Existing Redis/Payment rationale aliases, including “What led to … introduced …” | `decision_trace` | Registered; existing async `trace_decision` gateway and Context Builder |
| Explicit downstream impact, removal, change hypothetical, or “What depends on …” | `impact_analysis` | Registered; existing Impact Analysis gateway and validator |
| Expert/experts, “who knows”, “who worked on”, “who can explain” | `find_expert` | Intent only; unregistered and never executed |
| Stale, freshness, outdated, “up to date” | `find_stale_knowledge` | Intent only; unregistered and never executed |

Execution order is the trusted rule order above, irrespective of clause order. Current combined questions make at most one Decision Trace traversal and one Impact Analysis traversal. Their canonical source IDs are unioned in that order for **one** exact retrieval call, then each validator receives only its own requested sources. Current per-capability lookups are limited to 40 distinct IDs and combined lookup to 60. Capability calls have a 15-second async timeout; source retrieval has 10 seconds, in addition to existing adapter/socket/query timeouts. Cancelling a worker await still cannot terminate an already-running database thread.

Internal `decision_trace` maps to the established public `tools_used` name **`trace_decision`**, preserving Phase 1 consumers. `tools_used` lists validated result-producing tools, including genuine empty results; failed or unfinished tools are not presented as successful uses. The internal per-tool outcome still records them.

Existing single-tool routing, deterministic summaries, optional Phase 1 Ollama behavior and the dedicated Impact Analysis endpoint retain their original execution paths. The legacy `route_question()` remains a compatibility resolver; new orchestration uses `plan_question()`. Compound answers are deterministic even when an Ollama provider is configured. No OpenRouter calls or new provider integration were added.

Unknown/ambiguous clauses yield explicit missing-evidence limitations. A valid sibling can answer its own part but cannot make the whole answer supported. Historical “What changed …” questions and upstream dependency questions are not misrouted to downstream impact. This does not implement Change Intelligence.

## Context Builder V2 contract

`ToolSpec.build` first invokes the existing capability validator (`build_context` or `build_impact_context`) and returns `ToolEvidence`. Only then does `merge_contexts()` construct this internal JSON-serializable packet:

```typescript
{
  entities: (GraphNode & {tools: string[]})[];
  paths: (GraphEdge & {tools: string[]; retrieved_ids: {[tool: string]: string[]}})[];
  snippets: {text: string; source_ids: string[]; tools: string[]}[];
  sources: (Source & {tools: string[]})[];
}
```

`entities` retain full actual properties. `paths` are actual **directed edges**, not inferred shortcuts. Identical edges deduplicate by source/type/target/properties; the first genuine ID is used in the public graph and every original ID remains in internal `retrieved_ids`. Distinct parallel edges with different IDs/properties remain distinct. Reused edge IDs with conflicting endpoints/type/properties fail closed. No synthetic graph IDs or stored provenance edges are introduced.

Sources deduplicate by canonical ID and must agree in content, type, title, timestamp, URL, metadata and entity associations (association ordering is normalized). Raw duplicate-source conflicts are checked before legacy “richest excerpt” merging can hide them. Identical snippets deduplicate by text while retaining every source ID and tool association. Full timestamps and chunk/source metadata remain in source records; they are not replaced with display labels.

`CombinedContext.per_tool` contains each capability's **support status, state** (`validated`, `unavailable`, `invalid`, `unregistered`), node/edge/source IDs and actual validated traversal edge sequences. Impact traversal order is preserved separately from stored edge direction. Decision Trace exposes its actual returned edges without inventing a narrative shortcut. Invalid/unavailable/unregistered capabilities have insufficient evidence and empty provenance associations.

No merge can promote one tool's support using another's graph or sources. Removing Trace's USES or Chunk FROM_* path still prevents its rationale from becoming supported, even when Impact returns that same edge. Tool-local summary citations must refer to that tool's own validated sources. Existing Phase 1 citation validation, accepted-decision checks and Impact provenance checks are unchanged. The new path reuses their deterministic summaries; it does not generate new rationale from raw dictionaries or invoke an LLM.

V2 limits: **80 entities, 200 edges, 30 sources, 24,000 unique snippet characters, 160,000 UTF-8 packet bytes, four tool contexts**. Existing tighter per-tool limits still apply. Excess results raise a sanitized contract error; they are never silently truncated and presented as complete. Public graph/source objects preserve their original schemas; the packet and tool associations are internal only.

## Failure and support behavior

| Situation | Behavior |
| --- | --- |
| Every selected capability supported, no omitted intent | Overall `supported` |
| Any usable supported/partial result plus a partial, missing, failed or omitted part | Overall `partially_supported` |
| All validated results insufficient, or only future/unknown intents | `insufficient_evidence`; no invented results |
| One tool unavailable/timed out or returns invalid evidence | Discard its complete result, retain independently valid siblings, name the missing capability and lower overall status |
| Every attempted registered tool unavailable | Sanitized HTTP 503 `GRAPH_UNAVAILABLE` |
| No valid result and any attempted tool has a contract error | Sanitized HTTP 502 `GRAPH_CONTRACT_ERROR` |
| Conflicting shared nodes/edge identities/source provenance, invalid shared source payload, or V2 size excess | Reject the entire response with sanitized 502; choosing one conflicting version is unsafe |
| Source outage | Retain each tool's graph; independently recalculate support with no sources and preserve warnings |
| Unexpected programming/runtime exception outside the known adapter failures | Existing sanitized 500; no fabricated partial success |

Warnings retain capability attribution. Error summaries never expose underlying exception messages. The combined answer labels historical decision evidence separately from current graph relationships and potential downstream impact, keeps the failure-propagation caveat, and explicitly describes unavailable/ambiguous parts. A related issue citation does not prove downstream failure. Fixture mode remains explicit; real mode never substitutes fixtures, local corpus reads or an in-memory graph.

## Files and extension handoff

| Files | Change |
| --- | --- |
| `backend/app/router.py` | Typed bounded plan, ordered rule registry, deduplication and deferred future intents; existing resolver retained |
| `backend/app/orchestration.py` | Trusted `ToolSpec` registry, bounded sequential execution, one source retrieval, isolated known failures and per-tool outcomes |
| `backend/app/context_v2.py` | Internal packet, provenance membership, strict conflict detection, bounds and conservative combined narrative/status |
| `backend/app/main.py` | Route composite/deferred/unresolved questions through the new orchestration; public response unchanged |
| `backend/tests/test_multitool.py` | 54 new routing, merged-function integration, failure, provenance, conflict, deduplication, support and bound regressions |
| `backend/tests/test_impact_integration.py` | Extend the existing explicit offline database double to answer actual Decision Trace queries too |
| `frontend/src/impact.ts` | Keep compound/deferred/change-history questions out of the single-impact endpoint shortcut |
| `frontend/src/App.test.tsx`, `impact.test.ts` | Combined-answer citation/graph-inspector workflow and frontend routing guard regressions |
| `README.md`, `docs/README.md`, this document | Discovery and handoff |

Antony's Cypher, `weave_graph`, Alen's ingestion/retrieval, API models, original Context Builder, Impact validator, citation validator, graph renderer and source inspector are unchanged.

**Expert Finder can be integrated without rewriting the planner or public response:**

1. Inspect Antony's actual function/contract when available. Replace that rule's `DeferredIntent` matcher with an explicit canonical-argument resolver and input model; do not execute today's question-only placeholder as graph arguments.
2. Add its async method to the existing gateway/Antony adapter using `weave_graph`, timeouts, sanitized failures and explicit real/fixture boundaries.
3. Register a `ToolSpec`: public name, async gateway method, input/result models, canonical source-ID selector and an independent validator returning `ToolEvidence`. Provide only actual validated path sequences and source associations. Use Alen's existing exact retrieval.
4. Test the real contract, missing provenance, conflicts, mixed support and failures with the other tools. The same steps apply to Knowledge Freshness; neither tool has been implemented or mocked as a product feature here.

## Verification and remaining limits

Baseline: **270 Python tests passed, 8 skipped**. Final:

- **324 Python tests passed, 0 failed, 8 skipped**; one existing Starlette test-client deprecation warning.
- **70 frontend tests passed, 0 failed, 0 skipped**, four files.
- Scoped Ruff, ESLint, TypeScript and Vite production build passed.
- Browser: actual FastAPI/Vite in explicit fixture mode, no intercepted responses; combined historical/impact paragraphs, `partially_supported`, six deduplicated fixture sources, 12 actual React Flow nodes/14 edges, working citation inspector, no horizontal overflow and no console warnings/errors. Owned QA servers used ports 8013/5175 and were stopped afterward.

Reproduce from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate' # isolate offline doubles from local .env
.\.venv\Scripts\python.exe -m pytest backend\tests tests app\graph -q --basetemp=.local/pytest-multitool-final
.\.venv\Scripts\python.exe -m ruff check --config backend\pyproject.toml backend app\graph weave_graph tests\test_decision_trace.py tests\test_impact_analysis.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
Remove-Item Env:WEAVE_SOURCE_BACKEND
```

New integration regressions execute Antony's actual merged trace/impact and Alen's actual retrieval against explicit offline database doubles, independently of application development fixtures. **No live combined FalkorDB verification was executed in this task.** The eight existing opt-in live tests remain skipped. Phase 1's QA approval supplied by the project lead is not a claim that this new combined path has passed independent/live QA. For live acceptance, use the existing real-mode settings and expanded seeded corpus from `PHASE2_IMPACT_HANDOFF.md`, repeat the JSON query above, and run the existing opt-in real trace/source/impact acceptances. Do not enable fixture mode for live verification.

Remaining limits: bounded English clause grammar/aliases, no pronoun inference, one target per capability, one shortest dependency path as supplied by Antony, strict shared-record snapshot consistency, no live combined acceptance in this pass, and no expert/freshness/OpenRouter/Change Intelligence implementation. Existing unrelated repository-wide lint debt was not edited or represented as resolved. Ready for independent review and offline QA; live combined acceptance remains to be performed.
