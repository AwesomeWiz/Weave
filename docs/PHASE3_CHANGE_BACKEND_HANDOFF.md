# Phase 3 Change Intelligence backend foundation

## State and Git safety — October 18, 2026

Implemented on the existing, initially clean `integration/phase3` branch. Starting HEAD, local `main`, and fetched `origin/main` all equal `75e7f7c4c29b169d2737dcc1436ec0ae4953c742` (the QA-approved Phase 2 merge). No teammate branches were merged. The implementation remains uncommitted for review; no push or main update was performed.

Both starting stashes remain intact:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

The existing Phase 2 QA report records its earlier real FalkorDB acceptance. **This Phase 3 workflow was verified offline only.** Its opt-in live acceptance test was not run. No live OpenRouter requests, provider probes, deployments, UI implementation, or Trace Mode work were performed.

## Changed files

| File | Change |
| --- | --- |
| `backend/app/change_intelligence.py` | Finite proposal resolution, four-tool plan, grounded structured brief, deterministic narrative |
| `backend/app/models.py` | Typed request, target, history, impact, reviewers, risks, recommendations, document review, tool support, response |
| `backend/app/router.py` | Explicit proposed-change workflow selector; additional `Which Payment Service documents need review?` Freshness grammar |
| `backend/app/main.py` | Dedicated endpoint and canonical `/api/query` dispatch; sanitized input errors |
| `backend/app/context_v2.py` | Optional internal validated structured data on `ToolEvidence`/`ToolProvenance`, copied during merge |
| `backend/app/orchestration.py` | Retain the existing validators' Impact/Expert/Freshness data instead of discarding it |
| `backend/tests/test_change_intelligence.py` | 60 offline regressions and one opt-in live acceptance check |
| `docs/PHASE3_CHANGE_BACKEND_HANDOFF.md` | This contract and handoff |
| `docs/README.md` | Handoff index link |

No teammate graph queries, graph gateways, ingestion, source retrievers, provider implementations, citation validators, or frontend files were changed.

## API examples and exact contracts

Dedicated structured endpoint:

```http
POST /api/change-intelligence
Content-Type: application/json

{"target":"Payment Service","change":"Remove Redis from Payment Service"}
```

`ChangeInput` forbids unknown fields, requires strings, strips surrounding whitespace, and rejects blank values. `target` is bounded to 256 characters and `change` to 2,000 characters. Canonical aliases also work:

```json
{"target":"service:payment-service","change":"Remove tech:redis from service:payment-service"}
```

Top-level response:

```text
ChangeResponse = {
  answer: string,
  support_status: supported | partially_supported | insufficient_evidence,
  tools_used: string[],
  sources: Source[],
  graph: EvidenceGraph,
  metadata: Metadata,
  data: ChangeBriefData
}
```

The existing `Source`, `GraphNode`, `GraphEdge`, `EvidenceGraph`, and `Metadata` schemas remain unchanged. `metadata.generation` is always `deterministic` for Change Intelligence in this stage.

`ChangeBriefData` has these exact fields:

| Field | Representation |
| --- | --- |
| `proposed_change` | `requested_target: string|null`, `requested_change: string`, `intent: remove_technology|unsupported`, `resolution: resolved|unsupported|unresolved|ambiguous|inconsistent`, `service: GraphNode|null`, `technology: GraphNode|null`, `limitation: string|null` |
| `historical_context` | `support_status`, full validated `summary`, actual `decision_ids`, `evidence: ChangeEvidenceReference|null` |
| `impact` | Existing `ImpactData` fields (`entity`, `direct_impact`, `indirect_impact`, `related_issues`, `related_incidents`) plus `support_status` and `max_depth` |
| `reviewers` | Existing validated `ExpertRanking` objects, with every field preserved |
| `risks` | `classification`, `description`, `evidence`, `uncertainty`, `affected_entity_ids` |
| `validation_steps` | `classification: RECOMMENDATION`, `description`, `evidence`, `performed: false` |
| `current_freshness_findings` | Unchanged validated `FreshnessFinding` objects, including dates, triggers, association paths and source IDs |
| `documents_to_review_if_change_proceeds` | `document: GraphNode`, `condition: if_change_approved_and_implemented`, `reason`, `evidence` |
| `tool_support` | Map from existing tool registry keys to `support_status`, `state`, and `evidence` |
| `limitations` | Preserved validation/orchestration warnings and change-specific qualifications |

