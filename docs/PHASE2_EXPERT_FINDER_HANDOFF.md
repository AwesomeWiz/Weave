# Phase 2 Expert Finder integration

October 17, 2026. Started on clean `integration/phase2` at `31c05b3`, preserving the completed OpenRouter integration and its `570f59d` multi-tool ancestor. Fetched `origin/feature/phase2-graph`, inspected Antony's implementation/tests, and merged **`c0232a8e55d6e31ea12fc3abcc6eecf53867b8aa`** through merge commit **`50ad4d6`** without conflicts. The branch added only `app/graph/experts.py` and `tests/test_expert_finder.py`. No reset, push, stash operation, or merge into `main` was performed. Application integration changes follow that merge in the working tree.

## Actual graph contract and compatibility fixes

The adapter calls **`weave_graph.experts.find_expert(client, query: str, limit: int = 5)`**, using the existing namespace bridge. It retains `{data, sources, nodes, edges, warnings}`. Client construction, socket bounds, worker ownership/closure, and the 15-second gateway timeout follow the existing adapters. The caller never supplies Cypher or manufactures an `entity_id` argument.

The graph tool resolves up to 20 topic candidates, performs two bounded neighborhood expansions, retrieves directed person contributions, issue assignments and team membership, and returns fixed weighted rankings. Its source entries are `{id, chunk_id, title, text, url}`, not full public `Source` records. Their canonical IDs are independently resolved through Alen's existing graph-backed `find_sources()` before validation. No ingestion/retrieval code changed.

Two verified compatibility gaps required small Python topic-resolution fixes in Antony's module: explicit `D-007` keys now participate as canonical decision lookup candidates, with case-normalized confidence comparison; an explicitly requested named technology decision can resolve a decision title containing that technology's known alias. Before these fixes, the required queries `Who approved D-007?` and `Who can explain the Redis decision?` returned no topic even against the ingested NovaPay corpus. Generic incidental substrings remain insufficient; equal decision matches remain ambiguous. Added graph regression tests cover both forms and tied Redis decisions. **No Cypher, scoring weights, contribution selection, or ranking algorithm changed.** The teammate test import uses `weave_graph.experts` to avoid the existing FastAPI `app.graph` collision.

## Final API

`POST /api/tools/expert-finder`:

```json
{"query":"Who knows Payment Service?","limit":5}
```

Query: nonblank string, maximum 2,000 characters, trimmed. Limit: strict integer 1–10, default 5; booleans, numeric strings, fractions and null are rejected. Extra request fields, including the obsolete `entity_id`, are rejected. Errors reuse `INVALID_REQUEST` (422), `GRAPH_UNAVAILABLE` (503), and `GRAPH_CONTRACT_ERROR` (502), with sanitized messages.

The response extends the existing evidence response with **only `data`**:

```typescript
{
  answer: string;
  support_status: 'supported' | 'partially_supported' | 'insufficient_evidence';
  tools_used: ['find_expert'];
  sources: Source[]; // existing canonical records, original chunk metadata retained
  graph: {nodes: GraphNode[]; edges: GraphEdge[]};
  metadata: {latency_ms: number; graph_mode: 'fixture' | 'falkordb';
             generation: 'deterministic' | 'ollama' | 'openrouter'; warnings: string[]};
  data: {
    query: string;
    topics: GraphNode[];
    scoring: {[category: string]: number};
    experts: {
      person: {id: string; name: string; role: string | null};
      score: number;
      ranking_reasons: string[];
      ownership_classification:
        'team_membership_with_team_owned_service' | 'no_current_ownership_evidence';
      evidence: ExpertEvidence[];
      ownership: ExpertEvidence[];
      historical_contributions: ExpertEvidence[];
    }[];
  };
}

type ExpertEvidence = {
  category: 'team_ownership' | 'decision_approval' | 'decision_participation' |
            'commit_authorship' | 'issue_assignment' | 'discussion_contribution';
  entity_id: string;
  entity_type: string;
  path: {source: string; type: string; target: string}[];
  source_ids: string[]; // application-derived validated contextual citations
};
```