`ChangeEvidenceReference` contains `tool`, `node_ids`, `edge_ids`, `source_ids`, and `relationship_paths` (lists of actual edge IDs). `tool` is one of `decision_trace`, `impact_analysis`, `find_expert`, `find_stale_knowledge`. Each reference must stay within that tool's independently validated provenance. Graph-only claims deliberately have empty textual citation lists.

`ChangeReviewer` preserves `person`, `score`, `ranking_reasons`, `evidence`, `ownership`, `historical_contributions`, and `ownership_classification` exactly as returned by the Expert validator. No new ranking or personal-ownership inference is performed.

The canonical question also works through the original query endpoint:

```http
POST /api/query
Content-Type: application/json

{"question":"What happens if we remove Redis from Payment Service?"}
```

Its response still contains **exactly** `answer`, `support_status`, `tools_used`, `sources`, `graph`, and `metadata`. Structured `data` is available only through the dedicated Change endpoint. Existing capability and health endpoints retain their contracts.

## Intent and entity resolution

The main query handler checks `router.is_change_question()` before the Phase 2 graph-tool planner. Change Intelligence is a workflow, not a fifth graph tool and not a new `ToolSpec`.

Explicit proposal prefixes include `what happens if`, `what would happen if`, `if we remove`, `if we replace`, and leading `remove`, `replace`, `migrate`, `deprecate`, `switch from`, `move away from`, or `upgrade` (optionally preceded by `please`, `can we`, or `should we`).

This foundation executes only the complete bounded grammar `Remove <technology> from <service>`, including the canonical question and `If we remove ...` form. Names/IDs are selected through the repository's existing finite aliases. The validated pair is Payment Service / Redis. Other proposals, ambiguous targets, unknown names, and conflicting target/change pairs return HTTP 200 with qualified `insufficient_evidence`, empty tools/graph/sources, and an explicit limitation. They never silently run Redis-removal tools.

Alias matching is not proof of graph existence. The proposed change becomes `resolved` only after a returned, tool-local `Service USES Technology` edge establishes the actual canonical pair. Properties such as a service's technology list, matching node names alone, or a reversed edge cannot substitute for that relationship. Without it, the result stays insufficient and no risks, reviewer recommendations, or conditional document reviews are constructed.

Preserved Phase 2 selection includes:

- `Why does Payment Service use Redis?` → Decision Trace.
- `What depends on Payment Service?` → Impact Analysis.
- `What services might be affected if Redis were removed?` → existing Impact Analysis grammar.
- `Who knows Payment Service?` → Expert Finder.
- `Which Payment Service documents need review?` → Knowledge Freshness.

Arbitrary mixed proposals, replacements, migrations, upgrades, multiple services and pronouns are not supported change scenarios. The LLM does not choose tools or entities.

## Composition, retrieval, and Context Builder V2

`analyze_change(request: ChangeInput | str, gateway: GraphGateway, graph_mode: str) -> ChangeResponse` builds one explicit `RoutingPlan` and invokes the existing `execute_plan()` once:

| Capability | Actual arguments |
| --- | --- |
| Decision Trace | `TraceInput(service="Payment Service", technology="Redis")` |
| Impact Analysis | `ImpactInput(entity_id="tech:redis", max_depth=3)` |
| Expert Finder | `ExpertInput(query="Who knows Payment Service?", limit=5)` |
| Knowledge Freshness | `FreshnessInput(entity="service:payment-service")` |

Depth 3 is within the existing tool bound: Payment Service is depth 1 from Redis, Checkout depth 2, and Order depth 3. Stored directions remain `Payment USES Redis`, `Checkout DEPENDS_ON Payment`, `Order DEPENDS_ON Checkout`.

Technology traversal can return other Redis users. The brief includes only Impact findings whose validated traversal starts `[tech:redis, service:payment-service]`; it does not predict that unrelated Redis users are affected by removal from this service. Included findings retain their exact depth/type/path/path_edges/owners/related records/source IDs. The full bounded validated graph remains available for inspection.

The orchestrator still performs each capability once, deduplicates source IDs into one lookup, applies existing source-record conflict checks, and invokes the original capability validators before `merge_contexts()`. No second source retriever, traversal algorithm, or graph client was added.