`data` otherwise preserves Antony's nested schema and ordering. The additive per-evidence `source_ids` is derived at the application boundary after graph/chunk validation; upstream citation associations are overwritten. `ranking_reasons`, scores, person records, topics, ownership classifications, and graph paths are checked rather than rewritten. Warnings map to existing `metadata.warnings`; graph nodes/edges map to existing `graph`.

**`POST /api/query` remains exactly `answer, support_status, tools_used, sources, graph, metadata`.** A single expert query runs the same validator but strips structured `data` from that endpoint. Combined requests use the registered `ToolSpec` and Context Builder V2. The dedicated Impact Analysis endpoint is preserved.

## Routing and combined execution

Expert intent recognizes `expert(s)`, `who knows`, `who worked on`, `who can explain`, `who approved`, and `who made the/this decision`. The complete resolved clause is passed as a query string; the graph tool resolves topics. Expert questions are excluded from the single Decision Trace matcher, so a word such as `decision` does not steal the expert intent. Topic ambiguity is decided by the actual graph tool, not an LLM or a fabricated ID mapping.

The exact showcase grammar is supported:

> Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?

It deterministically selects Decision Trace, Impact Analysis on **Redis**, and Expert Finder with the explicit query `Who can explain the Redis decision?`. The narrowly documented pronoun rule treats `it` as the object of `use` in this specific service/technology sentence. Arbitrary pronouns and unresolved clauses remain qualified. No decision ID or person is inferred by this rule. Invocation order remains the established registry order: `trace_decision`, `impact_analysis`, `find_expert`. The four-clause limit and existing deduplication/ambiguity rules remain intact.

Combined execution retrieves the union of genuine source IDs once, then validates each tool independently using only that tool's IDs. Context Builder V2 retains tool-local sources, nodes, directed edges, proof paths, narratives and completeness. A missing Expert Finder approval edge cannot be repaired by Decision Trace's separate graph. A failed/invalid expert result is excluded and recorded as missing evidence while valid siblings remain usable. Knowledge Freshness remains unregistered/deferred; Change Intelligence is not implemented.

## Independent evidence validation

`build_expert_context()` validates:

- Canonical IDs/types, node properties/labels, matching person names/roles and resolved topic records; dangling or conflicting duplicate graph records fail closed.
- One resolved topic for rankings. Multiple tied topics return no experts and `insufficient_evidence`; a ranked payload with ambiguous/no topics is rejected. No numeric confidence field is invented because Antony does not return one.
- Every evidence entity belongs to the returned two-expansion topic neighborhood. Every proof step is an actual returned **directed** relationship with the correct person, entity type and category.
- Approval/participation (`Person -> Decision`), authorship (`Person -> Commit`), discussion (`Person -> Message`), issue assignment (`Issue -> Person`), and ownership (`Person -> Team -> Service`) are distinct proof forms.
- The returned weighting dictionary matches Antony's policy. Each category/entity pair counts once, each reported score equals the weighted sum of its verified items, reasons match those items, and returned ordering agrees with descending score/canonical-ID tie breaks. This verifies returned rankings; it does not discover candidates or replace Antony's ranking implementation.
- Ownership/historical lists and classification agree with evidence. Team membership is never personal ownership. Antony's current result schema has no direct personal-owner classification; the application does not invent one. Historical contributions never imply current ownership or availability.
- Canonical source IDs, source types and chunk references match actual `Chunk -[:FROM_ISSUE|FROM_MESSAGE|FROM_COMMIT|FROM_DOCUMENT]-> Source` paths. Chunk parent/type/index/text, exact aggregate excerpt, title, URL, timestamp and available chunk metadata must agree with independently retrieved records. Conflicting source records fail closed; missing/mismatched retrieval is excluded from citations and lowers completeness.
- Citation association is contribution-local. A direct source contribution cites its actual source; approval/participation context requires an actual `Decision -> SUPPORTED_BY|DOCUMENTED_IN|IMPLEMENTED_BY -> Source` link plus verified chunk provenance. Such citations are retrieved context; graph relationships establish the contribution/approval, and an implementation excerpt alone is not textual proof of who approved it. No direct chunk-to-person/decision edge is fabricated.

Scores remain Antony's fixed policy:

| Category | Weight |
| --- | --- |
| Team ownership through membership | 4 |
| Decision approval | 5 |
| Decision participation | 3 |
| Commit authorship | 4 |
| Issue assignment | 3 |
| Discussion contribution | 2 |

`supported` means the **returned bounded ranking** has valid proofs and required historical textual provenance, with no incompleteness warnings. Missing textual provenance, cap warnings or source outages retain valid graph-backed rankings as `partially_supported`. No experts/topic or ambiguous topic is `insufficient_evidence`. Invalid identities, scores, reasons or paths cause a contract failure rather than exposing unverified rankings. All rankings explicitly say they are bounded/non-exhaustive, including `limit`-truncated results even when the tool has no explicit total-count field. Existing focused graph/context bounds remain strict (80 nodes, 200 edges, 30 combined sources); oversized results reject rather than silently dropping proof.

## OpenRouter and React

Expert Finder adds one complete server-authored block to the existing constrained presentation system. The model can select/order sections but cannot change scores, rank order, people, ownership, contributions, citations or support status. Both expert rendering choices contain the same complete validated ranking and caveats. Cap and missing-evidence warnings cannot be omitted. Existing citation checks, response/prompt bounds, pinned model, sanitized errors and exact deterministic fallback are preserved. Ollama behavior remains unchanged.

The existing React Expert Finder card now runs the query-based endpoint. Natural single expert questions use the same endpoint for structured rankings. Compound questions use `/api/query`. Existing layout, fonts, graph renderer, source and entity inspectors, relationship views and citation controls are reused. Each person displays name/canonical ID, score, verified reasons, team ownership distinction and historical contribution paths/citations. Controls support query and bounded limit changes; retry/history retain the selected request. Empty, ambiguous, missing textual evidence, cap warnings and graph-unavailable states are qualified explicitly. Fixture mode returns an explicitly labeled empty expert result; no fabricated expert dataset is loaded in real mode.

## Verification and live blockers

Initial integration baseline: **382 passed, 8 skipped**. The merged graph tests use actual ingestion into an explicitly offline adapter. New application tests call Antony's actual function and Alen's retrieval while replacing only database transport/storage with explicit offline doubles; production validators are exercised. OpenRouter tests replace only its HTTP transport. An autouse backend-test fixture now defaults provider selection to `none`, so local `.env` credentials/provider cannot activate hosted synthesis accidentally; provider tests select and mock their provider explicitly.

Final verification:

| Check | Result |
| --- | --- |
| Full Python regression | **453 passed, 9 skipped**, zero failures (18.73 seconds) |
| New focused expert application cases | **59** cases included in the full suite |
| Scoped Ruff | Passed |
| Frontend Vitest | **94 passed** across 5 files, zero failures |
| ESLint | Passed |
| TypeScript | Passed |
| Vite production build | Passed |
| `git diff --check` | Passed |

The existing Starlette TestClient/httpx deprecation warning is unrelated and unchanged. The nine skipped cases require opt-in live services, including the new real Expert Finder application smoke. Earlier failures were obsolete deferred-Expert expectations, the verified topic-resolution compatibility gaps, and a new frontend test needing to select the person header specifically; they were fixed rather than bypassing grounding.