The small internal `ToolEvidence.data` / `ToolProvenance.data` extension preserves only the validators' structured output, copied on merge. It is not added to `ContextPacket`, the old public query response, or hosted synthesis payloads. All existing per-tool membership, identity conflict detection, source deduplication, direction checks, support calculation, and context limits remain in effect.

## History, risks, and recommendations

Historical text is the validated Decision Trace narrative. Current-use rationale is never rebuilt from a sibling's sources or repaired by an edge found only in another capability. Actual decision IDs and tool-local graph/source inventories remain inspectable.

Risk classes are explicit:

- **KNOWN_FACT:** actual Impact dependency/use relationships. Their evidence references contain directed graph proof, not fabricated textual citations. Structural connectivity does not establish guaranteed failure.
- **INFERRED_RISK:** a cautious latency implication, generated only when Decision Trace is supported and an exact, accepted-decision rationale span contains the relevant latency/traffic evidence. The full excerpt/citation span is matched in the already-validated narrative; internal blank paragraphs do not detach the excerpt from its citation. Neighboring ADR/commit sources are not automatically assigned as rationale citations.
- **RECOMMENDATION:** proposed cache-removal validation. These are suggested actions, not observations or test results.

Validation steps include testing returned direct/downstream paths, checking cache-removal behavior, load-testing comparable traffic when justified by the rationale, seeking evidence-ranked review while verifying current ownership/approval responsibilities, and reviewing actual service-linked documents if the change proceeds. Every step has evidence references and `performed: false`.

Reviewer scores and classifications come exclusively from Expert Finder. Historical contribution and team membership do not establish current individual ownership; historical approval does not authorize the new proposal. No security, compliance, data-loss, numerical performance forecast or guaranteed-outage claim is introduced.

## Current freshness versus future review

These remain independent structured sections:

1. `current_freshness_findings` is copied only from the validated Freshness result, preserving actual timestamps and later-change paths. It does not mean the documents are definitively wrong.
2. `documents_to_review_if_change_proceeds` is a conditional recommendation using returned local `Document DESCRIBES Service` or `Decision DOCUMENTED_IN Document` plus that same `Decision AFFECTS Service` proof. A standalone document node or citation is insufficient. No document IDs or edges are invented.

In the offline seeded-corpus test, Architecture Overview is a current review candidate. ADR-7 and the payment latency runbook appear in conditional future review, without being labeled currently stale. Architecture Overview can appear in both sections for independently stated reasons.

Decision/Incident trigger evidence remains graph-only where the ingestion schema has no chunks. Conditional document review is supported by actual graph associations; it does not attach an unrelated textual citation.

## Support, errors, bounds, and generation

The existing `CombinedContext` conservative support result is retained. Missing/invalid/unavailable capabilities stay independently qualified, and sibling results cannot upgrade them. Missing current-use connectivity caps the entire Change result at `insufficient_evidence`. A global Redis impact result with no path through Payment Service cannot establish this change's scoped impact.

Canonical offline per-tool result:

```text
Decision Trace: supported
Impact Analysis: partially_supported
Expert Finder: supported
Knowledge Freshness: supported
Overall Change Brief: partially_supported
```

Existing sanitized errors remain: `INVALID_REQUEST` / 422, `GRAPH_UNAVAILABLE` / 503, `GRAPH_CONTRACT_ERROR` / 502, `INTERNAL_ERROR` / 500. Total graph outage does not create fixtures. Explicit fixture mode remains labeled and incomplete, with no invented Expert/Freshness records.

Existing tool/context bounds remain unchanged (four capabilities, per-tool source lookup 40 IDs, combined lookup 60 IDs; merged packet 80 nodes, 200 paths, 30 sources, 24,000 snippet characters, 160,000 serialized bytes). The new structured brief is additionally bounded to 160,000 bytes, 30 risks, 30 validation steps, 10 reviewers, and 50 current/conditional document findings. Oversized results fail closed. The deterministic answer uses the shared 6,000-character citation validator, allowing explicitly graph-backed paragraphs without fabricated textual citations. Full validated historical detail remains in structured data if it is too long for the concise narrative.

Change endpoints do not invoke provider generation or availability, even if settings select OpenRouter or Ollama. No new LLM client exists. Stage 3 hosted presentation is deferred until a safe Change-specific renderer and a newly reviewed/approved payload are available. Existing Phase 2 hosted behavior remains unchanged.