Run offline verification from the repository root:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-expert-final
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend app/graph weave_graph tests/test_decision_trace.py tests/test_impact_analysis.py tests/test_expert_finder.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
Remove-Item Env:WEAVE_SOURCE_BACKEND,Env:WEAVE_LLM_PROVIDER
```

**Real FalkorDB integration remains pending.** The configured local workspace is currently fixture mode; an actual database-health probe returned false, and Docker CLI was unavailable. No live Expert Finder application success is claimed. The opt-in `backend/tests/test_real_expert_integration.py` exercises the real configured adapters and seeded graph, requires expected canonical NovaPay people, proof/citation records and accepted D-007 in the three-tool answer, and forbids fixture construction. It does not seed or alter the database:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_GRAPH_MODE = 'falkordb'
$env:WEAVE_GRAPH_FACTORY = 'app.antony:create_gateway'
$env:WEAVE_SOURCE_BACKEND = 'weave_data'
$env:WEAVE_LLM_PROVIDER = 'none'
$env:WEAVE_RUN_REAL_EXPERT_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_real_expert_integration.py -v
```

Run against an independently reviewed seeded NovaPay revision, alongside existing Decision Trace/Impact live QA and reviewed-source manifest tests. Inspect tied topics, missing chunks, team ownership and cap behavior on real query results. Restore environment overrides after testing. A healthy Redis port alone is insufficient.

**Deliberate live OpenRouter smoke remains pending approval.** A configured key was detected without displaying it. Automatic approval review rejected the attempted smoke command because it would transmit potentially sensitive NovaPay evidence to OpenRouter without explicit payload/destination approval. That smoke command was not executed; no workaround was used. A credential-free local preview was prepared at `.local/openrouter_expert_smoke_preview.json` using explicit offline validated graph evidence. It describes three requests to `https://openrouter.ai/api/v1/chat/completions`, pinned to `openai/gpt-oss-120b`, with a 30-second deadline each and no retries. Packet sizes are 12,480, 11,238 and 19,523 UTF-8 bytes. This preview is not committed. Approval must cover those evidence packets/destination before the proposed live smoke runs. Even a successful provider test over these offline packets would not verify live FalkorDB.

## Changed files

| Files | Purpose |
| --- | --- |
| `app/graph/experts.py`, `tests/test_expert_finder.py` | Merged teammate tool/tests; narrow verified topic compatibility fixes and namespace import |
| `backend/app/models.py` | Query-based request, actual typed graph result, structured response |
| `backend/app/antony.py`, `backend/app/graph.py` | Async namespace/gateway integration, strict real-mode behavior |
| `backend/app/experts.py` | Independent proof, score, ownership and chunk-provenance validator |
| `backend/app/router.py`, `backend/app/orchestration.py` | Registered expert capability, intent priority and bounded showcase grammar |
| `backend/app/main.py` | Dedicated endpoint, unchanged query contract, fallback handling |
| `backend/app/synthesis.py` | Complete validated expert presentation block |
| `backend/tests/conftest.py` | Prevent local hosted-provider selection leaking into offline tests |
| `backend/tests/test_expert_integration.py`, `backend/tests/test_real_expert_integration.py` | Offline actual-function regressions and opt-in real application smoke |
| `backend/tests/test_multitool.py` | Replace obsolete deferred-Expert assumptions; freshness remains deferred |
| `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/experts.ts` | Structured API validation/types and single-expert endpoint routing |
| `frontend/src/components/ExpertResults.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/globals.css` | Functional card, rankings/controls and reused evidence navigation/styles |
| `frontend/src/experts.test.ts`, `frontend/src/App.test.tsx`, `frontend/src/test/expertFixture.ts` | API/routing and UI/citation regression coverage with explicit test-only data |
| `README.md`, `docs/PHASE2_EXPERT_FINDER_HANDOFF.md` | Setup, verification and this handoff |

No Decision Trace/Impact Cypher, `weave_data` implementation, existing grounding validators, Context Builder V2 merge rules, OpenRouter transport/security settings, secrets, or stash contents were changed. No live external-service QA is inferred from offline results.