## Verification

At `75e7f7c`, before edits: **518 Python tests passed, 10 skipped**. This reproduces the QA report's Phase 2 baseline.

After implementation:

- **578 Python tests passed, 11 skipped**, including 60 new offline Change tests.
- Scoped Ruff: passed.
- `git diff --check`: passed.
- One pre-existing Starlette/httpx deprecation warning remains.
- No frontend files changed, so frontend checks were not rerun for this backend-only task.
- The 11 skips are the existing 10 opt-in live tests plus the new opt-in Change acceptance test. No live FalkorDB or OpenRouter success is claimed from this run.

Regressions cover the canonical question and structured API, exact original query schema, all four Phase 2 routes/endpoints, explicit unsupported proposals, input bounds, unknown/ambiguous/inconsistent targets, canonical aliases, single deduplicated retrieval, depth/direction, exact reviewer rankings, partial/outage propagation, source and graph conflicts, missing chunks/connectivity, no cross-tool borrowing, scoped technology impact, conditional document associations, explicit risk categories, unperformed validation steps, deterministic provider isolation, fixture isolation and size limits.

Reproduce from the repository root:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-phase3
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
git diff --check
```

An ignored review artifact, `.local/change_brief_offline.json`, was generated through actual adapters/validators over the explicit offline graph double. Its `graph_mode=falkordb` describes the tested integration boundary, **not a live database result**. It must not be used as production evidence or an implicit fixture fallback.

Observed offline example: 4,583 answer characters; five canonical sources (commit 8fae2, ADR-7, PAY-42, payment-perf-7, Architecture Overview); reviewer scores Ravi 16, Alice 14, Maya 5; one current document review and three conditional future document reviews. Scores are the existing graph tool's fixed evidence weights, not objective expertise measurements.

## Ordered-path seam and frontend Stage 2

Antony's future ordered Decision Trace work is not required by this implementation. Historical evidence currently preserves the actual local edge IDs and existing Phase 2 relationship groups. No linear historical timeline is invented. Once its interface is available, add normalized validated ordered paths through the existing Decision Trace `ToolEvidence`/`ToolProvenance` boundary and consume them in historical evidence references. Do not change the old query schema or infer new edges.

Impact `path` lists run from the technology toward dependents, while each `path_edge` retains stored dependency orientation. Document association proof groups can contain two edges sharing a Decision source; they are not necessarily a linear walk. Stage 2 must render those actual directions rather than reinterpret list order as a new causal edge.

The backend is ready for the bounded React Change Brief integration:

1. Call `/api/change-intelligence` for structured data; leave `/api/query` compatibility intact.
2. Render historical context, direct/indirect impact, unchanged rankings, classified risks and unperformed recommendations separately.
3. Keep current freshness and conditional future document review in distinct sections. Label the approval/implementation condition prominently.
4. Use reference tool membership and canonical node/edge/source IDs for focused selection, citations and inspection. Do not repair missing evidence in the frontend.
5. Preserve per-tool status, warnings, graph-only labels and team-versus-personal ownership distinctions.
6. Respect the intentionally bounded scenario. Replacements, arbitrary targets, change execution, Trace Mode and hosted Change presentation are future scope.

## Live Phase 3 QA requirements

The new acceptance gate is deliberately opt-in:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:WEAVE_GRAPH_FACTORY = 'app.antony:create_gateway'
$env:WEAVE_RUN_REAL_CHANGE_INTEGRATION = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_change_intelligence.py -m integration -v
Remove-Item Env:WEAVE_RUN_REAL_CHANGE_INTEGRATION
```

Configure real host/port/graph/credentials through the existing local settings and seed using Alen's approved ingestion path. Record the actual seed revision, run the original Phase 2 real acceptance suites against the same database, then run the new Change gate. It forces real graph/source modes, forbids fixture construction, requires real database health, accepted D-007, genuine chunk-backed canonical supporting sources, expected downstream paths and conditional ADR review, with hosted generation disabled.

Arnold should also verify missing/reversed USES edges, source outages, partial tool failures, unrelated Redis consumers, graph identity conflicts, date/provenance gaps, and future-review wording against real seeded data. Record results and versions before declaring Phase 3 live acceptance. The prior Phase 2 live sign-off does not by itself verify this new composition.
